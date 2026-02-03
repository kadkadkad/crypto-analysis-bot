"""
Multi-Exchange Arbitrage Tracker - Real-time arbitrage opportunity scanner
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import aiohttp


class ArbitrageTracker:
    """Tracks price differences across exchanges for arbitrage opportunities"""
    
    def __init__(self):
        self.exchanges = {
            "binance": "https://fapi.binance.com/fapi/v1/ticker/price",
            "bybit": "https://api.bybit.com/v5/market/tickers",
            "okx": "https://www.okx.com/api/v5/market/tickers",
            "coinbase": "https://api.exchange.coinbase.com/products"
        }
        self.cache = {}
        self.min_spread = 0.3  # Minimum 0.3% spread to consider
    
    async def fetch_binance_price(self, session, symbol):
        """Fetch Binance price"""
        try:
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("price", 0))
        except:
            pass
        return None
    
    async def fetch_bybit_price(self, session, symbol):
        """Fetch Bybit price"""
        try:
            normalized = symbol.replace("USDT", "")
            url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={normalized}USDT"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("result") and data["result"].get("list"):
                        return float(data["result"]["list"][0].get("lastPrice", 0))
        except:
            pass
        return None
    
    async def fetch_okx_price(self, session, symbol):
        """Fetch OKX price"""
        try:
            normalized = symbol.replace("USDT", "")
            url = f"https://www.okx.com/api/v5/market/ticker?instId={normalized}-USDT-SWAP"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        return float(data["data"][0].get("last", 0))
        except:
            pass
        return None
    
    async def get_multi_exchange_prices(self, symbol: str) -> Dict:
        """Fetch prices from multiple exchanges simultaneously"""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_binance_price(session, symbol),
                self.fetch_bybit_price(session, symbol),
                self.fetch_okx_price(session, symbol)
            ]
            results = await asyncio.gather(*tasks)
            
            return {
                "binance": results[0],
                "bybit": results[1],
                "okx": results[2]
            }
    
    def calculate_arbitrage_opportunity(self, prices: Dict) -> Optional[Dict]:
        """Calculate arbitrage spread between exchanges"""
        # Filter out None values
        valid_prices = {k: v for k, v in prices.items() if v is not None and v > 0}
        
        if len(valid_prices) < 2:
            return None
        
        # Find min and max
        min_exchange = min(valid_prices, key=valid_prices.get)
        max_exchange = max(valid_prices, key=valid_prices.get)
        
        min_price = valid_prices[min_exchange]
        max_price = valid_prices[max_exchange]
        
        # Calculate spread percentage
        spread_pct = ((max_price - min_price) / min_price) * 100
        
        if spread_pct < self.min_spread:
            return None
        
        return {
            "buy_exchange": min_exchange,
            "sell_exchange": max_exchange,
            "buy_price": min_price,
            "sell_price": max_price,
            "spread_pct": spread_pct,
            "profit_per_1k": spread_pct * 10  # Profit on $1000 trade
        }
    
    def get_arbitrage_report(self, coins_data: List[Dict]) -> str:
        """Generate arbitrage opportunities report"""
        report = "💰 <b>Multi-Exchange Arbitrage Opportunities</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += f"🎯 Min Spread: {self.min_spread}%\n\n"
        
        opportunities = []
        
        # Check top coins by volume
        sorted_coins = sorted(
            coins_data,
            key=lambda x: float(str(x.get("24h Volume", 0)).replace(",", "")),  # Changed field
            reverse=True
        )[:30]  # Top 30 by volume
        
        for coin in sorted_coins:
            symbol = coin.get("Coin", "")  # Changed from "Symbol"
            if not symbol:
                continue
            
            try:
                # Get prices async
                prices = asyncio.run(self.get_multi_exchange_prices(symbol))
                arb = self.calculate_arbitrage_opportunity(prices)
                
                if arb:
                    opportunities.append({
                        "symbol": symbol.replace("USDT", ""),
                        **arb
                    })
            except Exception as e:
                print(f"[DEBUG] Arbitrage check failed for {symbol}: {e}")
                continue
        
        # Sort by spread
        opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
        
        if opportunities:
            report += "🔥 <b>ACTIVE ARBITRAGE OPPORTUNITIES</b>\n\n"
            
            for idx, opp in enumerate(opportunities[:10], 1):
                report += f"{idx}. <b>${opp['symbol']}</b>\n"
                report += f"   📉 Buy: {opp['buy_exchange'].upper()} @ ${opp['buy_price']:.4f}\n"
                report += f"   📈 Sell: {opp['sell_exchange'].upper()} @ ${opp['sell_price']:.4f}\n"
                report += f"   💵 Spread: <b>{opp['spread_pct']:.2f}%</b>\n"
                report += f"   🎁 Est. Profit/1K: ${opp['profit_per_1k']:.2f}\n\n"
            
            report += "⚠️ <b>Important Notes:</b>\n"
            report += "• Includes exchange fees (~0.1% each side)\n"
            report += "• Withdrawal time may impact profitability\n"
            report += "• Flash loan opportunities require technical setup\n"
        else:
            report += "✅ No significant arbitrage opportunities detected.\n"
            report += f"(Min spread threshold: {self.min_spread}%)\n\n"
            report += "Market is efficient across exchanges.\n"
        
        return report


# Global instance
ARBITRAGE_TRACKER = ArbitrageTracker()


def get_arbitrage_report(coins_data: List[Dict]) -> str:
    """Get arbitrage opportunities report"""
    return ARBITRAGE_TRACKER.get_arbitrage_report(coins_data)
