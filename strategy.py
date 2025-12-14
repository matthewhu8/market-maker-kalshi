import asyncio
from config import Config
from client import KalshiClient
from market_data import MarketDataService

class MarketMakingStrategy:
    def __init__(self, config: Config, client: KalshiClient, market_data: MarketDataService):
        self.config = config
        self.client = client
        self.market_data = market_data
        # Track active orders by side: {'yes': {'price': 10, 'id': '...'}, 'no': {'price': 90, 'id': '...'}}
        self.current_pos = {'yes': None, 'no': None}

    async def run(self):
        print("Starting Strategy...")
        while True:
            await self.tick()
            await asyncio.sleep(5) 

    async def tick(self):
        best_bid, best_ask = self.market_data.get_best_prices()
        
        if best_bid == 0 and best_ask == 100:
            print("Empty book, waiting for data...")
            return

        print(f"Market: {best_bid} @ {best_ask}")

        # 1. Calculate Target Quotes
        mid = (best_bid + best_ask) / 2
        spread = self.config.SPREAD_CENTS
        
        target_bid = int(mid - spread)
        target_ask = int(mid + spread) # Target Ask for YES
        
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
