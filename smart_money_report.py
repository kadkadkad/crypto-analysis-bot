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
    - Whale Net Accumulation (Buy/Sell Pressure)
    - Open Interest Momentum (Futures Positioning)
    - Funding Rate Dynamics (Market Sentiment)
    
    Returns formatted report string for web dashboard.
    """
    
    if not all_results:
        return "⚠️ No analysis data available yet. Please wait for the first analysis cycle."
    
    # Import helpers locally to avoid circular imports
    from utils import extract_numeric, format_money
    from main import get_turkey_time
    
    timestamp = get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""🧠 <b>SMART MONEY INDICATORS – {timestamp}</b>

<b>📊 Key Metrics:</b>
• <b>Net Accum</b>: Taker Buy - Sell (+ = Whales Buying)
• <b>OI Change</b>: Futures positioning momentum
• <b>Funding Rate</b>: Long/Short sentiment

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🔥 TOP SMART MONEY SIGNALS (Confluence)</b>

"""
    
    # Combine all 3 indicators for confluence scoring
    smart_money_signals = []
    
    for coin in all_results[:50]:
        try:
            symbol = coin.get("Coin", "Unknown")
            price = extract_numeric(coin.get("Price", 0))
            price_str = format_money(price)
            change_24h = extract_numeric(coin.get("24h Change Raw", coin.get("24h Change", 0)))
            
            # Extract metrics - USE CORRECT KEYS
            net_accum_1h = extract_numeric(coin.get("NetAccum_raw", 0))  # 1H net accum
            net_accum_12h = extract_numeric(coin.get("net_accum_12h", net_accum_1h))  # fallback to 1h
            oi_value = extract_numeric(coin.get("Open Interest", 0))
            oi_change = extract_numeric(coin.get("OI Change %", 0))
            funding_rate = extract_numeric(coin.get("Funding Rate", 0))
            
            # Calculate confluence score (0-100)
            score = 0
            signals_detected = []
            
            # Whale Accumulation Signal (Max 35 points) - LOWERED THRESHOLD
            if abs(net_accum_1h) > 1_000_000:  # 1M threshold
                if net_accum_1h > 0:
                    score += min((net_accum_1h / 5_000_000) * 35, 35)
                    signals_detected.append("🐋 WHALE BUYING")
                else:
                    score -= min((abs(net_accum_1h) / 5_000_000) * 35, 35)
                    signals_detected.append("💸 WHALE SELLING")
            
            # OI Momentum Signal (Max 35 points) - LOWERED THRESHOLD
            if abs(oi_change) > 1:  # 1% threshold
                oi_score = min((abs(oi_change) / 20) * 35, 35)
                if oi_change > 0 and change_24h > 0:
                    score += oi_score
                    signals_detected.append("📈 OI + PRICE UP")
                elif oi_change > 0 and change_24h < 0:
                    score -= oi_score
                    signals_detected.append("📉 OI UP, PRICE DOWN")
                elif oi_change < 0 and abs(change_24h) > 1:
                    signals_detected.append("⚠️ OI DECLINING")
            
            # Funding Rate Signal (Max 30 points)
            if abs(funding_rate) > 0.00005:
                funding_score = min((abs(funding_rate) / 0.0005) * 30, 30)
                if funding_rate < -0.0001:  # Negative = squeeze potential
                    score += funding_score
                    signals_detected.append("🔥 FUNDING SQUEEZE")
                elif funding_rate > 0.0003:  # Extreme positive = overheat
                    score -= funding_score
                    signals_detected.append("🥵 FUNDING OVERHEAT")
            
            # LOWERED: Include coins with at least 1 signal and score > 5
            if abs(score) > 5 and len(signals_detected) >= 1:
                smart_money_signals.append({
                    "symbol": symbol,
                    "price": price_str,
                    "change_24h": change_24h,
                    "score": score,
                    "signals": signals_detected,
                    "net_accum": net_accum_1h,
                    "oi_change": oi_change,
                    "funding": funding_rate
                })
        
        except Exception as e:
            continue
    
    # Sort by absolute score (strongest signals first)
    smart_money_signals.sort(key=lambda x: abs(x["score"]), reverse=True)
    
    # Display Top 15 Signals
    for i, signal in enumerate(smart_money_signals[:15], 1):
        direction = "🟢 BULLISH" if signal["score"] > 0 else "🔴 BEARISH"
        confidence = min(abs(signal["score"]), 100)
        
        # Build signal breakdown
        signals_str = " + ".join(signal["signals"])
        
        report += f"""<b>{i}. ${signal['symbol'].replace('USDT','')}</b> — {direction} ({confidence:.0f}%)
   📊 {signals_str}
   • Net: {format_money(signal['net_accum'])} | OI: {signal['oi_change']:+.1f}% | FR: {signal['funding']*100:.3f}%

"""
    
    if not smart_money_signals:
        report += "✨ No strong smart money confluence detected.\n\n"
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 DETAILED BREAKDOWN - TOP 15</b>

"""
    
    # Section 1: Net Accumulation Leaders - FIXED KEY
    report += "<b>🐋 WHALE ACTIVITY (1H Net Accumulation)</b>\n"
    whale_sorted = sorted(
        [(c, extract_numeric(c.get("NetAccum_raw", 0))) for c in all_results[:50]],
        key=lambda x: x[1],
        reverse=True
    )[:15]
    
    for i, (coin, net_accum) in enumerate(whale_sorted, 1):
        if abs(net_accum) > 100_000:  # LOWERED to 100K
            symbol = coin.get("Coin", "").replace("USDT", "")
            direction = "🟢 BUY" if net_accum > 0 else "🔴 SELL"
            report += f"{i}. ${symbol}: {direction} {format_money(net_accum)}\n"
    
    report += "\n"
    
    # Section 2: Open Interest Momentum - LOWERED THRESHOLD
    report += "<b>📊 OI MOMENTUM (Futures)</b>\n"
    oi_sorted = sorted(
        [(c, extract_numeric(c.get("OI Change %", 0))) for c in all_results[:50]],
        key=lambda x: abs(x[1]),
        reverse=True
    )[:15]
    
    for i, (coin, oi_change) in enumerate(oi_sorted, 1):
        if abs(oi_change) > 0.5:  # LOWERED to 0.5%
            symbol = coin.get("Coin", "").replace("USDT", "")
            direction = "🟢 +" if oi_change > 0 else "🔴 "
            report += f"{i}. ${symbol}: {direction}{oi_change:.2f}%\n"
    
    report += "\n"
    
    # Section 3: Funding Rate Extremes
    report += "<b>⚡ FUNDING RATE</b>\n"
    funding_sorted = sorted(
        [(c, extract_numeric(c.get("Funding Rate", 0))) for c in all_results[:50]],
        key=lambda x: x[1]  # Most negative first
    )[:10]
    
    for i, (coin, funding) in enumerate(funding_sorted, 1):
        if abs(funding) > 0.00001:  # LOWERED threshold
            symbol = coin.get("Coin", "").replace("USDT", "")
            if funding < -0.0001:
                status = "🔥 LONG SQUEEZE"
            elif funding > 0.0002:
                status = "🥵 SHORT SQUEEZE"
            else:
                status = "⚖️ Neutral"
            report += f"{i}. ${symbol}: {status} ({funding*100:.4f}%)\n"
    
    report += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💡 QUICK GUIDE</b>
• 🐋 + 📈 OI + 🔥 FR = <b>Strong Long Setup</b>
• 💸 + 📉 OI + 🥵 FR = <b>Strong Short Setup</b>

<i>⚡ Powered by Radar Ultra AI</i>
"""
    
    return report


# Export function for integration
__all__ = ['generate_smart_money_indicators_report']
