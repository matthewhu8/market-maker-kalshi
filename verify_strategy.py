import asyncio
from unittest.mock import MagicMock
from config import Config
from strategy import MarketMakingStrategy

async def test_strategy():
    print("--- Starting Strategy Verification ---")
    
    # 1. Setup Mocks
    config = Config(API_KEY="test", PRIVATE_KEY_PATH="test", TARGET_TICKER="TEST-MARKET")
    
    client = MagicMock()
    # Mock positions: Net Long 500 YES
    client.get_positions.return_value = {
        'market_positions': [{'ticker': 'TEST-MARKET', 'position': 500}]
    }
    client.create_order.return_value = {'order': {'order_id': '123'}}
    
    market_data = MagicMock()
    market_data.add_listener = MagicMock()
    # Mock Market: 50 Bid, 54 Ask. Mid = 52.
    market_data.get_best_prices.return_value = (50, 54)
    
    # Mock Imbalance: High Buying Pressure (VOI = 0.8)
    market_data.get_imbalance.return_value = 0.8
    
    # 2. Init Strategy
    strategy = MarketMakingStrategy(config, client, market_data)
    
    # 3. trigger inventory sync manually
    print("\n[Test 1] Syncing Inventory (Simulated)...")
    # await strategy.sync_inventory_once() 
    strategy.net_position = 500
    print(f"Net Position set to: {strategy.net_position}")
    
    # 4. Trigger Market Update
    print("\n[Test 2] Triggering Market Update...")
    # Parameters:
    # Mid = 52
    # Imbalance = 0.8 -> Alpha Adj = +1.6 cents
    # Inventory = 500 -> Skew = -(500/100)*0.5 = -2.5 cents
    # Fair Value = 52 + 1.6 - 2.5 = 51.1
    # Spread = 2
    # Target Bid = 51.1 - 2 = 49.1 -> 49
    # Target Ask = 51.1 + 2 = 53.1 -> 53
    
    print(f"Expected Fair Value Calculation:")
    print(f"Mid: 52")
    print(f"Alpha (+1.6): Imbalance 0.8 * 2.0")
    print(f"Skew (-2.5): Inventory 500 * -0.5")
    print(f"Fair: 51.1")
    print(f"Quotes: 49 / 53")
    
    await strategy.on_market_update()
    
    # 5. Verify Orders
    # Check if create_order was called with 49 and 53 (actually NO order at 100-53=47)
    
    print("\n[Result] Client Calls:")
    for call in client.create_order.call_args_list:
        args = call[1] # kwargs
        print(f"Order: {args.get('side')} {args.get('action')} @ {args.get('price')}")
        
    print("--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(test_strategy())
