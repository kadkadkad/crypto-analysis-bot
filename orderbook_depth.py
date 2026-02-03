"""
Order Book Imbalance & Wall Detector - Real-time depth analysis
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import aiohttp

class OrderBookAnalyzer:
    """Analyzes order book depth for support/resistance walls and spoofing"""
    
    def __init__(self):
        self.base_url = "https://fapi.binance.com/fapi/v1/depth"
    
    async def fetch_depth(self, session, symbol: str) -> Dict:
        """Fetch depth data asynchronously"""
        try:
            params = {"symbol": symbol, "limit": 100} # Top 100 limit orders sufficient for imbalance
            async with session.get(self.base_url, params=params, timeout=3) as response:
                if response.status == 200:
                    return await response.json()
        except:
            pass
        return {}
    
    def analyze_imbalance(self, depth_data: Dict, symbol: str) -> Dict:
        """Calculate Bid/Ask Imbalance and detect Walls"""
        if not depth_data:
            return None
            
        bids = depth_data.get("bids", [])
        asks = depth_data.get("asks", [])
        
        if not bids or not asks:
            return None
            
        # Calculate total volume in USD for top levels
        total_bid_vol = sum([float(p) * float(q) for p, q in bids])
        total_ask_vol = sum([float(p) * float(q) for p, q in asks])
        
        total_vol = total_bid_vol + total_ask_vol
        if total_vol == 0: return None
        
        bid_pct = (total_bid_vol / total_vol) * 100
        ask_pct = (total_ask_vol / total_vol) * 100
        
        imbalance_ratio = bid_pct / ask_pct if ask_pct > 0 else 100
        
        # Detect Large Walls (Orders > 5% of total depth volume)
        walls = []
        for p, q in bids:
            vol = float(p) * float(q)
            if vol > total_vol * 0.05:
                walls.append(f"🟢 BUY WALL: ${vol/1000:.0f}K @ {float(p):.4f}")
        
        for p, q in asks:
            vol = float(p) * float(q)
            if vol > total_vol * 0.05:
                walls.append(f"🔴 SELL WALL: ${vol/1000:.0f}K @ {float(p):.4f}")
        
        return {
            "symbol": symbol.replace("USDT", ""),
            "bid_vol": total_bid_vol,
            "ask_vol": total_ask_vol,
            "bid_pct": bid_pct,
            "ask_pct": ask_pct,
            "imbalance_ratio": imbalance_ratio,
            "walls": walls[:3] # Top 3 walls
        }

    async def run_analysis(self, symbols: List[str]) -> List[Dict]:
        """Run batch analysis"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_depth(session, s) for s in symbols]
            results = await asyncio.gather(*tasks)
            
            analyzed = []
            for i, data in enumerate(results):
                res = self.analyze_imbalance(data, symbols[i])
                if res and (res["bid_pct"] > 60 or res["ask_pct"] > 60): # Only significant imbalance
                    analyzed.append(res)
            return analyzed

    def get_orderbook_report(self, coins_data: List[Dict]) -> str:
        """Generate Order Book Report"""
        report = "🧱 <b>Order Book Imbalance (Wall Detector)</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "⚖️ Real-time Bid/Ask pressure from Depth 100\n\n"
        
        # Get symbols
        symbols = [c.get("Coin") for c in coins_data if c.get("Coin")]
        symbols = symbols[:20] # Limit to top 20 to be fast
        
        analyzed = asyncio.run(self.run_analysis(symbols))
        
        # Sort by imbalance intensity
        analyzed.sort(key=lambda x: abs(50 - x["bid_pct"]), reverse=True)
        
        buy_pressure = [x for x in analyzed if x["bid_pct"] > 55]
        sell_pressure = [x for x in analyzed if x["ask_pct"] > 55]
        
        if buy_pressure:
            report += "🟢 <b>BUY PRESSURE (Bids Dominating)</b>\n"
            for x in buy_pressure[:5]:
                report += f"<b>${x['symbol']}</b>: {x['bid_pct']:.1f}% Bids\n"
                if x["walls"]:
                    for w in x["walls"]: report += f"   {w}\n"
            report += "\n"

        if sell_pressure:
            report += "🔴 <b>SELL PRESSURE (Asks Dominating)</b>\n"
            for x in sell_pressure[:5]:
                report += f"<b>${x['symbol']}</b>: {x['ask_pct']:.1f}% Asks\n"
                if x["walls"]:
                     for w in x["walls"]: report += f"   {w}\n"
            report += "\n"
            
        if not buy_pressure and not sell_pressure:
            report += "✅ Order books are balanced.\n"
            
        return report

# Global Instance
ORDERBOOK_ANALYZER = OrderBookAnalyzer()

def get_orderbook_report(coins_data: List[Dict]) -> str:
    return ORDERBOOK_ANALYZER.get_orderbook_report(coins_data)
