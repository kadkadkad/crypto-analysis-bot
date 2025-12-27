"""
SMART MONEY INDICATORS REPORT GENERATOR
========================================
Whale Activity + Open Interest + Funding Rate Analysis

This module provides deep analysis of three critical metrics:
1. Net Accumulation (Whale Buy/Sell Pressure)
2. Open Interest (Futures Market Positioning)  
3. Funding Rate (Long/Short Sentiment)
"""

import requests
import time
from datetime import datetime, timedelta


def generate_smart_money_indicators_report(all_results):
    """
    🧠 SMART MONEY INDICATORS - Deep Analysis Report
    
    Analyzes the three most critical smart money metrics:
    - Whale Net Accumulation (12H Buy/Sell Pressure)
    - Open Interest Momentum (Futures Positioning)
    - Funding Rate Dynamics (Market Sentiment)
    
    Returns formatted report string for web dashboard.
    """
    
    if not all_results:
        return "⚠️ No analysis data available yet. Please wait for the first analysis cycle."
    
    # Import helpers locally to avoid circular imports
    from utils import extract_numeric, format_money
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""🧠 <b>SMART MONEY INDICATORS - Deep Analysis – {timestamp}</b>

<b>📊 Methodology:</b>
This report tracks the three most powerful indicators used by institutional traders and market makers to predict large moves:

<b>1️⃣ Net Accumulation (Whale Activity)</b>
   • Measures buy vs sell pressure from large wallets
   • Calculated from Taker Buy Volume vs Total Volume
   • Positive = Accumulation (Bullish), Negative = Distribution (Bearish)

<b>2️⃣ Open Interest (OI)</b>
   • Total value of open futures contracts
   • Rising OI + Rising Price = Strong Bullish Trend
   • Rising OI + Falling Price = Strong Bearish Trend
   • Falling OI = Trend Exhaustion

<b>3️⃣ Funding Rate</b>
   • Periodic payments between longs and shorts
   • Positive = Longs pay Shorts (Bullish Sentiment)
   • Negative = Shorts pay Longs (Bearish Sentiment)
   • Extreme values signal potential reversals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🔥 TOP SMART MONEY SIGNALS (Combined Analysis)</b>

"""
    
    # Combine all 3 indicators for confluence scoring
    smart_money_signals = []
    
    for coin in all_results[:50]:
        try:
            symbol = coin.get("Coin", "Unknown")
            price = extract_numeric(coin.get("Price", 0))
            price_str = format_money(price)
            change_24h = extract_numeric(coin.get("24h Change", 0))
            
            # Extract metrics
            net_accum_12h = extract_numeric(coin.get("Net Accum 12h", 0))
            oi_value = extract_numeric(coin.get("Open Interest", 0))
            oi_change = extract_numeric(coin.get("OI Change %", 0))
            funding_rate = extract_numeric(coin.get("Funding Rate", 0))
            
            # Calculate confluence score (0-100)
            score = 0
            signals_detected = []
            
            # Whale Accumulation Signal (Max 35 points)
            if abs(net_accum_12h) > 3_000_000:
                if net_accum_12h > 0:
                    score += min((net_accum_12h / 10_000_000) * 35, 35)
                    signals_detected.append("🐋 WHALE BUYING")
                else:
                    score -= min((abs(net_accum_12h) / 10_000_000) * 35, 35)
                    signals_detected.append("💸 WHALE SELLING")
            
            # OI Momentum Signal (Max 35 points)
            if abs(oi_change) > 5:
                oi_score = min((abs(oi_change) / 50) * 35, 35)
                if oi_change > 0 and change_24h > 0:
                    score += oi_score
                    signals_detected.append("📈 OI + PRICE UP")
                elif oi_change > 0 and change_24h < 0:
                    score -= oi_score
                    signals_detected.append("📉 OI UP, PRICE DOWN")
                elif oi_change < 0 and abs(change_24h) > 2:
                    signals_detected.append("⚠️ OI DECLINING")
            
            # Funding Rate Signal (Max 30 points)
            if abs(funding_rate) > 0.0001:
                funding_score = min((abs(funding_rate) / 0.001) * 30, 30)
                if funding_rate < -0.0002:  # Extreme negative = squeeze potential
                    score += funding_score
                    signals_detected.append("🔥 FUNDING SQUEEZE")
                elif funding_rate > 0.0005:  # Extreme positive = overheat
                    score -= funding_score
                    signals_detected.append("🥵 FUNDING OVERHEAT")
            
            # Only include coins with significant signals
            if abs(score) > 15 and len(signals_detected) >= 2:
                smart_money_signals.append({
                    "symbol": symbol,
                    "price": price_str,
                    "change_24h": change_24h,
                    "score": score,
                    "signals": signals_detected,
                    "net_accum": net_accum_12h,
                    "oi_change": oi_change,
                    "funding": funding_rate
                })
        
        except Exception as e:
            continue
    
    # Sort by absolute score (strongest signals first)
    smart_money_signals.sort(key=lambda x: abs(x["score"]), reverse=True)
    
    # Display Top 20 Signals
    for i, signal in enumerate(smart_money_signals[:20], 1):
        direction = "🟢 BULLISH" if signal["score"] > 0 else "🔴 BEARISH"
        confidence = min(abs(signal["score"]), 100)
        conf_bars = int(confidence / 10)
        conf_visual = "█" * conf_bars + "░" * (10 - conf_bars)
        
        # Build signal breakdown
        signals_str = " | ".join(signal["signals"])
        
        report += f"""<b>{i}. {signal['symbol']}</b> — {direction}
   💵 Price: {signal['price']} ({signal['change_24h']:+.2f}%)
   🎯 Confluence Score: {confidence:.0f}% [{conf_visual}]
   🔎 Signals: {signals_str}
   
   📊 Raw Data:
   • Net Accum (12H): ${format_money(signal['net_accum'])}
   • OI Change: {signal['oi_change']:+.2f}%
   • Funding Rate: {signal['funding']*100:.4f}%

"""
    
    if not smart_money_signals:
        report += "✨ No strong smart money confluence detected at the moment.\n"
        report += "All metrics are within normal ranges.\n\n"
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 DETAILED BREAKDOWN - TOP 30 BY INDIVIDUAL METRICS</b>

"""
    
    # Section 1: Net Accumulation Leaders
    report += "<b>🐋 WHALE ACCUMULATION LEADERS (12H Period)</b>\n\n"
    whale_sorted = sorted(
        [(c, extract_numeric(c.get("Net Accum 12h", 0))) for c in all_results[:50]],
        key=lambda x: x[1],
        reverse=True
    )[:15]
    
    for i, (coin, net_accum) in enumerate(whale_sorted, 1):
        if abs(net_accum) > 500_000:  # Filter noise
            symbol = coin.get("Coin", "").replace("USDT", "")
            direction = "🟢 ACCUMULATION" if net_accum > 0 else "🔴 DISTRIBUTION"
            report += f"{i}. ${symbol}: {direction} ${format_money(abs(net_accum))}\n"
    
    report += "\n"
    
    # Section 2: Open Interest Momentum
    report += "<b>📊 OPEN INTEREST MOMENTUM LEADERS</b>\n\n"
    oi_sorted = sorted(
        [(c, extract_numeric(c.get("OI Change %", 0))) for c in all_results[:50]],
        key=lambda x: abs(x[1]),
        reverse=True
    )[:15]
    
    for i, (coin, oi_change) in enumerate(oi_sorted, 1):
        if abs(oi_change) > 3:
            symbol = coin.get("Coin", "").replace("USDT", "")
            direction = "🟢 INCREASING" if oi_change > 0 else "🔴 DECREASING"
            report += f"{i}. ${symbol}: {direction} {oi_change:+.2f}%\n"
    
    report += "\n"
    
    # Section 3: Funding Rate Extremes
    report += "<b>⚡ FUNDING RATE EXTREMES (Potential Squeezes)</b>\n\n"
    funding_sorted = sorted(
        [(c, extract_numeric(c.get("Funding Rate", 0))) for c in all_results[:50]],
        key=lambda x: x[1]  # Most negative first
    )[:15]
    
    for i, (coin, funding) in enumerate(funding_sorted, 1):
        if abs(funding) > 0.00005:
            symbol = coin.get("Coin", "").replace("USDT", "")
            if funding < -0.0001:
                status = "🔥 LONG SQUEEZE RISK"
            elif funding > 0.0003:
                status = "🥵 SHORT SQUEEZE RISK"
            else:
                status = "⚖️ NEUTRAL"
            report += f"{i}. ${symbol}: {status} ({funding*100:.4f}%)\n"
    
    report += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💡 INTERPRETATION GUIDE</b>

<b>Strong Bullish Confluence:</b>
• Whale Accumulation (+) + OI Rising + Funding Negative
• Interpretation: Smart money accumulating before a squeeze

<b>Strong Bearish Confluence:</b>
• Whale Distribution (-) + OI Rising + Funding Positive
• Interpretation: Smart money exiting before a dump

<b>Reversal Signals:</b>
• Extreme Funding (>0.05% or <-0.05%) = Potential reversal
• OI Declining + Price Volatile = Trend exhaustion

<i>⚡ Data updated every 5-10 minutes • Powered by Radar Ultra AI</i>
"""
    
    return report


# Export function for integration
__all__ = ['generate_smart_money_indicators_report']
