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
        Detect market regime based on multiple indicators
        
        Regimes:
        - BULL MARKET: Strong uptrend, high momentum
        - BEAR MARKET: Strong downtrend, low momentum
        - SIDEWAYS: Consolidation, low directional movement
        - HIGH VOLATILITY: Choppy, dangerous conditions
        
        Args:
            results: ALL_RESULTS data
            
        Returns:
            dict: regime, confidence, indicators, recommendation
        """
        if not results or len(results) < 10:
            return self._default_regime()
        
        # Analyze top 20 coins
        top_coins = results[:20]
        
        # 1. EMA Trend Analysis
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for coin in top_coins:
            trend = coin.get('EMA Trend', '')
            if 'Bullish' in trend or 'X-Over' in trend and '🚀' in trend:
                bullish_count += 1
            elif 'Bearish' in trend or ('X-Over' in trend and '📉' in trend):
                bearish_count += 1
            else:
                neutral_count += 1
        
        trend_score = (bullish_count - bearish_count) / len(top_coins)
        
        # 2. Momentum Analysis
        avg_momentum = np.mean([coin.get('Momentum', 0) for coin in top_coins])
        
        # 3. ADX Analysis (trend strength)
        avg_adx = np.mean([coin.get('ADX', 0) for coin in top_coins])
        
        # 4. Volatility Analysis (ATR)
        avg_atr = np.mean([coin.get('ATR_raw', 0) for coin in top_coins])
        avg_price = np.mean([coin.get('Price', 1) for coin in top_coins])
        volatility_ratio = (avg_atr / avg_price * 100) if avg_price > 0 else 0
        
        # 5. Volume Analysis
        avg_vol_ratio = np.mean([coin.get('Volume Ratio', 1) for coin in top_coins])
        
        # 6. Net Accumulation (whale buying/selling)
        total_net_accum = sum([coin.get('net_accum_1d', 0) for coin in top_coins])
        net_accum_score = total_net_accum / 1000000  # in millions
        
        # Decision Logic
        regime = self._calculate_regime(
            trend_score, avg_momentum, avg_adx, 
            volatility_ratio, avg_vol_ratio, net_accum_score
        )
        
        return regime
    
    def _calculate_regime(self, trend_score, momentum, adx, volatility, vol_ratio, net_accum):
        """Internal regime calculation"""
        
        # HIGH VOLATILITY takes precedence
        if volatility > 5.0 or vol_ratio > 3.0:
            return {
                "regime": "HIGH_VOLATILITY",
                "emoji": "⚠️",
                "color": "#f59e0b",
                "display": "HIGH VOLATILITY",
                "confidence": min(volatility / 5.0, 1.0),
                "description": "⚠️ Choppy conditions detected. High risk period.",
                "strategy": "Reduce position sizes, use tight stops, avoid leverage",
                "indicators": {
                    "volatility": f"{volatility:.2f}%",
                    "volume_ratio": f"{vol_ratio:.2f}x",
                    "trend_strength": "Weak"
                }
            }
        
        # BULL MARKET
        if trend_score > 0.3 and momentum > 20 and adx > 20:
            confidence = min((trend_score + momentum/100 + (adx-20)/30) / 3, 1.0)
            return {
                "regime": "BULL_MARKET",
                "emoji": "🐂",
                "color": "#10b981",
                "display": "BULL MARKET",
                "confidence": confidence,
                "description": "🚀 Strong uptrend confirmed. Momentum strategies favored.",
                "strategy": "Buy dips, ride trends, use momentum indicators, bullish positions",
                "indicators": {
                    "trend_score": f"+{trend_score:.2f}",
                    "momentum": f"{momentum:.1f}",
                    "adx": f"{adx:.1f}",
                    "whale_flow": f"${net_accum:.1f}M"
                }
            }
        
        # BEAR MARKET
        if trend_score < -0.3 and momentum < -20 and adx > 20:
            confidence = min((abs(trend_score) + abs(momentum)/100 + (adx-20)/30) / 3, 1.0)
            return {
                "regime": "BEAR_MARKET",
                "emoji": "🐻",
                "color": "#ef4444",
                "display": "BEAR MARKET",
                "confidence": confidence,
                "description": "📉 Strong downtrend detected. Capital preservation mode.",
                "strategy": "Preserve capital, short positions, wait for reversal signals",
                "indicators": {
                    "trend_score": f"{trend_score:.2f}",
                    "momentum": f"{momentum:.1f}",
                    "adx": f"{adx:.1f}",
                    "whale_flow": f"${net_accum:.1f}M"
                }
            }
        
        # SIDEWAYS / CONSOLIDATION
        if abs(trend_score) < 0.3 and adx < 25:
            return {
                "regime": "SIDEWAYS",
                "emoji": "↔️",
                "color": "#6b7280",
                "display": "SIDEWAYS MARKET",
                "confidence": 1.0 - abs(trend_score),
                "description": "📊 Consolidation phase. Range-bound trading.",
                "strategy": "Range trading, sell resistance/buy support, wait for breakout",
                "indicators": {
                    "trend_score": f"{trend_score:.2f}",
                    "adx": f"{adx:.1f} (weak trend)",
                    "range": "Consolidating"
                }
            }
        
        # DEFAULT: TRANSITIONAL
        return {
            "regime": "TRANSITIONAL",
            "emoji": "🔄",
            "color": "#8b5cf6",
            "display": "TRANSITIONAL",
            "confidence": 0.5,
            "description": "🔄 Market in transition. Mixed signals.",
            "strategy": "Wait for clear direction, reduce exposure, observe",
            "indicators": {
                "trend_score": f"{trend_score:.2f}",
                "momentum": f"{momentum:.1f}",
                "status": "Transitioning"
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
