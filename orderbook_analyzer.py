"""
Order Book Analyzer Module
Fetches and analyzes order book data from Binance to provide:
- Bid-Ask Spread
- Order Book Imbalance
- Depth Analysis (±1%, ±2%, ±5%)
- Whale Wall Detection
"""

import aiohttp
import config
from typing import Dict, List, Tuple, Optional

async def fetch_order_book(session: aiohttp.ClientSession, symbol: str, limit: int = 100) -> Optional[Dict]:
    try:
        url = f"{config.BINANCE_API_URL}depth?symbol={symbol}&limit={limit}"
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    "bids": [[float(price), float(qty)] for price, qty in data.get("bids", [])],
                    "asks": [[float(price), float(qty)] for price, qty in data.get("asks", [])]
                }
            return None
    except Exception as e:
        print(f"[ERROR] Order book fetch error for {symbol}: {e}")
        return None

def calculate_spread(order_book: Dict) -> Dict[str, float]:
    try:
        if not order_book or not order_book.get("bids") or not order_book.get("asks"):
            return {"spread_pct": 0, "spread_usd": 0}
        best_bid = order_book["bids"][0][0]
        best_ask = order_book["asks"][0][0]
        spread_usd = best_ask - best_bid
        spread_pct = (spread_usd / best_bid) * 100
        return {"spread_pct": round(spread_pct, 4), "spread_usd": round(spread_usd, 2)}
    except:
        return {"spread_pct": 0, "spread_usd": 0}

def calculate_imbalance(order_book: Dict, depth_levels: int = 10) -> float:
    try:
        if not order_book or not order_book.get("bids") or not order_book.get("asks"):
            return 0.0
        bids = order_book["bids"][:depth_levels]
        asks = order_book["asks"][:depth_levels]
        bid_volume = sum(qty for price, qty in bids)
        ask_volume = sum(qty for price, qty in asks)
        total_volume = bid_volume + ask_volume
        if total_volume == 0: return 0.0
        imbalance = (bid_volume - ask_volume) / total_volume
        return round(imbalance, 3)
    except:
        return 0.0

def calculate_depth(order_book: Dict, current_price: float, percentages: List[int] = [1, 2, 5]) -> Dict:
    try:
        if not order_book: return {}
        result = {}
        for pct in percentages:
            bid_threshold = current_price * (1 - pct / 100)
            ask_threshold = current_price * (1 + pct / 100)
            bid_volume = sum(qty for price, qty in order_book["bids"] if price >= bid_threshold)
            ask_volume = sum(qty for price, qty in order_book["asks"] if price <= ask_threshold)
            result[f"{pct}%"] = {"bid": round(bid_volume, 2), "ask": round(ask_volume, 2)}
        return result
    except:
        return {}

def detect_whale_walls(order_book: Dict, avg_multiplier: int = 10) -> Dict:
    try:
        if not order_book: return {"bid_walls": [], "ask_walls": []}
        bid_sizes = [qty for price, qty in order_book["bids"]]
        ask_sizes = [qty for price, qty in order_book["asks"]]
        avg_bid = sum(bid_sizes) / len(bid_sizes) if bid_sizes else 0
        avg_ask = sum(ask_sizes) / len(ask_sizes) if ask_sizes else 0
        bid_walls = [{"price": p, "size": q} for p, q in order_book["bids"] if q > avg_bid * avg_multiplier]
        ask_walls = [{"price": p, "size": q} for p, q in order_book["asks"] if q > avg_ask * avg_multiplier]
        return {"bid_walls": bid_walls[:5], "ask_walls": ask_walls[:5]}
    except:
        return {"bid_walls": [], "ask_walls": []}

def analyze_order_book(order_book: Dict, current_price: float) -> Dict:
    if not order_book: return {}
    return {
        "spread": calculate_spread(order_book),
        "imbalance": calculate_imbalance(order_book),
        "depth": calculate_depth(order_book, current_price),
        "whale_walls": detect_whale_walls(order_book)
    }
