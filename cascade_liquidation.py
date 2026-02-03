"""
Cascade Liquidation Risk Analyzer - Advanced liquidation cascade detection
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import statistics


class CascadeLiquidationAnalyzer:
    """Analyzes liquidation cascade risk and domino effects"""
    
    def __init__(self):
        self.common_leverages = [3, 5, 10, 20, 25, 50, 100]
        self.cache = {}
    
    def calculate_liquidation_zones(self, price: float, open_interest: float, leverage_distribution: Dict = None) -> List[Dict]:
        """
        Calculate liquidation price zones for different leverage levels
        """
        if leverage_distribution is None:
            # Estimated distribution (can be enhanced with real data)
            leverage_distribution = {
                3: 0.05,    # 5% of traders
                5: 0.10,    # 10% of traders
                10: 0.25,   # 25% of traders
                20: 0.30,   # 30% of traders
                25: 0.15,   # 15% of traders
                50: 0.10,   # 10% of traders
                100: 0.05   # 5% of traders
            }
        
        zones = []
        
        for leverage, distribution_pct in leverage_distribution.items():
            # Long liquidation (price drops)
            long_liq_price = price * (1 - (1 / leverage))
            long_liq_value = open_interest * distribution_pct * 0.6  # Assume 60% longs
            
            # Short liquidation (price rises)
            short_liq_price = price * (1 + (1 / leverage))
            short_liq_value = open_interest * distribution_pct * 0.4  # Assume 40% shorts
            
            zones.append({
                "leverage": leverage,
                "long_liq_price": long_liq_price,
                "long_liq_value_usd": long_liq_value,
                "short_liq_price": short_liq_price,
                "short_liq_value_usd": short_liq_value,
                "distance_pct_long": ((price - long_liq_price) / price) * 100,
                "distance_pct_short": ((short_liq_price - price) / price) * 100
            })
        
        return zones
    
    def detect_cascade_risk(self, zones: List[Dict], price: float, volatility_24h: float) -> Dict:
        """
        Detect cascade liquidation risk
        Cascade occurs when one liquidation triggers another in a domino effect
        """
        # Find zones within volatility range
        cascade_zones_long = []
        cascade_zones_short = []
        
        for zone in zones:
            # Long cascade risk (downward)
            if zone["distance_pct_long"] <= volatility_24h * 1.5:
                cascade_zones_long.append(zone)
            
            # Short cascade risk (upward)
            if zone["distance_pct_short"] <= volatility_24h * 1.5:
                cascade_zones_short.append(zone)
        
        # Calculate total liquidatable value
        total_long_cascade_value = sum(z["long_liq_value_usd"] for z in cascade_zones_long)
        total_short_cascade_value = sum(z["short_liq_value_usd"] for z in cascade_zones_short)
        
        # Determine risk level
        long_risk = "high" if len(cascade_zones_long) >= 3 else "medium" if len(cascade_zones_long) >= 2 else "low"
        short_risk = "high" if len(cascade_zones_short) >= 3 else "medium" if len(cascade_zones_short) >= 2 else "low"
        
        return {
            "cascade_zones_long": cascade_zones_long,
            "cascade_zones_short": cascade_zones_short,
            "total_long_at_risk": total_long_cascade_value,
            "total_short_at_risk": total_short_cascade_value,
            "long_cascade_risk": long_risk,
            "short_cascade_risk": short_risk,
            "nearest_long_liq": min([z["long_liq_price"] for z in zones]) if zones else 0,
            "nearest_short_liq": min([z["short_liq_price"] for z in zones], key=lambda x: abs(x - price)) if zones else 0
        }
    
    def get_cascade_report(self, coins_data: List[Dict]) -> str:
        """Generate cascade liquidation risk report"""
        report = "⚠️ <b>CASCADE LIQUIDATION RISK ANALYSIS</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "🔥 Detecting domino liquidation threats\n\n"
        
        high_risk_coins = []
        
        for coin in coins_data:
            symbol = coin.get("Coin", "")  # Changed from "Symbol"
            # Get data with fallbacks for different key names that might exist
            price = coin.get("Current Price", coin.get("Price", 0))
            oi = coin.get("Open Interest", 0)
            volatility = coin.get("ATR", coin.get("atr", 0))
            
            try:
                # Handle price (might be string "$123" or float)
                if isinstance(price, str):
                    price_val = float(str(price).replace('$', '').replace(',', ''))
                else:
                    price_val = float(price)

                # Handle Open Interest (might be string or float)
                if isinstance(oi, str):
                    oi_val = float(str(oi).replace('$', '').replace(',', ''))
                else:
                    oi_val = float(oi)
                
                # Handle Volatility
                if isinstance(volatility, str):
                    vol_val = float(str(volatility).replace('$', '').replace(',', ''))
                else:
                    vol_val = float(volatility)
                
                if vol_val == 0:
                     vol_val = price_val * 0.03 # Default 3%
            except:
                continue
            
            if oi_val == 0 or price_val == 0:
                continue
            
            # Calculate liquidation zones
            zones = self.calculate_liquidation_zones(price_val, oi_val)
            
            # Detect cascade risk
            cascade_analysis = self.detect_cascade_risk(zones, price_val, (vol_val / price_val) * 100)
            
            # Focus on high risk
            if cascade_analysis["long_cascade_risk"] == "high" or cascade_analysis["short_cascade_risk"] == "high":
                high_risk_coins.append({
                    "symbol": symbol.replace("USDT", ""),
                    "price": price_val,
                    "oi": oi_val,
                    **cascade_analysis
                })
        
        # Sort by total at-risk value
        high_risk_coins.sort(key=lambda x: x["total_long_at_risk"] + x["total_short_at_risk"], reverse=True)
        
        if high_risk_coins:
            report += "🚨 <b>HIGH CASCADE RISK COINS</b>\n\n"
            
            for coin in high_risk_coins[:10]:
                report += f"<b>${coin['symbol']}</b> @ ${coin['price']:.4f}\n"
                
                # Long cascade risk
                if coin["long_cascade_risk"] == "high":
                    report += f"   🔴 Long Cascade: <b>HIGH RISK</b>\n"
                    report += f"      Nearest: ${coin['nearest_long_liq']:.4f} ({len(coin['cascade_zones_long'])} zones)\n"
                    report += f"      At Risk: ${coin['total_long_at_risk']/1e6:.2f}M\n"
                
                # Short cascade risk
                if coin["short_cascade_risk"] == "high":
                    report += f"   🟢 Short Cascade: <b>HIGH RISK</b>\n"
                    report += f"      Nearest: ${coin['nearest_short_liq']:.4f} ({len(coin['cascade_zones_short'])} zones)\n"
                    report += f"      At Risk: ${coin['total_short_at_risk']/1e6:.2f}M\n"
                
                report += "\n"
            
            report += "💥 <b>Cascade Effect Explained:</b>\n"
            report += "• Multiple leverage zones clustered together\n"
            report += "• First liquidation triggers next → domino effect\n"
            report += "• Can cause 5-10% sudden price swings\n"
            report += "• High risk when volatility reaches these zones\n"
        else:
            report += "✅ No high cascade risk detected.\n"
            report += "Liquidation zones are well-distributed.\n\n"
        
        return report


# Global instance
CASCADE_ANALYZER = CascadeLiquidationAnalyzer()


def get_cascade_liquidation_report(coins_data: List[Dict]) -> str:
    """Get cascade liquidation risk report"""
    return CASCADE_ANALYZER.get_cascade_report(coins_data)
