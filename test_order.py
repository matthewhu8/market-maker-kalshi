import asyncio
import sys
import time
from config import load_config
from client import KalshiClient
from market_data import MarketDataService
from strategy import MarketMakingStrategy
from scan_markets import find_best_market

async def run_live_test():
    print("Starting Live Order Test...")
    try:
        config = load_config()
        config.ORDER_SIZE = 1 # Force size 1 for safety
        
        client = KalshiClient(config)
        
        # 1. Find Market
        print("Finding active market...")
        market_info = find_best_market(client)
        if not market_info:
            print("No active market found.")
            sys.exit(1)
            
        ticker = market_info['ticker']
        config.TARGET_TICKER = ticker
        print(f"Testing on {ticker}")
        
        # 2. Init Services
        market_data = MarketDataService(config)
        strategy = MarketMakingStrategy(config, client, market_data)
        
        # 3. Hook up strategy
        market_data.add_listener(strategy.on_market_update)
        
        # 4. Start WebSocket in background
        print("Connecting to WebSocket...")
        ws_task = asyncio.create_task(market_data.start())
        
        # 5. Start Strategy inventory sync in background
        sync_task = asyncio.create_task(strategy.sync_inventory())
        
        # 6. Monitor for Orders
        print("Waiting for strategy to place orders (Timeout: 60s)...")
        start_time = time.time()
        orders_placed = False
        
        while time.time() - start_time < 60:
            yes_pos = strategy.current_pos.get('yes')
            no_pos = strategy.current_pos.get('no')
            
            if yes_pos and no_pos:
                print(f"SUCCESS: Orders placed! YES: {yes_pos}, NO: {no_pos}")
                orders_placed = True
                break
            
            await asyncio.sleep(1)
            
        # 7. Cancel and Cleanup
        # Cancel tasks
        ws_task.cancel()
        sync_task.cancel()
        
        if orders_placed:
            print("Cancelling test orders...")
            yes_id = strategy.current_pos['yes']['id']
            no_id = strategy.current_pos['no']['id']
            
            await cancel_order(client, yes_id)
            await cancel_order(client, no_id)
            print("Test Passed.")
            sys.exit(0)
        else:
            print("TIMEOUT: Strategy did not place orders in time.")
            sys.exit(1)

    except Exception as e:
        print(f"Test Failed with Exception: {e}")
        # Try to cleanup if strategy exists
        try:
            if 'strategy' in locals():
                yes = strategy.current_pos.get('yes')
                no = strategy.current_pos.get('no')
                if yes: await cancel_order(client, yes['id'])
                if no: await cancel_order(client, no['id'])
        except:
            pass
        sys.exit(1)

async def cancel_order(client, oid):
    try:
        client.cancel_order(oid)
        print(f"Cancelled {oid}")
    except Exception as e:
        print(f"Failed to cancel {oid}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_live_test())
    except KeyboardInterrupt:
        pass
