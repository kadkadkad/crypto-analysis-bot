import pandas as pd
import numpy as np
import requests
from datetime import datetime
import binance_client

def detect_stophunt_pattern(klines, threshold=3.0):
    """
    Detects Stop-Hunt patterns
    """
    if not klines or len(klines) < 10:
        return {"detected": False}

    try:
        df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume",
                                          "close_time", "quote_volume", "trades", "taker_buy_base",
                                          "taker_buy_quote", "ignore"])

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])

        if len(df) < 10:
            return {"detected": False}

        recent_prices = df["close"].tail(10).values
        min_idx = np.argmin(recent_prices)

        if min_idx == 0:
            return {"detected": False}

        max_drop_pct = (recent_prices[0] - recent_prices[min_idx]) / recent_prices[0] * 100 if recent_prices[0] > 0 else 0

        if max_drop_pct < threshold:
            return {"detected": False}

        if min_idx < len(recent_prices) - 1:
            recovery_pct = (recent_prices[-1] - recent_prices[min_idx]) / recent_prices[min_idx] * 100 if recent_prices[min_idx] > 0 else 0

            if recovery_pct > threshold / 2:
                if len(df) > 10:
                    drop_volume = df["volume"].iloc[-(10 - min_idx):-1].mean()
                    avg_volume = df["volume"].iloc[:-10].mean() if len(df) > 20 else df["volume"].mean()
                    volume_spike = drop_volume > avg_volume * 1.5
                else:
                    volume_spike = False

                return {
                    "detected": True,
                    "drop_percent": max_drop_pct,
                    "recovery_percent": recovery_pct,
                    "volume_spike": volume_spike,
                    "confidence": min(100, max(max_drop_pct * recovery_pct / 10, 50))
                }
        return {"detected": False}
    except Exception as e:
        print(f"[ERROR] Stop hunt detection failed: {e}")
        return {"detected": False}

def detect_price_compression(klines, window=20):
    """Detects price compression (low volatility)"""
    if not klines or len(klines) < window * 2:
        return {"compression": False}
    try:
        df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume",
                                          "close_time", "quote_volume", "trades", "taker_buy_base",
                                          "taker_buy_quote", "ignore"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"])

        if len(df) < window * 2:
            return {"compression": False}

        atr_series = []
        for i in range(1, len(df)):
            high = df["high"].iloc[i]
            low = df["low"].iloc[i]
            prev_close = df["close"].iloc[i - 1]
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
            atr_series.append(true_range)

        window_size = min(window, len(atr_series))
        smoothed_atr = []
        for i in range(len(atr_series) - window_size + 1):
            smoothed_atr.append(sum(atr_series[i:i + window_size]) / window_size)

        if len(smoothed_atr) < 2:
            return {"compression": False}

        half_size = max(1, len(smoothed_atr) // 2)
        recent_atr = smoothed_atr[-half_size:]
        older_atr = smoothed_atr[-len(smoothed_atr):-half_size]

        if not older_atr or not recent_atr:
            return {"compression": False}

        avg_recent_atr = sum(recent_atr) / len(recent_atr)
        avg_older_atr = sum(older_atr) / len(older_atr)
        compression_ratio = avg_recent_atr / avg_older_atr if avg_older_atr > 0 else 1

        return {
            "compression": compression_ratio < 0.7,
            "compression_ratio": compression_ratio,
            "avg_recent_atr": avg_recent_atr,
            "avg_older_atr": avg_older_atr
        }
    except Exception as e:
        print(f"[ERROR] Compression detection failed: {e}")
        return {"compression": False}

def evaluate_vix_risk():
    try:
        # Using constant values as per original code due to rate limits
        vix_value = 18.45
        vix_change = 2.35
        impact = "high" if vix_value > 25 else "medium" if vix_value > 15 else "low"
        description = (
            f"VIX index is at {vix_value} with a {'+' if vix_change > 0 else ''}{vix_change}% change. "
            f"{'This high value indicates increased market volatility.' if vix_value > 25 else 'This medium value indicates normal market fluctuations.' if vix_value > 15 else 'This low value indicates calm market conditions.'}"
        )
        risk_score = min(vix_value * 2, 100)
        return {
            "factor": "VIX Volatility",
            "impact": impact,
            "description": description,
            "risk_score": risk_score
        }
    except Exception as e:
        print(f"[ERROR] VIX risk evaluation failed: {e}")
        return None

import asyncio
import aiohttp

async def analyze_market_risks_async(symbols):
    """
    Analyzes risk for multiple coins asynchronously
    """
    print(f"[INFO] Analyzing risk for {len(symbols)} coins (Async)...")
    all_data = {}
    risk_scores = []
    
    # Create a session and fetch all data in parallel
    async with aiohttp.ClientSession() as session:
        tasks = [binance_client.fetch_binance_data_async(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        for symbol, data in zip(symbols, results):
            if data:
                all_data[symbol] = data

    btc_data = all_data.get("BTCUSDT")
    eth_data = all_data.get("ETHUSDT")
    
    market_sentiment = {}
    if btc_data:
        market_sentiment["btc_price"] = btc_data["price"]
        market_sentiment["btc_change"] = btc_data["price_change_percent"]
    if eth_data:
        market_sentiment["eth_price"] = eth_data["price"]
        market_sentiment["eth_change"] = eth_data["price_change_percent"]

    try:
        # Ideally fetch this async too, but keeping minimal changes for external APIs for now
        fg_response = requests.get("https://api.alternative.me/fng/", timeout=5)
        if fg_response.status_code == 200:
            fg_data = fg_response.json()
            market_sentiment["fear_greed_index"] = int(fg_data["data"][0]["value"])
    except:
        market_sentiment["fear_greed_index"] = 50

    for symbol, data in all_data.items():
        components = {}
        price = data["price"]
        atr = data.get("atr", (data["high"] - data["low"]) / 2)
        
        components["volatility_risk"] = min((atr / price * 100) * 5, 100) if price > 0 else 0
        
        rsi = data.get("rsi", 50)
        components["rsi_risk"] = abs(50 - rsi) / 50 * 100
        
        macd = data.get("macd", 0)
        components["momentum_risk"] = min(abs(macd) * 60, 60)
        
        volume_ratio = data.get("volume_ratio", 1)
        components["volume_risk"] = min((1 / max(volume_ratio, 0.2)) * 50, 50)
        
        funding_rate = data.get("funding_rate", 0)
        components["funding_risk"] = min(abs(funding_rate) * 200, 80)
        
        ls_ratio = data.get("long_short_ratio", 1.0)
        components["ls_imbalance"] = abs(1 - ls_ratio) * 100

        weights = {
            "volatility_risk": 0.15, "rsi_risk": 0.15, "momentum_risk": 0.15,
            "volume_risk": 0.15, "funding_risk": 0.20, "ls_imbalance": 0.20
        }
        
        total_risk = sum(components[k] * weights[k] for k in components)
        
        if total_risk >= 75: risk_level = "very high"
        elif total_risk >= 50: risk_level = "high"
        elif total_risk >= 30: risk_level = "medium"
        else: risk_level = "low"

        sorted_risks = sorted(components.items(), key=lambda x: x[1], reverse=True)[:3]
        top_risks = {k: v for k, v in sorted_risks}

        risk_scores.append({
            "symbol": symbol,
            "risk_score": round(total_risk, 1),
            "risk_level": risk_level,
            "components": components,
            "top_risks": top_risks,
            "price": price,
            "price_change": data["price_change_percent"]
        })

    risk_scores = sorted(risk_scores, key=lambda x: x["risk_score"], reverse=True)
    
    return {
        "market_sentiment": market_sentiment,
        "risk_scores": risk_scores,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def analyze_market_risks(symbols):
    """
    Analyzes risk for multiple coins (Synchronous Wrapper)
    """
    return asyncio.run(analyze_market_risks_async(symbols))


def generate_market_risk_report(risk_data):
    """
    Generates readable report from risk analysis data
    """
    market = risk_data["market_sentiment"]
    scores = risk_data["risk_scores"]
    timestamp = risk_data["timestamp"]
    
    if not scores:
        return "⚠️ No risk data available."

    avg_risk = sum(s["risk_score"] for s in scores) / len(scores)
    
    high_risk = len([s for s in scores if s["risk_level"] in ["high", "very high"]])
    medium_risk = len([s for s in scores if s["risk_level"] == "medium"])
    low_risk = len([s for s in scores if s["risk_level"] == "low"])

    report = f"⚠️ <b>Real-Time Risk Analysis Report – {timestamp}</b>\n\n"
    report += "<b>📊 Global Market Outlook:</b>\n"
    
    if "btc_price" in market:
        btc_arrow = "🟢" if market["btc_change"] > 0 else "🔴"
        report += f"• BTC: ${market['btc_price']} ({btc_arrow} {market['btc_change']:+.2f}%)\n"
    if "eth_price" in market:
        eth_arrow = "🟢" if market["eth_change"] > 0 else "🔴"
        report += f"• ETH: ${market['eth_price']} ({eth_arrow} {market['eth_change']:+.2f}%)\n"
    if "fear_greed_index" in market:
        fg = market["fear_greed_index"]
        fg_state = "Extreme Fear" if fg <= 25 else "Fear" if fg <= 40 else "Neutral" if fg <= 60 else "Greed" if fg <= 75 else "Extreme Greed"
        report += f"• Fear & Greed Index: {fg}/100 ({fg_state})\n"

    report += f"\n<b>📈 Risk Distribution:</b>\n"
    report += f"• Average Risk Score: {avg_risk:.1f}/100\n"
    report += f"• High Risk Coins: {high_risk}\n"
    report += f"• Medium Risk Coins: {medium_risk}\n"
    report += f"• Low Risk Coins: {low_risk}\n"

    report += "\n<b>🚨 Top 5 High Risk Coins:</b>\n"
    for i, score in enumerate(scores[:5], 1):
        symbol = score["symbol"]
        risk_score = score["risk_score"]
        risk_level = score["risk_level"]
        top_risks = score["top_risks"]

        risk_emoji = "🔴" if risk_level == "very high" else "🟠" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
        report += f"• {risk_emoji} <b>{symbol}</b>: Risk Score {risk_score}/100\n"

        for risk_type, risk_value in top_risks.items():
            readable_name = risk_type.replace("_risk", "").replace("_", " ").title()
            readable_name = readable_name.replace("Ls Imbalance", "Long/Short Imbalance").replace("Rsi", "RSI")
            report += f"  - {readable_name} Risk: {risk_value:.1f}/100\n"

    report += "\n<b>💡 Risk Assessment:</b>\n"
    if avg_risk >= 60:
        report += "The market is generally trading at high risk levels. It is recommended to be cautious and reduce position sizes."
    elif avg_risk >= 40:
        report += "There is a medium level of risk in the market. It is recommended to be selective and open positions gradually."
    else:
        report += "The market is generally at low risk levels. Suitable conditions for trading may exist."

    return report

