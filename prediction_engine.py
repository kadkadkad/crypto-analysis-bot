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
        Calculates a 0-100 score for a given asset.
        """
        symbol = coin_data.get('Coin', '').upper()
        display_symbol = coin_data.get('DisplaySymbol', symbol)
        
        scores = {}
        
        # 1. TVL Score (30%)
        tvl_score = 0
        # Find if this coin has a protocol anomaly
        anomaly = next((a for a in tvl_anomalies if a.get('symbol', '').upper() == symbol or a.get('token', '').upper() == symbol), None)
        if anomaly:
            inflow = anomaly.get('change_1d', 0)
            if inflow > 25: tvl_score = 100
            elif inflow > 10: tvl_score = 80
            elif inflow > 5: tvl_score = 50
            else: tvl_score = 30
        scores['tvl'] = tvl_score

        # 2. Futures Score (25%)
        futures_score = 0
        oi_chg = float(coin_data.get('OI Change %', 0) or 0)
        funding = float(coin_data.get('Funding Rate', '0%').replace('%', '') or 0)
        
        if oi_chg > 10 and funding < 0.02: futures_score += 60 # Bullish OI build
        elif oi_chg > 5: futures_score += 30
        
        if funding < 0: futures_score += 40 # Short squeeze potential
        elif funding < 0.01: futures_score += 20
        scores['futures'] = min(futures_score, 100)

        # 3. Structure Score (20%)
        struct_score = 0
        advice = coin_data.get('Advice', '').upper()
        if "BULLISH" in advice or "ACCUMULATION" in advice: struct_score += 50
        if "MSB" in advice or "BREAKOUT" in advice: struct_score += 50
        scores['structure'] = struct_score

        # 4. Whale Score (15%)
        whale_score = 0
        net_accum = float(coin_data.get('NetAccum_raw', 0) or 0)
        if net_accum > 100000: whale_score = 100
        elif net_accum > 50000: whale_score = 70
        elif net_accum > 0: whale_score = 30
        scores['whales'] = whale_score

        # 5. Technical Score (10%)
        tech_score = 0
        rsi = float(coin_data.get('RSI', 50) or 50)
        vol_ratio = float(coin_data.get('Volume Ratio', 1) or 1)
        squeeze = coin_data.get('BB_Squeeze', '')

        if 30 < rsi < 55: tech_score += 40 # Room to run
        if vol_ratio > 2: tech_score += 40 # Volume surge
        if "Squeeze" in squeeze: tech_score += 20
        scores['technicals'] = tech_score

        # Weighted Total
        total_score = sum(scores[k] * self.weights[k] for k in self.weights)
        
        # Confluence Analysis (Actionable Intel)
        confluences = []
        if scores['tvl'] >= 80: confluences.append("Strong TVL Inflow")
        if oi_chg > 10: confluences.append("Aggressive OI Build")
        if net_accum > 100000: confluences.append("Whale Accumulation")
        if "Squeeze" in squeeze: confluences.append("Bollinger Squeeze")
        
        return {
            'symbol': symbol,
            'display': display_symbol,
            'score': round(total_score, 1),
            'confluences': confluences,
            'breakdown': scores,
            'price': coin_data.get('Price_Display', 'N/A')
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
