"""
Pump Prediction Engine - Master Confluence Scorer
Combines TVL, OI, Funding, Whale Accumulation, and Technicals into a single Pump Probability Score.
"""
import datetime
import pandas as pd
import numpy as np

class PumpPredictionEngine:
    def __init__(self, tvl_tracker):
        self.tvl_tracker = tvl_tracker
        self.weights = {
            'tvl': 0.30,         # TVL Flow (DeFiLlama)
            'futures': 0.25,     # OI/Funding (Binance)
            'structure': 0.20,   # Antigravity PA (MSB, PO3)
            'whales': 0.15,      # Net Accumulation
            'technicals': 0.10    # RSI, Vol Ratio, Squeeze
        }

    def calculate_pump_score(self, coin_data, tvl_anomalies):
        """
        Calculates a 0-100 score for a given asset. Handles both lowercase and dashboard-style keys.
        """
        raw_symbol = coin_data.get('Coin', coin_data.get('symbol', '')).upper()
        # Ensure symbol is clean for indexing (no $ or USDT)
        clean_symbol = raw_symbol.replace("USDT", "").replace("$", "")
        # Display symbol with $ prefix
        display_symbol = "$" + clean_symbol
        
        scores = {}
        
        # Helper to extract numeric values safely from various key styles
        def get_val(keys, default=0):
            for k in keys:
                if k in coin_data:
                    val = coin_data[k]
                    if isinstance(val, str):
                        try:
                            # Handle percent strings like "0.05%"
                            return float(val.replace('%', '').replace('$', '').replace('x', ''))
                        except: continue
                    return float(val or 0)
            return default

        # 1. TVL Score (30%)
        tvl_score = 0
        anomaly = next((a for a in tvl_anomalies if a.get('symbol', '').upper() == clean_symbol or a.get('token', '').upper() == clean_symbol), None)
        if anomaly:
            inflow = anomaly.get('change_1d', 0)
            if inflow > 25: tvl_score = 100
            elif inflow > 10: tvl_score = 80
            elif inflow > 5: tvl_score = 50
            else: tvl_score = 30
        scores['tvl'] = tvl_score

        # 2. Futures Score (25%)
        futures_score = 0
        oi_chg = get_val(['OI Change %', 'oi_change_pct', 'oi_change'])
        funding = get_val(['Funding Rate', 'funding_rate'])
        
        if oi_chg > 15: futures_score += 70
        elif oi_chg > 5: futures_score += 40
        if funding < 0: futures_score += 30 
        scores['futures'] = min(futures_score, 100)

        # 3. Structure Score (20%)
        struct_score = 0
        advice = str(coin_data.get('Advice', coin_data.get('advice', ''))).upper()
        if "REVERSAL" in advice or "MSB" in advice: struct_score += 70
        elif "BULLISH" in advice: struct_score += 40
        scores['structure'] = min(struct_score, 100)

        # 4. Whale Score (15%)
        whale_score = 0
        net_accum = get_val(['NetAccum_raw', 'net_accumulation', 'net_accum'])
        if net_accum > 50000: whale_score = 100
        elif net_accum > 10000: whale_score = 60
        scores['whales'] = whale_score

        # 5. Technical Score (10%)
        tech_score = 0
        rsi = get_val(['RSI', 'rsi'], 50)
        vol_ratio = get_val(['Volume Ratio', 'volume_ratio'], 1)
        
        if 50 < rsi < 60: tech_score += 60 
        elif 30 < rsi < 50: tech_score += 30 
        if vol_ratio > 1.2: tech_score += 40
        scores['technicals'] = min(tech_score, 100)

        # Weighted Total
        total_score = sum(scores[k] * self.weights[k] for k in self.weights)
        
        # Confluence Analysis
        confluences = []
        if oi_chg > 10: confluences.append("🚀 Fresh OI Spike (1H)")
        if 50 < rsi < 55: confluences.append("📈 Bullish RSI Pivot")
        if net_accum > 20000: confluences.append("🐋 Whale Front-run")
        if scores['tvl'] >= 50: confluences.append("💧 TVL Lead")
        
        return {
            'symbol': raw_symbol,
            'display': display_symbol,
            'score': round(total_score, 1),
            'confluences': confluences,
            'breakdown': scores,
            'price': coin_data.get('Price_Display', coin_data.get('price', 'N/A'))
        }

    def generate_prediction_report(self, all_results, tvl_anomalies):
        """
        Generates the final report for the top 10 potential pumps.
        """
        predictions = []
        for coin in all_results:
            res = self.calculate_pump_score(coin, tvl_anomalies)
            predictions.append(res)
            
        # Sort by score
        predictions.sort(key=lambda x: x['score'], reverse=True)
        top_picks = predictions[:10]
        
        report = f"🎯 <b>MASTER PUMP PREDICTIONS (AI Confluence)</b>\n"
        report += f"<i>Time: {datetime.datetime.now().strftime('%H:%M')} | Confidence Weighted</i>\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, p in enumerate(top_picks, 1):
            emoji = "🔥" if p['score'] >= 80 else "📈" if p['score'] >= 60 else "👀"
            report += f"{i}. {emoji} <b>{p['display']}</b> - <b>Score: {p['score']}%</b>\n"
            report += f"   Price: {p['price']}\n"
            if p['confluences']:
                report += f"   ⚡ <i>Signals: {', '.join(p['confluences'])}</i>\n"
            
            # Show a mini progress bar for the score
            bar_len = int(p['score'] / 10)
            report += f"   [{'■' * bar_len}{'□' * (10 - bar_len)}]\n\n"
            
        report += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "<i>Scoring: TVL(30%), OI(25%), Structures(20%), Whales(15%), Techs(10%)</i>\n"
        report += "<i>⚡ Strategy: High score + Whale Accum = Best RR</i>\n"
        
        return report

# Global instance for easy import
PREDICTION_ENGINE = None # Will be initialized in main.py with tvl_tracker
