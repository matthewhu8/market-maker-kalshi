import json
import time
import base64
import requests
from config import Config
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

class KalshiClient:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.API_BASE_URL
        self.session = requests.Session()
        self.private_key = self._load_private_key()

    def _load_private_key(self):
        with open(self.config.PRIVATE_KEY_PATH, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None
            )
        return private_key

    def _sign_pss_text(self, text: str) -> str:
        message = text.encode('utf-8')
        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e

    def get_auth_headers(self, method: str, path: str):
        timestamp = str(int(time.time() * 1000))
        # Strip query parameters for signature
        path_without_query = path.split('?')[0]
        msg_string = timestamp + method + path_without_query
        signature = self._sign_pss_text(msg_string)
        
        return {
            'KALSHI-ACCESS-KEY': self.config.KEY_ID,
            'KALSHI-ACCESS-SIGNATURE': signature,
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }

    def request(self, method: str, endpoint: str, params=None, data=None):
        url = f"{self.base_url}{endpoint}"
        
        # We need to construct the full path for signing
        # Assuming config.API_BASE_URL includes the version prefix
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_for_signing = parsed.path
        
        headers = self.get_auth_headers(method, path_for_signing)
        
        response = self.session.request(
            method, 
            url, 
            params=params, 
            json=data, 
            headers=headers
        )
        
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"API Error: {e}")
            print(f"Response: {response.text}")
            raise

    def get_market(self, ticker: str):
        return self.request("GET", f"/markets/{ticker}")

    def get_markets(self, limit: int = 100, status: str = "open"):
        return self.request("GET", "/markets", params={"limit": limit, "status": status})

    def get_balance(self):
        return self.request("GET", "/portfolio/balance")

    def create_order(self, ticker: str, action: str, count: int, price: int, side: str = "yes"):
        # action: "buy" or "sell"
        # price: in cents. If side="no", this is the price of the NO contract.
        
        data = {
            "action": action,
            "count": count,
            "type": "limit",
            "ticker": ticker,
            "side": side,
            "client_order_id": str(int(time.time() * 1000000))
        }
        
        if side == "yes":
            data["yes_price"] = price
        else:
            data["no_price"] = price
            
        return self.request("POST", "/portfolio/orders", data=data)

    def cancel_order(self, order_id: str):
        return self.request("DELETE", f"/portfolio/orders/{order_id}")
