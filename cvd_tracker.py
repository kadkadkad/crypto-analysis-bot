"""
Cumulative Volume Delta (CVD) Tracker - Real-time buy/sell pressure analysis
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import statistics


class CVDTracker:
    """Tracks Cumulative Volume Delta for order flow analysis"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
    
    def calculate_cvd_from_trades(self, symbol: str, interval: str = "1h") -> Dict:
        """
        Calculate CVD from recent trades
        CVD = Cumulative (Buy Volume - Sell Volume)
        """
        try:
            # Get recent trades from Binance
            url = f"https://fapi.binance.com/fapi/v1/aggTrades"
            params = {
                "symbol": symbol,
                "limit": 1000  # Last 1000 trades
            }
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                return self._empty_cvd()
            
            trades = response.json()
            if not trades:
                return self._empty_cvd()
            
            # Calculate CVD
            buy_volume = 0
            sell_volume = 0
            cvd_series = []
            cumulative = 0
            
            for trade in trades:
                qty = float(trade['q'])
                price = float(trade['p'])
                volume_usd = qty * price
                
                is_buyer_maker = trade['m']  # True if seller was maker
                
                if is_buyer_maker:
                    # Seller initiated (market sell)
                    sell_volume += volume_usd
                    cumulative -= volume_usd
                else:
                    # Buyer initiated (market buy)
                    buy_volume += volume_usd
                    cumulative += volume_usd
                
                cvd_series.append(cumulative)
            
            # Calculate metrics
            total_volume = buy_volume + sell_volume
            buy_percentage = (buy_volume / total_volume * 100) if total_volume > 0 else 50
            
            # CVD trend (comparing first and last quarter)
            first_quarter_avg = statistics.mean(cvd_series[:250]) if len(cvd_series) >= 250 else cvd_series[0]
            last_quarter_avg = statistics.mean(cvd_series[-250:]) if len(cvd_series) >= 250 else cvd_series[-1]
            
            trend = "bullish" if last_quarter_avg > first_quarter_avg else "bearish" if last_quarter_avg < first_quarter_avg else "neutral"
            
            return {
                "cvd": cumulative,
                "buy_volume_usd": buy_volume,
                "sell_volume_usd": sell_volume,
                "buy_percentage": buy_percentage,
                "trend": trend,
                "strength": abs(last_quarter_avg - first_quarter_avg) / abs(first_quarter_avg) if first_quarter_avg != 0 else 0
            }
            
        except Exception as e:
            print(f"[ERROR] CVD calculation failed for {symbol}: {e}")
            return self._empty_cvd()
    
    def _empty_cvd(self) -> Dict:
        """Return empty CVD data structure"""
        return {
            "cvd": 0,
            "buy_volume_usd": 0,
            "sell_volume_usd": 0,
            "buy_percentage": 50,
            "trend": "neutral",
            "strength": 0
        }
    
    def get_cvd_report(self, coins_data: List[Dict]) -> str:
        """Generate CVD report for coins with volume spikes"""
        report = "📊 <b>Cumulative Volume Delta (CVD) Analysis</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "⚡ Detecting pump/dump patterns via order flow\n\n"
        
        # Filter coins with high volume or price change
        high_activity_coins = []
        
        for coin in coins_data:
            symbol = coin.get("Symbol", "")
            price_change = coin.get("24h Change (%)", 0)
            volume = coin.get("24h Volume (USDT)", 0)
            
            try:
                price_change_val = float(str(price_change).replace("%", ""))
                volume_val = float(volume)
            except:
                continue
            
            # Focus on coins with >5% move or >$10M volume
            if abs(price_change_val) > 5 or volume_val > 10_000_000:
                high_activity_coins.append({
                    "symbol": symbol,
                    "price_change": price_change_val,
                    "volume": volume_val
                })
        
        # Analyze top movers
        sorted_coins = sorted(high_activity_coins, key=lambda x: abs(x["price_change"]), reverse=True)[:15]
        
        bullish_cvd = []
        bearish_cvd = []
        
        for coin_info in sorted_coins:
            symbol = coin_info["symbol"]
            cvd_data = self.calculate_cvd_from_trades(symbol)
            
            entry = {
                "symbol": symbol.replace("USDT", ""),
                "price_change": coin_info["price_change"],
                "buy_pct": cvd_data["buy_percentage"],
                "cvd": cvd_data["cvd"],
                "trend": cvd_data["trend"]
            }
            
            # Detect divergence (price up but CVD bearish = fake pump)
            if coin_info["price_change"] > 5 and cvd_data["buy_percentage"] < 45:
                entry["signal"] = "⚠️ DIVERGENCE (Fake Pump)"
                bearish_cvd.append(entry)
            elif coin_info["price_change"] < -5 and cvd_data["buy_percentage"] > 55:
                entry["signal"] = "⚠️ DIVERGENCE (Fake Dump)"
                bullish_cvd.append(entry)
            elif cvd_data["buy_percentage"] > 60:
                entry["signal"] = "🟢 Strong Buy Pressure"
                bullish_cvd.append(entry)
            elif cvd_data["buy_percentage"] < 40:
                entry["signal"] = "🔴 Strong Sell Pressure"
                bearish_cvd.append(entry)
        
        # Report bullish CVD
        if bullish_cvd:
            report += "🟢 <b>BULLISH CVD (Buy Pressure Dominant)</b>\n\n"
            for entry in bullish_cvd[:7]:
                report += f"${entry['symbol']}: {entry['signal']}\n"
                report += f"   Price: {entry['price_change']:+.2f}% | Buy%: {entry['buy_pct']:.1f}%\n"
            report += "\n"
        
        # Report bearish CVD
        if bearish_cvd:
            report += "🔴 <b>BEARISH CVD (Sell Pressure Dominant)</b>\n\n"
            for entry in bearish_cvd[:7]:
                report += f"${entry['symbol']}: {entry['signal']}\n"
                report += f"   Price: {entry['price_change']:+.2f}% | Buy%: {entry['buy_pct']:.1f}%\n"
            report += "\n"
        
        if not bullish_cvd and not bearish_cvd:
            report += "✅ No significant CVD divergences detected.\n\n"
        
        report += "💡 <b>Interpretation:</b>\n"
        report += "• <i>Buy% > 60</i>: Strong accumulation\n"
        report += "• <i>Buy% < 40</i>: Strong distribution\n"
        report += "• <i>Divergence</i>: Price and CVD moving opposite = potential reversal\n"
        
        return report


# Global instance
CVD_TRACKER = CVDTracker()


def get_cvd_report(coins_data: List[Dict]) -> str:
    """Get CVD analysis report"""
    return CVD_TRACKER.get_cvd_report(coins_data)
