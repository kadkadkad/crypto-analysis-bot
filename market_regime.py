"""
Market Regime Detector
Automatically detects current market conditions
"""
import numpy as np
from datetime import datetime

class MarketRegimeDetector:
    def __init__(self):
        self.current_regime = "UNKNOWN"
        self.confidence = 0.0
        
    def detect_regime(self, results):
        """
        Detect market regime using Market Breadth (% of coins above EMA 50)
        """
        if not results or len(results) < 5:
            return self._default_regime()
        
        total_coins = len(results)
        above_ema50 = 0
        
        # Analyze trend for all coins
        for coin in results:
            trend = coin.get('EMA Trend', coin.get('SMA Trend', ''))
            # In our main loop, 'Bullish' usually means Price > EMAs
            if 'Bullish' in trend or (isinstance(trend, str) and '🚀' in trend):
                above_ema50 += 1
        
        breadth_pct = (above_ema50 / total_coins) * 100
        
        # Confluence indicators (Average of Top 20 for momentum)
        top_coins = results[:20]
        def safe_num(v):
            if v is None or isinstance(v, str): return 0.0
            return float(v)
            
        avg_rsi = np.mean([safe_num(coin.get('RSI', 50)) for coin in top_coins])
        avg_adx = np.mean([safe_num(coin.get('ADX', 0)) for coin in top_coins])
        avg_vol_ratio = np.mean([safe_num(coin.get('Volume Ratio', 1)) for coin in top_coins])

        # Regime Calculation
        return self._calculate_breadth_regime(breadth_pct, avg_rsi, avg_adx, avg_vol_ratio)
    
    def _calculate_breadth_regime(self, breadth, rsi, adx, vol_ratio):
        """
        Breadth-based Regime Logic:
        - BULL: > 60% of market in uptrend
        - BEAR: < 40% of market in uptrend
        - SIDEWAYS: 40-60%
        """
        
        # BULL MARKET
        if breadth >= 60:
            confidence = min(breadth / 100 + (rsi-50)/100, 1.0)
            return {
                "regime": "BULL_MARKET",
                "emoji": "🐂",
                "color": "#10b981",
                "display": "BULL MARKET (HEALTHY)",
                "confidence": confidence,
                "description": f"🚀 Market Breadth is strong. {breadth:.1f}% of assets are in an uptrend.",
                "strategy": "Aggressive momentum, buy the leaders, hold trend positions.",
                "indicators": {
                    "market_breadth": f"{breadth:.1f}%",
                    "avg_rsi": f"{rsi:.1f}",
                    "trend_strength": "High"
                }
            }
        
        # BEAR MARKET
        if breadth <= 40:
            confidence = min((100-breadth)/100 + (50-rsi)/100, 1.0)
            return {
                "regime": "BEAR_MARKET",
                "emoji": "🐻",
                "color": "#ef4444",
                "display": "BEAR MARKET (WEAK)",
                "confidence": confidence,
                "description": f"📉 Market Breadth is failing. Only {breadth:.1f}% of assets holding trend.",
                "strategy": "Capital preservation, high cash levels, wait for reversal.",
                "indicators": {
                    "market_breadth": f"{breadth:.1f}%",
                    "avg_rsi": f"{rsi:.1f}",
                    "trend_strength": "Deteriorating"
                }
            }

        # SIDEWAYS / TRANSITIONAL
        return {
            "regime": "SIDEWAYS",
            "emoji": "↔️",
            "color": "#8b5cf6",
            "display": "TRANSITIONAL",
            "confidence": 0.5,
            "description": "🔄 Market in transition. Mixed signals.",
            "strategy": "Wait for clear direction, reduce exposure, observe",
            "indicators": {
                "trend_score": f"{trend_score:.2f}",
                "momentum": f"{momentum:.1f}",
                "adx": f"{adx:.1f}",
                "status": "Mixed/Transitioning"
            }
        }
    
    def _default_regime(self):
        """Default regime when not enough data"""
        return {
            "regime": "UNKNOWN",
            "emoji": "❓",
            "color": "#6b7280",
            "display": "ANALYZING",
            "confidence": 0.0,
            "description": "⏳ Gathering data for regime detection...",
            "strategy": "Wait for sufficient market data",
            "indicators": {}
        }
    
    def format_regime_banner(self, regime_data):
        """Format regime for display banner"""
        confidence_bar = "█" * int(regime_data['confidence'] * 10)
        
        banner = f"{regime_data['emoji']} <b>{regime_data['display']}</b> "
        banner += f"(Confidence: {confidence_bar} {regime_data['confidence']*100:.0f}%)\n\n"
        banner += f"{regime_data['description']}\n\n"
        banner += f"<b>📋 Recommended Strategy:</b>\n{regime_data['strategy']}\n\n"
        
        if regime_data['indicators']:
            banner += "<b>📊 Key Indicators:</b>\n"
            for key, value in regime_data['indicators'].items():
                banner += f"  • {key.replace('_', ' ').title()}: {value}\n"
        
        return banner
