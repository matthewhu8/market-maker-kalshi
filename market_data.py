import asyncio
import json
import websockets
from config import Config

class MarketDataService:
    def __init__(self, config: Config):
        self.config = config
        self.url = config.WS_Url
        self.ticker = config.TARGET_TICKER
        self.orderbook = {"yes": {}, "no": {}}
        self.listeners = []
        self.websocket = None

    def add_listener(self, callback):
        self.listeners.append(callback)

    async def connect(self):
        # WebSocket headers need signature too? 
        # Documentation says: "API key authentication required for WebSocket connections. The API key should be provided during the WebSocket handshake."
        # Usually this means we send a message after connecting, or query params?
        # The docs say:
        # { "id": 1, "cmd": "subscribe", ... }
        # And also: "API key authentication required... provided during the WebSocket handshake"
        # Wait, if it's during handshake, it's likely headers or query params.
        # Let's check the doc reference again ideally.
        # But commonly for Kalshi, it's a "login" message or headers.
        # Wait, the `websocket-connection` chunk said: "API key authentication required... provided during the WebSocket handshake"
        # Often this means standard headers if it's a library, or the `protocol` kwarg.
        
        # Let's try connecting without, if it fails, we know.
        # Actually, browsing the docs again (mentally), Kalshi v2 requires signing the connection request?
        # Or maybe it's just public data?
        # "Learn how to access real-time market data without authentication" -> Quick Start says no auth needed for public market data?
        # Quick Start Market Data says: "Start with an initial breakdown... without authentication"
        # But WEBSOCKETS usually require it for trading? 
        # Actually, let's assume public feed `orderbook_delta` MIGHT be public?
        # If not, I'll need to sign the URL or headers.
        
        # Re-reading my research: "Step 3: Get Orderbook Data" in quick start was unauthenticated REST.
        # WebSocket docs said: "API key authentication required...".
        # So I probably need to sign.
        
        pass

    async def start(self):
        # We'll use a loop to maintain connection
        while True:
            try:
                # Based on Kalshi V2 docs, auth is often via query params or headers on handshake.
                # Constructing signed headers similar to REST
                # But websockets library supports extra_headers.
                
                from urllib.parse import urlparse
                from client import KalshiClient
                
                temp_client = KalshiClient(self.config)
                ws_path = urlparse(self.url).path
                headers = temp_client.get_auth_headers("GET", ws_path)

                # I'll re-use the signing logic from client if possible, or duplicate it here for now to avoid circular deps or complex refactoring.
                # Actually, let's just use the `KalshiClient` to generate headers if I could. 
                async with websockets.connect(self.url, additional_headers=headers) as websocket:
                    self.websocket = websocket
                    print("Connected to WebSocket")
                    
                    # Subscribe
                    sub_msg = {
                        "id": 1,
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["orderbook_delta"],
                            "market_ticker": self.ticker
                        }
                    }
                    await websocket.send(json.dumps(sub_msg))
                    
                    async for message in websocket:
                        data = json.loads(message)
                        self._handle_message(data)
                        
            except Exception as e:
                print(f"WebSocket connection dropped: {e}")
                await asyncio.sleep(5)

    def _handle_message(self, data):
        msg_type = data.get("type")
        msg = data.get("msg", {})

        if msg_type == "subscribed":
            print(f"Subscribed to {msg.get('channel')}")
        elif msg_type == "orderbook_snapshot":
            self._process_snapshot(msg)
        elif msg_type == "orderbook_delta":
            self._process_delta(msg)
        elif msg_type == "error":
             print(f"WS Error: {data}")

    async def _notify_listeners(self):
        for listener in self.listeners:
            if asyncio.iscoroutinefunction(listener):
                await listener()
            else:
                listener()

    def _process_snapshot(self, msg):
        # msg keys: yes, no (list of [price, qty])
        # We store them as dicts for easy update: price -> qty
        self.orderbook['yes'] = {item[0]: item[1] for item in msg.get('yes', [])}
        self.orderbook['no'] = {item[0]: item[1] for item in msg.get('no', [])}
        # print("Book snapshot received")
        asyncio.create_task(self._notify_listeners())

    def _process_delta(self, msg):
        # Update YES
        for price, qty in msg.get('yes', []):
            if qty == 0:
                self.orderbook['yes'].pop(price, None)
            else:
                self.orderbook['yes'][price] = qty
        
        # Update NO
        for price, qty in msg.get('no', []):
            if qty == 0:
                self.orderbook['no'].pop(price, None)
            else:
                self.orderbook['no'][price] = qty
        
        asyncio.create_task(self._notify_listeners())

    
    def get_imbalance(self):
        # Calculate simple volume imbalance at top levels
        # VOI = (BidVol - AskVol) / (BidVol + AskVol)
        # Returns float between -1.0 and 1.0
        
        yes_bids = self.orderbook.get('yes', {})
        no_bids = self.orderbook.get('no', {}) # recall: no bids are effectively yes asks
        
        # Get volume at best bid
        if not yes_bids:
            bid_vol = 0
        else:
            best_bid = max(yes_bids.keys())
            bid_vol = yes_bids[best_bid]
            
        # Get volume at best ask (which is best NO bid)
        if not no_bids:
            ask_vol = 0 # No supply
        else:
            best_no_bid = max(no_bids.keys())
            ask_vol = no_bids[best_no_bid]
            
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
            
        # If bid_vol is high, buying pressure -> positive
        # If ask_vol is high (lots of NO bids), selling pressure on YES -> negative
        return (bid_vol - ask_vol) / total

    def get_best_prices(self):
        # Returns (best_yes_bid, best_yes_ask)
        # best_yes_bid = max price in yes book
        # best_yes_ask = 100 - max price in no book (since NO bid X means YES ask 100-X)
        
        yes_bids = self.orderbook.get('yes', {})
        no_bids = self.orderbook.get('no', {})
        
        best_bid = max(yes_bids.keys()) if yes_bids else 0
        
        # Best NO bid = highest price people are willing to pay for NO
        best_no_bid = max(no_bids.keys()) if no_bids else 0
        
        if best_no_bid > 0:
            best_ask = 100 - best_no_bid
        else:
            best_ask = 100 # No one selling YES (no one buying NO)
            
        return best_bid, best_ask
