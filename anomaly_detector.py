
import numpy as np
import statistics
from typing import Dict, List, Optional, Tuple

class AnomalyDetector:
    """
    Advanced Anomaly Detection Engine using Statistical Analysis (Z-Score, Sigma).
    Monitors 67+ metrics for significant deviations indicating market shifts.
    """

    def __init__(self):
        # Historical data buffer for calculating moving averages and std dev
        # Format: { 'BTCUSDT': { 'RSI': [50, 52, ...], 'Volume': [...] } }
        self.history = {}
        self.window_size = 24  # Keep last 24 data points (e.g., 24 hours if hourly)
        
        # Metric Definitions & Thresholds (Sigma Multipliers)
        # Higher Sigma = Less sensitive, only major anomalies
        self.metric_config = {
            # --- Whale & Liquidity ---
            'NetAccum_raw': {'sigma': 2.5, 'type': 'leading', 'desc': 'Whale Accumulation'},
            'Whale Ranking': {'sigma': 2.0, 'type': 'leading', 'desc': 'Whale Rank Change'},
            'Manipulation Score': {'sigma': 2.0, 'type': 'risk', 'desc': 'Manipulation Risk'},
            'Liq Heat Map': {'sigma': 2.5, 'type': 'support', 'desc': 'Liquidity Clusters'},
            
            # --- Technicals ---
            'RSI': {'sigma': 2.5, 'type': 'momentum', 'desc': 'RSI Momentum'},
            'MACD': {'sigma': 2.5, 'type': 'trend', 'desc': 'MACD Trend'},
            'ADX': {'sigma': 2.0, 'type': 'trend', 'desc': 'ADX Trend Strength'},
            'MFI': {'sigma': 2.5, 'type': 'flow', 'desc': 'Money Flow Index'},
            'Bollinger Squeeze': {'sigma': 1.5, 'type': 'volatility', 'desc': 'BB Squeeze'},
            'Volume Ratio': {'sigma': 3.0, 'type': 'volume', 'desc': 'Volume Anomaly'},
            
            # --- Price & Volatility ---
            'Price Change': {'sigma': 3.0, 'type': 'price', 'desc': 'Price Shock'},
            'Volatility': {'sigma': 2.0, 'type': 'volatility', 'desc': 'Volatility Spike'},
            'Spread': {'sigma': 3.0, 'type': 'risk', 'desc': 'Liquidity Crunch (Spread)'},
            
            # --- Derivatives ---
            'Open Interest': {'sigma': 2.5, 'type': 'leverage', 'desc': 'OI Surge'},
            'Funding Rate': {'sigma': 3.0, 'type': 'leverage', 'desc': 'Funding Rate Shock'},
            'Long/Short Ratio': {'sigma': 2.5, 'type': 'sentiment', 'desc': 'L/S Ratio Shift'},
            'Taker Rate': {'sigma': 2.0, 'type': 'sentiment', 'desc': 'Taker Buy/Sell imbalance'},
            
            # --- Correlations ---
            'BTC Correlation': {'sigma': 2.0, 'type': 'correlation', 'desc': 'Decoupling from BTC'},
            
            # --- Scores ---
            'Smart Score': {'sigma': 2.0, 'type': 'composite', 'desc': 'Smart Score Shift'},
            'Composite Score': {'sigma': 2.0, 'type': 'composite', 'desc': 'Composite Score Shift'},
        }

    def update_history(self, symbol: str, metrics: Dict):
        """Update historical buffer for a coin"""
        if symbol not in self.history:
            self.history[symbol] = {}
        
        # [DEBUG] Trace incoming data once per cycle (for BTC)
        if symbol == 'BTCUSDT':
            print(f"[DEBUG-HISTORY] Updating history for {symbol}. Metric count: {len(metrics)}")
            
        for key, value in metrics.items():
            # Only track numeric values defined in config
            if key not in self.metric_config:
                continue
                
            try:
                # Basic normalization for history
                val = float(value)
                if key not in self.history[symbol]:
                    self.history[symbol][key] = []
                
                self.history[symbol][key].append(val)
                
                # Keep window fixed
                if len(self.history[symbol][key]) > self.window_size:
                    self.history[symbol][key].pop(0)
            except Exception as e:
                # [DEBUG] errors
                if symbol == 'BTCUSDT': print(f"[DEBUG-ERROR] History update failed for {key}: {e}")
                pass

    def check_anomalies(self, symbol: str, current_metrics: Dict, market_context: Dict = None) -> List[Dict]:
        """
        Generic Outlier Detection Engine with Market Context Awareness.
        Finds metrics behaving abnormally and cross-references with Market Risk & News.
        """
        anomalies = []
        if symbol not in self.history: return anomalies
        
        # --- CONTEXT INTEGRATION (The "Risk Shield") ---
        # Default values if no context provided
        risk_level = 'low'
        sentiment_score = 0.0 # Neutral
        is_high_volatility = False
        
        if market_context:
            risk_level = market_context.get('risk_level', 'low')
            sentiment_score = market_context.get('sentiment_score', 0.0)
            is_high_volatility = market_context.get('is_high_volatility_day', False)
        
        # Dynamic Threshold Adjustment
        # Logic: If market is risky (e.g. Fed Day), we need STRONGER anomalies to trigger a signal.
        # "Don't bother me with small stuff when the house is on fire."
        base_threshold_multiplier = 1.0
        if risk_level == 'high':
            base_threshold_multiplier = 1.4 # Requires 40% stronger signal
        elif risk_level == 'medium':
            base_threshold_multiplier = 1.2
            
        # 1. Detect Outliers (Velocity & Acceleration)
        candidates = []
        for key, config in self.metric_config.items():
            if key not in current_metrics or key not in self.history[symbol]: continue
            
            history = self.history[symbol][key]
            if len(history) < 2: continue
            
            curr = float(current_metrics[key])
            prev = history[-1]
            
            # Velocity calculation
            velocity = (curr - prev)
            
            changes = [history[i] - history[i-1] for i in range(1, len(history))]
            if not changes: changes = [0]
            
            vel_mean = statistics.mean(changes)
            vel_std = statistics.stdev(changes) if len(changes) > 1 else 0.0001
            if vel_std == 0: vel_std = 0.0001
            
            z_velocity = (velocity - vel_mean) / vel_std
            
            # Apply Dynamic Threshold
            config_sigma = config['sigma'] * base_threshold_multiplier
            
            # Detection
            if abs(z_velocity) > config_sigma:
                # Determine "Related" metrics for verification
                verification_msg, v_score = self._verify_with_related(symbol, config['type'], z_velocity)
                
                # --- NEWS SENTIMENT FILTER ---
                # check for "News Conflict"
                # If Anomaly is Bullish (z > 0) BUT News is Bearish (score < -0.3) -> WARNING
                news_warning = ""
                if z_velocity > 0 and sentiment_score < -0.3:
                    news_warning = " ⚠️ NEWS MISMATCH (Bearish News)"
                    v_score -= 2 # Penalty
                elif z_velocity < 0 and sentiment_score > 0.3:
                    news_warning = " ⚠️ NEWS MISMATCH (Bullish News)"
                    v_score -= 2 # Penalty
                    
                # Final filtering based on Verification Score & Context
                # If High Risk Day, we strictly require POSITIVE verification
                if risk_level == 'high' and v_score <= 0:
                    continue # Discard unverified signals on risky days
                
                final_desc = f"{verification_msg}{news_warning}"
                
                candidates.append({
                    'metric': key,
                    'desc': config['desc'],
                    'value': curr,
                    'z_score': round(z_velocity, 2),
                    'verification': final_desc,
                    'timestamp': 'Just Now'
                })

        # 2. Filter Candidates
        return candidates

    def _verify_with_related(self, symbol: str, m_type: str, primary_z: float) -> Tuple[str, int]:
        """
        [ADVANCED] Cross-Category Verification (Global Context).
        Returns: (Message, Score)
        """
        score = 0
        total_checks = 0

        # ... (Verification matrix same as before)
        verification_matrix = {
            'momentum': ['volume', 'leading', 'leverage'],
            'price': ['volume', 'leading', 'momentum'],
            'volume': ['momentum', 'leading'],
            'leading': ['volume', 'momentum', 'leverage'], 
            'leverage': ['momentum', 'price']
        }
        categories = {
            'momentum': ['RSI', 'MFI'],
            'volume': ['Volume Ratio', 'NetAccum_raw'],
            'leading': ['NetAccum_raw', 'Whale Ranking'],
            'leverage': ['Open Interest', 'Funding Rate'],
            'price': ['Price Change']
        }

        target_categories = verification_matrix.get(m_type, ['volume', 'leading'])

        for cat in target_categories:
            metrics_in_cat = categories.get(cat, [])
            for metric in metrics_in_cat:
                if metric not in self.history[symbol]: continue
                
                history = self.history[symbol][metric]
                if len(history) < 2: continue
                change = history[-1] - history[-2]
                
                aligned = (primary_z > 0 and change > 0) or (primary_z < 0 and change < 0)
                
                if aligned:
                    score += 1
                else:
                    score -= 1 
                
                total_checks += 1

        # Final Verdict Logic
        msg = "⚪ Neutral Context"
        if score > 0:
            msg = f"✅ Confirmed by Market Structure (Score: +{score})"
        elif score < 0:
            if m_type == 'price' and 'leading' in target_categories:
                 msg = f"💎 WHALE DIVERGENCE (Price fakeout detected)"
                 score += 5 # Boost score for this special setup
            elif m_type == 'leading' and 'price' in target_categories:
                 msg = f"💎 HIDDEN ACCUMULATION (Price lagging)"
                 score += 5
            else:
                msg = f"⚠️ Unsupported Move (Fakeout Risk) (Score: {score})"
        
        return msg, score

    def analyze_market_snapshot(self, all_coins_data: List[Dict], market_context: Dict = None) -> List[Dict]:
        """
        Batch process all coins and return global anomalies.
        """
        global_anomalies = []
        for coin in all_coins_data:
            symbol = coin.get('Coin')
            if not symbol: continue
            
            # 1. Update history
            self.update_history(symbol, coin)
            
            # 2. Check anomalies with Context
            anomalies = self.check_anomalies(symbol, coin, market_context)
            
            if anomalies:
                for a in anomalies:
                    a['coin'] = symbol
                    global_anomalies.append(a)
        
        # Sort by severity (Z-Score)
        global_anomalies.sort(key=lambda x: abs(x['z_score']), reverse=True)
        return global_anomalies

