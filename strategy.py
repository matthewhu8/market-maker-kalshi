import asyncio
from config import Config
from client import KalshiClient
from market_data import MarketDataService

class MarketMakingStrategy:
    async def sync_inventory(self):
        while True:
            try:
                data = self.client.get_positions()
                # data is likely dict with keys 'market_positions' which is a list
                positions = data.get('market_positions', [])
                
                found = False
                for p in positions:
                    if p.get('ticker') == self.config.TARGET_TICKER:
                        # Net position: YES is +, NO is -?
                        # Or typically Kalshi separates them.
                        # For simplicity, let's sum 'position' if 'market_position' (or similar field)
                        # Actually Kalshi likely returns 'position' as signed int relative to YES?
                        # Or 'side' field.
                        # Let's assume we just want specific exposures. 
                        # IF explicit 'yes_count' and 'no_count' exist:
                        yes = p.get('position', 0) # Simplification
                        # For now, let's assume 'position' is the net exposure to YES.
                        self.net_position = yes
                        found = True
                        break
                
                if not found:
                    self.net_position = 0
                    
                # print(f"Inventory Synced: {self.net_position}")
            except Exception as e:
                print(f"Inventory Sync Error: {e}")
            
            await asyncio.sleep(10)

    def __init__(self, config: Config, client: KalshiClient, market_data: MarketDataService):
        self.config = config
        self.client = client
        self.market_data = market_data
        # Track active orders by side: {'yes': {'price': 10, 'id': '...'}, 'no': {'price': 90, 'id': '...'}}
        self.current_pos = {'yes': None, 'no': None}
        self.net_position = 0

    async def run(self):
        print("Starting Strategy (Event-Driven)...")
        self.market_data.add_listener(self.on_market_update)
        asyncio.create_task(self.sync_inventory())
        # Keep running until cancelled
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            print("Strategy stopping...")

    async def on_market_update(self):
        best_bid, best_ask = self.market_data.get_best_prices()
        
        if best_bid == 0 and best_ask == 100:
            # print("Empty book, waiting for data...")
            return

        print(f"Market: {best_bid} @ {best_ask}")

        # 1. Calculate Target Quotes
        mid = (best_bid + best_ask) / 2
        
        # Alpha: Order Book Imbalance
        imbalance = self.market_data.get_imbalance() # -1.0 to 1.0
        
        # Risk: Inventory Skew
        # If we have positive position (Long YES), we want to sell YES -> Lower target price
        # If we have negative position (Long NO/Short YES), we want to buy YES -> Higher target price
        # Skew factor: reduce price by X cents per 100 contracts
        inventory_skew = -(self.net_position / 100.0) * 0.5 
        
        # Alpha factor: increase price if buying pressure (positive imbalance)
        alpha_adj = imbalance * 2.0 # Swing 2 cents based on full imbalance
        
        fair_value = mid + alpha_adj + inventory_skew
        
        spread = self.config.SPREAD_CENTS
        
        target_bid = int(fair_value - spread)
        target_ask = int(fair_value + spread) # Target Ask for YES
        
        # Competitive Logic
        if best_bid > target_bid:
            max_bid = best_ask - 1 
            if best_bid < max_bid:
                # print(f"Squeezing Bid: {target_bid} -> {best_bid}")
                target_bid = best_bid
        
        if best_ask < target_ask:
            min_ask = best_bid + 1
            if best_ask > min_ask:
                # print(f"Squeezing Ask: {target_ask} -> {best_ask}")
                target_ask = best_ask
        
        # Safety checks
        if target_bid < 1: target_bid = 1
        if target_ask > 99: target_ask = 99
        if target_bid >= target_ask:
            target_bid = best_bid
            target_ask = max(target_bid + 1, best_ask)
            if target_ask > 99: target_bid = 98; target_ask = 99
            
        # 2. Update orders if needed
        size = self.config.ORDER_SIZE
        
        # YES SIDE
        await self.update_order("yes", "buy", target_bid, size)
        
        # NO SIDE (Synthetic Sell YES)
        # Sell YES at target_ask == Buy NO at (100 - target_ask)
        target_no_price = 100 - target_ask
        await self.update_order("no", "buy", target_no_price, size)

    async def update_order(self, side, action, price, size):
        current = self.current_pos.get(side)
        
        # If we have an order at the correct price, do nothing
        if current and current['price'] == price:
            # print(f"{side.upper()} order at {price} is valid.")
            return

        # If we have an order at WRONG price, cancel it first
        if current:
            print(f"Updating {side.upper()}: Cancel {current['price']} -> New {price}")
            try:
                self.client.cancel_order(current['id'])
            except Exception as e:
                print(f"Cancel failed: {e}")
            self.current_pos[side] = None

        # Place new order
        try:
            resp = self.client.create_order(
                self.config.TARGET_TICKER, action, size, price, side=side
            )
            if 'order' in resp:
                oid = resp['order']['order_id']
                self.current_pos[side] = {'price': price, 'id': oid}
                print(f"Placed {side.upper()} at {price}")
            elif 'error' in resp:
                err = resp['error']
                if err.get('code') == 'insufficient_balance':
                    print(f"Skipped {side}: Insufficient Balance (Need ~{price}c)")
                else:
                    print(f"Error {side}: {err}")
        except Exception as e:
            print(f"Place failed {side}: {e}")
