"""
AI Trade Doctor - Position Analysis & Recommendations
Analyzes your positions and gives AI-powered buy/sell/hold recommendations.
Uses real market data from Binance.
"""

import requests
import datetime
from typing import Dict, List, Optional
import json

class TradeDoctor:
    """AI-powered position analyzer with real market data"""
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.futures_url = "https://fapi.binance.com/fapi/v1"
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price from Binance"""
        try:
            symbol = symbol.upper().replace('$', '')
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            response = requests.get(f"{self.base_url}/ticker/price", 
                                   params={'symbol': symbol}, timeout=5)
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return 0.0
    
    def get_24h_stats(self, symbol: str) -> Dict:
        """Get 24h price change stats"""
        try:
            symbol = symbol.upper().replace('$', '')
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            response = requests.get(f"{self.base_url}/ticker/24hr",
                                   params={'symbol': symbol}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'price_change_pct': float(data.get('priceChangePercent', 0)),
                    'high_24h': float(data.get('highPrice', 0)),
                    'low_24h': float(data.get('lowPrice', 0)),
                    'volume_24h': float(data.get('quoteVolume', 0))
                }
        except:
            pass
        return {'price_change_pct': 0, 'high_24h': 0, 'low_24h': 0, 'volume_24h': 0}
    
    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 100) -> List:
        """Get candlestick data for technical analysis"""
        try:
            symbol = symbol.upper().replace('$', '')
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            response = requests.get(f"{self.base_url}/klines",
                                   params={'symbol': symbol, 'interval': interval, 'limit': limit},
                                   timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []
    
    def calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI from close prices"""
        if len(closes) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return 50.0
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def get_support_resistance(self, symbol: str) -> Dict:
        """Calculate support and resistance levels"""
        klines = self.get_klines(symbol, '4h', 50)
        if not klines:
            return {'support': 0, 'resistance': 0}
        
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        
        current_price = closes[-1] if closes else 0
        
        # Simple S/R based on recent pivots
        recent_lows = sorted(lows[-20:])[:5]
        recent_highs = sorted(highs[-20:], reverse=True)[:5]
        
        support = sum(recent_lows) / len(recent_lows) if recent_lows else 0
        resistance = sum(recent_highs) / len(recent_highs) if recent_highs else 0
        
        return {
            'support': round(support, 4),
            'resistance': round(resistance, 4),
            'distance_to_support_pct': round(((current_price - support) / current_price) * 100, 2) if current_price else 0,
            'distance_to_resistance_pct': round(((resistance - current_price) / current_price) * 100, 2) if current_price else 0
        }
    
    def analyze_position(self, symbol: str, entry_price: float, quantity: float, position_type: str = 'long') -> Dict:
        """
        Comprehensive position analysis
        
        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')
            entry_price: Your entry price
            quantity: Amount you hold
            position_type: 'long' or 'short'
        
        Returns:
            Complete analysis with recommendation
        """
        symbol = symbol.upper().replace('$', '').replace('USDT', '')
        
        # Get current market data
        current_price = self.get_current_price(symbol)
        if current_price == 0:
            return {'error': f'Could not fetch price for {symbol}'}
        
        stats_24h = self.get_24h_stats(symbol)
        klines = self.get_klines(symbol, '1h', 100)
        sr_levels = self.get_support_resistance(symbol)
        
        # Calculate technicals
        closes = [float(k[4]) for k in klines] if klines else []
        rsi = self.calculate_rsi(closes) if closes else 50
        ema_20 = self.calculate_ema(closes, 20) if len(closes) >= 20 else current_price
        ema_50 = self.calculate_ema(closes, 50) if len(closes) >= 50 else current_price
        
        # Calculate P&L
        if position_type == 'long':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_usd = (current_price - entry_price) * quantity
        else:  # short
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
            pnl_usd = (entry_price - current_price) * quantity
        
        position_value = current_price * quantity
        
        # Determine trend
        if ema_20 > ema_50:
            trend = 'bullish'
            trend_strength = min(((ema_20 - ema_50) / ema_50) * 100, 10)
        else:
            trend = 'bearish'
            trend_strength = min(((ema_50 - ema_20) / ema_50) * 100, 10)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            position_type=position_type,
            pnl_pct=pnl_pct,
            rsi=rsi,
            trend=trend,
            current_price=current_price,
            sr_levels=sr_levels,
            stats_24h=stats_24h
        )
        
        # Calculate risk/reward targets
        risk_reward = self._calculate_risk_reward(
            entry_price=entry_price,
            current_price=current_price,
            support=sr_levels['support'],
            resistance=sr_levels['resistance'],
            position_type=position_type
        )
        
        return {
            'symbol': symbol,
            'position_type': position_type,
            'entry_price': entry_price,
            'current_price': round(current_price, 4),
            'quantity': quantity,
            'position_value_usd': round(position_value, 2),
            'pnl': {
                'percentage': round(pnl_pct, 2),
                'usd': round(pnl_usd, 2),
                'status': 'profit' if pnl_usd > 0 else 'loss' if pnl_usd < 0 else 'breakeven'
            },
            'technicals': {
                'rsi': rsi,
                'rsi_signal': 'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral',
                'ema_20': round(ema_20, 4),
                'ema_50': round(ema_50, 4),
                'trend': trend,
                'trend_strength': round(trend_strength, 2)
            },
            'support_resistance': sr_levels,
            'stats_24h': stats_24h,
            'recommendation': recommendation,
            'risk_reward': risk_reward,
            'analyzed_at': datetime.datetime.now().isoformat()
        }
    
    def _generate_recommendation(self, position_type: str, pnl_pct: float, rsi: float,
                                  trend: str, current_price: float, sr_levels: Dict,
                                  stats_24h: Dict) -> Dict:
        """Generate AI recommendation based on multiple factors"""
        
        action_scores = {'HOLD': 0, 'SELL': 0, 'BUY_MORE': 0, 'CLOSE': 0}
        reasons = []
        
        # P&L Analysis
        if pnl_pct > 20:
            action_scores['SELL'] += 3
            reasons.append(f"Taking profit at +{pnl_pct:.1f}% gain is wise")
        elif pnl_pct > 10:
            action_scores['HOLD'] += 2
            reasons.append(f"Position in profit (+{pnl_pct:.1f}%), consider trailing stop")
        elif pnl_pct < -15:
            action_scores['CLOSE'] += 3
            reasons.append(f"Position down {pnl_pct:.1f}%, evaluate stop-loss")
        elif pnl_pct < -5:
            action_scores['HOLD'] += 1
            reasons.append(f"Minor drawdown ({pnl_pct:.1f}%), patience may pay off")
        
        # RSI Analysis
        if rsi > 75:
            if position_type == 'long':
                action_scores['SELL'] += 2
                reasons.append(f"RSI overbought ({rsi}), reversal risk high")
        elif rsi < 25:
            if position_type == 'long':
                action_scores['BUY_MORE'] += 2
                reasons.append(f"RSI oversold ({rsi}), potential bounce")
        else:
            action_scores['HOLD'] += 1
        
        # Trend Analysis
        if position_type == 'long':
            if trend == 'bullish':
                action_scores['HOLD'] += 2
                action_scores['BUY_MORE'] += 1
                reasons.append("Trend is bullish, momentum on your side")
            else:
                action_scores['SELL'] += 1
                reasons.append("Trend turning bearish, be cautious")
        else:  # short
            if trend == 'bearish':
                action_scores['HOLD'] += 2
                reasons.append("Trend is bearish, short position favorable")
            else:
                action_scores['CLOSE'] += 1
                reasons.append("Trend turning bullish, consider closing short")
        
        # Support/Resistance
        dist_to_support = sr_levels.get('distance_to_support_pct', 0)
        dist_to_resistance = sr_levels.get('distance_to_resistance_pct', 0)
        
        if position_type == 'long':
            if dist_to_resistance < 3:
                action_scores['SELL'] += 2
                reasons.append(f"Approaching resistance ({dist_to_resistance:.1f}% away)")
            if dist_to_support < 3:
                action_scores['BUY_MORE'] += 1
                reasons.append(f"Near support ({dist_to_support:.1f}% away)")
        
        # 24h momentum
        price_change = stats_24h.get('price_change_pct', 0)
        if abs(price_change) > 10:
            if price_change > 0 and position_type == 'long':
                action_scores['SELL'] += 1
                reasons.append(f"Strong 24h pump (+{price_change:.1f}%), consider partial take profit")
            elif price_change < 0 and position_type == 'long':
                action_scores['HOLD'] += 1
                reasons.append(f"24h dump ({price_change:.1f}%), may be oversold")
        
        # Determine final recommendation
        best_action = max(action_scores, key=action_scores.get)
        confidence = min((action_scores[best_action] / sum(action_scores.values())) * 100, 95) if sum(action_scores.values()) > 0 else 50
        
        # Map to user-friendly action
        action_map = {
            'HOLD': '🔒 HOLD',
            'SELL': '🔴 TAKE PROFIT / SELL',
            'BUY_MORE': '🟢 BUY MORE',
            'CLOSE': '⚠️ CLOSE POSITION'
        }
        
        return {
            'action': action_map.get(best_action, 'HOLD'),
            'action_raw': best_action,
            'confidence': round(confidence, 1),
            'reasons': reasons[:4],  # Top 4 reasons
            'scores': action_scores
        }
    
    def _calculate_risk_reward(self, entry_price: float, current_price: float,
                               support: float, resistance: float, position_type: str) -> Dict:
        """Calculate suggested stop-loss and take-profit levels"""
        
        if position_type == 'long':
            # Stop loss below support
            stop_loss = support * 0.98  # 2% below support
            # Take profit at resistance
            take_profit = resistance * 0.98  # 2% below resistance to be safe
            
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            # Short position
            stop_loss = resistance * 1.02
            take_profit = support * 1.02
            
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            'stop_loss': round(stop_loss, 4),
            'take_profit': round(take_profit, 4),
            'risk_usd_per_unit': round(risk, 4),
            'reward_usd_per_unit': round(reward, 4),
            'risk_reward_ratio': round(rr_ratio, 2),
            'is_favorable': rr_ratio >= 1.5
        }
    
    def quick_check(self, symbol: str) -> Dict:
        """Quick health check for a coin without position info"""
        symbol = symbol.upper().replace('$', '').replace('USDT', '')
        
        current_price = self.get_current_price(symbol)
        if current_price == 0:
            return {'error': f'Could not fetch {symbol}'}
        
        stats = self.get_24h_stats(symbol)
        klines = self.get_klines(symbol, '1h', 50)
        closes = [float(k[4]) for k in klines] if klines else []
        rsi = self.calculate_rsi(closes) if closes else 50
        
        # Quick signal
        if rsi < 30 and stats['price_change_pct'] < -5:
            signal = '🟢 OVERSOLD - Potential Buy'
        elif rsi > 70 and stats['price_change_pct'] > 5:
            signal = '🔴 OVERBOUGHT - Caution'
        elif rsi > 50 and stats['price_change_pct'] > 0:
            signal = '🟡 BULLISH MOMENTUM'
        elif rsi < 50 and stats['price_change_pct'] < 0:
            signal = '🟡 BEARISH MOMENTUM'
        else:
            signal = '⚪ NEUTRAL'
        
        return {
            'symbol': symbol,
            'price': round(current_price, 4),
            'change_24h': round(stats['price_change_pct'], 2),
            'rsi': rsi,
            'signal': signal
        }


# Global instance
TRADE_DOCTOR = None

def init_trade_doctor():
    global TRADE_DOCTOR
    TRADE_DOCTOR = TradeDoctor()
    return TRADE_DOCTOR

def get_trade_doctor():
    global TRADE_DOCTOR
    if not TRADE_DOCTOR:
        init_trade_doctor()
    return TRADE_DOCTOR


if __name__ == "__main__":
    print("Testing Trade Doctor...")
    doc = TradeDoctor()
    
    # Test quick check
    result = doc.quick_check('BTC')
    print(f"BTC Quick Check: {json.dumps(result, indent=2)}")
    
    # Test position analysis
    analysis = doc.analyze_position('BTC', entry_price=95000, quantity=0.1, position_type='long')
    print(f"\nPosition Analysis: {json.dumps(analysis, indent=2)}")
