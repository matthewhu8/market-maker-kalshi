from config import load_config
from client import KalshiClient

def find():
    config = load_config()
    client = KalshiClient(config)
    try:
        data = client.get_markets(limit=5)
        print("Markets Found:")
        markets = data.get("markets", [])
        if markets:
            print(f"Sample Market Data: {markets[0]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find()
