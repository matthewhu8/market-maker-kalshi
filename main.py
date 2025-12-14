import asyncio
from config import load_config
from client import KalshiClient
from market_data import MarketDataService
from strategy import MarketMakingStrategy
from scan_markets import find_best_market
import sys

async def main():
    config = load_config()
    client = KalshiClient(config)
    
    # Dynamic Market Selection
    print("Searching for best market...")
    best_market = find_best_market(client)
    
    if best_market:
        ticker = best_market['ticker']
        print(f"Selected Market: {ticker} (Spread: {best_market['spread']}c)")
        # Override config
        config.TARGET_TICKER = ticker
    else:
        print("No suitable market found. Using default/configured ticker.")
    
    print(f"Starting Market Maker for {config.TARGET_TICKER}")
    
    market_data = MarketDataService(config)
    strategy = MarketMakingStrategy(config, client, market_data)

    # Start WS in background
    asyncio.create_task(market_data.connect()) 
    # Logic in market_data.connect() needs to actually run the loop or be separate. 
    # Ideally `start()` method is what runs the loop.
    asyncio.create_task(market_data.start())

    # Start Strategy
    await strategy.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping...")
