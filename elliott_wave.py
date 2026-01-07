"""
Elliott Wave Analysis Module
Identifies wave patterns in crypto price data based on Elliott Wave Theory.
Uses Fibonacci relationships and swing point detection.
"""

import requests
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

class ElliottWaveAnalyzer:
    """
    Elliott Wave Pattern Analyzer
    Identifies 5-3 wave structures in price data.
    """
    
    def __init__(self):
        self.binance_url = "https://api.binance.com/api/v3"
        
        # Fibonacci ratios used in Elliott Wave
        self.fib_ratios = {
            'retrace_38': 0.382,
            'retrace_50': 0.500,
            'retrace_62': 0.618,
            'retrace_78': 0.786,
            'extend_127': 1.272,
            'extend_162': 1.618,
            'extend_200': 2.000,
            'extend_262': 2.618
        }
        
        # Wave rules
        self.wave_rules = {
            'wave2_max_retrace': 1.0,     # Wave 2 can't retrace 100% of Wave 1
            'wave4_no_overlap': True,      # Wave 4 can't overlap Wave 1
            'wave3_not_shortest': True     # Wave 3 can't be the shortest
        }
    
    def analyze(self, symbol: str, timeframe: str = '4h') -> Dict:
        """
        Perform Elliott Wave analysis on a symbol
        
        Args:
            symbol: Coin symbol (BTC, ETH, etc.)
            timeframe: Candle interval (1h, 4h, 1d)
        
        Returns:
            Complete Elliott Wave analysis
        """
        # Add USDT suffix if needed
        if not symbol.endswith('USDT'):
            symbol = symbol.upper() + 'USDT'
        
        result = {
            'symbol': symbol.replace('USDT', ''),
            'timeframe': timeframe,
            'analyzed_at': datetime.now().isoformat(),
            'current_price': 0,
            'wave_count': None,
            'current_wave': None,
            'wave_structure': [],
            'fibonacci_levels': {},
            'trend': 'unknown',
            'confidence': 0,
            'signals': [],
            'recommendation': '',
            'error': None
        }
        
        try:
            # Fetch price data
            klines = self._fetch_klines(symbol, timeframe, limit=200)
            if not klines or len(klines) < 50:
                result['error'] = "Insufficient price data"
                return result
            
            # Extract OHLC data
            closes = np.array([float(k[4]) for k in klines])
            highs = np.array([float(k[2]) for k in klines])
            lows = np.array([float(k[3]) for k in klines])
            
            result['current_price'] = float(closes[-1])
            
            # Find swing points (pivots)
            swing_highs, swing_lows = self._find_swing_points(highs, lows, window=5)
            
            # Identify waves
            waves = self._identify_waves(closes, highs, lows, swing_highs, swing_lows)
            
            if waves:
                result['wave_structure'] = waves
                result['current_wave'] = self._determine_current_wave(waves, closes[-1])
                result['wave_count'] = len(waves)
                
                # Calculate Fibonacci levels
                result['fibonacci_levels'] = self._calculate_fib_levels(waves, closes[-1])
                
                # Determine trend
                result['trend'] = self._determine_trend(waves)
                
                # Generate signals
                result['signals'] = self._generate_signals(waves, closes[-1], result['fibonacci_levels'])
                
                # Calculate confidence
                result['confidence'] = self._calculate_confidence(waves)
                
                # Generate recommendation
                result['recommendation'] = self._generate_recommendation(result)
            else:
                result['wave_count'] = 0
                result['signals'].append("No clear wave pattern identified")
                result['recommendation'] = "⚡ No clear Elliott Wave pattern. Wait for structure to develop."
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> List:
        """Fetch candlestick data from Binance"""
        try:
            url = f"{self.binance_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Klines fetch: {e}")
        return []
    
    def _find_swing_points(self, highs: np.ndarray, lows: np.ndarray, window: int = 5) -> Tuple[List, List]:
        """
        Find swing highs and swing lows (pivot points)
        """
        swing_highs = []
        swing_lows = []
        
        for i in range(window, len(highs) - window):
            # Swing high: highest point in window
            if highs[i] == max(highs[i - window:i + window + 1]):
                swing_highs.append({
                    'index': i,
                    'price': float(highs[i]),
                    'type': 'high'
                })
            
            # Swing low: lowest point in window
            if lows[i] == min(lows[i - window:i + window + 1]):
                swing_lows.append({
                    'index': i,
                    'price': float(lows[i]),
                    'type': 'low'
                })
        
        return swing_highs, swing_lows
    
    def _identify_waves(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                        swing_highs: List, swing_lows: List) -> List[Dict]:
        """
        Identify Elliott Waves from swing points
        """
        waves = []
        
        # Combine and sort pivots by index
        all_pivots = sorted(swing_highs + swing_lows, key=lambda x: x['index'])
        
        if len(all_pivots) < 5:
            return waves
        
        # Take recent pivots for analysis
        recent_pivots = all_pivots[-12:]
        
        # Determine if we're in uptrend or downtrend
        first_pivot = recent_pivots[0]
        last_pivot = recent_pivots[-1]
        is_uptrend = last_pivot['price'] > first_pivot['price']
        
        # Label waves based on alternating pivots
        wave_number = 1
        wave_labels = ['1', '2', '3', '4', '5', 'A', 'B', 'C']
        
        for i, pivot in enumerate(recent_pivots[-8:]):  # Focus on last 8 pivots
            if i >= len(wave_labels):
                break
            
            wave_type = 'impulse' if wave_labels[i].isdigit() else 'corrective'
            direction = 'up' if (wave_labels[i] in ['1', '3', '5', 'B']) else 'down'
            
            # Flip direction for downtrend
            if not is_uptrend:
                direction = 'down' if direction == 'up' else 'up'
            
            waves.append({
                'label': wave_labels[i],
                'type': wave_type,
                'direction': direction,
                'start_price': pivot['price'] if i == 0 else waves[-1]['end_price'],
                'end_price': pivot['price'],
                'index': pivot['index'],
                'pivot_type': pivot['type']
            })
        
        # Validate wave structure against rules
        waves = self._validate_waves(waves)
        
        return waves
    
    def _validate_waves(self, waves: List[Dict]) -> List[Dict]:
        """
        Validate waves against Elliott Wave rules
        """
        if len(waves) < 3:
            return waves
        
        valid_waves = []
        
        for wave in waves:
            # Add validation scores
            wave['valid'] = True
            wave['violations'] = []
            valid_waves.append(wave)
        
        # Check Wave 2 rule: Can't retrace 100% of Wave 1
        wave1 = next((w for w in valid_waves if w['label'] == '1'), None)
        wave2 = next((w for w in valid_waves if w['label'] == '2'), None)
        
        if wave1 and wave2:
            wave1_move = abs(wave1['end_price'] - wave1['start_price'])
            wave2_retrace = abs(wave2['end_price'] - wave2['start_price'])
            if wave1_move > 0:
                retrace_pct = wave2_retrace / wave1_move
                if retrace_pct >= 1.0:
                    wave2['valid'] = False
                    wave2['violations'].append("Wave 2 retraced 100%+ of Wave 1")
        
        # Check Wave 3 rule: Can't be shortest
        impulse_waves = [w for w in valid_waves if w['label'] in ['1', '3', '5']]
        if len(impulse_waves) >= 3:
            wave_lengths = [(w['label'], abs(w['end_price'] - w['start_price'])) for w in impulse_waves]
            wave3_length = next((l for label, l in wave_lengths if label == '3'), 0)
            min_length = min(l for _, l in wave_lengths)
            
            if wave3_length == min_length and wave3_length > 0:
                wave3 = next((w for w in valid_waves if w['label'] == '3'), None)
                if wave3:
                    wave3['violations'].append("Wave 3 is shortest (rule violation)")
        
        return valid_waves
    
    def _determine_current_wave(self, waves: List[Dict], current_price: float) -> Dict:
        """
        Determine which wave we're currently in based on last completed wave
        Returns the NEXT expected wave (what we're entering now)
        """
        if not waves:
            return {'label': '1', 'position': 'start', 'phase': 'impulse', 'message': 'No clear pattern yet'}
        
        last_wave = waves[-1]
        last_label = last_wave['label']
        
        # Map: last completed wave -> current wave we're in
        wave_progression = {
            '1': ('2', 'impulse', '📉 Wave 2 correction. Wait for support.'),
            '2': ('3', 'impulse', '📈 Wave 3 starting - strongest wave! BUY.'),
            '3': ('4', 'impulse', '📉 Wave 4 pullback. Accumulation zone.'),
            '4': ('5', 'impulse', '📈 Wave 5 final push. Take profits soon.'),
            '5': ('A', 'corrective', '� Wave A correction starting. Be cautious.'),
            'A': ('B', 'corrective', '📈 Wave B bounce. Don\'t chase - it\'s a trap.'),
            'B': ('C', 'corrective', '🔻 Wave C final leg down. Best buy at bottom.'),
            'C': ('1', 'new_cycle', '🚀 New cycle! Wave 1 impulse starting.')
        }
        
        if last_label in wave_progression:
            next_wave, phase, message = wave_progression[last_label]
            return {
                'label': next_wave,
                'position': f'after_{last_label}',
                'phase': phase,
                'message': message
            }
        
        return {'label': '1', 'position': 'uncertain', 'phase': 'developing', 'message': 'Pattern developing...'}
    
    def _calculate_fib_levels(self, waves: List[Dict], current_price: float, highs: np.ndarray = None, lows: np.ndarray = None) -> Dict:
        """
        Calculate Fibonacci retracement and extension levels based on recent swing range
        """
        fib_levels = {}
        
        if len(waves) < 2:
            return fib_levels
        
        # Find the major swing high and low from the wave structure
        wave_prices = [w['end_price'] for w in waves]
        swing_high = max(wave_prices)
        swing_low = min(wave_prices)
        move_range = swing_high - swing_low
        
        if move_range <= 0:
            return fib_levels
        
        # Determine if currently bullish (price near highs) or bearish (price near lows)
        is_bullish = current_price > (swing_low + move_range * 0.5)
        
        # Retracement levels - from swing high down (for pullback buys)
        fib_levels['retracement'] = {
            '23.6%': swing_high - (move_range * 0.236),
            '38.2%': swing_high - (move_range * 0.382),
            '50.0%': swing_high - (move_range * 0.500),
            '61.8%': swing_high - (move_range * 0.618),
            '78.6%': swing_high - (move_range * 0.786),
        }
        
        # Extension levels - above swing high (for targets)
        fib_levels['extension'] = {
            '127.2%': swing_low + (move_range * 1.272),
            '161.8%': swing_low + (move_range * 1.618),
            '200.0%': swing_low + (move_range * 2.000),
            '261.8%': swing_low + (move_range * 2.618),
        }
        
        # Add swing info for context
        fib_levels['swing_high'] = round(swing_high, 2)
        fib_levels['swing_low'] = round(swing_low, 2)
        
        # Find nearest level to current price
        all_levels = {**fib_levels.get('retracement', {}), **fib_levels.get('extension', {})}
        if all_levels:
            nearest = min(all_levels.items(), key=lambda x: abs(x[1] - current_price))
            fib_levels['nearest_level'] = {
                'name': nearest[0],
                'price': round(nearest[1], 4),
                'distance_pct': round((nearest[1] - current_price) / current_price * 100, 2)
            }
        
        return fib_levels
    
    def _determine_trend(self, waves: List[Dict]) -> str:
        """Determine overall trend from wave structure"""
        if not waves:
            return 'unknown'
        
        # Check if in impulse or correction
        last_wave = waves[-1]
        
        if last_wave['label'].isdigit():
            if last_wave['direction'] == 'up':
                return 'bullish_impulse'
            else:
                return 'bearish_impulse'
        else:
            if last_wave['direction'] == 'down':
                return 'bullish_correction'  # Correcting up move
            else:
                return 'bearish_correction'  # Correcting down move
    
    def _generate_signals(self, waves: List[Dict], current_price: float, fib_levels: Dict) -> List[str]:
        """Generate trading signals based on wave analysis"""
        signals = []
        
        if not waves:
            return signals
        
        last_wave = waves[-1]
        
        # Signal based on wave position
        if last_wave['label'] == '2':
            signals.append("🟢 Wave 2 complete - Potential Wave 3 entry (strongest wave)")
        elif last_wave['label'] == '4':
            signals.append("🟢 Wave 4 complete - Potential Wave 5 entry (final push)")
        elif last_wave['label'] == '5':
            signals.append("🔴 Wave 5 complete - Take profits, correction incoming")
        elif last_wave['label'] == 'A':
            signals.append("🟡 Wave A complete - Watch for Wave B bounce (don't chase)")
        elif last_wave['label'] == 'C':
            signals.append("🟢 Wave C complete - Major buy opportunity if cycle continues")
        
        # Fibonacci signals
        if fib_levels.get('nearest_level'):
            nearest = fib_levels['nearest_level']
            if abs(nearest['distance_pct']) < 2:
                signals.append(f"📊 Price at {nearest['name']} Fib level (${nearest['price']:,.2f})")
        
        return signals
    
    def _calculate_confidence(self, waves: List[Dict]) -> int:
        """Calculate confidence score for wave count"""
        if not waves:
            return 0
        
        confidence = 50  # Base confidence
        
        # More waves = more confidence
        confidence += min(len(waves) * 5, 25)
        
        # Check for rule validations
        valid_waves = [w for w in waves if w.get('valid', True)]
        validity_ratio = len(valid_waves) / len(waves) if waves else 0
        confidence += int(validity_ratio * 20)
        
        # Fibonacci alignment bonus
        # (In real implementation, check if pivots align with fib levels)
        confidence += 5
        
        return min(confidence, 100)
    
    def _generate_recommendation(self, result: Dict) -> str:
        """Generate actionable recommendation"""
        current_wave = result.get('current_wave', {})
        trend = result.get('trend', 'unknown')
        confidence = result.get('confidence', 0)
        
        phase = current_wave.get('phase', 'unknown')
        message = current_wave.get('message', '')
        
        if confidence < 40:
            return "⚠️ Wave structure unclear. Wait for better pattern formation."
        
        if 'bullish' in trend:
            if phase == 'impulse':
                return f"🚀 BULLISH - {message}"
            elif phase == 'corrective':
                return f"📉 BULLISH CORRECTION - {message}"
            else:
                return f"🟢 BULLISH BIAS - Watch for continuation"
        elif 'bearish' in trend:
            if phase == 'impulse':
                return f"🔻 BEARISH - {message}"
            elif phase == 'corrective':
                return f"📈 BEARISH CORRECTION - {message}"
            else:
                return f"🔴 BEARISH BIAS - Watch for continuation"
        
        return "⚡ Pattern developing - Monitor for clear wave structure"


# Global instance
ELLIOTT_ANALYZER = None

def get_elliott_analyzer():
    global ELLIOTT_ANALYZER
    if not ELLIOTT_ANALYZER:
        ELLIOTT_ANALYZER = ElliottWaveAnalyzer()
    return ELLIOTT_ANALYZER


if __name__ == "__main__":
    print("Testing Elliott Wave Analyzer...")
    analyzer = ElliottWaveAnalyzer()
    
    # Test with BTC
    result = analyzer.analyze("BTC", "4h")
    
    print(f"\n{'='*60}")
    print(f"Symbol: ${result['symbol']}")
    print(f"Timeframe: {result['timeframe']}")
    print(f"Current Price: ${result['current_price']:,.2f}")
    print(f"Trend: {result['trend']}")
    print(f"Wave Count: {result['wave_count']}")
    print(f"Confidence: {result['confidence']}%")
    
    if result['current_wave']:
        print(f"\nCurrent Wave: {result['current_wave'].get('label', 'N/A')}")
    
    print(f"\nSignals:")
    for s in result.get('signals', []):
        print(f"  {s}")
    
    print(f"\nRecommendation: {result['recommendation']}")
    
    if result.get('fibonacci_levels', {}).get('retracement'):
        print(f"\nFibonacci Retracement Levels:")
        for level, price in result['fibonacci_levels']['retracement'].items():
            print(f"  {level}: ${price:,.2f}")
