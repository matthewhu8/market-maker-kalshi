from config import load_config
from client import KalshiClient

def find_best_market(client: KalshiClient):
    print("Scanning for best market opportunities...")
    try:
        # Fetch mostly open markets
        data = client.get_markets(limit=1000, status="open")
        markets = data.get("markets", [])
        
        candidates = []
        for m in markets:
            # Metrics
            bid = m.get('yes_bid', 0)
            ask = m.get('yes_ask', 100)
            vol = m.get('volume', 0)
            
            # 1. Basic Filters
            if bid <= 1 or ask >= 99: continue # Empty book
            if bid >= ask: continue # Inverted or crossed
            
            # 2. Spread Calculation
            spread = ask - bid
            
            # 3. Liquidity Filter (Ensure active market)
            '''
            Volume: Total contracts traded
            Open Interest: Total active contracts
            Liquidity: Approx Book depth in cents
            '''
            oi = m.get('open_interest', 0)
            liq = m.get('liquidity', 0)
            
            # Require substantial volume and depth
            # $1,000 liquidity = 100,000 cents
            if vol < 1000 or oi < 3000 or liq < 50000: continue 
            
            # 4. Sanity Check on Spread
            # If spread is > 15 cents, it's likely broken/untouchable
            if spread > 10: continue

            score = spread 
            
            candidates.append({
                'ticker': m['ticker'],
                'bid': bid,
                'ask': ask,
                'spread': spread,
                'vol': vol,
                'title': m.get('title')
            })
            
        # Sort by Spread Descending
        candidates.sort(key=lambda x: x['spread'], reverse=True)
        
        if not candidates:
            print("No suitable markets found.")
            return None
            
        return candidates[0]

    except Exception as e:
        print(f"Error scanning: {e}")
        return None

def scan():
    config = load_config()
    client = KalshiClient(config)
    best = find_best_market(client)
    
    if best:
        print(f"\nBest Opportunity Found: {best['ticker']}")
        print(f"Title: {best['title']}")
        print(f"Spread: {best['spread']} (Bid {best['bid']} / Ask {best['ask']})")
        print(f"Volume: {best['vol']}")
    else:
        print("No opportunities found.")

if __name__ == "__main__":
    scan()
