import aiohttp
import asyncio
import json
import time

class ExchangeAggregator:
    def __init__(self, session=None):
        self.session = session

    async def _get_session(self):
        if self.session and not self.session.closed:
            return self.session
        return aiohttp.ClientSession()

    async def fetch_bybit_ticker(self, symbol):
        """Fetches ticker data from Bybit V5 API."""
        # Bybit uses classic symbols like BTCUSDT
        try:
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
            session = await self._get_session()
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["retCode"] == 0 and data["result"]["list"]:
                        ticker = data["result"]["list"][0]
                        return {
                            "exchange": "Bybit",
                            "price": float(ticker["lastPrice"]),
                            "volume": float(ticker["volume24h"]),
                            "quote_volume": float(ticker["turnover24h"])
                        }
        except Exception as e:
            # print(f"[WARN] Bybit fetch failed for {symbol}: {e}")
            pass
        return None

    async def fetch_okx_ticker(self, symbol):
        """Fetches ticker data from OKX V5 API."""
        # OKX uses hyphenated symbols like BTC-USDT
        try:
            okx_symbol = f"{symbol[:-4]}-{symbol[-4:]}" # Convert BTCUSDT to BTC-USDT
            url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_symbol}"
            session = await self._get_session()
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["code"] == "0" and data["data"]:
                        ticker = data["data"][0]
                        return {
                            "exchange": "OKX",
                            "price": float(ticker["last"]),
                            "volume": float(ticker["vol24h"]), # Base volume
                            "quote_volume": float(ticker["volCcy24h"]) # Quote volume
                        }
        except Exception as e:
            # print(f"[WARN] OKX fetch failed for {symbol}: {e}")
            pass
        return None

    async def get_global_metrics(self, symbol, binance_data=None):
        """
        Aggregates data from Binance (passed in), Bybit, and OKX.
        Returns a dictionary with global metrics.
        """
        valid_sources = []
        
        # 1. Add Binance if provided
        if binance_data:
            valid_sources.append({
                "exchange": "Binance",
                "price": binance_data["price"],
                "volume": binance_data.get("volume", 0),
                "quote_volume": binance_data.get("quote_volume", 0)
            })

        # 2. Fetch others concurrently
        results = await asyncio.gather(
            self.fetch_bybit_ticker(symbol),
            self.fetch_okx_ticker(symbol),
            return_exceptions=True
        )

        for res in results:
            if res and isinstance(res, dict):
                valid_sources.append(res)
        
        if not valid_sources:
            return None

        # 2. Calculate Aggregates
        total_vol = sum(s["quote_volume"] for s in valid_sources)
        weighted_price = sum(s["price"] * s["quote_volume"] for s in valid_sources) / total_vol if total_vol > 0 else 0
        
        prices = [s["price"] for s in valid_sources]
        min_price = min(prices)
        max_price = max(prices)
        spread_pct = ((max_price - min_price) / min_price) * 100 if min_price > 0 else 0

        # Find Dominant Exchange
        dominant = max(valid_sources, key=lambda x: x["quote_volume"])
        
        return {
            "Global_Price": weighted_price,
            "Global_Volume_24h": total_vol,
            "Price_Spread_Pct": spread_pct,
            "Source_Count": len(valid_sources),
            "Dominant_Exchange": dominant["exchange"],
            "Exchanges": {s["exchange"]: {"price": s["price"], "vol": s["quote_volume"]} for s in valid_sources}
        }
