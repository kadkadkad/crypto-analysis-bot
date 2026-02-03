"""
Funding Rate Tracker - Comprehensive funding rate analysis with historical trends
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics


class FundingRateTracker:
    """Tracks funding rates across exchanges with historical analysis"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 60  # 1 minute cache
    
    def get_binance_funding_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get Binance funding rate history"""
        try:
            url = f"https://fapi.binance.com/fapi/v1/fundingRate"
            params = {
                "symbol": symbol,
                "limit": hours // 8  # 8 saatte bir funding
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Binance funding history fetch failed: {e}")
        return []
    
    def calculate_funding_metrics(self, history: List[Dict]) -> Dict:
        """Calculate funding rate statistics"""
        if not history:
            return {
                "current": 0,
                "avg_24h": 0,
                "avg_48h": 0,
                "trend": "neutral",
                "extreme_count": 0
            }
        
        rates = [float(item['fundingRate']) * 100 for item in history]  # Convert to %
        current_rate = rates[0] if rates else 0
        
        # 24h average (last 3 funding periods)
        avg_24h = statistics.mean(rates[:3]) if len(rates) >= 3 else current_rate
        
        # 48h average (last 6 funding periods)
        avg_48h = statistics.mean(rates[:6]) if len(rates) >=6 else avg_24h
        
        # Trend detection
        if current_rate > avg_24h * 1.2:
            trend = "increasing"
        elif current_rate < avg_24h * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Count extreme funding events (>0.1% or <-0.1%)
        extreme_count = sum(1 for r in rates if abs(r) > 0.1)
        
        return {
            "current": round(current_rate, 4),
            "avg_24h": round(avg_24h, 4),
            "avg_48h": round(avg_48h, 4),
            "trend": trend,
            "extreme_count": extreme_count,
            "next_payment_hours": 8  # Binance pays every 8h
        }
    
    def get_comprehensive_funding_report(self, coins_data: List[Dict]) -> str:
        """Generate comprehensive funding rate report"""
        report = "📊 <b>Funding Rate Analysis – Full Report</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        # Categorize by funding levels
        extreme_positive = []  # > 0.1%
        positive = []  # 0.01% to 0.1%
        neutral = []  # -0.01% to 0.01%
        negative = []  # -0.1% to -0.01%
        extreme_negative = []  # < -0.1%
        
        for coin in coins_data:
            symbol = coin.get("Symbol", "UNKNOWN")
            funding = coin.get("Funding Rate", 0)
            
            try:
                funding_val = float(funding)
            except:
                funding_val = 0
            
            # Get historical data
            history = self.get_binance_funding_history(symbol, hours=48)
            metrics = self.calculate_funding_metrics(history)
            
            entry = {
                "symbol": symbol.replace("USDT", ""),
                "current": metrics["current"],
                "avg_24h": metrics["avg_24h"],
                "trend": metrics["trend"],
                "ls_ratio": coin.get("Long/Short Ratio", 1.0)
            }
            
            # Categorize
            if metrics["current"] > 0.1:
                extreme_positive.append(entry)
            elif metrics["current"] > 0.01:
                positive.append(entry)
            elif metrics["current"] < -0.1:
                extreme_negative.append(entry)
            elif metrics["current"] < -0.01:
                negative.append(entry)
            else:
                neutral.append(entry)
        
        # Report sections
        if extreme_positive:
            report += "🔴 <b>EXTREME POSITIVE FUNDING (>0.1%)</b>\n"
            report += "⚠️ High shorts squeeze risk, longs paying heavy fees\n\n"
            for entry in sorted(extreme_positive, key=lambda x: x["current"], reverse=True)[:10]:
                arrow = "📈" if entry["trend"] == "increasing" else "📉" if entry["trend"] == "decreasing" else "➡️"
                report += f"${entry['symbol']}: <b>{entry['current']:.4f}%</b> {arrow}\n"
                report += f"   24h Avg: {entry['avg_24h']:.4f}% | L/S: {entry['ls_ratio']:.2f}\n"
            report += "\n"
        
        if extreme_negative:
            report += "🟢 <b>EXTREME NEGATIVE FUNDING (<-0.1%)</b>\n"
            report += "⚠️ High longs squeeze risk, shorts paying heavy fees\n\n"
            for entry in sorted(extreme_negative, key=lambda x: x["current"])[:10]:
                arrow = "📈" if entry["trend"] == "increasing" else "📉" if entry["trend"] == "decreasing" else "➡️"
                report += f"${entry['symbol']}: <b>{entry['current']:.4f}%</b> {arrow}\n"
                report += f"   24h Avg: {entry['avg_24h']:.4f}% | L/S: {entry['ls_ratio']:.2f}\n"
            report += "\n"
        
        if positive:
            report += "🟠 <b>MODERATE POSITIVE (0.01% - 0.1%)</b>\n"
            report += f"Total: {len(positive)} coins\n"
            for entry in sorted(positive, key=lambda x: x["current"], reverse=True)[:5]:
                report += f"${entry['symbol']}: {entry['current']:.4f}% (24h: {entry['avg_24h']:.4f}%)\n"
            report += "\n"
        
        if negative:
            report += "🟡 <b>MODERATE NEGATIVE (-0.1% - -0.01%)</b>\n"
            report += f"Total: {len(negative)} coins\n"
            for entry in sorted(negative, key=lambda x: x["current"])[:5]:
                report += f"${entry['symbol']}: {entry['current']:.4f}% (24h: {entry['avg_24h']:.4f}%)\n"
            report += "\n"
        
        # Summary stats
        report += "📈 <b>Market-Wide Summary</b>\n"
        report += f"• Extreme Positive: {len(extreme_positive)} coins\n"
        report += f"• Extreme Negative: {len(extreme_negative)} coins\n"
        report += f"• Neutral: {len(neutral)} coins\n"
        report += f"\n💡 Next funding payment: Every 8 hours (00:00, 08:00, 16:00 UTC)\n"
        
        return report


# Global instance
FUNDING_TRACKER = FundingRateTracker()


def get_funding_rate_report(coins_data: List[Dict]) -> str:
    """Get funding rate report for all coins"""
    return FUNDING_TRACKER.get_comprehensive_funding_report(coins_data)
