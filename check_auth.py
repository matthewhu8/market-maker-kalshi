from config import load_config
from client import KalshiClient

def check():
    try:
        config = load_config()
        print(f"Checking auth for Key ID: {config.KEY_ID}")
        client = KalshiClient(config)
        balance = client.get_balance()
        print("Auth Success!")
        print(f"Balance: {balance}")
    except Exception as e:
        print(f"Auth Failed: {e}")

if __name__ == "__main__":
    check()
