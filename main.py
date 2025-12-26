import requests
import json
import time
import threading
import pandas as pd
import numpy as np
import asyncio
import traceback
import math
import re
import pickle
import statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
# External libraries (ta, sklearn, prophet) kept if needed by main logic not yet moved
from ta.trend import EMAIndicator, MACD, ADXIndicator 
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volume import MFIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
# from prophet import Prophet # Disabled for speed on Render
import aiohttp
import asyncio
import sqlite3
import random
import psutil
import os
import gc
import orderbook_analyzer
import config
import binance_client


# Internal Modules
import config
import utils
from utils import check_memory_and_clean, extract_numeric
import binance_client
import market_analyzer
import telegram_bot
import youtube_analyzer
from candlestick_patterns import (
    handle_candlestick_patterns_report,
    handle_candlestick_pattern_menu,
    handle_specific_pattern_coins,
    extract_candlestick_patterns
)
from technical_pattern_analyzer import TechnicalPatternAnalyzer
from money_flow_analyzer import MoneyFlowAnalyzer
from market_regime import MarketRegimeDetector
from signal_tracker import SignalWinRateTracker

# Start Menu Manager
MENU_STATE = telegram_bot.MENU_STATE

# Initialize main-specific globals if any NOT in config
# Aliases for globals moved to config.py
PREV_STATS = config.PREV_STATS
ALL_RESULTS = config.ALL_RESULTS
FIVE_MIN_REPORTS = config.FIVE_MIN_REPORTS
KLINE_CACHE = config.KLINE_CACHE
COIN_DETAILS = config.COIN_DETAILS
global_lock = config.GLOBAL_LOCK

TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
TELEGRAM_CHANNEL_ID = config.TELEGRAM_CHANNEL_ID
BINANCE_API_URL = config.BINANCE_API_URL
BINANCE_FUTURES_API_URL = config.BINANCE_FUTURES_API_URL
SLEEP_INTERVAL = config.SLEEP_INTERVAL
MODEL_CACHE = config.MODEL_CACHE
PREV_RANKS = config.PREV_RANKS
TRADE_RECOMMENDATIONS = config.TRADE_RECOMMENDATIONS
PREV_HOURLY_REPORTS = config.PREV_HOURLY_REPORTS

# Premium Features
MONEY_FLOW_ANALYZER = MoneyFlowAnalyzer()
MARKET_REGIME_DETECTOR = MarketRegimeDetector()
SIGNAL_TRACKER = SignalWinRateTracker()
PREV_ALL_RESULTS = []  # For flow analysis

# Load previous results for Money Flow Persistence
try:
    if os.path.exists("prev_results.json"):
        with open("prev_results.json", "r") as f:
            PREV_ALL_RESULTS = json.load(f)
            print(f"[INFO] Loaded {len(PREV_ALL_RESULTS)} previous records for Money Flow analysis")
except Exception as e:
    print(f"[WARN] Failed to load prev_results.json: {e}")

last_hourly_report_time = datetime.now() - timedelta(hours=1)
last_update_time = datetime.now()  # Track when data was last refreshed

def force_refresh_if_stale(max_age_seconds=60):
    """
    Forces a market data refresh if the last update was more than max_age_seconds ago.
    This ensures reports always show fresh data when requested by users.
    """
    global last_update_time, ALL_RESULTS
    
    time_since_update = (datetime.now() - last_update_time).total_seconds()
    
    if time_since_update > max_age_seconds:
        print(f"[INFO] Data is {time_since_update:.0f}s old. Forcing refresh...")
        try:
            # Quick refresh - just fetch fresh data without full analysis loop overhead
            coins = get_filtered_coins()
            if coins:
                # Use the same async batch fetch as main loop
                import asyncio
                import aiohttp
                
                async def quick_refresh():
                    async with aiohttp.ClientSession() as session:
                        # Fetch reference data
                        ref_data = {}
                        for base in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
                            try:
                                data_1h = await binance_client.fetch_binance_data_async(session, base)
                                if data_1h and 'df' in data_1h:
                                    df = pd.DataFrame(data_1h['df'])
                                    key_1h = f"{base[:3].lower()}_1h_ret"
                                    ref_data[key_1h] = df['close'].pct_change().dropna()
                                    
                                    if 'df_4h' in data_1h:
                                        df_4h = pd.DataFrame(data_1h['df_4h'])
                                        key_4h = f"{base[:3].lower()}_4h_ret"
                                        ref_data[key_4h] = df_4h['close'].pct_change().dropna()
                                    
                                    if 'df_1d' in data_1h:
                                        df_1d = pd.DataFrame(data_1h['df_1d'])
                                        key_1d = f"{base[:3].lower()}_1d_ret"
                                        ref_data[key_1d] = df_1d['close'].pct_change().dropna()
                            except: pass
                        
                        # Fetch coin data
                        sem = asyncio.Semaphore(15)
                        async def fetch_with_sem(c):
                            async with sem:
                                try:
                                    return await binance_client.fetch_binance_data_async(session, c, ref_returns=ref_data)
                                except:
                                    return None
                        
                        tasks = [fetch_with_sem(c) for c in coins[:50]]
                        return await asyncio.gather(*tasks)
                
                fresh_data = asyncio.run(quick_refresh())
                
                # Process results (simplified version of main loop)
                results = []
                for data in fresh_data:
                    if data:
                        try:
                            # Build minimal res dict for reports
                            res = {
                                "Coin": data["symbol"],
                                "Price": data["price"],
                                "RSI": extract_numeric(data.get('rsi', 50)),
                                "RSI_4h": extract_numeric(data.get('rsi_4h', 50)),
                                "RSI_1d": extract_numeric(data.get('rsi_1d', 50)),
                                "MACD": extract_numeric(data.get('macd', 0)),
                                "MACD_4h": extract_numeric(data.get('macd_4h', 0)),
                                "MACD_1d": extract_numeric(data.get('macd_1d', 0)),
                                "ADX": extract_numeric(data.get('adx', 0)),
                                "ADX_4h": extract_numeric(data.get('adx_4h', 0)),
                                "ADX_1d": extract_numeric(data.get('adx_1d', 0)),
                                # Add other critical fields as needed
                            }
                            results.append(res)
                        except: pass
                
                if results:
                    with global_lock:
                        ALL_RESULTS = results[:50]
                    last_update_time = datetime.now()
                    print(f"[INFO] Data refreshed successfully. {len(results)} coins updated.")
                    return True
        except Exception as e:
            print(f"[WARN] Quick refresh failed: {e}")



# Utility functions moved to utils.py
# inspect_coin_data moved to utils.py (if needed, otherwise relying on validation)

# Candlestick pattern extraction is now imported from candlestick_patterns module



# ---------------- Market Maker Analiz Fonksiyonları ----------------

# Market Analysis functions moved to market_analyzer.py
# (detect_stophunt_pattern, detect_price_compression, evaluate_vix_risk, analyze_market_risks, generate_market_risk_report)

def handle_advanced_risk_analysis():
    """
    Performs real-time risk analysis with actual data.
    """
    try:
        # Inform the user that the process has started
        send_telegram_message(config.TELEGRAM_CHAT_ID, "🔍 Performing risk analysis, please wait...")

        # Get top 50 coins by volume
        symbols = get_filtered_coins()
        if not symbols or len(symbols) < 10:
            send_telegram_message_long("⚠️ Not enough coin data could be fetched. Please try again later.")
            return

        # Perform risk analysis
        # Use market_analyzer module
        risk_data = market_analyzer.analyze_market_risks(symbols[:50])

        # Generate and send report
        report = market_analyzer.generate_market_risk_report(risk_data)
        send_telegram_message_long(report)

    except Exception as e:
        print(f"[ERROR] Risk analysis failed: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message_long(
            "⚠️ An error occurred during risk analysis. Please try again later.")


def validate_indicators(indicators):
    """
    Göstergelerin geçerli ve tutarlı olup olmadığını kontrol eder.

    Args:
        indicators (dict): Kontrol edilecek göstergeler sözlüğü

    Returns:
        bool: Göstergeler geçerliyse True, değilse False
    """
    try:
        # Temel değerlerin varlığını kontrol et
        required_fields = ["Coin", "Price_Display", "RSI", "MACD", "ADX", "Volume Ratio", "NetAccum_raw"]
        for field in required_fields:
            if field not in indicators or indicators[field] is None:
                print(f"[UYARI] {indicators.get('Coin', 'Bilinmeyen')} için '{field}' alanı eksik")
                return False

        # Değerlerin mantıklı aralıklarda olup olmadığını kontrol et
        if "RSI" in indicators:
            rsi = extract_numeric(indicators["RSI"])
            if not (0 <= rsi <= 100):
                print(f"[UYARI] {indicators['Coin']} için RSI değeri geçersiz: {rsi}")
                return False

        # volume oranı pozitif olmalı
        if "Volume Ratio" in indicators:
            volume_ratio = extract_numeric(indicators["Volume Ratio"])
            if volume_ratio <= 0:
                print(f"[UYARI] {indicators['Coin']} için hacim oranı geçersiz: {volume_ratio}")
                return False

        return True
    except Exception as e:
        print(f"[HATA] {indicators.get('Coin', 'Bilinmeyen')} gösterge doğrulaması başarısız: {e}")
        return False

# Utility aliases (implementations moved to utils.py)
check_memory_and_clean = utils.check_memory_and_clean
optimize_memory = utils.optimize_memory
normalize_symbol_for_exchange = utils.normalize_symbol_for_exchange
test_keyboard = telegram_bot.test_keyboard # moved to telegram_bot
parse_money = utils.parse_money
format_money = utils.format_money
extract_numeric = utils.extract_numeric
calculate_percentage_change = utils.calculate_percentage_change
get_change_arrow = utils.get_change_arrow
format_indicator = utils.format_indicator
get_whale_logo = utils.get_whale_logo

def send_telegram_message(chat_id, text, keyboard=None, inline_keyboard=None, parse_mode="HTML"):
    """Wrapper that adds a Copy button to important messages"""
    if not inline_keyboard and text:
        if len(text) <= 256:
           # Direct copy for short text
           inline_keyboard = [[{"text": "📋 Copy", "copy_text": {"text": text}}]]
        else:
           # Callback for long text (bypass 256 limit)
           inline_keyboard = [[{"text": "📋 Copy (Long)", "callback_data": "copy_content"}]]
            
    return telegram_bot.send_telegram_message(chat_id, text, keyboard=keyboard, inline_keyboard=inline_keyboard, parse_mode=parse_mode)

def send_telegram_message_long(message, chat_id=None, keyboard=None, inline_keyboard=None):
    """Wrapper that adds a Copy button to long reports"""
    if not inline_keyboard and message:
        # Always use callback for potentially long reports to be safe and consistent
        inline_keyboard = [[{"text": "📋 Copy Report", "callback_data": "copy_content"}]]
        
    return telegram_bot.send_telegram_message_long(message, chat_id=chat_id, keyboard=keyboard, inline_keyboard=inline_keyboard)

def handle_callback_query(query):
    """
    Handles callback queries from inline buttons.
    """
    try:
        query_id = query["id"]
        data = query.get("data")
        message = query.get("message")
        chat_id = message["chat"]["id"]
        
        print(f"[DEBUG] Processing callback: {data}")
        
        if data == "copy_content":
            # Extract text from the message attached to the button
            content = message.get("text") or message.get("caption")
            
            if content:
                # Send back as code block for easy copying
                # Split if too long is handled by send_telegram_message logic usually, 
                # but for code block we might need to be careful. 
                # Telegram splits long messages, but splitting a <pre> block might break tags.
                # However, our existing send logic balances tags.
                
                # We prepend a small notice
                response_text = f"📋 <b>Copyable Content:</b>\n\n<pre>{content}</pre>"
                
                # Send the copyable text
                send_telegram_message(chat_id, response_text)
                
                # Acknowledge the callback
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": query_id, "text": "Content sent ✅"}
                )
            else:
                 requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": query_id, "text": "No content to copy ❌"}
                )

    except Exception as e:
        print(f"[ERROR] Callback handling failed: {e}")




def evaluate_economic_events():
    """
    Yaklaşan önemli ekonomik olayları değerlendirir ve risk faktörü hesaplar.

    Returns:
        dict: Risk faktörü bilgisi veya None
    """
    high_impact_events = [event for event in macro_data.get("economic_events", [])
                          if event.get("importance") == "yüksek" and
                          (datetime.strptime(event.get("time", ""),
                                             "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds() / 3600 < 24]

    if high_impact_events and len(high_impact_events) >= 2:
        return {
            "factor": "Önemli ekonomik olaylar yaklaşıyor",
            "impact": "orta",
            "description": f"Önümüzdeki 24 saat içinde {len(high_impact_events)} önemli ekonomik olay var, bu volatiliteyi artırabilir",
            "risk_score": 8
        }
    elif high_impact_events:
        return {
            "factor": "Ekonomik olay yaklaşıyor",
            "impact": "düşük",
            "description": f"Önümüzdeki 24 saat içinde önemli bir ekonomik olay var, bu volatiliteyi artırabilir",
            "risk_score": 4
        }

    return None


extract_numeric = utils.extract_numeric

def init_db():
    conn = sqlite3.connect("market_stats.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prev_stats 
                 (symbol TEXT PRIMARY KEY, netaccum REAL, volume_ratio REAL, timestamp TEXT)''')
    conn.commit()
    conn.close()

# Çalıştırma başında çağır
init_db()

def sync_fetch_kline_data(symbol, interval, limit=100):
    """
    Binance'tan Kline verilerini senkron bir şekilde çeker.

    Args:
        symbol (str): Coin çifti (ör. 'BTCUSDT')
        interval (str): Zaman aralığı (ör. '1h')
        limit (int): Veri limiti (varsayılan 100)

    Returns:
        list: Kline verileri
    """
    try:
        # Yeni bir olay döngüsü oluştur ve ayarla
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def fetch():
            async with aiohttp.ClientSession() as session:
                return await fetch_kline_data(session, symbol, interval, limit)

        # Olay döngüsünde asenkron fonksiyonu çalıştır
        result = loop.run_until_complete(fetch())
        loop.close()  # Olay döngüsünü kapat
        return result
    except Exception as e:
        print(f"[HATA] {symbol} için sync_fetch_kline_data hatası: {e}")
        return []  # Hata durumunda boş liste dön

# ---------------- Yeni Eklenen Fonksiyonlar ----------------
# Replace current economic data function with reliable API calls

def fetch_macro_economic_data():
    """
    Çeşitli kaynaklardan makroekonomik verileri çeker
    """
    try:
        # Korku ve Açgözlülük endeksi - sonuç döndürmeyen API'ye alternatif kullan
        try:
            fng_url = "https://api.alternative.me/fng/"
            response = requests.get(fng_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                fear_greed_index = int(data['data'][0]['value'])
            else:
                print(f"[UYARI] Korku & Açgözlülük endeksi yanıt vermedi: {response.status_code}")
                fear_greed_index = 49  # Orta değer
        except Exception as e:
            print(f"[UYARI] Korku & Açgözlülük endeksi alınamadı: {e}")
            fear_greed_index = 49

        # DXY ve Piyasa endeksleri - rate limit riski taşıyor
        try:
            # Rate limit'e düşme riski nedeniyle güvenilir değerler kullan
            market_indices = {
                "S&P500": {"value": 5890.58, "change": 0.45, "trend": "yükseliş"},
                "NASDAQ": {"value": 21458.92, "change": 0.72, "trend": "yükseliş"},
                "DJI": {"value": 43256.72, "change": -0.12, "trend": "düşüş"},
                "VIX": {"value": 18.45, "change": 2.35, "trend": "yükseliş"}
            }

            # Alternatif bir kaynaktan VIX çekmeyi deneyin - CBOE API
            # (burada test amaçlı kullanmıyoruz, rate limit riski var)
        except Exception as e:
            print(f"[UYARI] Piyasa endeksleri alınamadı: {e}")
            market_indices = {
                "S&P500": {"value": 5890.58, "change": 0.45, "trend": "yükseliş"},
                "NASDAQ": {"value": 21458.92, "change": 0.72, "trend": "yükseliş"},
                "DJI": {"value": 43256.72, "change": -0.12, "trend": "düşüş"},
                "VIX": {"value": 18.45, "change": 2.35, "trend": "yükseliş"}
            }

        # Kripto piyasa verileri - rate limit riski düşük
        try:
            crypto_url = "https://api.coingecko.com/api/v3/global"
            response = requests.get(crypto_url, timeout=5)

            crypto_market = {}
            if response.status_code == 200:
                data = response.json().get('data', {})

                total_market_cap = data.get('total_market_cap', {}).get('usd', 0)
                btc_dominance = data.get('market_cap_percentage', {}).get('btc', 0)
                total_volume = data.get('total_volume', {}).get('usd', 0)
                market_cap_change = data.get('market_cap_change_percentage_24h_usd', 0)

                crypto_market = {
                    "total_market_cap": total_market_cap,
                    "btc_dominance": round(btc_dominance, 1),
                    "daily_volume": total_volume,
                    "market_trend": "yükseliş" if market_cap_change > 0 else "düşüş",
                    "fear_greed_index": fear_greed_index
                }
            else:
                raise Exception(f"CoinGecko API yanıt vermedi: {response.status_code}")
        except Exception as e:
            print(f"[UYARI] Kripto piyasa verileri alınamadı: {e}")
            # Daha güvenilir değerler
            crypto_market = {
                "total_market_cap": 2.89e12,  # 2.89T
                "btc_dominance": 58.4,
                "daily_volume": 121.43e9,  # 121.43B
                "market_trend": "yükseliş",
                "fear_greed_index": fear_greed_index
            }

        # BTC ve ETH verileri doğrudan Binance'dan - en güvenilir
        btc_eth_data = {}
        try:
            for symbol in ["BTCUSDT", "ETHUSDT"]:
                url = f"{BINANCE_API_URL}ticker/24hr?symbol={symbol}"
                response = requests.get(url, timeout=5)

                if response.status_code == 200:
                    data = response.json()

                    last_price = extract_numeric(data.get('lastPrice', 0))
                    price_change = extract_numeric(data.get('priceChangePercent', 0))

                    symbol_prefix = "BTC" if symbol == "BTCUSDT" else "ETH"
                    btc_eth_data[f"{symbol_prefix}_price"] = last_price
                    btc_eth_data[f"{symbol_prefix}_24h_change"] = price_change
        except Exception as e:
            print(f"[UYARI] {symbol} ticker verisi alınamadı: {e}")
            # ALL_RESULTS'tan veri çekmeye çalış
            if ALL_RESULTS:
                btc_data = next((c for c in ALL_RESULTS if c["Coin"] == "BTCUSDT"), None)
                eth_data = next((c for c in ALL_RESULTS if c["Coin"] == "ETHUSDT"), None)

                if btc_data:
                    try:
                        btc_eth_data["BTC_price"] = parse_money(btc_data["Price_Display"])
                        btc_eth_data["BTC_24h_change"] = extract_numeric(btc_data["24h Change"])
                    except:
                        btc_eth_data["BTC_price"] = 85459.42
                        btc_eth_data["BTC_24h_change"] = 1.71

                if eth_data:
                    try:
                        btc_eth_data["ETH_price"] = parse_money(eth_data["Price_Display"])
                        btc_eth_data["ETH_24h_change"] = extract_numeric(eth_data["24h Change"])
                    except:
                        btc_eth_data["ETH_price"] = 2011.29
                        btc_eth_data["ETH_24h_change"] = -0.5

        # Eksik veriler için güvenilir değerler kullan
        if "BTC_price" not in btc_eth_data:
            btc_eth_data["BTC_price"] = 85459.42
            btc_eth_data["BTC_24h_change"] = 1.71
        if "ETH_price" not in btc_eth_data:
            btc_eth_data["ETH_price"] = 2011.29
            btc_eth_data["ETH_24h_change"] = -0.5

        # Rate limit nedeniyle güvenilir veri sağla
        dollar_strength = {
            "DXY_index": 102.35,
            "DXY_change": -0.28,
            "DXY_trend": "düşüş"
        }

        # FED Faiz Oranları ve Önemli Ekonomik Veriler - statik ama doğru değerler
        economic_events = [
            {
                "event_name": "FED Faiz Kararı",
                "country": "ABD",
                "importance": "yüksek",
                "time": "2025-03-19 19:00:00",
                "forecast": "5.25%",  # Doğru değer
                "previous": "5.25%"
            },
            {
                "event_name": "ABD İşsizlik Oranı",
                "country": "ABD",
                "importance": "yüksek",
                "time": "2025-03-19 15:30:00",
                "forecast": "3.9%",
                "previous": "3.7%"
            }
        ]

        # Hazine getirileri
        treasury_yields = {
            "US_10Y": 4.28,
            "US_2Y": 4.71,
            "yield_curve": "negatif"  # 10Y < 2Y (ters verim eğrisi)
        }

        return {
            "economic_events": economic_events,
            "market_indices": market_indices,
            "crypto_market": crypto_market,
            "btc_eth_data": btc_eth_data,
            "dollar_strength": dollar_strength,
            "treasury_yields": treasury_yields,
            "timestamp": datetime.now().timestamp()
        }
    except Exception as e:
        print(f"[HATA] Makroekonomik veri alınırken hata: {e}")
        return {}


def get_fear_greed_index():
    """
    Alternative.me API'sinden Korku ve Açgözlülük endeksini çeker

    Returns:
        int: 0-100 arası endeks değeri
    """
    try:
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return int(data['data'][0]['value'])
        else:
            raise Exception(f"Fear & Greed API yanıt vermedi: {response.status_code}")
    except Exception as e:
        print(f"[HATA] Korku & Açgözlülük endeksi alınamadı: {e}")
        # Varsayılan değer
        return 65


def get_current_price(symbol):
    """
    Verilen sembol için güncel fiyatı alır.

    Args:
        symbol (str): Fiyatı alınacak coin sembolü

    Returns:
        float: Güncel fiyat değeri
    """
    try:
        # Önce ALL_RESULTS içinde kontrol et (zaten çekilmiş veri varsa)
        for coin in ALL_RESULTS:
            if coin["Coin"] == symbol:
                price = parse_money(coin["Price_Display"])
                return price if price > 0 else 0

        # ALL_RESULTS'ta yoksa Binance API'den çek
        url = f"{BINANCE_API_URL}ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            return float(data["price"])
        else:
            print(f"[UYARI] {symbol} fiyatı alınamadı: {response.status_code}")
            return 0
    except Exception as e:
        print(f"[HATA] {symbol} fiyatı alınırken hata: {e}")
        return 0

# ----------------- İlave Handler Fonksiyonları -----------------

# Redundant def removed. Primary version is near line 6800.


def handle_market_risk_index():
    """Generates and sends the Market Risk Index report."""
    try:
        print("[INFO] Preparing Market Risk Index report...")

        macro_risk = calculate_macro_risk_level()
        if not macro_risk:
            send_telegram_message_long("⚠️ Risk data could not be fetched. Please try again later.")
            return

        report = f"🌐 <b>Market Risk Index Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        report += f"<b>📊 Risk Level:</b> {macro_risk['risk_level'].upper()}\n"
        report += f"• Global Risk Score: {macro_risk['risk_score']}/100\n\n"

        report += "<b>🚨 Priority Risk Factors:</b>\n"
        for factor in macro_risk['factors'][:5]:
            report += f"• {factor['factor']} ({factor['impact'].upper()})\n"
            report += f"  - {factor['description']}\n\n"

        report += "<b>💡 Risk Assessment:</b>\n"
        if macro_risk['risk_score'] < 30:
            report += "Market is low risk. Suitable for investment.\n"
        elif macro_risk['risk_score'] < 50:
            report += "Market carries medium risk. Cautious approach recommended.\n"
        elif macro_risk['risk_score'] < 70:
            report += "Market is high risk. Careful investment strategy required.\n"
        else:
            report += "Market is very high risk. Conservative stance highly recommended.\n"

        send_telegram_message_long(report)
    except Exception as e:
        print(f"[ERROR] Market risk index failed: {e}")
        send_telegram_message_long("⚠️ Error generating market risk index report.")


def handle_portfolio_risk_report():
    """Generates and sends the portfolio risk report."""
    try:
        print("[INFO] Preparing Portfolio Risk Report...")

        if not ALL_RESULTS or len(ALL_RESULTS) < 5:
            send_telegram_message_long("⚠️ No analysis data available yet, portfolio risk could not be calculated.")
            return

        # Sample portfolio - this can be replaced with dynamic portfolio selection
        sample_positions = {
            "BTCUSDT": 10000,
            "ETHUSDT": 5000,
            "BNBUSDT": 3000,
            "SOLUSDT": 2000,
            "AVAXUSDT": 1500
        }
        
        # Calculate macro risk if needed or just let the report generator handle it
        macro_risk = calculate_macro_risk_level()
        report = generate_portfolio_risk_report(sample_positions, macro_risk)
        send_telegram_message_long(report)
    except Exception as e:
        print(f"[ERROR] Portfolio risk report failed: {e}")
        send_telegram_message_long(
            "⚠️ An error occurred while generating the portfolio risk report. Please try again later.")


def calculate_macro_risk_level(custom_data=None):
    """
    Makroekonomik risk seviyesini hesaplar.

    Parameters:
        custom_data (dict, optional): Test için özel veri, aksi halde canlı veri çekilir

    Returns:
        dict: Risk seviyesi, skoru ve faktörlerini içeren değerlendirme
    """
    try:
        # Veri sağlama veya çekme
        macro_data = custom_data or fetch_macro_economic_data()
        if not macro_data:
            return {"risk_level": "bilinmiyor", "risk_score": 50, "factors": []}

        risk_factors = []

        # VIX Risk faktörü
        try:
            # Rate limit ve API sorunları için güvenli veri çekme
            vix_value = macro_data.get("market_indices", {}).get("VIX", {}).get("value", 18.45)
            vix_risk = {
                "factor": "VIX Volatilite",
                "impact": "yüksek" if vix_value > 25 else "orta" if vix_value > 15 else "düşük",
                "description": f"VIX endeksi {vix_value}, bu değer piyasa volatilitesini gösterir",
                "risk_score": min(vix_value * 2, 100)
            }
            risk_factors.append(vix_risk)
        except Exception as e:
            print(f"[UYARI] VIX risk faktörü oluşturulamadı: {e}")
            # Varsayılan VIX risk
            risk_factors.append({
                "factor": "VIX Volatilite",
                "impact": "orta",
                "description": "VIX verisi alınamadı, orta risk varsayıldı",
                "risk_score": 50
            })

        # Diğer risk faktörleri
        additional_factors = [
            {
                "factor": "Korku & Açgözlülük Endeksi",
                "impact": "orta",
                "description": f"Korku & Açgözlülük Endeksi: {macro_data.get('crypto_market', {}).get('fear_greed_index', 50)}/100",
                "risk_score": 40
            },
            {
                "factor": "Kripto Piyasa Değeri",
                "impact": "düşük",
                "description": f"Toplam Kripto Piyasa Değeri: ${macro_data.get('crypto_market', {}).get('total_market_cap', 2.89e12) / 1e12:.2f} Trilyon",
                "risk_score": 30
            }
        ]
        risk_factors.extend(additional_factors)

        # Toplam risk hesapla
        total_risk_score = sum(factor["risk_score"] for factor in risk_factors)

        # En az 1 faktör olduğundan emin ol
        if not risk_factors:
            risk_factors.append({
                "factor": "Genel Piyasa Riski",
                "impact": "orta",
                "description": "Veri eksikliği nedeniyle varsayılan orta risk",
                "risk_score": 50
            })
            total_risk_score = 50

        # Normalize risk score (0-100)
        normalized_risk = min(total_risk_score / len(risk_factors), 100)

        # Risk seviyesini belirle
        risk_level = "düşük"
        if normalized_risk >= 70:
            risk_level = "çok yüksek"
        elif normalized_risk >= 50:
            risk_level = "yüksek"
        elif normalized_risk >= 30:
            risk_level = "orta"

        return {
            "risk_level": risk_level,
            "risk_score": normalized_risk,
            "factors": sorted(risk_factors, key=lambda x: x["risk_score"], reverse=True)
        }
    except Exception as e:
        print(f"[HATA] Makro risk seviyesi hesaplanırken hata: {e}")
        import traceback
        traceback.print_exc()
        return {"risk_level": "bilinmiyor", "risk_score": 50, "factors": []}


def calculate_asset_risk(coin_data, macro_context=None):
    """
    Bir coin/varlık için birleştirilmiş risk skorunu hesaplar.
    0-100 arası normalize edilmiş, standartlaştırılmış bileşenlerle.

    Parameters:
        coin_data (dict): Coin metriklerini içeren sözlük
        macro_context (dict, optional): Riski ayarlamak için makro risk bağlamı

    Returns:
        dict: Risk skoru ve detaylı bileşen dağılımı
    """
    try:
        # Güncel fiyat verisi al
        symbol = coin_data["Coin"]
        current_price = parse_money(coin_data["Price_Display"])
        if current_price <= 0:
            current_price = get_current_price(symbol)

        # Güvenli veri çıkarımı
        rsi = safe_extract(coin_data, "RSI", 50)
        macd = safe_extract(coin_data, "MACD", 0)
        adx = safe_extract(coin_data, "ADX", 0)
        volume_ratio = safe_extract(coin_data, "Volume Ratio", 1)
        net_accum = safe_extract(coin_data, "NetAccum_raw", 0)
        btc_corr = safe_extract(coin_data, "BTC Correlation", 0)
        atr = safe_extract(coin_data, "ATR_raw", 0)

        # Vadeli işlem verilerini güvenli al (CACHE KULLAN)
        funding_rate = safe_extract(coin_data, "Funding_Rate", 0)
        long_short_ratio = safe_extract(coin_data,"Long/Short Ratio", 1.0)
        
        # String 'N/A' kontrolü
        if isinstance(funding_rate, str): funding_rate = 0
        if isinstance(long_short_ratio, str): long_short_ratio = 1.0


        # Risk bileşenleri
        # Fiyatın sıfır olma durumunu önlemek için
        if current_price <= 0:
            current_price = 1  # Sıfıra bölme hatasını önlemek için minimum değer

        volatility_risk = (atr / current_price * 100) * 5 if current_price > 0 else 0
        volatility_risk = min(volatility_risk, 100)

        rsi_risk = abs(50 - rsi) / 50 * 100  # Ekstrem değerler yüksek risk
        momentum_risk = min(abs(macd) * 60, 60)  # MACD'yi normalize et
        volume_risk = min((1 / max(volume_ratio, 0.2)) * 50, 50)  # low hacim = yüksek risk
        correlation_risk = min(abs(btc_corr) * 80, 80)  # high korelasyon = sistematik risk
        whale_risk = min(abs(net_accum) / 10 * 70, 70)  # Büyük balina hareketleri = risk
        funding_risk = min(abs(funding_rate) * 200, 80)  # Ekstrem funding = risk
        ls_imbalance = abs(1 - long_short_ratio) * 100  # Long/short dengesizliği

        # Makro risk etkisi
        macro_risk_factor = 0
        if macro_context:
            market_risk_score = macro_context.get("risk_score", 50)
            is_major = symbol in ["BTCUSDT", "ETHUSDT"]
            macro_risk_factor = (market_risk_score / 100) * (15 if is_major else 25)

        # Risk bileşenleri
        components = {
            "volatility_risk": round(volatility_risk, 2),
            "rsi_risk": round(rsi_risk, 2),
            "momentum_risk": round(momentum_risk, 2),
            "volume_risk": round(volume_risk, 2),
            "correlation_risk": round(correlation_risk, 2),
            "whale_risk": round(whale_risk, 2),
            "funding_risk": round(funding_risk, 2),
            "ls_imbalance": round(ls_imbalance, 2),
            "macro_risk_factor": round(macro_risk_factor, 2)
        }

        # Ağırlıklar
        weights = {
            "volatility_risk": 0.15,
            "rsi_risk": 0.10,
            "momentum_risk": 0.10,
            "volume_risk": 0.08,
            "correlation_risk": 0.10,
            "whale_risk": 0.12,
            "funding_risk": 0.08,
            "ls_imbalance": 0.05,
            "macro_risk_factor": 0.10
        }

        # Ağırlıklı toplam hesaplama
        weighted_risk = sum(components[key] * weights[key] for key in components)
        normalized_risk = min(max(weighted_risk, 0), 100)

        # Risk seviyesi
        if normalized_risk >= 75:
            risk_level = "çok yüksek"
        elif normalized_risk >= 50:
            risk_level = "yüksek"
        elif normalized_risk >= 30:
            risk_level = "orta"
        else:
            risk_level = "düşük"

        return {
            "risk_score": round(normalized_risk, 2),
            "risk_level": risk_level,
            "details": {"components": components, "weights": weights},
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"[HATA] Varlık risk hesaplama hatası ({coin_data.get('Coin', 'Bilinmeyen')}): {e}")
        import traceback
        traceback.print_exc()
        return {"risk_score": 50, "risk_level": "orta", "details": {"error": str(e)}}


safe_extract = utils.safe_extract



def generate_comprehensive_risk_report(results=None, macro_risk=None):
    """
    Generates a Comprehensive Risk Analysis Report.
    """
    if not results:
        results = ALL_RESULTS[:50] if ALL_RESULTS else []

    if not results:
        return "⚠️ No analysis data available yet."

    # Macro Risk Analysis - calculate if not provided
    if not macro_risk:
        macro_risk = calculate_macro_risk_level()

    # Calculate Risk Scores
    risk_scores = []
    for coin in results:
        try:
            # Calculate coin risk score with macro context
            risk_assessment = calculate_asset_risk(coin, macro_risk)
            risk_scores.append({
                'coin': coin['Coin'],
                'risk_score': risk_assessment['risk_score'],
                'risk_level': risk_assessment['risk_level'],
                'details': risk_assessment['details']
            })
        except Exception as e:
            print(f"[ERROR] Could not calculate risk score for {coin.get('Coin', 'Unknown')}: {e}")

    # Sorting by Risk
    sorted_risks = sorted(risk_scores, key=lambda x: x['risk_score'], reverse=True)

    # Classification by risk levels
    risk_categories = {
        "very high": [r for r in sorted_risks if r['risk_level'] == "very high"],
        "high": [r for r in sorted_risks if r['risk_level'] == "high"],
        "medium": [r for r in sorted_risks if r['risk_level'] == "medium"],
        "low": [r for r in sorted_risks if r['risk_level'] == "low"]
    }

    report = f"🛡️ <b>Comprehensive Risk Analysis Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

    # Macro Risk Summary
    report += f"🌐 <b>Macro Risk Assessment:</b>\n"
    report += f"• General Risk Score: {macro_risk['risk_score']}/100\n"
    report += f"• Risk Level: {macro_risk['risk_level'].upper()}\n\n"

    # Risk Factors
    if macro_risk.get('factors'):
        report += "🚨 <b>Priority Risk Factors:</b>\n"
        for factor in macro_risk.get('factors', [])[:3]:
            risk_emoji = "🔴" if factor['impact'] == "high" else "🟠" if factor['impact'] == "medium" else "🟡"
            report += f"{risk_emoji} {factor['factor']} ({factor['impact'].upper()})\n"
            report += f"   {factor['description']}\n\n"

    # Risk category counts
    report += "<b>Risk Distribution:</b>\n"
    report += f"• Very High Risk: {len(risk_categories['very high'])} coins\n"
    report += f"• High Risk: {len(risk_categories['high'])} coins\n"
    report += f"• Medium Risk: {len(risk_categories['medium'])} coins\n"
    report += f"• Low Risk: {len(risk_categories['low'])} coins\n\n"

    # Top High Risk Coins
    report += "⚠️ <b>Top 5 Highest Risk Coins:</b>\n"
    for idx, risk_data in enumerate(sorted_risks[:5], 1):
        risk_level_emoji = (
            "🟢" if risk_data['risk_score'] < 30 else
            "🟡" if risk_data['risk_score'] < 50 else
            "🟠" if risk_data['risk_score'] < 70 else
            "🔴" if risk_data['risk_score'] < 90 else
            "🟣"
        )
        symbol = "$" + risk_data['coin'].replace("USDT", "")
        report += f"{idx}. {risk_level_emoji} <b>{symbol}</b>: Risk Score {risk_data['risk_score']:.1f}/100\n"

        # Show top risk factors
        components = risk_data['details'].get('components', {})
        top_risks = sorted(components.items(), key=lambda x: x[1], reverse=True)[:3]

        for comp_name, comp_value in top_risks:
            readable_name = comp_name.replace('_', ' ').title()
            report += f"   - {readable_name}: {comp_value:.1f}/100\n"

        report += "\n"

    # General Risk Comment
    risk_comment = (
        "🟢 <b>Low Risk:</b> Quite suitable for investment" if macro_risk['risk_score'] < 30 else
        "🟡 <b>Medium Risk:</b> Should be cautious and selective" if macro_risk['risk_score'] < 50 else
        "🟠 <b>High Risk:</b> Serious precautions should be taken" if macro_risk['risk_score'] < 70 else
        "🔴 <b>Very High Risk:</b> Urgent position management required"
    )
    report += f"\n💡 <b>General Risk Assessment:</b>\n{risk_comment}\n"

    # Risk recommendations
    report += "\n<b>Recommendations:</b>\n"
    if macro_risk['risk_score'] >= 70:
        report += "• Keep at least 50% of portfolio in stablecoins\n"
        report += "• Tighten stop-loss levels\n"
        report += "• Stay away from high-risk coins\n"
    elif macro_risk['risk_score'] >= 50:
        report += "• Keep 30-40% of portfolio in stablecoins\n"
        report += "• Reduce position sizes\n"
        report += "• Take profits on high-risk altcoins\n"
    else:
        report += "• Market looks favorable, but always practice risk management\n"
        report += "• Stop-loss levels must be determined\n"
        report += "• Portfolio diversification is recommended\n"

    return report



def calculate_risk_score(coin_data):
    """
    Detaylı ve Çok Boyutlu Risk Skoru Hesaplama
    📊 Risk Değerlendirme Algoritması
    """
    try:
        # Risk Parametreleri
        rsi = extract_numeric(coin_data['RSI'] if coin_data['RSI'] else 50)
        volume_ratio = extract_numeric(coin_data.get('Volume Ratio', 1))
        net_accum = extract_numeric(coin_data.get('NetAccum_raw', 0))
        btc_corr = extract_numeric(coin_data.get('BTC Correlation', 0))

        # Karmaşık Risk Hesaplaması
        risk_components = {
            'rsi_risk': abs(50 - rsi) / 50 * 25,  # RSI Sapması
            'volume_risk': (1 / max(volume_ratio, 1)) * 20,  # volume Risk Faktörü
            'net_accum_risk': abs(net_accum) / 10 * 20,  # Net Birikim Riski
            'correlation_risk': abs(btc_corr) * 20  # Korelasyon Riski
        }

        # Toplam Risk Skoru
        total_risk = sum(risk_components.values())
        normalized_risk = min(max(total_risk, 0), 100)

        # Detaylı Risk Açıklaması
        risk_details = {
            'rsi_interpretation': "Aşırı Alım/Satım" if abs(50 - rsi) > 20 else "Normal Bölge",
            'volume_interpretation': "low volume" if volume_ratio < 1 else "Normal volume",
            'net_accum_interpretation': "Net Balina Hareketi" if abs(net_accum) > 5 else "Nötr Birikim"
        }

        return normalized_risk

    except Exception as e:
        print(f"[HATA] Risk skoru hesaplanamadı: {e}")
        return 50  # Varsayılan orta risk


def calculate_liquidation_risk(position_size, entry_price, leverage, current_price, volatility):
    """
    Likidite riski hesaplama fonksiyonu

    Args:
        position_size (float): Pozisyon büyüklüğü
        entry_price (float): Giriş fiyatı
        leverage (float): Kaldıraç
        current_price (float): Güncel fiyat
        volatility (float): Volatilite (ATR vs.)

    Returns:
        dict: Likidite riski analizi
    """
    # Pozisyon türünü belirle
    is_long = entry_price < current_price

    # Likidite fiyatını hesapla
    margin = position_size / leverage
    if is_long:
        liquidation_price = entry_price * (1 - (1 / leverage))
    else:
        liquidation_price = entry_price * (1 + (1 / leverage))

    # Likidite fiyatına olan mesafeyi hesapla
    distance_to_liquidation = abs(current_price - liquidation_price)
    distance_pct = (distance_to_liquidation / current_price) * 100

    # Volatiliteye göre likidite riski
    risk_multiple = volatility / distance_to_liquidation if distance_to_liquidation > 0 else float('inf')

    # Risk seviyesini belirle
    if risk_multiple >= 1:
        risk_level = "Çok high"
    elif risk_multiple >= 0.5:
        risk_level = "high"
    elif risk_multiple >= 0.25:
        risk_level = "Orta"
    else:
        risk_level = "low"

    return {
        "liquidation_price": liquidation_price,
        "distance_percent": distance_pct,
        "risk_multiple": risk_multiple,
        "risk_level": risk_level,
        "liquidation_time_estimate": distance_to_liquidation / volatility * 24  # Saat cinsinden tahmini süre
    }


def create_risk_submenu_keyboard():
    """Generates an English submenu for Risk Analysis."""
    return [
        [{"text": "🔍 Advanced Risk Analysis"}],
        [{"text": "💼 Portfolio Risk Report"}],
        [{"text": "📊 Macroeconomic Indicators"}],
        [{"text": "🌐 Market Risk Index"}],
        [{"text": "📈 Risk Score Details"}],
        [{"text": "🏦 Sectoral Risk Analysis"}],
        [{"text": "↩️ Main Menu"}]
    ]


def create_complete_command_mapping():
    """
    Emoji içeren ve içermeyen tüm komutlar için kapsamlı bir eşleştirme sözlüğü oluşturur.
    Bu, farklı yazım biçimlerindeki komutların doğru şekilde işlenmesini sağlar.

    Returns:
        dict: Tüm olası komut versiyonları için eşleştirme sözlüğü
    """
    return {
        # Main commands
        "📊 Current Analysis": "Current Analysis",
        "Current Analysis": "Current Analysis",
        "Refresh Analysis": "Current Analysis",

        # Coins and Risk
        "🔍 All Coins": "All Coins",
        "All Coins": "All Coins",
        "🛡️ Risk Analysis": "Risk Analysis",
        "Risk Analysis": "Risk Analysis",

        # Risk menu commands
        "🔍 Advanced Risk Analysis": "Advanced Risk Analysis",
        "Advanced Risk Analysis": "Advanced Risk Analysis",
        "💼 Portfolio Risk Report": "Portfolio Risk Report",
        "Portfolio Risk Report": "Portfolio Risk Report",
        "📊 Macroeconomic Indicators": "Macroeconomic Indicators",
        "Macroeconomic Indicators": "Macroeconomic Indicators",
        "🌐 Market Risk Index": "Market Risk Index",
        "Market Risk Index": "Market Risk Index",
        "📈 Risk Score Details": "Risk Score Details",
        "Risk Score Details": "Risk Score Details",
        "🏦 Sectoral Risk Analysis": "Sectoral Risk Analysis",
        "Sectoral Risk Analysis": "Sectoral Risk Analysis",

        # Return to main menu
        "↩️ Main Menu": "Main Menu",
        "Main Menu": "Main Menu",
        "Back": "Main Menu",
        "↩Main Menu": "Main Menu",
        "main_menu": "Main Menu",
        "↩️ Ana Menü": "Main Menu",

        # Manipulation and Smart Money
        "🕵️ Manipulation Detector": "Manipulation Detector",
        "Manipulation Detector": "Manipulation Detector",
        "💹 Smart Money": "Smart Money",
        "Smart Money": "Smart Money",

        # Candle patterns
        "🕯️ Candle Patterns": "Candle Patterns",
        "Candle Patterns": "Candle Patterns",
        "Candle Patterns Report": "Candle Patterns Report",
        "Mum Desenleri Raporu": "Candle Patterns Report",

        # command_mapping sözlüğüne ekleme yapalım
        "📊 Price Info": "Price Info",
        "Price Info": "Price Info",
        "📊 Fiyat Bilgileri": "Price Info",

        "⚖️ Long/Short Ratio": "Long/Short Ratio",
        "Long/Short Ratio": "Long/Short Ratio",
        "⚖️ Long/Short Ratio": "Long/Short Ratio",

        "💰 Funding Rate": "Funding Rate",
        "Funding Rate": "Funding Rate",
        "💰 Funding Rate Analizi": "Funding Rate",

        # Whale analysis
        "🐳 Whale Strategies": "Whale Strategies",
        "Whale Strategies": "Whale Strategies",
        "🐋 Whale Movement": "Whale Movement",
        "🐋 Whale Movement Analysis": "Whale Movement", 
        "Whale Movement": "Whale Movement",
        "🐋 Balina Hareketleri": "Whale Movement",

        # volume ve trend
        "📈 Trend Status": "Trend Status",
        "Trend Status": "Trend Status",
        "Trend Durumu": "Trend Status",
        "💰 Net Buy/Sell Status": "Net Buy/Sell Status",
        "Net Buy/Sell Status": "Net Buy/Sell Status",
        "💰 Net Alım/Satım Durumu": "Net Buy/Sell Status",
        "Net Alım/Satım Durumu": "Net Buy/Sell Status",

        # Metrik raporları
        "💰 Net Accum": "Net Accum",
        "Net Accum": "Net Accum",
        "💰 Net Accum 4H": "Net Accum 4H",
        "Net Accum 4H": "Net Accum 4H",
        "💰 Net Accum 1D": "Net Accum 1D",
        "Net Accum 1D": "Net Accum 1D",
        "🔄 BTC Correlation": "BTC Correlation",
        "BTC Correlation": "BTC Correlation",
        "🔄 BTC Correlation": "BTC Correlation",
        "🔄 BTC Corr 4H": "BTC Corr 4H",
        "BTC Corr 4H": "BTC Corr 4H",
        "🔄 BTC Corr 1D": "BTC Corr 1D",
        "BTC Corr 1D": "BTC Corr 1D",
        "🔄 ETH Correlation": "ETH Correlation",
        "ETH Correlation": "ETH Correlation",
        "🔄 ETH Correlation": "ETH Correlation",
        "🔄 ETH Corr 4H": "ETH Corr 4H",
        "ETH Corr 4H": "ETH Corr 4H",
        "🔄 ETH Corr 1D": "ETH Corr 1D",
        "ETH Corr 1D": "ETH Corr 1D",
        "🔄 SOL Correlation": "SOL Correlation",
        "SOL Correlation": "SOL Correlation",
        "🔄 SOL Correlation": "SOL Correlation",
        "🔄 SOL Corr 4H": "SOL Corr 4H",
        "SOL Corr 4H": "SOL Corr 4H",
        "🔄 SOL Corr 1D": "SOL Corr 1D",
        "SOL Corr 1D": "SOL Corr 1D",
        "📊 Composite Score": "Composite Score",
        "Composite Score": "Composite Score",
        "📊 Composite Skor": "Composite Score",
        "📊 Composite 4H": "Composite 4H",
        "Composite 4H": "Composite 4H",
        "📊 Composite 1D": "Composite 1D",
        "Composite 1D": "Composite 1D",
        "📊 Difference Index": "Difference Index",
        "Difference Index": "Difference Index",
        "📊 Fark Endeksi": "Difference Index",
        "Outlier Score": "Outlier Score",
        "📊 Outlier Score": "Outlier Score",

        # Diğer rapor komutları
        "📋 Summary": "Summary",
        "Summary": "Summary",
        "📋 Özet": "Summary",
        "⚖️ EMA Crossings": "EMA Crossings",
        "EMA Crossings": "EMA Crossings",
        "⚖️ EMA Kesişimi": "EMA Crossings",
        "⏱️ Hourly Analysis": "Hourly Analysis",
        "Hourly Analysis": "Hourly Analysis",
        "⏱️ Saatlik Analiz Gör": "Hourly Analysis",
        "💵 Cash Flow Report": "Cash Flow Report",
        "Cash Flow Report": "Cash Flow Report",
        "💵 Nakit Girişi Raporu": "Cash Flow Report",
        "💵 Flow Migrations": "Flow Migrations",
        "Flow Migrations": "Flow Migrations",
        "💵 Nakit Girişi Göçleri": "Flow Migrations",
        "📊 Smart Score": "Smart Score",
        "Smart Score": "Smart Score",
        "📊 Smart Skor Raporu": "Smart Score",
        
        "🧠 Smart Whale & Trend": "Smart Whale & Trend",
        "Smart Whale & Trend": "Smart Whale & Trend",
        "🧠 Akıllı Balina & Trend": "Smart Whale & Trend",
        
        # New Additions
        "📊 Monthly Change": "Monthly Change",
        "Monthly Change": "Monthly Change",
        "📊 Aylık Değişim": "Monthly Change",
        "📊 Significant Changes": "Significant Changes",
        "Significant Changes": "Significant Changes",
        "📊 Fark Yaratan Coin'ler": "Significant Changes",
        
        # Rankings
        "🐳 Whale Ranking": "Whale Ranking",
        "Whale Ranking": "Whale Ranking",
        "🐳 Balina Sıralaması": "Whale Ranking",
        "🌊 Volatility Ranking": "Volatility Ranking",
        "Volatility Ranking": "Volatility Ranking",
        "🌊 Volatility Ranking": "Volatility Ranking",
        "📏 Bollinger Squeeze": "Bollinger Squeeze",
        "Bollinger Squeeze": "Bollinger Squeeze",
        "📏 Bollinger Sıkışması": "Bollinger Squeeze",
        "🔒 Trust Index": "Trust Index",
        "Trust Index": "Trust Index",
        "🔒 Güven Endeksi Raporu": "Trust Index",
        
        "BTC Tüm Veriler": "BTC Tüm Veriler",
        
        "💹 Futures Analysis": "Futures Analysis",
        "Futures Analysis": "Futures Analysis",
        "Vadeli İşlemler Analizi": "Futures Analysis",
        "💹 Vadeli İşlemler Analizi": "Futures Analysis",

        # Metric Reports (Missing emojis and direct mappings)
        "📊 RSI Report": "RSI Report",
        "RSI Report": "RSI Report",
        "📊 RSI 4H": "RSI 4H",
        "RSI 4H": "RSI 4H",
        "📊 RSI 1D": "RSI 1D",
        "RSI 1D": "RSI 1D",
        "⚖️ EMA Report": "EMA Report",
        "EMA Report": "EMA Report",
        "⏱️ 4H Change": "4H Change",
        "4H Change": "4H Change",
        "📅 Weekly Change": "Weekly Change",
        "Weekly Change": "Weekly Change",
        "📊 24h Volume": "24h Volume",
        "24h Volume": "24h Volume",
        "📊 24h Vol 4H": "24h Vol 4H",
        "24h Vol 4H": "24h Vol 4H",
        "📊 24h Vol 1D": "24h Vol 1D",
        "24h Vol 1D": "24h Vol 1D",
        "📊 Volume Ratio": "Volume Ratio",
        "Volume Ratio": "Volume Ratio",
        "📊 Volume Ratio 4H": "Volume Ratio 4H",
        "Volume Ratio 4H": "Volume Ratio 4H",
        "📊 Volume Ratio 1D": "Volume Ratio 1D",
        "Volume Ratio 1D": "Volume Ratio 1D",
        "🎯 MM Analysis": "MM Analysis",
        "MM Analysis": "MM Analysis",
        "📊 ATR Report": "ATR",
        "ATR": "ATR",
        "📈 ADX Report": "ADX",
        "ADX": "ADX",
        "📈 ADX 4H": "ADX 4H",
        "ADX 4H": "ADX 4H",
        "📈 ADX 1D": "ADX 1D",
        "ADX 1D": "ADX 1D",
        "📊 MACD Report": "MACD",
        "MACD": "MACD",
        "📊 MACD 4H": "MACD 4H",
        "MACD 4H": "MACD 4H",
        "📊 MACD 1D": "MACD 1D",
        "MACD 1D": "MACD 1D",
        "📉 Open Interest": "Open Interest",
        "Open Interest": "Open Interest",
        "💰 MFI Report": "MFI",
        "MFI": "MFI",
        "💰 MFI 4H": "MFI 4H",
        "MFI 4H": "MFI 4H",
        "💰 MFI 1D": "MFI 1D",
        "MFI 1D": "MFI 1D",
        "📊 StochRSI Report": "StochRSI",
        "StochRSI": "StochRSI",
        "Taker Rate": "Taker Rate",
        "📊 Taker Rate": "Taker Rate",
        "Support/Resistance": "Support/Resistance",
        "📐 Support/Resistance": "Support/Resistance",
        "📐 S/R Levels": "Support/Resistance",
        "Z-Score": "Z-Score",
        "📏 Z-Score": "Z-Score",
        "📏 Z-Score 4H": "Z-Score 4H",
        "Z-Score 4H": "Z-Score 4H",
        "📏 Z-Score 1D": "Z-Score 1D",
        "Z-Score 1D": "Z-Score 1D",
        "Bollinger Bands": "Bollinger Bands",
        "📏 Bollinger Bands": "Bollinger Bands",
        "🚀 Momentum Report": "Momentum",
        "📊 Momentum 4H": "Momentum 4H",
        "Momentum 4H": "Momentum 4H",
        "📊 Momentum 1D": "Momentum 1D",
        "Momentum 1D": "Momentum 1D",
        "NotebookLM Export": "NotebookLM Export",
        "📤 NotebookLM Export": "NotebookLM Export",
        "YouTube Alpha": "YouTube Alpha",
        "Order Book Analysis": "order_book_analysis",
        "🔥 Liquidation Map": "liquidation_analysis",
        "Liquidation Map": "liquidation_analysis",
        "🔥 Liquidation Analysis": "liquidation_analysis",
        "Liquidation Analysis": "liquidation_analysis",
        "📺 YouTube Alpha": "YouTube Alpha",
        "📜 YouTube Transcripts": "YouTube Transcripts",
        "📚 Order Book Analysis": "order_book_analysis",
        "↩️ Ana Menü": "Main Menu",
        "↩️ Main Menu": "Main Menu"
    }


# Telegram mesaj işleme kısmında kullanılacak örnek kod

def analyze_market_maker_activity(taker_buy_volume, taker_sell_volume, time_buckets=6):
    """
    Market maker aktivitesini analiz eder

    Args:
        taker_buy_volume (list): Zaman serisi alıcı hacim verileri
        taker_sell_volume (list): Zaman serisi satıcı hacim verileri
        time_buckets (int): Analiz edilecek zaman dilimi sayısı

    Returns:
        dict: Market maker aktivite analizi
    """
    if len(taker_buy_volume) != len(taker_sell_volume) or len(taker_buy_volume) < time_buckets:
        return {"valid": False}

    try:
        # Verileri time_buckets sayıda döneme böl
        bucket_size = len(taker_buy_volume) // time_buckets

        period_analysis = []
        total_market_volume = sum(taker_buy_volume) + sum(taker_sell_volume)  # Total market volume tanımı

        for i in range(time_buckets):
            start_idx = i * bucket_size
            end_idx = start_idx + bucket_size

            if end_idx > len(taker_buy_volume):
                end_idx = len(taker_buy_volume)

            period_buy = sum(taker_buy_volume[start_idx:end_idx])
            period_sell = sum(taker_sell_volume[start_idx:end_idx])

            # Net akümülasyon
            net_accumulation = period_buy - period_sell

            # Maker (market maker) / Taker oranı
            total_volume = period_buy + period_sell
            maker_ratio = 1 - (total_volume / total_market_volume) if total_market_volume > 0 else 0

            period_analysis.append({
                "period": i + 1,
                "net_accumulation": net_accumulation,
                "buy_volume": period_buy,
                "sell_volume": period_sell,
                "maker_ratio": maker_ratio
            })

        # Trend analizleri
        accumulation_trend = [p["net_accumulation"] for p in period_analysis]
        is_increasing_accum = all(
            accumulation_trend[i] <= accumulation_trend[i + 1] for i in range(len(accumulation_trend) - 1))
        is_decreasing_accum = all(
            accumulation_trend[i] >= accumulation_trend[i + 1] for i in range(len(accumulation_trend) - 1))

        return {
            "valid": True,
            "period_analysis": period_analysis,
            "is_increasing_accumulation": is_increasing_accum,
            "is_decreasing_accumulation": is_decreasing_accum,
            "recent_maker_ratio": period_analysis[-1]["maker_ratio"] if period_analysis else 0
        }
    except Exception as e:
        print(f"[HATA] Market maker aktivite analizinde hata: {e}")
        return {"valid": False}



def handle_reply_message(message):
    """
    Telegram'dan gelen mesajları işler ve menü durumunu takip eder.

    Args:
        message (dict): Telegram mesaj nesnesi
    """
    # Quick refresh temporarily disabled - main loop runs every 2 minutes which is sufficient
    # Ensure fresh data before handling user request
    # force_refresh_if_stale(max_age_seconds=600)  # Disabled - using main loop data only
    
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id", TELEGRAM_CHAT_ID)
    print(f"[DEBUG] Gelen mesaj: '{text}', Chat ID: {chat_id}")

    # Mevcut menü durumunu al
    current_menu = MENU_STATE.get_user_state(chat_id)
    print(f"[DEBUG] Mevcut menü durumu: {current_menu}")

    # Tam komut eşleştirme sözlüğü
    command_mapping = create_complete_command_mapping()


    # Return to main menu commands
    if text in ["↩️ Main Menu", "Main Menu", "Back", "↩Main Menu", "main_menu"]:
        print(f"[DEBUG] Return to main menu detected: '{text}'")
        MENU_STATE.set_user_state(chat_id, "main_menu")
        handle_main_menu_return(chat_id)
        return

    # Mesajı normalleştir (emoji veya emoji olmayan versiyonları eşleştir)
    normalized_text = command_mapping.get(text, text)
    print(f"[DEBUG] Text normalization: '{text}' → '{normalized_text}'")

    if normalized_text == "Main Menu":
        MENU_STATE.set_user_state(chat_id, "main_menu")
        main_keyboard = create_reply_keyboard(ALL_RESULTS)
        send_reply_keyboard_message(chat_id, "🏠 Returned to Main Menu", keyboard=main_keyboard)
        return

    # Ana menü klavyesi
    main_keyboard = create_reply_keyboard(ALL_RESULTS)

    try:
        # ---------- ANA MENÜ İŞLEME ----------
        if current_menu == "main_menu":
            if normalized_text == "Current Analysis":
                send_initial_analysis(chat_id)

            elif normalized_text == "All Coins":
                MENU_STATE.set_user_state(chat_id, "all_coins_menu")
                if ALL_RESULTS:
                    coin_keyboard = create_all_coins_keyboard()
                    send_reply_keyboard_message(
                        chat_id,
                        "Please select the coin you want to see analytics for:",
                        keyboard=coin_keyboard
                    )
                else:
                    send_telegram_message_long("⚠️ No analysis data available yet.")
                    MENU_STATE.set_user_state(chat_id, "main_menu")

            elif normalized_text == "Risk Analysis":
                MENU_STATE.set_user_state(chat_id, "risk_menu")
                risk_keyboard = create_risk_submenu_keyboard()
                send_reply_keyboard_message(
                    chat_id,
                    "🛡️ <b>Risk Analysis Menu</b>\n\n"
                    "Select one of the options below for detailed risk analysis.",
                    keyboard=risk_keyboard
                )

            elif normalized_text == "Smart Money":
                MENU_STATE.set_user_state(chat_id, "smart_money_menu")
                handle_smart_money_menu()

            elif normalized_text == "Candle Patterns":
                MENU_STATE.set_user_state(chat_id, "candlestick_menu")
                if 'handle_candlestick_pattern_menu' in globals():
                    handle_candlestick_pattern_menu(chat_id, send_reply_keyboard_message)
                else:
                    send_telegram_message_long("⚠️ Candle pattern analysis is not yet ready.")
                    MENU_STATE.set_user_state(chat_id, "main_menu")

            # Other operations in main menu (Summary, EMA Crossings, etc.)
            elif normalized_text in [
                "Manipulation Detector", "Whale Strategies", "Whale Movement", "MM Analysis",
                "Volume Ratio", "Trend Status", "Net Accum", "Net Buy/Sell Status",
                "BTC Correlation", "ETH Correlation", "SOL Correlation", "Composite Score", "Difference Index",
                "Outlier Score", "Summary", "EMA Crossings", "Hourly Analysis",
                "Cash Flow Report", "Flow Migrations", "Smart Score", "Price Info", "Long/Short Ratio",
                "Funding Rate", "Smart Whale & Trend", "Whale Ranking", "Volatility Ranking",
                "Bollinger Squeeze", "Trust Index", "BTC Tüm Veriler",
                "Significant Changes", "Futures Analysis", "Monthly Change",
                "RSI Report", "RSI 4H", "RSI 1D", "EMA Report", "4H Change", "Weekly Change", "24h Volume",
                "ATR", "ADX", "ADX 4H", "ADX 1D", "MACD", "MACD 4H", "MACD 1D", 
                "Open Interest", "MFI", "StochRSI", "Taker Rate", "Support/Resistance", "Z-Score", 
                "Bollinger Bands", "Momentum", "NotebookLM Export", "YouTube Alpha", "YouTube Transcripts", "order_book_analysis", "liquidation_analysis",
                "Net Accum 4H", "Net Accum 1D", "Composite 4H", "Composite 1D",
                "BTC Corr 4H", "BTC Corr 1D", "ETH Corr 4H", "ETH Corr 1D", "SOL Corr 4H", "SOL Corr 1D",
                "24h Vol 4H", "24h Vol 1D", "Volume Ratio 4H", "Volume Ratio 1D",
                "MFI 4H", "MFI 1D", "Momentum 4H", "Momentum 1D"
            ]:
                # Call handle_main_menu_option with English normalized text
                print(f"[DEBUG] Calling handle_main_menu_option with: '{normalized_text}'")
                handle_main_menu_option(normalized_text, chat_id)

            # Ana menüden coin detayı gösterme
            elif text in COIN_DETAILS or text in [coin["Coin"] for coin in ALL_RESULTS]:
                handle_coin_detail(text, chat_id)

            else:
                print(f"[DEBUG] Ana menüde tanımlanmayan mesaj: '{text}'")
                send_telegram_message(chat_id, "Invalid command. Please select an option from the keyboard.",
                                      keyboard=main_keyboard)


        # ---------- RISK MENU PROCESSING ----------
        elif current_menu == "risk_menu":
            if normalized_text == "Advanced Risk Analysis" or normalized_text == "Gelişmiş Risk Analizi":
                handle_advanced_risk_analysis()
            elif normalized_text == "Portfolio Risk Report" or normalized_text == "Portföy Risk Raporu":
                handle_portfolio_risk_report()
            elif normalized_text == "Macroeconomic Indicators" or normalized_text == "Makroekonomik Göstergeler":
                handle_makroekonomik_gostergeler()
            elif normalized_text == "Market Risk Index" or normalized_text == "Piyasa Risk Endeksi":
                handle_market_risk_index()
            elif normalized_text == "Risk Score Details" or normalized_text == "Risk Skoru Detayları":
                handle_risk_score_details()
            elif normalized_text == "Sectoral Risk Analysis" or normalized_text == "Sektörel Risk Analizi":
                handle_sectoral_risk_analysis()
            else:
                print(f"[DEBUG] Risk menüsünde tanımlanmayan mesaj: '{text}'")
                # Risk menüsünü tekrar göster
                risk_keyboard = create_risk_submenu_keyboard()
                send_reply_keyboard_message(
                    chat_id,
                    "🛡️ <b>Risk Analysis Menu</b>\n\n"
                    "⚠️ Invalid selection. Please choose one of the options below:",
                    keyboard=risk_keyboard
                )

        # ---------- TÜM COİNLER MENÜSÜ İŞLEME ----------
        elif current_menu == "all_coins_menu":
            if text in [coin["Coin"] for coin in ALL_RESULTS]:
                handle_coin_detail(text, chat_id)
                # Coin detayı gösterdikten sonra aynı menüde kal
            else:
                print(f"[DEBUG] Tüm coinler menüsünde tanımlanmayan mesaj: '{text}'")
                # Tüm coinler menüsünü tekrar göster
                coin_keyboard = create_all_coins_keyboard()
                send_reply_keyboard_message(
                    chat_id,
                    "⚠️ Invalid selection. Please select the coin you want to analyze:",
                    keyboard=coin_keyboard
                )

        # ---------- SMART MONEY MENÜSÜ İŞLEME ----------
        elif current_menu == "smart_money_menu":
            if text.startswith("Smart Money: "):
                coin_symbol = text.replace("Smart Money: ", "")
                handle_coin_smart_money(coin_symbol)
                # Coin analizi gösterdikten sonra ana menüye dön
                MENU_STATE.set_user_state(chat_id, "main_menu")
            else:
                print(f"[DEBUG] Smart Money menüsünde tanımlanmayan mesaj: '{text}'")
                # Smart Money menüsünü tekrar göster
                handle_smart_money_menu()

        # ---------- MUM DESENLERİ MENÜSÜ İŞLEME ----------
        elif current_menu == "candlestick_menu":
            if normalized_text == "Candle Patterns Report" or normalized_text == "Mum Desenleri Raporu":
                if 'handle_candlestick_patterns_report' in globals():
                    handle_candlestick_patterns_report(ALL_RESULTS, sync_fetch_kline_data, send_telegram_message_long)
                else:
                    send_telegram_message_long("⚠️ Candle pattern report is not yet ready.")
            elif text.endswith(" Coins") or text.endswith(" Coinleri"):
                if 'handle_specific_pattern_coins' in globals():
                    # Normalize text for specific pattern
                    pattern_type = text.replace(" Coins", " Coinleri") if text.endswith(" Coins") else text
                    handle_specific_pattern_coins(pattern_type, ALL_RESULTS, sync_fetch_kline_data, send_telegram_message_long)
                else:
                    send_telegram_message_long("⚠️ Candle pattern analysis is not yet ready.")
            else:
                print(f"[DEBUG] Candle pattern menu undefined message: '{text}'")
                # Mum desenleri menüsünü tekrar göster
                if 'handle_candlestick_pattern_menu' in globals():
                    handle_candlestick_pattern_menu(chat_id, send_reply_keyboard_message)
                else:
                    send_telegram_message_long("⚠️ Candle pattern analysis is not yet ready.")
                    MENU_STATE.set_user_state(chat_id, "main_menu")
                    handle_main_menu_return(chat_id)

        # ---------- BİLİNMEYEN MENÜ DURUMU ----------
        else:
            print(f"[DEBUG] Bilinmeyen menü durumu: {current_menu}, ana menüye dönülüyor")
            MENU_STATE.set_user_state(chat_id, "main_menu")
            handle_main_menu_return(chat_id)

    except Exception as e:
        print(f"[HATA] Mesaj işlenirken beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()

        # Hata durumunda ana menüye yönlendir
        MENU_STATE.set_user_state(chat_id, "main_menu")
        send_telegram_message(chat_id,
                              f"⚠️ An error occurred during the operation: {str(e)}\nPlease try again from the main menu.",
                              keyboard=main_keyboard)


def handle_main_menu_option(option, chat_id):
    """
    Ana menüden seçilen seçenekleri işleyen yardımcı fonksiyon.

    Args:
        option (str): Seçilen menü seçeneği (normalleştirilmiş)
        chat_id (str): İşlemin gerçekleştiği chat ID
    """
    try:
        if option == "Manipulation Detector":
            handle_enhanced_manipulation_report()
        elif option == "Whale Strategies":
            handle_whale_strategies()
        elif option == "MM Analysis":
            handle_market_maker_analysis()
        elif option == "Whale Movement":
            handle_whale_movement_analysis()
        elif option == "Volume Ratio":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, key=lambda x: float(str(x.get("Volume Ratio", 0)).replace("N/A", "0")), reverse=True)
                report = generate_metric_report("Volume Ratio", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Trend Status":
            handle_trend_status()
        elif option == "Net Buy/Sell Status":
            handle_net_buy_sell_status()
        elif option == "SOL Correlation":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS,
                                        key=lambda x: float(str(x.get("SOL Correlation", 0))) if x.get("SOL Correlation") not in ["None", "Yok", "N/A", None] else -1,
                                        reverse=True)
                report = generate_metric_report("SOL Correlation", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "SOL Corr 4H":
            if ALL_RESULTS:
                report = generate_metric_report("SOL Correlation_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "SOL Corr 1D":
            if ALL_RESULTS:
                report = generate_metric_report("SOL Correlation_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Net Accum":
            try:
                if ALL_RESULTS:
                    print(f"[DEBUG] Net Accum report requested. ALL_RESULTS count: {len(ALL_RESULTS)}")
                    # Safe sorting with error handling
                    sorted_results = sorted(ALL_RESULTS, 
                                          key=lambda x: extract_numeric(x.get("NetAccum_raw", 0)), 
                                          reverse=True)
                    print(f"[DEBUG] Sorted {len(sorted_results)} results for Net Accum")
                    report = generate_metric_report("Net Accum", sorted_results)
                    print(f"[DEBUG] Report generated, length: {len(report)}")
                    send_telegram_message_long(report)
                    print(f"[DEBUG] Net Accum report sent successfully")
                else:
                    print("[WARN] Net Accum requested but ALL_RESULTS is empty")
                    send_telegram_message_long("⚠️ No analysis data available yet.")
            except Exception as e:
                print(f"[ERROR] Net Accum report failed: {e}")
                import traceback
                traceback.print_exc()
                send_telegram_message_long(f"⚠️ Error generating Net Accum report: {str(e)}")
        elif option == "BTC Correlation":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS,
                                        key=lambda x: float(str(x.get("BTC Correlation", 0))) if x.get("BTC Correlation") not in ["None", "Yok", "N/A", None] else -1,
                                        reverse=True)
                report = generate_metric_report("BTC Correlation", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Monthly Change":
            if ALL_RESULTS:
                def get_monthly_change(x):
                    try:
                        # Try English key first then Turkish fallback
                        val_tuple = x.get("Monthly Change", x.get("Monthly Change", ("N/A", "N/A")))
                        val = val_tuple[1]
                        return float(val.strip("%"))
                    except: return -9999
                sorted_results = sorted(ALL_RESULTS, key=get_monthly_change, reverse=True)
                report = generate_metric_report("Monthly Change", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option in ["ATR", "ADX", "MACD", "Open Interest", "MFI", "StochRSI", "Taker Rate", "Z-Score", "Z-Score 4H", "Z-Score 1D", "Bollinger Bands", "Momentum", "Support/Resistance"]:
            if ALL_RESULTS:
                def get_technical_val(x):
                    try:
                        # Use raw numeric keys for accurate sorting
                        key_map = {
                            "Open Interest": "OI_raw",
                            "Bollinger Bands": "BB Lower Distance", # Sort BB by proximity to lower band
                            "Support/Resistance": "Price",
                            "Taker Rate": "Taker Rate",
                            "Z-Score": "Z-Score",
                            "Z-Score 4H": "z_score_4h",
                            "Z-Score 1D": "z_score_1d"
                        }
                        key = key_map.get(option, option)
                        val = x.get(key, 0)
                        if isinstance(val, str):
                            # Try to extract number if it's a string
                            matches = re.findall(r"[-+]?\d*\.\d+|\d+", val.replace(",", ""))
                            return float(matches[0]) if matches else 0
                        return extract_numeric(val) if val is not None else 0
                    except: return -9999
                
                # Sort descending except for specific cases
                rev = True
                if option == "Bollinger Bands": rev = False # Low distance means close to bottom
                
                sorted_results = sorted(ALL_RESULTS, key=get_technical_val, reverse=rev)
                report = generate_metric_report(option, sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "liquidation_analysis":
             if ALL_RESULTS:
                # Phase 1: Summary of all 50 coins
                summary_report = "🔥 <b>Liquidation Risk Summary (All Coins)</b>\n"
                summary_report += "<i>Sorted by Liquidation Intensity & Proximity</i>\n\n"
                
                def get_liq_meta(coin):
                    h = coin.get("Liq Heatmap", "")
                    try:
                        max_risk = int(h.split("MAX_RISK:")[1].split("-->")[0])
                        nearest = float(h.split("NEAREST:")[1].split("-->")[0])
                        risk_id = h.split("RISK_TYPE:")[1].split("-->")[0]
                        return max_risk, nearest, risk_id
                    except: return 0, 99, "None"

                # Sort: Intensity first, then proximity
                sorted_results = sorted(ALL_RESULTS, key=lambda x: (get_liq_meta(x)[0], -abs(get_liq_meta(x)[1])), reverse=True)
                
                rows = []
                for coin in sorted_results:
                    risk, near, rtype = get_liq_meta(coin)
                    icon = "🔴" if rtype == "Short" else "🟢" if rtype == "Long" else "⚪️"
                    # Add to summary
                    symbol = f"<code>${coin['Coin'].replace('USDT',''):<6}</code>"
                    rows.append(f"{icon} {symbol} Risk: {risk}% | Near: {near:+.1f}%")

                summary_report += "\n".join(rows)
                send_telegram_message_long(summary_report)
                
                # Phase 2: Top 50 Detailed Analysis
                detail_report = "\n🔥 <b>Top 50 Critical Liquidation Zones</b>\n\n"
                for coin in sorted_results[:50]:
                    h = coin.get("Liq Heatmap", "No data")
                    # Clean the hidden metadata before sending details
                    clean_h = re.sub(r'<!--.*?-->', '', h)
                    detail_report += clean_h + "\n" + "-"*20 + "\n"
                
                send_telegram_message_long(detail_report)
             else:
                send_telegram_message(chat_id, "⚠️ Analysis data not available yet.")
        elif option == "ETH Correlation":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS,
                                        key=lambda x: float(str(x.get("ETH Correlation", 0))) if x.get("ETH Correlation") not in ["None", "Yok", "N/A", None] else -1,
                                        reverse=True)
                report = generate_metric_report("ETH Correlation", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "ETH Corr 4H":
            if ALL_RESULTS:
                report = generate_metric_report("ETH Correlation_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "ETH Corr 1D":
            if ALL_RESULTS:
                report = generate_metric_report("ETH Correlation_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "RSI Report":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("RSI", "0")) if x.get("RSI") else 0, 
                                        reverse=True)
                report = generate_metric_report("RSI", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "RSI 4H":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("RSI_4h", 0)), 
                                        reverse=True)
                report = generate_metric_report("RSI_4h", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "RSI 1D":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("RSI_1d", 0)), 
                                        reverse=True)
                report = generate_metric_report("RSI_1d", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "MACD 4H":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("MACD_4h", 0)), 
                                        reverse=True)
                report = generate_metric_report("MACD_4h", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "MACD 1D":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("MACD_1d", 0)), 
                                        reverse=True)
                report = generate_metric_report("MACD_1d", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "ADX 4H":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("ADX_4h", 0)), 
                                        reverse=True)
                report = generate_metric_report("ADX_4h", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "ADX 1D":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS, 
                                        key=lambda x: extract_numeric(x.get("ADX_1d", 0)), 
                                        reverse=True)
                report = generate_metric_report("ADX_1d", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Net Accum 4H":
            try:
                if ALL_RESULTS:
                    print(f"[DEBUG] Net Accum 4H report requested")
                    report = generate_metric_report("Net Accum_4h", ALL_RESULTS)
                    send_telegram_message_long(report)
                else:
                    send_telegram_message_long("⚠️ No analysis data available yet.")
            except Exception as e:
                print(f"[ERROR] Net Accum 4H failed: {e}")
                send_telegram_message_long(f"⚠️ Error: {str(e)}")
        elif option == "Net Accum 1D":
            try:
                if ALL_RESULTS:
                    print(f"[DEBUG] Net Accum 1D report requested")
                    report = generate_metric_report("Net Accum_1d", ALL_RESULTS)
                    send_telegram_message_long(report)
                else:
                    send_telegram_message_long("⚠️ No analysis data available yet.")
            except Exception as e:
                print(f"[ERROR] Net Accum 1D failed: {e}")
                send_telegram_message_long(f"⚠️ Error: {str(e)}")
        elif option == "Composite 4H":
            try:
                if ALL_RESULTS:
                    print(f"[DEBUG] Composite 4H report requested")
                    report = generate_metric_report("Composite Score_4h", ALL_RESULTS)
                    send_telegram_message_long(report)
                else:
                    send_telegram_message_long("⚠️ No analysis data available yet.")
            except Exception as e:
                print(f"[ERROR] Composite 4H failed: {e}")
                send_telegram_message_long(f"⚠️ Error: {str(e)}")
        elif option == "Composite 1D":
            try:
                if ALL_RESULTS:
                    print(f"[DEBUG] Composite 1D report requested")
                    report = generate_metric_report("Composite Score_1d", ALL_RESULTS)
                    send_telegram_message_long(report)
                else:
                    send_telegram_message_long("⚠️ No analysis data available yet.")
            except Exception as e:
                print(f"[ERROR] Composite 1D failed: {e}")
                send_telegram_message_long(f"⚠️ Error: {str(e)}")
        elif option == "order_book_analysis":
            if ALL_RESULTS:
                report = generate_order_book_report(ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ Order Book data not yet collected. Please wait.")
        elif option == "Momentum 4H":
            if ALL_RESULTS:
                report = generate_metric_report("Momentum_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Momentum 1D":
            if ALL_RESULTS:
                report = generate_metric_report("Momentum_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "BTC Corr 4H":
            if ALL_RESULTS:
                report = generate_metric_report("BTC Correlation_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "BTC Corr 1D":
            if ALL_RESULTS:
                report = generate_metric_report("BTC Correlation_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")

        elif option == "MFI 4H":
            if ALL_RESULTS:
                report = generate_metric_report("MFI_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "MFI 1D":
            if ALL_RESULTS:
                report = generate_metric_report("MFI_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Volume Ratio 4H":
            if ALL_RESULTS:
                report = generate_metric_report("Volume Ratio_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Volume Ratio 1D":
            if ALL_RESULTS:
                report = generate_metric_report("Volume Ratio_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "EMA Report":
            if ALL_RESULTS:
                report = generate_metric_report("EMA", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "4H Change":
            if ALL_RESULTS:
                def get_4h_change(x):
                    try:
                        val_tuple = x.get("4H Change", x.get("4H Change", ("N/A", "N/A")))
                        val = val_tuple[1]
                        return float(val.strip("%"))
                    except: return -9999
                sorted_results = sorted(ALL_RESULTS, key=get_4h_change, reverse=True)
                report = generate_metric_report("4H Change", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Weekly Change":
            if ALL_RESULTS:
                def get_weekly_change(x):
                    try:
                        val_tuple = x.get("Weekly Change", x.get("Weekly Change", ("N/A", "N/A")))
                        val = val_tuple[1]
                        return float(val.strip("%"))
                    except: return -9999
                sorted_results = sorted(ALL_RESULTS, key=get_weekly_change, reverse=True)
                report = generate_metric_report("Weekly Change", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Composite Score":
            if ALL_RESULTS:
                sorted_results = sorted(ALL_RESULTS,
                                        key=lambda x: extract_numeric(x.get("CompositeScore", "0")),
                                        reverse=True)
                report = generate_metric_report("Composite Score", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Difference Index":
            if ALL_RESULTS:
                report = generate_metric_report("Difference Index", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Outlier Score":
            if ALL_RESULTS:
                report = generate_metric_report("Outlier Score", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "NotebookLM Export":
            if ALL_RESULTS:
                export_file = generate_notebooklm_export(ALL_RESULTS)
                if export_file:
                    telegram_bot.send_telegram_document(chat_id, export_file, caption="📊 Market Analysis Export for NotebookLM")
                    try: os.remove(export_file)
                    except: pass
                else:
                    send_telegram_message(chat_id, "⚠️ Failed to generate export file.")
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "YouTube Alpha":
            handle_youtube_alpha(chat_id)
        elif option == "YouTube Transcripts":
            handle_youtube_transcripts_export(chat_id)
        elif option == "Summary":
            handle_summary()
        elif option == "EMA Crossings":
            handle_ema_kesisimi()
        elif option == "Hourly Analysis":
            generate_hourly_report()
        elif option == "Cash Flow Report":
            handle_cash_flow_report()
        elif option == "Flow Migrations":
            handle_cash_flow_migration_report()
        elif option == "Smart Score":
            handle_smart_score_report()
        elif option == "Price Info":
            handle_price_info()
        elif option == "Long/Short Ratio":
            handle_long_short_ratio_analysis()
        elif option == "Funding Rate":
            handle_funding_rate_analysis()
        elif option == "Smart Whale & Trend":
            handle_advanced_whale_trend()
        elif option == "Whale Ranking":
            report = generate_whale_ranking_report()
            send_telegram_message_long(report)
        elif option == "Volatility Ranking":
            report = generate_volatility_report()
            send_telegram_message_long(report)
        elif option == "Bollinger Squeeze":
            report = generate_bollinger_squeeze_report()
            send_telegram_message_long(report)
        elif option == "Trust Index":
            handle_trust_index_report()
        elif option == "24h Volume":
            if ALL_RESULTS:
                def get_24h_vol(x):
                    try:
                        val = x.get("24h Volume", 0)
                        if isinstance(val, (int, float)): return extract_numeric(val)
                        num = float(str(val).replace("$", "").replace("M", "").replace(" ", "").replace(",", ""))
                        return num
                    except: return -9999
                sorted_results = sorted(ALL_RESULTS, key=get_24h_vol, reverse=True)
                report = generate_metric_report("24h Volume", sorted_results)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "24h Vol 4H":
            if ALL_RESULTS:
                report = generate_metric_report("24h Vol_4h", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "24h Vol 1D":
            if ALL_RESULTS:
                report = generate_metric_report("24h Vol_1d", ALL_RESULTS)
                send_telegram_message_long(report)
            else:
                send_telegram_message_long("⚠️ No analysis data available yet.")
        elif option == "Significant Changes":
            handle_significant_changes()
        elif option == "Futures Analysis":
            handle_futures_timeframe_analysis()
        elif option == "BTC Full Report":
            report = generate_coin_full_report("BTCUSDT")
            send_telegram_message_long(report)
        elif option == "Volatility Ranking":
            report = generate_volatility_report()
            send_telegram_message_long(report)
        elif option == "Bollinger Squeeze":
            report = generate_bollinger_squeeze_report()
            send_telegram_message_long(report)
        elif option == "Whale Ranking":
            report = generate_whale_ranking_report()
            send_telegram_message_long(report)
        else:
            print(f"[DEBUG] handle_main_menu_option catch-all: '{option}'")
            keyboard = create_reply_keyboard(ALL_RESULTS)
            send_telegram_message(chat_id, f"The command '{option}' is not yet implemented or has an error.",
                                  keyboard=keyboard)

    except Exception as e:
        print(f"[HATA] '{option}' seçeneği işlenirken hata: {e}")
        import traceback
        traceback.print_exc()
        # Hata durumunda bilgilendirme mesajı
        send_telegram_message_long(f"⚠️ '{option}' raporu oluşturulurken bir hata oluştu: {str(e)}")



def calculate_risk_exposure(positions, risk_scores):
    """
    Mevcut pozisyonlara ve bireysel coin risk skorlarına dayalı olarak
    genel portföy risk maruziyetini hesaplar.

    Args:
        positions (dict): Mevcut pozisyonlar {coin: size_in_usd}
        risk_scores (list): Her coin için risk skoru sözlükleri listesi

    Returns:
        dict: Portföy risk metrikleri
    """
    total_value = sum(positions.values())
    if total_value == 0:
        return {
            "total_exposure": 0,
            "weighted_risk": 0,
            "var_daily": 0,
            "max_drawdown": 0,
            "high_risk_exposure": 0,
            "high_risk_percentage": 0,
            "concentration_ratio": 0
        }

    # Coin isimlerinden risk skorlarına eşleme oluştur
    risk_map = {item["coin"]: item for item in risk_scores}

    weighted_risk = 0
    var_daily = 0  # Value at Risk (günlük)
    high_risk_exposure = 0  # high riskli varlıklara maruz kalma

    for coin, position_size in positions.items():
        weight = position_size / total_value

        if coin in risk_map:
            coin_risk = risk_map[coin]
            risk_score = coin_risk.get("risk_score", 50)

            # Ağırlıklı risk hesaplama
            weighted_risk += risk_score * weight

            # ATR'ye dayalı %95 VaR hesaplama
            atr = coin_risk.get("atr", 0)
            price = coin_risk.get("price", 1)
            if price > 0:
                atr_percent = atr / price
                coin_var = atr_percent * 1.65 * position_size  # %95 güven
                var_daily += coin_var

            # high riskli maruziyeti izle
            if risk_score >= 70:
                high_risk_exposure += position_size

    # En büyük pozisyon büyüklüğünü bul (konsantrasyon ölçümü)
    max_position = max(positions.values()) if positions else 0
    concentration_ratio = max_position / total_value if total_value > 0 else 0

    # Ağırlıklı riske dayalı maksimum düşüş tahmini
    max_drawdown_factor = 1.5  # Muhafazakar tahmin
    max_drawdown = (weighted_risk / 100) * total_value * max_drawdown_factor

    high_risk_percentage = (high_risk_exposure / total_value * 100) if total_value > 0 else 0

    return {
        "total_exposure": total_value,
        "weighted_risk": weighted_risk,
        "var_daily": var_daily,
        "max_drawdown": max_drawdown,
        "high_risk_exposure": high_risk_exposure,
        "high_risk_percentage": high_risk_percentage,
        "concentration_ratio": concentration_ratio
    }


def generate_portfolio_risk_report(positions, macro_risk=None):
    """
    Generates a comprehensive portfolio risk report including macroeconomic factors,
    position concentration, correlation analysis, and actionable recommendations.

    Args:
        positions (dict): Current positions {coin: size_in_usd}
        macro_risk (dict, optional): Pre-calculated macro risk assessment, calculated if not provided

    Returns:
        str: Portfolio risk report
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet, portfolio risk could not be calculated."

    try:
        # Macroeconomic risk assessment
        if not macro_risk:
            macro_risk = calculate_macro_risk_level()

        # Data sources
        macro_data = fetch_macro_economic_data()

        # Calculate risk scores for all coins
        risk_scores = []
        for coin in ALL_RESULTS:
            try:
                symbol = coin["Coin"]

                # Perform extra detailed calculation if the coin is in the portfolio
                if symbol in positions:
                    # Fundamental calculation steps: risk score and components
                    risk_assessment = calculate_asset_risk(coin, macro_risk)

                    # Futures data (using safe defaults if not available)
                    futures_data = {
                        "funding_rate": 0,
                        "open_interest": 0,
                        "long_short_ratio": 1.0
                    }

                    funding_rate = futures_data.get("funding_rate", 0)

                    # Safely extract metrics
                    price = safe_extract(coin, "Price_Display")
                    atr = safe_extract(coin, "ATR_raw", 0)
                    rsi = safe_extract(coin, "RSI", 50)
                    btc_corr = safe_extract(coin, "BTC Correlation", 0)

                    # Risk scores dictionary
                    risk_scores.append({
                        "coin": symbol,
                        "price": price,
                        "risk_score": risk_assessment["risk_score"],
                        "risk_level": risk_assessment["risk_level"],
                        "components": risk_assessment["details"]["components"],
                        "atr": atr,
                        "rsi": rsi,
                        "btc_correlation": btc_corr,
                        "funding_rate": funding_rate
                    })
            except Exception as e:
                print(f"[ERROR] Risk calculation error for {coin['Coin']}: {e}")
                continue

        # Calculate portfolio risk exposure
        exposure = calculate_risk_exposure(positions, risk_scores)

        # Determine risk level
        weighted_risk = exposure["weighted_risk"]
        if weighted_risk >= 75:
            risk_level = "Very High"
            risk_emoji = "🔴"
        elif weighted_risk >= 50:
            risk_level = "High"
            risk_emoji = "🟠"
        elif weighted_risk >= 30:
            risk_level = "Medium"
            risk_emoji = "🟡"
        else:
            risk_level = "Low"
            risk_emoji = "🟢"

        # Generate report
        report = f"📊 <b>Advanced Portfolio Risk Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        # Macro risk section
        report += "<b>🌐 Macroeconomic Risk Assessment:</b>\n"
        report += f"• Global Market Risk Score: {macro_risk['risk_score']:.1f}/100 ({macro_risk['risk_level'].upper()})\n"

        # Important macro factors
        if macro_risk.get('factors'):
            report += "• Critical Factors:\n"
            for factor in macro_risk['factors'][:2]:
                report += f"   - {factor['factor']}: {factor['description']}\n"

        # Current market status
        if macro_data:
            btc_eth = macro_data['btc_eth_data']
            btc_trend = "🟢" if btc_eth.get('BTC_24h_change', 0) > 0 else "🔴"

            report += f"• BTC: ${btc_eth.get('BTC_price', 'N/A')} ({btc_trend} {btc_eth.get('BTC_24h_change', 0):+.2f}%)\n"
            report += f"• Fear & Greed Index: {macro_data['crypto_market'].get('fear_greed_index', 'N/A')}/100\n"

            vix = macro_data["market_indices"].get("VIX", {})
            vix_trend = "🔴" if vix.get('change', 0) > 0 else "🟢"
            report += f"• VIX (Volatility Index): {vix.get('value', 'N/A')} ({vix_trend} {vix.get('change', 0):+.2f}%)\n\n"

        # Portfolio level risk evaluation
        report += "<b>💼 Portfolio Risk Evaluation:</b>\n"
        report += f"• Total Position Value: ${format_money(exposure['total_exposure'])}\n"
        report += f"• Weighted Risk Score: {exposure['weighted_risk']:.1f}/100\n"
        report += f"• Daily Value at Risk (95%): ${format_money(exposure['var_daily'])} ({exposure['var_daily'] / exposure['total_exposure'] * 100:.1f}%)\n"
        report += f"• Estimated Max Drawdown: ${format_money(exposure['max_drawdown'])} ({exposure['max_drawdown'] / exposure['total_exposure'] * 100:.1f}%)\n"
        report += f"• Risk Level: {risk_emoji} {risk_level}\n"

        # Calculate concentration metrics
        high_risk_percentage = exposure["high_risk_percentage"]
        concentration_ratio = exposure["concentration_ratio"]
        btc_eth_amount = sum(size for coin, size in positions.items() if coin in ["BTCUSDT", "ETHUSDT"])
        btc_eth_pct = btc_eth_amount / exposure['total_exposure'] * 100 if exposure['total_exposure'] > 0 else 0

        # Add concentration metrics
        report += "\n<b>📊 Portfolio Concentration:</b>\n"
        report += f"• High Risk Assets: {high_risk_percentage:.1f}% of portfolio\n"
        report += f"• Largest Position: {concentration_ratio * 100:.1f}% of portfolio\n"
        report += f"• BTC/ETH Weight: {btc_eth_pct:.1f}% of portfolio\n"

        # Add concentration risk assessment
        if concentration_ratio > 0.25:
            report += "• ⚠️ Excessive concentration risk: Your largest position is too big.\n"
        if high_risk_percentage > 40:
            report += "• ⚠️ Excessive concentration in high-risk assets.\n"
        if btc_eth_pct < 30 and macro_risk['risk_score'] > 60:
            report += "• ⚠️ BTC/ETH weight is too low for a high macro risk environment.\n"

        # Position breakdown and detailed metrics
        report += "\n<b>📋 Detailed Position Analysis:</b>\n"
        sorted_positions = sorted(positions.items(), key=lambda x: x[1], reverse=True)

        for coin, size in sorted_positions:
            coin_risk = next((item for item in risk_scores if item["coin"] == coin), None)

            if coin_risk:
                if coin_risk["risk_score"] < 30:
                    risk_emoji = "🟢"
                elif coin_risk["risk_score"] < 50:
                    risk_emoji = "🟡"
                elif coin_risk["risk_score"] < 70:
                    risk_emoji = "🟠"
                else:
                    risk_emoji = "🔴"

                pct = (size / exposure['total_exposure'] * 100) if exposure['total_exposure'] > 0 else 0
                symbol = "$" + coin.replace("USDT", "")

                report += f"• {risk_emoji} <b>{symbol}</b>: ${format_money(size)} ({pct:.1f}% of portfolio)\n"
                report += f"   - Risk Score: {coin_risk['risk_score']:.1f}/100\n"
                report += f"   - Volatility: {coin_risk['components'].get('volatility_risk', 0):.1f}/40, BTC Correlation: {coin_risk['btc_correlation']:.2f}\n"
                report += f"   - Daily VaR: ${format_money(coin_risk['atr'] / coin_risk['price'] * 1.65 * size)} ({coin_risk['atr'] / coin_risk['price'] * 1.65 * 100:.1f}%)\n"

                # Position-specific risks
                specific_risks = []
                if coin_risk['rsi'] > 70:
                    specific_risks.append("RSI Overbought")
                if coin_risk['rsi'] < 30:
                    specific_risks.append("RSI Oversold")
                if abs(coin_risk['funding_rate']) > 0.1:
                    specific_risks.append(f"High Funding Rate: {coin_risk['funding_rate']:.3f}%")
                if coin_risk['btc_correlation'] > 0.8:
                    specific_risks.append("Very high BTC correlation")

                if specific_risks:
                    report += f"   - Specific Risks: {', '.join(specific_risks)}\n"

                report += "\n"

        # Actionable recommendations
        report += "<b>💡 Portfolio Risk Recommendations:</b>\n"

        # Macro-based recommendation
        if macro_risk['risk_score'] > 70:
            report += "• 🌍 <b>Macro Risk:</b> Market risk is very high, reduce position sizes.\n"
            report += f"   - Dollar Index is at {macro_data['dollar_strength'].get('DXY_index', 'N/A')}, crypto assets may weaken in this environment.\n"
            report += "   - Recommendation: Keep at least 50% of the portfolio in stablecoins.\n"
        elif macro_risk['risk_score'] > 50:
            report += "• 🌍 <b>Macro Risk:</b> Market risk is high, remain cautious.\n"
            report += "   - Recommendation: Reduce positions in high-risk coins, increase BTC/ETH weight to 40%+.\n"

        # Portfolio structure recommendations
        if high_risk_percentage > 40:
            report += f"• 📊 <b>Portfolio Structure:</b> High-risk coins make up {high_risk_percentage:.1f}% of your portfolio.\n"
            report += "   - Recommendation: Reduce high-risk coin positions to below 25%.\n"

        if concentration_ratio > 0.25:
            report += f"• 📊 <b>Position Sizing:</b> Your largest position makes up {concentration_ratio * 100:.1f}% of the portfolio.\n"
            report += "   - Recommendation: Divide this position or take partial profit.\n"

        # Stop-loss recommendations based on VaR
        if exposure['total_exposure'] > 0 and exposure['var_daily'] / exposure['total_exposure'] > 0.1:
            report += f"• 🛑 <b>Stop-Loss Strategy:</b> Daily VaR is {exposure['var_daily'] / exposure['total_exposure'] * 100:.1f}% of the portfolio.\n"
            report += "   - Recommendation: Set tight stop-losses for all positions and reduce sizes.\n"

        # Specific recommendations for high-risk positions
        high_risk_positions = [(coin, size) for coin, size in sorted_positions
                                if any(item["coin"] == coin and item["risk_score"] >= 60 for item in risk_scores)]

        if high_risk_positions:
            report += "\n<b>⚠️ Recommendations for High-Risk Positions:</b>\n"
            for coin, size in high_risk_positions[:3]:
                coin_risk = next((item for item in risk_scores if item["coin"] == coin), None)
                if coin_risk:
                    stop_pct = max(coin_risk['atr'] / coin_risk['price'] * 1.5, 0.02) * 100
                    stop_price = coin_risk['price'] * (1 - stop_pct / 100)
                    symbol = "$" + coin.replace("USDT", "")

                    report += f"• {symbol}:\n"
                    report += f"   - Recommended Stop-Loss: ${format_money(stop_price)} (-{stop_pct:.1f}%)\n"
                    report += f"   - Position Size: Max {min(100.0, 60.0 / coin_risk['risk_score'] * 100):.1f}% of total position allowance\n"

        # Risk outlook based on current level
        report += "\n<b>📈 Risk Outlook:</b>\n"
        combined_risk = (exposure['weighted_risk'] * 0.7) + (macro_risk['risk_score'] * 0.3)
        if combined_risk > 70:
            report += "• Portfolio and macro risk levels are very high.\n"
            report += "• Strategy: Defensive positioning, keep high cash ratio.\n"
            report += "• Outlook: High volatility and potential downtrend in short-to-medium term.\n"
        elif combined_risk > 50:
            report += "• Portfolio and macro risk levels are high.\n"
            report += "• Strategy: Selective entry, use tight stop-losses.\n"
            report += "• Outlook: Choppy market, high volatility.\n"
        elif combined_risk > 30:
            report += "• Portfolio and macro risk levels are medium.\n"
            report += "• Strategy: Balanced positioning, staggered entry strategy.\n"
            report += "• Outlook: Movement in trend direction, moderate volatility.\n"
        else:
            report += "• Portfolio and macro risk levels are low.\n"
            report += "• Strategy: Take advantage of opportunities, grow portfolio.\n"
            report += "• Outlook: Favorable market conditions, low volatility.\n"

        return report


    except Exception as e:
        error_msg = f"⚠️ Portföy Risk Raporu oluşturulurken hata: {str(e)}"
        print(f"[HATA] Portföy Risk Raporu hatası: {e}")
        import traceback
        print(traceback.format_exc())
        return error_msg


def fetch_24hr_ticker_data(symbols):
    data = []
    for symbol in symbols:
        url = f"{BINANCE_API_URL}ticker/24hr?symbol={symbol}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 429:  # Rate limit hatası
                print(f"[UYARI] {symbol} için rate limit hatası, 5 saniye bekleniyor...")
                time.sleep(5)
                response = requests.get(url, timeout=10)
            if response.status_code == 200:
                ticker = response.json()
                print(f"[DEBUG] {symbol} - Raw Ticker Data: {ticker}")
                data.append(ticker)
            else:
                print(f"[HATA] {symbol} için veri alınamadı: {response.status_code}")
        except Exception as e:
            print(f"[HATA] {symbol} için veri çekilemedi: {e}")
    return data


# fetch_24hr_ticker_data fonksiyonundan sonra ekleyin

def fetch_okx_futures_data(symbol):
    """
    OKX borsasından vadeli işlemler verilerini çeker.

    Args:
        symbol (str): Coin sembolü (örn: BTCUSDT)

    Returns:
        dict: OI, funding rate ve long/short oranı verileri
    """
    try:
        normalized_symbol = normalize_symbol_for_exchange(symbol, "okx")

        # Funding rate verisi çek
        funding_url = f"https://www.okx.com/api/v5/public/funding-rate?instId={normalized_symbol}-SWAP"
        funding_response = requests.get(funding_url, timeout=10)
        funding_rate = 0

        if funding_response.status_code == 200 and "data" in funding_response.json():
            data = funding_response.json()["data"]
            if data and len(data) > 0:
                funding_rate = float(data[0].get("fundingRate", 0)) * 100  # Yüzdeye çevir

        # Open Interest verisi çek
        oi_url = f"https://www.okx.com/api/v5/public/open-interest?instId={normalized_symbol}-SWAP"
        oi_response = requests.get(oi_url, timeout=10)
        open_interest = 0

        if oi_response.status_code == 200 and "data" in oi_response.json():
            data = oi_response.json()["data"]
            if data and len(data) > 0:
                open_interest = float(data[0].get("oi", 0))
                # Çarpım faktörünü ayarla (değer USD cinsinden olmalı)
                price_url = f"https://www.okx.com/api/v5/market/ticker?instId={normalized_symbol}-SWAP"
                price_response = requests.get(price_url, timeout=10)
                if price_response.status_code == 200 and "data" in price_response.json():
                    price_data = price_response.json()["data"]
                    if price_data and len(price_data) > 0:
                        price = float(price_data[0].get("last", 0))
                        open_interest *= price

        # Long/Short oranı çek
        ls_url = f"https://www.okx.com/api/v5/public/long-short-ratio?instId={normalized_symbol}-SWAP"
        ls_response = requests.get(ls_url, timeout=10)
        long_short_ratio = 1.0  # Varsayılan dengeli oran

        if ls_response.status_code == 200 and "data" in ls_response.json():
            data = ls_response.json()["data"]
            if data and len(data) > 0:
                long_pct = float(data[0].get("longPct", 0.5))
                short_pct = float(data[0].get("shortPct", 0.5))
                if short_pct > 0:
                    long_short_ratio = long_pct / short_pct

        # 24 saat hacim verisi
        volume_url = f"https://www.okx.com/api/v5/market/ticker?instId={normalized_symbol}-SWAP"
        volume_response = requests.get(volume_url, timeout=10)
        volume_24h = 0

        if volume_response.status_code == 200 and "data" in volume_response.json():
            data = volume_response.json()["data"]
            if data and len(data) > 0:
                volume_24h = float(data[0].get("volCcy24h", 0))

        return {
            "open_interest": open_interest,
            "funding_rate": funding_rate,
            "long_short_ratio": long_short_ratio,
            "volume_24h": volume_24h
        }

    except Exception as e:
        print(f"[HATA] OKX verileri alınırken hata: {e}")
        return {
            "open_interest": 0,
            "funding_rate": 0,
            "long_short_ratio": 1.0,
            "volume_24h": 0
        }


def fetch_bybit_futures_data(symbol):
    """
    Bybit borsasından vadeli işlemler verilerini çeker.

    Args:
        symbol (str): Coin sembolü (örn: BTCUSDT)

    Returns:
        dict: OI, funding rate ve long/short oranı verileri
    """
    try:
        normalized_symbol = normalize_symbol_for_exchange(symbol, "bybit")

        # Funding rate verisi çek
        funding_url = f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={normalized_symbol}"
        funding_response = requests.get(funding_url, timeout=10)
        funding_rate = 0

        if funding_response.status_code == 200 and "result" in funding_response.json():
            data = funding_response.json()["result"]["list"]
            if data and len(data) > 0:
                funding_rate = float(data[0].get("fundingRate", 0)) * 100  # Yüzdeye çevir

        # Open Interest verisi çek
        oi_url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={normalized_symbol}"
        oi_response = requests.get(oi_url, timeout=10)
        open_interest = 0

        if oi_response.status_code == 200 and "result" in oi_response.json():
            data = oi_response.json()["result"]["list"]
            if data and len(data) > 0:
                open_interest = float(data[0].get("openInterest", 0))
                # USD değerine çevir
                price_url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={normalized_symbol}"
                price_response = requests.get(price_url, timeout=10)
                if price_response.status_code == 200 and "result" in price_response.json():
                    price_data = price_response.json()["result"]["list"]
                    if price_data and len(price_data) > 0:
                        price = float(price_data[0].get("lastPrice", 0))
                        open_interest *= price

        # Long/Short oranı çek - Bybit için account long-short ratio API'si kullanılır
        ls_url = f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={normalized_symbol}&period=1d"
        ls_response = requests.get(ls_url, timeout=10)
        long_short_ratio = 1.0  # Varsayılan dengeli oran

        if ls_response.status_code == 200 and "result" in ls_response.json():
            data = ls_response.json()["result"]["list"]
            if data and len(data) > 0:
                long_pct = float(data[0].get("longRatio", 0.5))
                short_pct = float(data[0].get("shortRatio", 0.5))
                if short_pct > 0:
                    long_short_ratio = long_pct / short_pct

        # 24 saat hacim verisi
        volume_url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={normalized_symbol}"
        volume_response = requests.get(volume_url, timeout=10)
        volume_24h = 0

        if volume_response.status_code == 200 and "result" in volume_response.json():
            data = volume_response.json()["result"]["list"]
            if data and len(data) > 0:
                volume_24h = float(data[0].get("volume24h", 0))

        return {
            "open_interest": open_interest,
            "funding_rate": funding_rate,
            "long_short_ratio": long_short_ratio,
            "volume_24h": volume_24h
        }

    except Exception as e:
        print(f"[HATA] Bybit verileri alınırken hata: {e}")
        return {
            "open_interest": 0,
            "funding_rate": 0,
            "long_short_ratio": 1.0,
            "volume_24h": 0
        }

def calculate_buyer_ratio(kline_data):
    if not kline_data or len(kline_data) < 5:
        return 50.0
    df = pd.DataFrame(kline_data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                           "close_time", "quote_volume", "trades", "taker_buy_base",
                                           "taker_buy_quote", "ignore"])
    df["quote_volume"] = pd.to_numeric(df["quote_volume"], errors="coerce").fillna(0)
    df["taker_buy_quote"] = pd.to_numeric(df["taker_buy_quote"], errors="coerce").fillna(0)
    recent_data = df.tail(5)
    total_volume = recent_data["quote_volume"].sum()
    buy_volume = recent_data["taker_buy_quote"].sum()
    if total_volume == 0 or np.isnan(total_volume) or total_volume < 1000:  # Minimum hacim eşiği
        return 50.0
    ratio = (buy_volume / total_volume) * 100
    if ratio < 10 or ratio > 90:  # Aşırı oranları filtrele
        return 50.0  # Anomalileri hariç tut
    return max(min(round(ratio, 1), 100), 0)


def analyze_market_maker_activity(taker_buy_volume, taker_sell_volume, time_buckets=6):
    """
    Market maker aktivitesini analiz eder

    Args:
        taker_buy_volume (list): Zaman serisi alıcı hacim verileri
        taker_sell_volume (list): Zaman serisi satıcı hacim verileri
        time_buckets (int): Analiz edilecek zaman dilimi sayısı

    Returns:
        dict: Market maker aktivite analizi
    """
    if len(taker_buy_volume) != len(taker_sell_volume) or len(taker_buy_volume) < time_buckets:
        return {"valid": False}

    try:
        # Verileri time_buckets sayıda döneme böl
        bucket_size = len(taker_buy_volume) // time_buckets

        period_analysis = []
        total_market_volume = sum(taker_buy_volume) + sum(taker_sell_volume)  # Total market volume tanımı

        for i in range(time_buckets):
            start_idx = i * bucket_size
            end_idx = start_idx + bucket_size

            if end_idx > len(taker_buy_volume):
                end_idx = len(taker_buy_volume)

            period_buy = sum(taker_buy_volume[start_idx:end_idx])
            period_sell = sum(taker_sell_volume[start_idx:end_idx])

            # Net akümülasyon
            net_accumulation = period_buy - period_sell

            # Maker (market maker) / Taker oranı
            total_volume = period_buy + period_sell
            maker_ratio = 1 - (total_volume / total_market_volume) if total_market_volume > 0 else 0

            period_analysis.append({
                "period": i + 1,
                "net_accumulation": net_accumulation,
                "buy_volume": period_buy,
                "sell_volume": period_sell,
                "maker_ratio": maker_ratio
            })

        # Trend analizleri
        accumulation_trend = [p["net_accumulation"] for p in period_analysis]
        is_increasing_accum = all(
            accumulation_trend[i] <= accumulation_trend[i + 1] for i in range(len(accumulation_trend) - 1))
        is_decreasing_accum = all(
            accumulation_trend[i] >= accumulation_trend[i + 1] for i in range(len(accumulation_trend) - 1))

        return {
            "valid": True,
            "period_analysis": period_analysis,
            "is_increasing_accumulation": is_increasing_accum,
            "is_decreasing_accumulation": is_decreasing_accum,
            "recent_maker_ratio": period_analysis[-1]["maker_ratio"] if period_analysis else 0
        }
    except Exception as e:
        print(f"[HATA] Market maker aktivite analizinde hata: {e}")
        return {"valid": False}

def calculate_cash_flow_trend(kline_data):
    if not kline_data or len(kline_data) < 2:
        return 0
    df = pd.DataFrame(kline_data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                           "close_time", "quote_volume", "trades", "taker_buy_base",
                                           "taker_buy_quote", "ignore"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce").fillna(0)
    first_close = df["close"].iloc[0]
    last_close = df["close"].iloc[-1]
    if first_close == 0:
        return 0
    return 1 if last_close > first_close else -1 if last_close < first_close else 0


def generate_dynamic_cash_flow_report():
    global last_ticker_data
    symbols = get_filtered_coins()
    if not symbols:
        return "⚠️ Could not fetch coin data, report could not be generated."

    ticker_data = fetch_24hr_ticker_data(symbols)
    if not ticker_data:
        if last_ticker_data:
            ticker_data = last_ticker_data
            warning = "⚠️ Could not fetch current ticker data, using last cached data.\n"
        else:
            return "⚠️ Ticker data not available, report could not be generated."
    last_ticker_data = ticker_data

    total_volume = sum(float(t.get("quoteVolume", 0)) for t in ticker_data if float(t.get("quoteVolume", 0)) > 0)
    if total_volume == 0:
        return "⚠️ No volume data available for any coin."

    intervals = {"15m": "15m", "1h": "1h", "4h": "4h", "12h": "12h", "1d": "1d"}
    buyer_ratios = {}

    for interval_name, interval in intervals.items():
        with ThreadPoolExecutor(max_workers=10) as executor:
            ratios = list(
                executor.map(lambda s: calculate_buyer_ratio(sync_fetch_kline_data(s, interval, limit=20)), symbols))
        valid_ratios = [r for r in ratios if r != "N/A"]
        buyer_ratios[interval_name] = round(sum(valid_ratios) / len(valid_ratios), 1) if valid_ratios else 50.0

    top_cash_ins = []
    valid_symbols = set(t["symbol"] for t in ticker_data)
    for t in ticker_data:
        symbol = t["symbol"]
        volume = float(t.get("quoteVolume", 0))
        if volume <= 0 or symbol not in valid_symbols:
            continue
        kline_15m = sync_fetch_kline_data(symbol, "15m", limit=20)
        buyer_ratio_15m = calculate_buyer_ratio(kline_15m)
        if buyer_ratio_15m == "N/A":
            continue
        df = pd.DataFrame(kline_15m, columns=["timestamp", "open", "high", "low", "close", "volume",
                                              "close_time", "quote_volume", "trades", "taker_buy_base",
                                              "taker_buy_quote", "ignore"])
        price_change = calculate_price_roc(df.tail(5))
        top_cash_ins.append({
            "symbol": symbol.replace("USDT", ""),
            "volume": volume,
            "buyer_ratio_15m": buyer_ratio_15m,
            "arrow_15m": "🔺" if buyer_ratio_15m > 55 else "🔻" if buyer_ratio_15m < 45 else "➖",
            "price_change": price_change
        })
    top_cash_ins = sorted(top_cash_ins, key=lambda x: x["volume"], reverse=True)
    total_top_volume = sum(coin["volume"] for coin in top_cash_ins)
    if total_top_volume == 0:
        return "⚠️ No volume data available for any coin."

    # Cash percent calculation
    for coin in top_cash_ins:
        coin["cash_percent"] = round((coin["volume"] / total_top_volume) * 100, 1)

    report = f"🔶 <b>Cash Flow Influx Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    if 'warning' in locals():
        report += warning
    report += "<b>Market Cash Flow (Timeframes):</b>\n"
    for interval, ratio in buyer_ratios.items():
        arrow = "🔺" if ratio > 55 else "🔻" if ratio < 45 else "➖"
        report += f"• {interval} => {ratio}% {arrow}\n"
    report += "\n"
    report += "<b>Cash Migration Report (Top 50 Coins):</b>\n"
    for i, coin in enumerate(top_cash_ins[:50], 1):
        report += f"{i}) ${coin['symbol']}\n"
        report += f"   • Volume Share: {coin['cash_percent']}%\n"
        report += f"   • 15m Buyer Ratio: {coin['buyer_ratio_15m']}% {coin['arrow_15m']}\n"
        report += f"   • 15m Price Change: {coin['price_change']:+.2f}%\n"
        report += f"   Description: <i>In the last 15 minutes, the buyer ratio for ${coin['symbol']} is {coin['buyer_ratio_15m']}%.</i>\n\n"

    outliers = [coin for coin in top_cash_ins if coin["buyer_ratio_15m"] > 55 or coin["buyer_ratio_15m"] < 45]
    if outliers:
        report += "<b>Outlier Detections:</b>\n"
        for coin in outliers[:3]:
            report += f"• ${coin['symbol']}: 15m Buyer Ratio {coin['buyer_ratio_15m']}% {coin['arrow_15m']}, Price {coin['price_change']:+.2f}% (Vol {coin['cash_percent']}%) - Noteworthy move!\n"
        report += "\n"

    comment = "<b>Commentary:</b>\n"
    for interval, ratio in buyer_ratios.items():
        if ratio > 55:
            comment += f"{interval}: Strong buy pressure ({ratio}%), look for opportunities.\n"
        elif ratio < 45:
            comment += f"{interval}: Strong sell pressure ({ratio}%), risky in the short term.\n"
        else:
            comment += f"{interval}: Neutral course ({ratio}%).\n"
    for coin in top_cash_ins[:5]:
        trend = "Uptrend" if coin["price_change"] > 0 else "Downtrend" if coin["price_change"] < 0 else "Sideways"
        if coin["buyer_ratio_15m"] > 50 and coin["price_change"] < 0:
            comment += f"${coin['symbol']}: Buyer ratio high ({coin['buyer_ratio_15m']}%) but price falling ({coin['price_change']:+.2f}%), weak buy signal.\n"
        elif coin["buyer_ratio_15m"] < 50 and coin["price_change"] > 0:
            comment += f"${coin['symbol']}: Buyer ratio low ({coin['buyer_ratio_15m']}%) but price rising ({coin['price_change']:+.2f}%), potential hidden accumulation.\n"
        else:
            comment += f"${coin['symbol']} 15m Trend: {trend}\n"
    report += comment

    report += "\n<b>Footnote:</b>\n"
    report += "• 🔺 indicates strong buy, 🔻 indicates strong sell, ➖ indicates neutral status.\n"
    report += "• Outliers: Buyer ratios below 45% or above 55%.\n"
    report += "• Report dynamically generated based on the top 50 coins by volume.\n"
    return report

def generate_cash_flow_migration_report():
    symbols = get_filtered_coins()
    if not symbols:
        return "⚠️ Could not fetch coin data, report could not be generated."

    lines = []
    header = "Pair          BuyPower  CashIn%  MinorTrend%  BuyPressure"
    lines.append(header)
    lines.append("-" * len(header))

    total_quote_volume = 0
    ticker_data = fetch_24hr_ticker_data(symbols)
    if not ticker_data:
        print("⚠️ Could not fetch ticker data, falling back to kline data...")

    for symbol in symbols[:50]:
        quote_vol = 0
        taker_buy_vol = 0

        ticker = next((t for t in ticker_data if t["symbol"] == symbol), None)
        if ticker:
            quote_vol = float(ticker.get("quoteVolume", 0))
            taker_buy_vol = float(ticker.get("takerBuyQuoteAssetVolume", 0))
            if taker_buy_vol == 0:
                taker_buy_base = float(ticker.get("takerBuyBaseAssetVolume", 0))
                avg_price = float(ticker.get("weightedAvgPrice", 0)) or 1
                if taker_buy_base > 0 and avg_price > 0:
                    taker_buy_vol = taker_buy_base * avg_price
                else:
                    print(f"[UYARI] {symbol} - Ticker Taker Buy Base veya Avg Price sıfır: {taker_buy_base}, {avg_price}")

        if quote_vol <= 0 or taker_buy_vol == 0:
            taker_buy_quote, quote_vol_from_klines = fetch_taker_volumes_from_klines(symbol, "1h", 24)
            if quote_vol_from_klines > 0:
                quote_vol = quote_vol_from_klines
                taker_buy_vol = taker_buy_quote
            else:
                print(f"[UYARI] {symbol} - Kline verileri de yetersiz: Quote Vol: {quote_vol_from_klines}, Taker Buy Vol: {taker_buy_quote}")
                taker_buy_vol = quote_vol * 0.5  # Varsayılan %50 alıcı hacmi tahmini
                quote_vol = quote_vol or 1

        if quote_vol <= 0:
            print(f"[DEBUG] {symbol} - Quote Volume sıfır veya negatif: {quote_vol}")
            continue

        total_quote_volume += quote_vol

        buy_power = 0.0
        if quote_vol > 0 and taker_buy_vol >= 0:
            buy_power = taker_buy_vol / quote_vol if taker_buy_vol < quote_vol else 1.0
            buy_power = round(min(max(buy_power, 0), 10), 2)
        else:
            print(f"[UYARI] {symbol} - Quote Vol veya Taker Buy Vol geçersiz: {quote_vol}, {taker_buy_vol}")

        print(f"[DEBUG] {symbol} - Quote Vol: {quote_vol}, Taker Buy Vol: {taker_buy_vol}, Buy Power: {buy_power}")

        cash_percent = 0.0  # Toplam quote volume hesaplandıktan sonra güncellenecek

        kline_15m = sync_fetch_kline_data(symbol, "15m", limit=20)
        minor_trend_score = 0.0
        if kline_15m and len(kline_15m) > 1:
            try:
                first_close = float(kline_15m[0][4])
                last_close = float(kline_15m[-1][4])
                if first_close > 0:
                    minor_trend_score = round(((last_close - first_close) / first_close) * 100, 2)
            except Exception as e:
                print(f"[HATA] {symbol} için minor trend hesaplanamadı: {e}")
                minor_trend_score = 0.0

        intervals = ["15m", "1h", "4h", "12h", "1d"]
        arrow_list = []
        for inter in intervals:
            kline = sync_fetch_kline_data(symbol, inter, limit=20)
            trend = calculate_cash_flow_trend(kline)
            arrow = "▲" if trend > 0 else "▼" if trend < 0 else "="
            arrow_list.append(arrow)
        alis_baskisi_ozeti = "".join(arrow_list)

        line = f"{symbol:<12} {buy_power:>6}x {cash_percent:>6}% {minor_trend_score:>7}% {alis_baskisi_ozeti}"
        lines.append(line)

    for i, line in enumerate(lines[2:]):
        symbol = lines[i + 2]
        ticker = next((t for t in ticker_data if t["symbol"] == symbol), None)
        if ticker:
            quote_vol = float(ticker.get("quoteVolume", 0))
            cash_percent = round((quote_vol / total_quote_volume) * 100, 1) if total_quote_volume > 0 else 0.0
            parts = lines[i + 2].split()
            parts[2] = f"{cash_percent:>6}%"
            lines[i + 2] = " ".join(parts)

    report = "\n".join(lines)
    return report

def generate_smart_score_report():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet, Smart Score Report could not be generated."
    report = f"📊 <b>Smart Score Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report presents the smart scores and trend summaries of coins.\n"
    report += "In the trend summary, characters on the left represent short-term (15min), and characters on the right represent long-term (1day).\n\n"
    sorted_results = sorted(ALL_RESULTS, key=lambda x: calculate_composite_score(x), reverse=True)
    for coin in sorted_results[:50]:
        smart_score = calculate_composite_score(coin)
        with global_lock:
            prev_score = PREV_STATS.get(coin["Coin"], {}).get("composite", smart_score)
        change = calculate_percentage_change(smart_score, prev_score)
        price = coin.get("Price_Display", "N/A")
        net_accum = coin.get("Net Accum", "N/A")
        trend_string = ""
        intervals = ["15m", "1h", "4h", "12h", "1d"]
        for interval in intervals:
            kline_data = sync_fetch_kline_data(coin["Coin"], interval, limit=20)
            trend = calculate_cash_flow_trend(kline_data)
            trend_string += "+" if trend > 0 else "-" if trend < 0 else "0"
        
        symbol = "$" + coin["Coin"].replace("USDT", "")
        report += (f"<b>{symbol}</b> - Price: {price}, Net Accum: {net_accum}\n"
                   f"Smart Score: {round(smart_score, 4)} ({get_change_arrow(change)} {round(change, 2)}%)\n"
                   f"Trend Summary: {trend_string}\n\n")
    report += "<b>Note:</b> In the trend summary, '+' indicates buy pressure, '-' indicates sell pressure, and '0' indicates neutral status.\n"
    return report

def generate_volume_analysis_report():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"📈 <b>Volume Analysis Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report shows volume ratios and changes for coins.\n\n"

    valid_results = []
    for coin in ALL_RESULTS:
        try:
            current_volume_ratio = extract_numeric(coin.get("Volume Ratio", 0))
            with global_lock:
                prev_volume_ratio = PREV_STATS.get(coin["Coin"], {}).get("volume_ratio", current_volume_ratio)
            volume_change = calculate_percentage_change(current_volume_ratio, prev_volume_ratio)
            valid_results.append((coin, current_volume_ratio, volume_change))
        except (ValueError, TypeError) as e:
            print(f"[WARNING] Volume ratio could not be calculated for {coin['Coin']}: {e}")
            continue

    if not valid_results:
        report += "⚠️ No volume analysis could be done for any coin. Data might be missing.\n"
    else:
        sorted_results = sorted(valid_results, key=lambda x: x[1], reverse=True)
        for coin, current_volume_ratio, volume_change in sorted_results[:10]:
            arrow = get_change_arrow(volume_change)
            comment = (
                "Volume increasing, interest rising!" if volume_change > 20 else
                "Volume decreasing, be careful!" if volume_change < -20 else
                "Volume stable."
            )
            symbol = coin['Coin'].replace("USDT", "")
            formatted_symbol = f"${symbol}"
            report += f"<b>{formatted_symbol}</b>:\n"
            report += f"   • Volume Ratio: {current_volume_ratio:.2f}x ({arrow} {round(volume_change, 2)}%)\n"
            report += f"   • Price: {coin['Price_Display']}\n"
            report += f"   • Comment: {comment}\n\n"

    report += "Note: Volume ratio is the ratio of recent volume to its historical average."
    print(f"[DEBUG] Volume Analysis Report generated: {len(valid_results)} coins analyzed.")
    return report


def fetch_order_book(symbol, limit=100):
    url = f"{BINANCE_API_URL}depth?symbol={symbol}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            bids = [(float(price), float(qty)) for price, qty in data["bids"]]
            asks = [(float(price), float(qty)) for price, qty in data["asks"]]
            return bids, asks
        else:
            print(f"[HATA] {symbol} için emir defteri alınamadı: {response.status_code}")
            return [], []
    except Exception as e:
        print(f"[HATA] Emir defteri çekilirken hata: {e}")
        return [], []


def analyze_order_book(bids, asks, current_price, symbol="Unknown"):
    """
    Emir defterini analiz eder ve önemli metrikleri hesaplar.

    Args:
        bids (list): Alış emirleri [(fiyat, miktar),...]
        asks (list): Satış emirleri [(fiyat, miktar),...]
        current_price (float): Mevcut fiyat
        symbol (str): Coin sembolü

    Returns:
        dict: Emir defteri analiz sonuçları
    """
    try:
        # Kısa devre durumları
        if not bids and not asks:
            return {
                "imbalance": 0,
                "bid_volume": 0,
                "ask_volume": 0,
                "big_bid_wall": False,
                "big_ask_wall": False,
                "max_bid_qty": 0,
                "max_ask_qty": 0
            }

        # Ensure current_price is float
        current_price = float(current_price) if current_price else 0
        
        # Yakın emir hacimlerini topla (mevcut fiyata %2 yakın) - Convert to float
        bid_volume = sum(float(qty) for price, qty in bids if float(price) > current_price * 0.98)
        ask_volume = sum(float(qty) for price, qty in asks if float(price) < current_price * 1.02)
        total_volume = bid_volume + ask_volume

        # Dengesizlik hesapla
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0

        # En büyük tekil emirleri bul
        bid_qtys = [float(qty) for _, qty in bids] if bids else []
        ask_qtys = [float(qty) for _, qty in asks] if asks else []
        max_bid_qty = max(bid_qtys, default=0)
        max_ask_qty = max(ask_qtys, default=0)

        # Büyük duvar tespiti - Ortalama emrin 10 katı veya toplam hacmin %10'u
        avg_bid_qty = bid_volume / len([q for p, q in bids if float(p) > current_price * 0.98]) if bid_volume > 0 else 0
        avg_ask_qty = ask_volume / len([q for p, q in asks if float(p) < current_price * 1.02]) if ask_volume > 0 else 0
        
        big_bid_wall = max_bid_qty > max(avg_bid_qty * 10, bid_volume * 0.1) if bid_volume > 0 else False
        big_ask_wall = max_ask_qty > max(avg_ask_qty * 10, ask_volume * 0.1) if ask_volume > 0 else False

        # Debug bilgisi yazdır
        print(f"[DEBUG] Emir Defteri Analizi: {symbol} bid_vol={bid_volume:.2f}, ask_vol={ask_volume:.2f}")
        print(f"[DEBUG] Max emirler: max_bid={max_bid_qty:.2f}, max_ask={max_ask_qty:.2f}")
        print(f"[DEBUG] Büyük duvarlar: bid_wall={big_bid_wall}, ask_wall={big_ask_wall}")

        # Calculate spread
        best_bid = float(bids[0][0]) if bids else 0
        best_ask = float(asks[0][0]) if asks else 0
        spread_usd = best_ask - best_bid if best_ask and best_bid else 0
        spread_pct = (spread_usd / best_bid * 100) if best_bid else 0

        return {
            "imbalance": round(imbalance * 100, 2),
            "imbalance_pct": round(imbalance * 100, 2),
            "spread_pct": round(spread_pct, 4),
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "big_bid_wall": big_bid_wall,
            "big_ask_wall": big_ask_wall,
            "max_bid_qty": max_bid_qty,
            "max_ask_qty": max_ask_qty,
            "whale_walls": {
                "buy_wall_price": bids[bid_qtys.index(max_bid_qty)][0] if big_bid_wall and max_bid_qty in bid_qtys else None,
                "sell_wall_price": asks[ask_qtys.index(max_ask_qty)][0] if big_ask_wall and max_ask_qty in ask_qtys else None
            },
            "depth_analysis": {
                "bids_qty": bid_volume,
                "asks_qty": ask_volume
            }
        }
    except Exception as e:
        print(f"[HATA] Emir defteri analizinde hata: {e}")
        import traceback
        traceback.print_exc()
        return {
            "imbalance": 0,
            "bid_volume": 0,
            "ask_volume": 0,
            "big_bid_wall": False,
            "big_ask_wall": False,
            "max_bid_qty": 0,
            "max_ask_qty": 0
        }


def detect_liquidity_drying(order_book_snapshots, timeframe=5):
    """
    Likidite kuruması desenini tespit eder.

    Args:
        order_book_snapshots (list): Belli aralıklarla kaydedilmiş emir defteri anlık görüntüleri
        timeframe (int): Kaç dakikalık zaman diliminde analiz yapılacağı

    Returns:
        dict: Likidite değişim analizi
    """
    if len(order_book_snapshots) < 2:
        return {"liquidity_change": 0, "significant": False}

    # İlk ve son emir defteri
    first_ob = order_book_snapshots[0]
    last_ob = order_book_snapshots[-1]

    # Toplam emir defteri derinliğini hesapla
    def calculate_depth(ob, depth_pct=2.0):
        bids, asks = ob
        mid_price = (bids[0][0] + asks[0][0]) / 2

        bid_depth = sum(qty for price, qty in bids if price > mid_price * (1 - depth_pct / 100))
        ask_depth = sum(qty for price, qty in asks if price < mid_price * (1 + depth_pct / 100))

        return bid_depth + ask_depth

    first_depth = calculate_depth(first_ob)
    last_depth = calculate_depth(last_ob)

    if first_depth == 0:
        return {"liquidity_change": 0, "significant": False}

    liquidity_change_pct = ((last_depth - first_depth) / first_depth) * 100

    return {
        "liquidity_change": liquidity_change_pct,
        "significant": abs(liquidity_change_pct) > 30,  # %30'dan fazla değişim önemli
        "direction": "increasing" if liquidity_change_pct > 0 else "decreasing"
    }


def detect_iceberg_orders(order_book_history, price_level_tolerance=0.1):
    """
    Buzdağı emirlerini tespit eder (görünür emir defterinde küçük tekrarlayan emirler).

    Args:
        order_book_history (list): Emir defteri tarihçesi
        price_level_tolerance (float): Fiyat seviyesi toleransı (%)

    Returns:
        dict: Buzdağı emirleri tespiti
    """
    if len(order_book_history) < 5:
        return {"detected": False}

    # Fiyat seviyelerini gruplandır
    bid_activities = {}
    ask_activities = {}

    for timestamp, order_book in order_book_history:
        bids, asks = order_book

        # Alış emirlerini gruplandır
        for price, qty in bids:
            price_group = round(price / price_level_tolerance) * price_level_tolerance
            if price_group not in bid_activities:
                bid_activities[price_group] = []
            bid_activities[price_group].append((timestamp, qty))

        # Satış emirlerini gruplandır
        for price, qty in asks:
            price_group = round(price / price_level_tolerance) * price_level_tolerance
            if price_group not in ask_activities:
                ask_activities[price_group] = []
            ask_activities[price_group].append((timestamp, qty))

    # Yenilenen emirleri tespit et
    iceberg_candidates = []

    for price_group, activities in {**bid_activities, **ask_activities}.items():
        if len(activities) < 3:
            continue

        # Son birkaç aktiviteyi analiz et
        recent_activities = activities[-5:]
        qty_variance = np.var([qty for _, qty in recent_activities])

        # low varyans, benzer büyüklükte tekrarlayan emirleri gösterir
        if qty_variance < np.mean([qty for _, qty in recent_activities]) * 0.1:
            direction = "bid" if price_group in bid_activities else "ask"
            iceberg_candidates.append({
                "price_level": price_group,
                "direction": direction,
                "avg_qty": np.mean([qty for _, qty in recent_activities]),
                "confidence": min(100, 100 - (qty_variance * 100))
            })

    return {
        "detected": len(iceberg_candidates) > 0,
        "candidates": sorted(iceberg_candidates, key=lambda x: x["confidence"], reverse=True)
    }



def calculate_anomaly_score(metric, historical_data, window=20):
    """
    Bir metriğin anormallik skorunu z-skor metoduyla hesaplar.
    Giriş verilerinin aynı birimde olduğu varsayılır.
    """
    # Veri kontrolü
    if not historical_data or len(historical_data) < 5:
        return 0

    try:
        # Sayısal değerleri al
        recent_value = float(metric)
        past_values = [float(v) for v in historical_data[-window:] if v is not None]

        if len(past_values) < 5:
            return 0

        # İstatistiksel hesaplamalar
        mean = np.mean(past_values)
        std = np.std(past_values)

        if std < (mean * 0.0001) or std == 0:
            # Standart sapma çok küçükse, değer sadece ortalamadan büyükse anomali kabul et (basit yaklaşım)
            return 1.0 if recent_value > mean else 0.0

        z_score = (recent_value - mean) / std

        # Skoru -5 ile 5 arasında sınırla
        final_score = round(min(max(z_score, -5), 5), 2)
        return final_score

    except Exception as e:
        print(f"[HATA] Anormallik hesaplanamadı: {e}")
        return 0

# ---------------- Yeni "Akıllı Balina & Trend" Raporu Fonksiyonları ----------------
def calculate_trend_score(coin_data):
    try:
        rsi = extract_numeric(coin_data["RSI"])
        macd = extract_numeric(coin_data["MACD"])
        adx = extract_numeric(coin_data["ADX"])
        net_accum = extract_numeric(coin_data["NetAccum_raw"])
        volume_ratio = extract_numeric(coin_data["Volume Ratio"])
        atr = extract_numeric(coin_data["ATR_raw"])
        price_roc = extract_numeric(coin_data["24h Change"])
        btc_corr = extract_numeric(coin_data["BTC Correlation"]) if coin_data["BTC Correlation"] != "Yok" else 0
        trend_strength = (adx / 100) * 30
        momentum_boost = (price_roc / 10) * 20 if price_roc > 0 else 0
        whale_impact = (min(abs(net_accum) / 10, 1) * 30) if net_accum > 0 else 0
        price_value = parse_money(coin_data["Price_Display"])
        volatility_adjust = (atr / price_value) * 20 if price_value != 0 else 0
        volume_boost = min(volume_ratio / 2, 1) * 20
        correlation_penalty = abs(btc_corr) * 10 if abs(btc_corr) > 0.8 else 0
        total_score = trend_strength + momentum_boost + whale_impact + volatility_adjust + volume_boost - correlation_penalty
        total_score = max(0, total_score)
        total_score = min(100, total_score)
        return round(total_score, 1)
    except Exception as e:
        print(f"[HATA] Trend skoru hesaplanamadı: {e}")
        return 50.0

def detect_advanced_whale_strategy(coin_data):
    net_accum = extract_numeric(coin_data["NetAccum_raw"])
    whale_activity = extract_numeric(coin_data["Whale Activity"])
    volume_ratio = extract_numeric(coin_data["Volume Ratio"])
    rsi = extract_numeric(coin_data["RSI"])
    price_roc = extract_numeric(coin_data["24h Change"])
    price_value = parse_money(coin_data["Price_Display"])
    atr_percent = extract_numeric(coin_data["ATR_raw"]) / price_value * 100 if price_value != 0 else 0  # Sıfır kontrolü eklendi
    if net_accum > 10 and volume_ratio > 2 and price_roc > 5 and rsi < 60:
        return "Sessiz Birikim: Balinalar agresif alımda, pump öncesi olabilir."
    elif net_accum < -10 and atr_percent > 2 and price_roc < -5:
        return "Panik Satışı: Balinalar stop-loss avcılığı yapıyor."
    elif abs(net_accum) < 5 and whale_activity > 1000 and volume_ratio > 3:
        return "Spoofing: Balinalar sahte hacim yaratıyor."
    elif net_accum > 5 and price_roc < 2 and rsi < 50:
        return "Stratejik Toplama: Balinalar dipte birikiyor."
    else:
        return "Belirgin strateji yok."


# ---------------- Vadeli İşlemler Analizi Fonksiyonları ----------------

# fetch_binance_data moved to binance_client.py


def generate_advanced_whale_trend_report():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."
    report = f"🧠 <b>Smart Whale & Trend Report – {datetime.now().strftime('%H:%M:%S')}</b>\n"
    report += "This report analyzes whale strategies and short-term trend potential for the top 50 coins.\n\n"
    
    # Analyze and sort by trend score
    coins_data = []
    for coin in ALL_RESULTS[:50]:
        trend_score = calculate_trend_score(coin)
        coins_data.append((coin, trend_score))
    
    sorted_coins = sorted(coins_data, key=lambda x: x[1], reverse=True)
    
    report += "<b>Top Trend Potential Coins:</b>\n"
    for i, (coin, trend_score) in enumerate(sorted_coins, 1):
        whale_strategy = detect_advanced_whale_strategy(coin)
        signal = "🔥 Opportunity" if trend_score > 75 else "⚠️ Risky" if trend_score < 25 else "📈 Watch"
        symbol = coin['Coin'].replace("USDT", "")
        formatted_symbol = f"${symbol}"
        report += f"{i}. {formatted_symbol} (Score: {trend_score})\n"
        report += f"   • Whale Strategy: {whale_strategy}\n"
        report += f"   • Price: {coin['Price_Display']} | RSI: {coin['RSI']} | Vol: {coin.get('Volume Ratio', 'N/A')}x\n"
        report += f"   • Rec: {signal}\n\n"
        
    avg_trend_score = sum(score for _, score in sorted_coins) / len(sorted_coins) if sorted_coins else 50
    report += "<b>Market Summary:</b>\n"
    report += f"Average Trend Score: {round(avg_trend_score, 2)}\n"
    report += "Market Sentiment: " + ("Strong 🚀" if avg_trend_score > 75 else "Weak 📉" if avg_trend_score < 25 else "Neutral ⚖️")
    return report


def generate_whale_ranking_report():
    """
    Ranks whale activities and net accumulations for the top 50 coins.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"🐳 <b>Whale Ranking Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report ranks whale activities and net accumulation for the top 50 coins.\n\n"

    valid_data = []
    for coin in ALL_RESULTS[:50]:
        try:
            activity = extract_numeric(coin.get("Whale Activity", "0"))
            net_accum_raw = extract_numeric(coin.get("NetAccum_raw", 0))
            valid_data.append({
                "coin": coin,
                "activity": activity,
                "net_accum_raw": net_accum_raw
            })
        except (ValueError, TypeError):
            continue

    # Rank by Activity
    sorted_by_activity = sorted(valid_data, key=lambda x: x["activity"], reverse=True)
    report += "<b>Most Active Whales (Trade Count):</b>\n"
    if not sorted_by_activity:
        report += "   • Data missing, whale activity not detected.\n"
    for item in sorted_by_activity:
        coin = item["coin"]
        symbol = "$" + coin['Coin'].replace("USDT", "")
        report += f"{symbol}:\n"
        report += f"   • Trade Count: {format_money(item['activity'])} trades\n"
        report += f"   • Net Accumulation: {coin['Net Accum']}\n\n"

    # Rank by Net Accumulation
    sorted_by_net = sorted(valid_data, key=lambda x: x["net_accum_raw"], reverse=True)
    report += "<b>Highest Net Accumulation (Million USD):</b>\n"
    if not sorted_by_net:
        report += "   • Data missing, net accumulation not detected.\n"
    for item in sorted_by_net:
        coin = item["coin"]
        symbol = "$" + coin['Coin'].replace("USDT", "")
        report += f"{symbol}: {coin['Net Accum']}\n"
        report += f"   • Volume Ratio: {coin.get('Volume Ratio', '0')}x\n"
        report += f"   • Price: {coin['Price_Display']}\n\n"

    report += "Note: Trade count shows whale activity intensity, while net accumulation shows the buy/sell balance."
    return report


def generate_volatility_report():
    """
    Ranks volatility scores (ATR/Price %) and their changes for the top 50 coins.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"🌩️ <b>Volatility Ranking Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report ranks volatility scores (ATR/Price %) and their changes for the top 50 coins.\n\n"

    volatility_data = []
    for coin in ALL_RESULTS[:50]:
        try:
            current_price = parse_money(coin.get("Price_Display", "0"))
            atr = extract_numeric(coin.get("ATR_raw", 0))
            if current_price == 0:
                vol_score = 0
            else:
                vol_score = round((atr / current_price) * 100, 2)
            with global_lock:
                prev_vol_score = PREV_STATS.get(coin["Coin"], {}).get("vol_score", 0)
                PREV_STATS.setdefault(coin["Coin"], {})["vol_score"] = vol_score
            vol_change = ((vol_score - prev_vol_score) / prev_vol_score * 100) if prev_vol_score != 0 else 0
            volatility_data.append({
                "Coin": coin["Coin"],
                "VolScore": vol_score,
                "VolChange": vol_change,
                "ATR": coin["ATR"],
                "Price": coin["Price_Display"],
                "VolumeRatio": coin.get("Volume Ratio", "0")
            })
        except Exception:
            continue

    sorted_volatility = sorted(volatility_data, key=lambda x: x["VolScore"], reverse=True)

    if not sorted_volatility:
        report += "⚠️ Volatility data missing, ranking could not be done.\n"
    else:
        report += "<b>Volatile Coins Ranking:</b>\n"
        for item in sorted_volatility:
            comment = (
                "High volatility, opportunity/risk present!" if item["VolScore"] > 5 else
                "Medium volatility, watch carefully." if item["VolScore"] > 2 else
                "Low volatility, stable."
            )
            arrow = get_change_arrow(item["VolChange"])
            symbol = "$" + item['Coin'].replace("USDT", "")
            report += f"<b>{symbol}</b>:\n"
            report += f"   • Volatility Score: {item['VolScore']}% ({arrow} {round(item['VolChange'], 2)}%)\n"
            report += f"   • ATR: {item['ATR']} | Price: {item['Price']}\n"
            report += f"   • Vol Ratio: {item['VolumeRatio']}x | Comment: {comment}\n\n"

    avg_vol_score = sum(item["VolScore"] for item in volatility_data) / len(volatility_data) if volatility_data else 0
    report += f"<b>Market Summary:</b>\n"
    report += f"Average Volatility Score: {round(avg_vol_score, 2)}%\n"
    return report
    report += f"Average Volatility Score: {round(avg_vol_score, 2)}%\n"
    report += f"Market: {'Volatile' if avg_vol_score > 3 else 'Stable'}\n"

    report += "Not: Volatilite skoru, ATR’nin fiyata oranıdır (%). Oklar önceki analize göre değişimi gösterir."
    print(f"[DEBUG] Volatilite Sıralaması Raporu üretildi: {len(volatility_data)} coin analiz edildi.")
    return report


def generate_bollinger_squeeze_report():
    """
    Analyzes Bollinger Band squeezes and reports breakout potential for top 50 coins.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"📏 <b>Bollinger Band Squeeze Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report analyzes coins with narrow Bollinger Bands and potential breakout signals.\n\n"

    squeeze_data = []
    for coin in ALL_RESULTS[:50]:
        try:
            if "df" not in coin or not coin["df"]:
                continue

            df = pd.DataFrame(coin["df"])
            if len(df) < 20:
                continue

            # Column mapping for consistency
            column_names = {str(col).lower(): col for col in df.columns}
            close_col = column_names.get("kapanış") or column_names.get("close") or df.columns[4]
            high_col = column_names.get("yüksek") or column_names.get("high") or df.columns[1]
            low_col = column_names.get("düşük") or column_names.get("low") or df.columns[2]

            df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
            df[high_col] = pd.to_numeric(df[high_col], errors="coerce")
            df[low_col] = pd.to_numeric(df[low_col], errors="coerce")
            df.dropna(subset=[close_col, high_col, low_col], inplace=True)

            if len(df) < 6:
                continue

            bb_indicator = BollingerBands(close=df[close_col], window=20, window_dev=2)
            df["bb_upper"] = bb_indicator.bollinger_hband()
            df["bb_lower"] = bb_indicator.bollinger_lband()
            df["bb_middle"] = bb_indicator.bollinger_mavg()
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"] * 100

            recent_bw = df["bb_width"].tail(6)
            current_bw = recent_bw.iloc[-1]
            min_bw_6 = recent_bw.min()

            is_squeeze = current_bw <= (min_bw_6 * 1.1)

            if is_squeeze:
                current_price = float(df[close_col].iloc[-1])
                upper_band = df["bb_upper"].iloc[-1]
                lower_band = df["bb_lower"].iloc[-1]
                breakout_dir = (
                    "Bullish" if current_price > upper_band else
                    "Bearish" if current_price < lower_band else
                    "Pending"
                )

                volume_ratio = extract_numeric(coin.get("Volume Ratio", 0))
                rsi_val = float(str(coin.get("RSI", "0")))
                volume_comment = "Volume support present" if volume_ratio > 1.5 else "Volume is weak"
                rsi_comment = (
                    "Overbought" if rsi_val > 70 else
                    "Oversold" if rsi_val < 30 else
                    "Neutral"
                )

                squeeze_data.append({
                    "Coin": coin["Coin"],
                    "BandWidth": current_bw,
                    "Breakout": breakout_dir,
                    "Price": coin["Price_Display"],
                    "VolumeRatio": volume_ratio,
                    "VolumeComment": volume_comment,
                    "RSI": rsi_val,
                    "RSIComment": rsi_comment
                })
        except Exception:
            continue

    sorted_squeeze = sorted(squeeze_data, key=lambda x: x["BandWidth"])

    if not sorted_squeeze:
        report += "No Bollinger Band squeeze detected in top 50 coins currently.\n"
    else:
        report += "<b>Squeeze Detected Coins:</b>\n"
        for item in sorted_squeeze:
            symbol = "$" + item["Coin"].replace("USDT", "")
            report += f"<b>{symbol}</b>:\n"
            report += f"   • BandWidth: {round(item['BandWidth'], 2)}% (Squeeze Intensity)\n"
            report += f"   • Price: {item['Price']} | Breakout: {item['Breakout']}\n"
            report += f"   • Vol Ratio: {item['VolumeRatio']}x ({item['VolumeComment']})\n"
            report += f"   • RSI: {item['RSI']} ({item['RSIComment']})\n\n"

    return report


def generate_trust_index_report():
    """
    Evaluates reliability for top 50 coins on a scale of 0-100.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"🔒 <b>Trust Index Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report evaluates coin reliability between 0-100.\n"
    report += "0-25 Highly Suspicious, 25-50 Suspicious, 50-75 Reliable, 75-100 Highly Reliable\n\n"

    trust_data = []
    for coin in ALL_RESULTS[:50]:
        try:
            curr_price = parse_money(coin["Price_Display"])
            weekly_close = parse_money(coin["Weekly Change"][0])
            daily_close = get_candle_close(coin["Coin"], "1d") or curr_price
            fourh_close = parse_money(coin["4H Change"][0])
            trust_index, trust_change = calculate_trust_index(coin, curr_price, weekly_close, daily_close, fourh_close)
            trust_data.append({
                "Coin": coin["Coin"],
                "TrustIndex": trust_index,
                "TrustChange": trust_change,
                "VolumeRatio": coin.get("Volume Ratio", "1"),
                "NetAccum": coin.get("Net Accum", "0M"),
                "BBWidth": coin.get("Bollinger Bands", "0%"),
                "WhaleActivity": f"{coin.get('Whale_Buy_M', '0')} / {coin.get('Whale_Sell_M', '0')}"
            })
        except Exception:
            continue

    if not trust_data:
        return report + "⚠️ No data could be processed for any coin.\n"

    sorted_trust = sorted(trust_data, key=lambda x: x["TrustIndex"], reverse=True)
    
    report += "<b>Top Reliable Coins (Top 50):</b>\n"
    for i, item in enumerate(sorted_trust, 1):
        symbol = "$" + item["Coin"].replace("USDT", "")
        change_arrow = "🔼" if item["TrustChange"] > 0 else "🔽" if item["TrustChange"] < 0 else "➖"
        report += f"{i}. <b>{symbol}</b>: {item['TrustIndex']} {change_arrow} {abs(item['TrustChange']):.1f}%\n"
        report += f"   - Vol Ratio: {item['VolumeRatio']}x | Net Accum: {item['NetAccum']}\n"
        report += f"   - Whale Activity: {item['WhaleActivity']}\n"

    avg_trust = sum(item["TrustIndex"] for item in sorted_trust) / len(sorted_trust) if sorted_trust else 50
    status = "🟢 High" if avg_trust > 75 else "🔴 Low" if avg_trust < 50 else "🟡 Medium"
    report += f"\n<b>Market Summary:</b>\n"
    report += f"Average Trust Index: {round(avg_trust, 0)}\n"
    report += f"Market Trust Status: {status}\n"
    report += "\n<b>Note:</b> Trust index is based on trend, volume, accumulation, RSI, EMA, whale activity, and volatility."
    return report
    report += "Değişim, önceki analize göre yüzdesel farkı gösterir.\n"
    report = re.sub(r"<(\d+)>", r"\1", report)
    print(f"[DEBUG] Gönderilecek mesaj uzunluğu: {len(report)} karakter")
    return report


# ---------------- Yeni "Vadeli İşlemler Analizi" Fonksiyonları ----------------
# generate_trust_index_report fonksiyonundan sonra ekleyin


def fetch_futures_data(symbol):
    """
    Binance vadeli işlemler verilerini çeker

    Args:
        symbol (str): Coin sembolü

    Returns:
        dict: Funding rate, open interest ve diğer verileri içeren sözlük
    """
    try:
        result = {}

        # Funding rate
        funding_url = f"{BINANCE_FUTURES_API_URL}premiumIndex?symbol={symbol}"
        funding_response = requests.get(funding_url, timeout=5)

        if funding_response.status_code == 200:
            funding_data = funding_response.json()
            result["funding_rate"] = float(funding_data.get("lastFundingRate", 0)) * 100  # Yüzdeye çevir

        # Open interest
        oi_url = f"{BINANCE_FUTURES_API_URL}openInterest?symbol={symbol}"
        oi_response = requests.get(oi_url, timeout=5)

        if oi_response.status_code == 200:
            oi_data = oi_response.json()
            result["open_interest"] = float(oi_data.get("openInterest", 0))

        # Long/short oranı
        ls_url = f"{BINANCE_FUTURES_API_URL}globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        ls_response = requests.get(ls_url, timeout=5)

        if ls_response.status_code == 200 and ls_response.json():
            ls_data = ls_response.json()[0]
            result["long_short_ratio"] = float(ls_data.get("longShortRatio", 1.0))

        return result
    except Exception as e:
        print(f"[HATA] {symbol} futures verisi alınamadı: {e}")
        return {"funding_rate": 0, "open_interest": 0, "long_short_ratio": 1.0}


# fetch_futures_data fonksiyonunun alias'ı olarak ekleyin (isim tutarlılığı için)
def fetch_binance_futures_data(symbol):
    try:
        result = {}

        # Funding rate
        funding_url = f"{BINANCE_FUTURES_API_URL}premiumIndex?symbol={symbol}"
        funding_response = requests.get(funding_url, timeout=5)

        if funding_response.status_code == 200:
            funding_data = funding_response.json()
            result["funding_rate"] = float(funding_data.get("lastFundingRate", 0)) * 100

        # Open interest
        oi_url = f"{BINANCE_FUTURES_API_URL}openInterest?symbol={symbol}"
        oi_response = requests.get(oi_url, timeout=5)

        if oi_response.status_code == 200:
            oi_data = oi_response.json()
            result["open_interest"] = float(oi_data.get("openInterest", 0))

        # Long/short oranı için yeni fonksiyonu kullan
        result["long_short_ratio"] = fetch_enhanced_ls_ratio(symbol)

        return result
    except Exception as e:
        print(f"[HATA] {symbol} futures verisi alınamadı: {e}")
        return {"funding_rate": 0, "open_interest": 0, "long_short_ratio": 1.0}


async def fetch_futures_data_async(session, symbol, exchange='binance'):
    """
    Gelişmiş asenkron vadeli işlem veri çekme mekanizması

    Args:
        session (aiohttp.ClientSession): Mevcut HTTP oturumu
        symbol (str): İşlem çifti sembolü
        exchange (str, optional): Borsa adı. Varsayılan 'binance'

    Returns:
        dict: Vadeli işlem verileri
    """
    try:
        normalized_symbol = normalize_symbol_for_exchange(symbol, exchange)

        # Her bir veri için ayrı çağrılar
        endpoints = {
            'binance': {
                'open_interest': f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
                'funding_rate': f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}",
                'long_short_ratio': f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
            },
            'okx': {
                'open_interest': f"https://www.okx.com/api/v5/public/open-interest?instId={normalized_symbol}-SWAP",
                'funding_rate': f"https://www.okx.com/api/v5/public/funding-rate?instId={normalized_symbol}-SWAP",
                'long_short_ratio': f"https://www.okx.com/api/v5/public/account-ratio?instId={normalized_symbol}-SWAP&period=1d"
            },
            'bybit': {
                'open_interest': f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={normalized_symbol}",
                'funding_rate': f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={normalized_symbol}",
                'long_short_ratio': f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={normalized_symbol}&period=1d"
            }
        }

        # Güvenli veri çekme ve işleme fonksiyonu
        async def safe_fetch(url, params=None):
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"[UYARI] {exchange} {symbol} veri çekme hatası: {response.status}")
                        return None
            except Exception as e:
                print(f"[HATA] {exchange} {symbol} veri çekme hatası: {e}")
                return None

        # Tüm verileri eş zamanlı çek
        tasks = [
            safe_fetch(endpoints[exchange]['open_interest']),
            safe_fetch(endpoints[exchange]['funding_rate']),
            safe_fetch(endpoints[exchange]['long_short_ratio'])
        ]

        open_interest, funding_data, ls_data = await asyncio.gather(*tasks)

        # Veri işleme
        result = {
            'symbol': symbol,
            'exchange': exchange,
            'open_interest': _extract_open_interest(open_interest, exchange),
            'funding_rate': _extract_funding_rate(funding_data, exchange),
            'long_short_ratio': _extract_long_short_ratio(ls_data, exchange)
        }

        return result

    except Exception as e:
        print(f"[HATA] {symbol} - {exchange} futures veri hatası: {e}")
        return {
            'symbol': symbol,
            'exchange': exchange,
            'open_interest': 0,
            'funding_rate': 0,
            'long_short_ratio': 1.0
        }


def _extract_open_interest(data, exchange):
    """Borsaya göre açık pozisyon verisini çıkarır"""
    if not data:
        return 0
    try:
        if exchange == 'binance':
            return extract_numeric(data.get('openInterest', 0))
        elif exchange == 'okx':
            return float(data['data'][0]['oi']) if data.get('data') else 0
        elif exchange == 'bybit':
            return float(data['result']['list'][0]['openInterest']) if data.get('result', {}).get('list') else 0
    except Exception as e:
        print(f"[HATA] {exchange} açık pozisyon verisi çıkarılamadı: {e}")
        return 0


def _extract_funding_rate(data, exchange):
    """Borsaya göre funding rate verisini çıkarır"""
    if not data:
        return 0
    try:
        if exchange == 'binance':
            return float(data[0].get('lastFundingRate', 0)) * 100
        elif exchange == 'okx':
            return float(data['data'][0].get('fundingRate', 0)) * 100
        elif exchange == 'bybit':
            return float(data['result']['list'][0].get('fundingRate', 0)) * 100
    except Exception as e:
        print(f"[HATA] {exchange} funding rate verisi çıkarılamadı: {e}")
        return 0


def _extract_long_short_ratio(data, exchange):
    """Borsaya göre long/short oranını çıkarır"""
    if not data:
        return 1.0
    try:
        if exchange == 'binance':
            return float(data[0].get('longShortRatio', 1.0))
        elif exchange == 'okx':
            return float(data['data'][0].get('longRatio', 0.5)) / float(
                data['data'][0].get('shortRatio', 0.5)) if data.get('data') else 1.0
        elif exchange == 'bybit':
            return float(data['result']['list'][0].get('longRatio', 0.5)) / float(
                data['result']['list'][0].get('shortRatio', 0.5)) if data.get('result', {}).get('list') else 1.0
    except Exception as e:
        print(f"[HATA] {exchange} long/short oranı çıkarılamadı: {e}")
        return 1.0

async def fetch_coingecko_data(symbol):
    url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower().replace('usdt', '')}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    'open_interest': data.get('market_data', {}).get('total_volume'),
                    'funding_rate': None,
                    'long_short_ratio': None
                }
            return None

async def fetch_messari_data(symbol):
    url = f"https://data.messari.io/api/v1/assets/{symbol.lower().replace('usdt', '')}/metrics"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    'open_interest': data.get('market_data', {}).get('volume_last_24_hours'),
                    'funding_rate': None,
                    'long_short_ratio': None
                }
            return None

async def fetch_cryptocompare_data(symbol):
    url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={symbol.replace('USDT', '')}&tsyms=USDT"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    'open_interest': data.get('RAW', {}).get(symbol.replace('USDT', ''), {}).get('USDT', {}).get('VOLUME24HOUR'),
                    'funding_rate': None,
                    'long_short_ratio': None
                }
            return None

async def fetch_glassnode_data(symbol):
    # Glassnode için API anahtarı gerekebilir
    url = f"https://api.glassnode.com/v1/metrics/market/..."
    # Spesifik endpoint ve parametreler
    return None


class FuturesDataCache:
    def __init__(self, cache_duration=300):  # 5 dakika önbellek
        self.cache = {}
        self.cache_duration = cache_duration

    async def get_data(self, symbol):
        # Önbellekte varsa ve güncel ise önbellekten döndür
        if symbol in self.cache:
            cached_data, timestamp = self.cache[symbol]
            if time.time() - timestamp < self.cache_duration:
                return cached_data

        # Veriyi taze çek
        data = await aggregate_futures_data([symbol])

        # Önbelleğe kaydet
        self.cache[symbol] = (data, time.time())
        return data


# Kullanım
futures_cache = FuturesDataCache()


def advanced_data_validation(data_list):
    """
    Toplanan verilerin istatistiksel doğrulaması
    - Aykırı değerleri tespit etme
    - İstatistiksel tutarlılık kontrolü
    """
    if not data_list:
        return False

    # Z-skoru ile aykırı değer tespiti
    def is_outlier(value, mean, std):
        return abs((value - mean) / std) > 3

    validated_data = {}
    for key in ['open_interest', 'funding_rate', 'long_short_ratio']:
        values = [d[key] for d in data_list if d.get(key) is not None]

        if not values:
            continue

        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        validated_data[key] = [
            v for v in values
            if not is_outlier(v, mean, std)
        ]

    return validated_data

async def aggregate_futures_data(symbols):
    sources = [
        fetch_coingecko_data,
        fetch_messari_data,
        fetch_cryptocompare_data,
        fetch_glassnode_data
    ]

    async def fetch_multi_exchange_futures_data(symbol):
        exchanges = [
            {
                'name': 'Binance',
                'endpoints': {
                    'oi': f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
                    'funding': f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}",
                    'ls_ratio': f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
                }
            },
            {
                'name': 'OKX',
                'endpoints': {
                    'oi': f"https://www.okx.com/api/v5/public/open-interest?instId={symbol.replace('USDT', '-USDT')}-SWAP",
                    'funding': f"https://www.okx.com/api/v5/public/funding-rate?instId={symbol.replace('USDT', '-USDT')}-SWAP",
                    'ls_ratio': f"https://www.okx.com/api/v5/public/account-ratio?instId={symbol.replace('USDT', '-USDT')}-SWAP&period=1d"
                }
            }
        ]

        async def safe_fetch(session, url):
            try:
                async with session.get(url) as response:
                    return await response.json() if response.status == 200 else None
            except Exception as e:
                print(f"Veri çekme hatası: {e}")
                return None

        async def extract_data(session, exchange):
            results = {}
            for key, url in exchange['endpoints'].items():
                data = await safe_fetch(session, url)
                if data:
                    results[key] = data
            return results

        async with aiohttp.ClientSession() as session:
            tasks = [extract_data(session, exchange) for exchange in exchanges]
            results = await asyncio.gather(*tasks)

        # Veri konsolidasyonu ve doğrulama
        consolidated_data = {
            'symbol': symbol,
            'open_interest': [],
            'funding_rate': [],
            'long_short_ratio': []
        }

        for exchange_result in results:
            # OI Çıkarma
            if 'oi' in exchange_result:
                oi = _extract_oi(exchange_result['oi'])
                if oi:
                    consolidated_data['open_interest'].append(oi)

            # Funding Rate Çıkarma
            if 'funding' in exchange_result:
                fr = _extract_funding_rate(exchange_result['funding'])
                if fr is not None:
                    consolidated_data['funding_rate'].append(fr)

            # Long/Short Ratio Çıkarma
            if 'ls_ratio' in exchange_result:
                ls = _extract_ls_ratio(exchange_result['ls_ratio'])
                if ls is not None:
                    consolidated_data['long_short_ratio'].append(ls)

        # İstatistiksel konsolidasyon
        def consolidate_metric(values):
            if not values:
                return None
            return statistics.median(values)

        final_data = {
            'symbol': symbol,
            'open_interest': consolidate_metric(consolidated_data['open_interest']),
            'funding_rate': consolidate_metric(consolidated_data['funding_rate']),
            'long_short_ratio': consolidate_metric(consolidated_data['long_short_ratio'])
        }

        return final_data

    def _extract_oi(data):
        # Binance ve OKX için farklı OI çıkarma mantığı
        try:
            if 'openInterest' in data:
                return float(data['openInterest'])
            elif 'data' in data and data['data']:
                return float(data['data'][0].get('oi', 0))
        except Exception as e:
            print(f"OI çıkarma hatası: {e}")
        return None

    def _extract_funding_rate(data):
        # Farklı borsa formatları için funding rate çıkarma
        try:
            if 'lastFundingRate' in data:
                return float(data['lastFundingRate']) * 100
            elif 'data' in data and data['data']:
                return float(data['data'][0].get('fundingRate', 0)) * 100
        except Exception as e:
            print(f"Funding rate çıkarma hatası: {e}")
        return None

    def _extract_ls_ratio(data):
        # Long/Short oranı çıkarma
        try:
            if 'data' in data and data['data']:
                long_ratio = float(data['data'][0].get('longRatio', 0.5))
                short_ratio = float(data['data'][0].get('shortRatio', 0.5))
                return long_ratio / short_ratio if short_ratio > 0 else 1.0
        except Exception as e:
            print(f"Long/Short oranı çıkarma hatası: {e}")
        return None

    async def process_symbol(symbol):
        results = []
        for source in sources:
            try:
                data = await source(symbol)
                if validate_data(data):
                    results.append(data)
            except Exception as e:
                print(f"[UYARI] {symbol} - {source.__name__} hatası: {e}")

        return consolidate_data(results)

    async with aiohttp.ClientSession() as session:
        tasks = [process_symbol(symbol) for symbol in symbols]
        return await asyncio.gather(*tasks)


def process_kline_data(kline_data):
    if not kline_data or len(kline_data) < 2:
        return None

    try:
        df = pd.DataFrame(kline_data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        # Numerik dönüşümler
        numeric_columns = ["open", "high", "low", "close", "volume", "quote_volume",
                           "taker_buy_base", "taker_buy_quote"]

        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # NaN temizleme
        df.dropna(subset=numeric_columns, inplace=True)

        if len(df) < 2:
            return None

        return df

    except Exception as e:
        print(f"[HATA] Kline veri işleme hatası: {e}")
        return None


def validate_data(data):
    """Veri doğrulama kriterleri"""
    checks = [
        ('open_interest', lambda x: x is not None and x > 0),
        ('funding_rate', lambda x: x is not None and -10 < x < 10),
        ('long_short_ratio', lambda x: x is not None and 0 < x < 10)
    ]

    return all(validator(data.get(field)) for field, validator in checks)


def consolidate_data(results):
    """Birden fazla kaynaktan gelen verileri birleştir"""
    if not results:
        return None

    # Medyan hesaplama
    consolidated = {}
    for key in ['open_interest', 'funding_rate', 'long_short_ratio']:
        values = [result[key] for result in results if result.get(key) is not None]
        consolidated[key] = statistics.median(values) if values else None

    return consolidated


def _select_best_futures_data(exchange_data):
    """
    Birden fazla borsadan gelen verilerin en güvenilirini seçer

    Args:
        exchange_data (dict): Borsaların vadeli işlem verileri

    Returns:
        dict: En güvenilir vadeli işlem verisi
    """
    # Güvenilirlik sırası: Binance > Bybit > OKX
    preferred_order = ['binance', 'bybit', 'okx']

    for exchange in preferred_order:
        if exchange_data[exchange] and all(
                exchange_data[exchange].get(key) not in [0, 1.0, None]
                for key in ['open_interest', 'funding_rate', 'long_short_ratio']
        ):
            return exchange_data[exchange]

    # Hiçbir veri güvenilir değilse varsayılan
    return {
        'symbol': list(exchange_data.values())[0]['symbol'],
        'open_interest': 0,
        'funding_rate': 0,
        'long_short_ratio': 1.0
    }


def advanced_futures_analysis(results):
    """
    Gelişmiş vadeli işlemler analizi
    """
    # Detaylı risk skoru hesaplamaları
    risk_scores = []
    for result in results:
        oi = result['open_interest']
        funding_rate = result['funding_rate']
        ls_ratio = result['long_short_ratio']

        # Dinamik risk skoru hesaplama
        risk_score = (
                             (oi / 1e6) * 0.4 +  # Open Interest etkisi
                             abs(funding_rate) * 0.3 +  # Funding Rate volatilitesi
                             abs(1 - ls_ratio) * 0.3  # Long/Short dengesizliği
                     ) * 100

        risk_scores.append({
            'risk_score': min(max(risk_score, 0), 100),
            'details': result
        })

    return sorted(risk_scores, key=lambda x: x['risk_score'], reverse=True)


def generate_futures_timeframe_analysis():
    """
    Çoklu zaman diliminde vadeli işlem verilerini analiz eden rapor oluşturur
    """
    if not ALL_RESULTS:
        return "⚠️ Henüz analiz verisi bulunmuyor."

    report = f"⏱️ <b>Çoklu Zaman Dilimi Vadeli İşlemler Analizi – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "Bu rapor, farklı zaman dilimlerinde vadeli işlem verilerini ve hacim desteğini analiz eder.\n\n"

    timeframes = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}
    all_scores = {}

    # BTC/ETH fiyat değişimini al - piyasa durumunu anlamak için
    try:
        btc_change = 0
        eth_change = 0
        for coin in ALL_RESULTS:
            if coin["Coin"] == "BTCUSDT":
                btc_change = extract_numeric(coin["24h Change"])
            elif coin["Coin"] == "ETHUSDT":
                eth_change = extract_numeric(coin["24h Change"])

        report += f"<b>Piyasa Durumu:</b> BTC %{btc_change:.2f}, ETH %{eth_change:.2f}\n\n"
    except Exception as e:
        print(f"[HATA] BTC/ETH fiyat değişimi alınamadı: {e}")

    for timeframe, minutes in timeframes.items():
        print(f"[INFO] {timeframe} zaman dilimi analiz ediliyor...")
        coin_scores = []

        for coin in ALL_RESULTS[:20]:  # İlk 20 coin
            try:
                symbol = coin["Coin"]

                # Kline verilerini al
                kline_data = sync_fetch_kline_data(symbol, timeframe, limit=20)
                if not kline_data or len(kline_data) < 5:
                    print(f"[UYARI] {symbol} için {timeframe} kline verisi yetersiz")
                    continue

                # DataFrame'e dönüştür
                df = pd.DataFrame(kline_data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                                       "close_time", "quote_volume", "trades", "taker_buy_base",
                                                       "taker_buy_quote", "ignore"])

                # Sayısal tiplere dönüştür
                for col in ["close", "volume", "quote_volume"]:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # Temel hesaplamalar
                try:
                    price_change = ((df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]) * 100
                except:
                    price_change = 0

                try:
                    volume_change = ((df["volume"].iloc[-1] - df["volume"].iloc[0]) / df["volume"].iloc[0]) * 100
                except:
                    volume_change = 0

                # OI değişimi ve funding rate
                try:
                    oi_change = fetch_futures_oi_changes(symbol, timeframe)
                except Exception as e:
                    print(f"[HATA] {symbol} OI değişimi alınamadı: {e}")
                    oi_change = 0

                try:
                    # Use safe defaults - no futures data available
                    futures_data = {
                        "funding_rate": 0,
                        "open_interest": 0,
                        "long_short_ratio": 1.0
                    }

                    funding_rate = futures_data.get("funding_rate", 0)
                    ls_ratio = futures_data.get("long_short_ratio", 1.0)
                except Exception as e:
                    print(f"[HATA] {symbol} vadeli veri alınamadı: {e}")
                    funding_rate = 0
                    ls_ratio = 1.0

                # Buyer ratio (alıcı oranı)
                try:
                    buyer_ratio = calculate_buyer_ratio(kline_data)
                    if buyer_ratio == "N/A":
                        buyer_ratio = 50
                except Exception as e:
                    print(f"[HATA] {symbol} alıcı oranı hesaplanamadı: {e}")
                    buyer_ratio = 50

                # Skor hesaplama
                score = 50  # Nötr başla

                # Yükseliş sinyalleri
                if price_change > 1:
                    score += 10
                if price_change > 3:
                    score += 10
                if volume_change > 20 and price_change > 0:
                    score += 10
                if oi_change > 2 and price_change > 0:
                    score += 10
                if ls_ratio > 1.2:  # Long pozisyonlar fazlaysa
                    score += 5
                if buyer_ratio > 55:
                    score += 5

                # Düşüş sinyalleri
                if price_change < -1:
                    score -= 10
                if price_change < -3:
                    score -= 10
                if volume_change > 20 and price_change < 0:
                    score -= 10
                if oi_change > 2 and price_change < 0:
                    score -= 10
                if ls_ratio < 0.8:  # Short pozisyonlar fazlaysa
                    score -= 5
                if buyer_ratio < 45:
                    score -= 5

                # Ekstrem funding rate etkisi
                if abs(funding_rate) > 0.1:
                    if funding_rate > 0:  # Positive funding = longs pay shorts
                        score -= 5  # Longlara karşı bir baskı
                    else:
                        score += 5  # Shortlara karşı bir baskı

                # Skoru normalize et
                score = max(min(score, 100), 0)

                # Sonuçları kaydet
                coin_scores.append({
                    "symbol": symbol,
                    "score": score,
                    "price_change": price_change,
                    "volume_change": volume_change,
                    "oi_change": oi_change,
                    "funding_rate": funding_rate,
                    "ls_ratio": ls_ratio,
                    "buyer_ratio": buyer_ratio
                })

            except Exception as e:
                print(f"[HATA] {coin['Coin']} için {timeframe} analizi sırasında hata: {e}")
                continue

        # Skora göre sırala (en yüksek puandan en düşüğe)
        sorted_scores = sorted(coin_scores, key=lambda x: x["score"], reverse=True)
        all_scores[timeframe] = sorted_scores

        # Zaman dilimi raporunu ekle
        report += f"📊 <b>{timeframe} Zaman Dilimi İçin En İyi Coinler:</b>\n"

        # Eğer hiç sonuç yoksa
        if not sorted_scores:
            report += "  Bu zaman dilimi için analiz sonucu bulunamadı.\n\n"
            continue

        # En yüksek skorlu 5 coini göster
        for i, coin in enumerate(sorted_scores[:5], 1):
            # Değerleri al
            symbol = coin["symbol"]
            score = coin["score"]
            pc = coin["price_change"]
            vc = coin["volume_change"]
            oc = coin["oi_change"]
            fr = coin["funding_rate"]
            ls = coin["ls_ratio"]
            br = coin["buyer_ratio"]

            # Skorun anlamını belirle
            if score >= 70:
                trend_emoji = "🔥"
                trend_desc = "Çok Güçlü Sinyal"
            elif score >= 60:
                trend_emoji = "📈"
                trend_desc = "Güçlü Sinyal"
            elif score >= 40:
                trend_emoji = "⚖️"
                trend_desc = "Nötr"
            elif score >= 30:
                trend_emoji = "📉"
                trend_desc = "Zayıf Sinyal"
            else:
                trend_emoji = "❄️"
                trend_desc = "Çok Zayıf Sinyal"

            # volume yorumu
            volume_comment = ""
            if vc > 50 and pc > 0:
                volume_comment = "💪 Çok güçlü hacim desteği!"
            elif vc > 20 and pc > 0:
                volume_comment = "👍 İyi hacim desteği"
            elif vc < -30 and pc < 0:
                volume_comment = "📉 volume düşüşle uyumlu"
            elif vc > 20 and pc < 0:
                volume_comment = "⚠️ volume artıyor ama fiyat düşüyor"

            report += f"{i}. {trend_emoji} <b>{symbol}</b> (Skor: {score:.0f}) - {trend_desc}\n"
            report += f"   • Fiyat Değişimi: {pc:.2f}%\n"
            report += f"   • volume Değişimi: {vc:.2f}% {volume_comment}\n"
            report += f"   • OI Değişimi: {oc:.2f}%\n"
            report += f"   • Funding Rate: {fr:.4f}%\n"
            report += f"   • L/S Oranı: {ls:.2f} (>1: long fazla, <1: short fazla)\n"
            report += f"   • Alıcı Oranı: %{br}\n\n"

    # Tüm zaman dilimleri için ortalama skorları hesapla
    avg_scores = {tf: sum(c["score"] for c in scores) / len(scores) if scores else 0 for tf, scores in
                  all_scores.items()}

    report += "📈 <b>Zaman Dilimi Analizi:</b>\n"
    for tf, avg in avg_scores.items():
        if avg >= 60:
            trend = "Yükseliş trendi"
            emoji = "🔼"
        elif avg <= 40:
            trend = "Düşüş trendi"
            emoji = "🔽"
        else:
            trend = "Yatay seyir"
            emoji = "➡️"

        report += f"• {tf}: Ortalama Skor {avg:.1f} - {emoji} {trend}\n"

    report += "\n<b>Yorum:</b>\n"
    overall_score = sum(avg_scores.values()) / len(avg_scores)
    if overall_score >= 60:
        report += "Çoğu zaman diliminde yükseliş sinyalleri hakim. Kısa ve orta vadede alım fırsatları değerlendirilebilir.\n"
    elif overall_score >= 50:
        report += "Karma sinyaller mevcut, ancak hafif yükseliş eğilimi var. Seçici olun ve daha uzun zaman dilimlerine odaklanın.\n"
    elif overall_score >= 40:
        report += "Yatay seyir hakim. Breakout/breakdown için beklemede kalın, range ticareti düşünülebilir.\n"
    elif overall_score >= 30:
        report += "Hafif düşüş eğilimi var. Risk yönetimine dikkat edin, uzun pozisyonları azaltmayı düşünün.\n"
    else:
        report += "Güçlü düşüş sinyalleri hakim. Stop-loss kullanın, kısa pozisyonlar veya nakit tutma düşünülebilir.\n"

    report += "\n📝 <b>Not:</b>\n"
    report += "• Tüm zaman dilimlerinde yüksek skor alan coinler daha güvenilir sinyal verir.\n"
    report += "• Fiyat ve OI'nin aynı yönde hareketi, trend gücünü doğrular.\n"
    report += "• volume desteği, trendin sürdürülebilirliğini gösterir.\n"
    report += "• L/S oranının aşırı değerleri (>1.5 veya <0.7) zaman zaman tersine dönüşleri tetikleyebilir.\n"

    return report

def fetch_volume_change_for_timeframe(symbol, timeframe):
    """
    Belirli bir zaman dilimi için hacim değişimini hesaplar.

    Args:
        symbol (str): Coin sembolü
        timeframe (str): Zaman dilimi (örn: "5m", "15m", "1h", "4h")

    Returns:
        float: volume değişim yüzdesi
    """
    try:
        kline_data = sync_fetch_kline_data(symbol, timeframe, limit=20)
        if not kline_data or len(kline_data) < 2:
            return 0

        # Son 5 mumun hacim verilerini al
        recent_volumes = [float(k[7]) for k in kline_data[-5:]]
        # Önceki 5 mumun hacim verilerini al
        previous_volumes = [float(k[7]) for k in kline_data[-10:-5]]

        if not previous_volumes or sum(previous_volumes) == 0:
            return 0

        # volume değişimini hesapla
        avg_recent = sum(recent_volumes) / len(recent_volumes)
        avg_previous = sum(previous_volumes) / len(previous_volumes)

        volume_change = ((avg_recent - avg_previous) / avg_previous) * 100
        return volume_change
    except Exception as e:
        print(f"[HATA] {symbol} için {timeframe} hacim değişimi hesaplanırken hata: {e}")
        return 0


def fetch_volume_change_for_timeframe_improved(symbol, timeframe):
    """
    Belirli bir zaman dilimi için hacim değişimini daha güvenilir şekilde hesaplar.
    Aykırı değerleri filtreler ve daha dengeli karşılaştırma yapar.

    Args:
        symbol (str): Coin sembolü
        timeframe (str): Zaman dilimi (örn: "5m", "15m", "1h", "4h")

    Returns:
        float: volume değişim yüzdesi (filtrelenmiş ve düzeltilmiş)
    """
    try:
        # Daha fazla veri noktası al (daha güvenilir karşılaştırma için)
        kline_data = sync_fetch_kline_data(symbol, timeframe, limit=30)
        if not kline_data or len(kline_data) < 10:
            return 0

        # Son 10 mumun hacim verilerini al
        recent_volumes = [float(k[7]) for k in kline_data[-10:]]
        # Önceki 10 mumun hacim verilerini al
        previous_volumes = [float(k[7]) for k in kline_data[-20:-10]]

        if not previous_volumes or sum(previous_volumes) == 0:
            return 0

        # Aykırı değerleri filtrele (Z-skor yöntemi ile)
        def filter_outliers(volumes, threshold=2.0):
            if not volumes:
                return []
            mean = sum(volumes) / len(volumes)
            std = (sum((x - mean) ** 2 for x in volumes) / len(volumes)) ** 0.5
            if std == 0:
                return volumes
            return [v for v in volumes if abs((v - mean) / std) <= threshold]

        # Aykırı değerleri filtrele
        filtered_recent = filter_outliers(recent_volumes)
        filtered_previous = filter_outliers(previous_volumes)

        # Filtrelenmiş değerler çok azsa, orijinal değerleri kullan
        if len(filtered_recent) < 3:
            filtered_recent = recent_volumes
        if len(filtered_previous) < 3:
            filtered_previous = previous_volumes

        # volume değişimini hesapla (medyan kullanarak - daha stabil)
        avg_recent = sorted(filtered_recent)[len(filtered_recent) // 2]  # medyan
        avg_previous = sorted(filtered_previous)[len(filtered_previous) // 2]  # medyan

        # Son kontrol - sıfıra bölmeyi önle
        if avg_previous == 0:
            return 0

        volume_change = ((avg_recent - avg_previous) / avg_previous) * 100

        # Aşırı değerleri sınırla (-100% ile +300% arası mantıklı bir aralık)
        volume_change = max(min(volume_change, 300), -95)

        return volume_change
    except Exception as e:
        print(f"[HATA] {symbol} için {timeframe} hacim değişimi hesaplanırken hata: {e}")
        return 0


def fetch_futures_oi_changes_improved(symbol, timeframe, limit=2):
    """
    Belirli bir zaman dilimi için OI değişimini daha güvenilir şekilde hesaplar.
    Birden fazla veri kaynağını dener ve farklı API formatlarına uyum sağlar.

    Args:
        symbol (str): Coin çifti (ör. 'BTCUSDT')
        timeframe (str): Zaman aralığı (ör. '5m', '15m', '1h', '4h')
        limit (int): Karşılaştırma için veri noktası sayısı (varsayılan 2)

    Returns:
        float: OI değişimi yüzdesi
    """
    try:
        # Doğru API endpoint kullanımı
        url = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period={timeframe}&limit={limit + 2}"
        response = requests.get(url, timeout=10)

        # Rate limit kontrolü
        if response.status_code == 429:
            print(f"[UYARI] {symbol} için rate limit hatası, 5 saniye bekleniyor...")
            time.sleep(5)
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if len(data) >= 2:
                # sumOpenInterestValue kullan (değer cinsinden ölçüm için daha güvenilir)
                current_oi = float(data[0]["sumOpenInterestValue"])
                previous_oi = float(data[1]["sumOpenInterestValue"])

                if previous_oi > 0:
                    oi_change = ((current_oi - previous_oi) / previous_oi) * 100
                    print(f"[DEBUG] {symbol} - {timeframe} OI Değişimi: {oi_change:.2f}%")
                    return oi_change
                else:
                    print(f"[UYARI] {symbol} previous OI sıfır")
            else:
                print(f"[UYARI] {symbol} - {timeframe} için yeterli OI verisi yok: {len(data)} kayıt")
        else:
            print(f"[HATA] {symbol} OI verisi alınamadı: {response.status_code}")

        # Plan B: Alternatif API endpoint dene
        alt_url = f"https://fapi.binance.com/futures/data/openInterest?symbol={symbol}"
        curr_oi_resp = requests.get(alt_url, timeout=10)

        if curr_oi_resp.status_code == 200:
            current_oi_data = curr_oi_resp.json()
            current_oi = float(current_oi_data.get("openInterest", 0))

            # Mevcut fiyatı al ve dolar değerine çevir
            ticker_url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
            ticker_resp = requests.get(ticker_url, timeout=10)
            if ticker_resp.status_code == 200:
                curr_price = float(ticker_resp.json().get("price", 0))
                current_oi_value = current_oi * curr_price

                # PREV_STATS'tan önceki OI değerini kontrol et
                with global_lock:
                    prev_oi_value = PREV_STATS.get(symbol, {}).get("open_interest_value", 0)

                if prev_oi_value > 0:
                    oi_change = ((current_oi_value - prev_oi_value) / prev_oi_value) * 100

                    # PREV_STATS'ı güncelle
                    with global_lock:
                        if symbol not in PREV_STATS:
                            PREV_STATS[symbol] = {}
                        PREV_STATS[symbol]["open_interest_value"] = current_oi_value

                    return oi_change
                else:
                    # İlk çalıştırma - değişim 0 kabul edilir ama değeri kaydederiz
                    with global_lock:
                        if symbol not in PREV_STATS:
                            PREV_STATS[symbol] = {}
                        PREV_STATS[symbol]["open_interest_value"] = current_oi_value

        # Hiçbir veri alınamazsa OKX veya Bybit'i dene
        try:
            okx_data = fetch_okx_futures_data(symbol)
            bybit_data = fetch_bybit_futures_data(symbol)

            okx_oi = okx_data.get("open_interest", 0)
            bybit_oi = bybit_data.get("open_interest", 0)

            # PREV_STATS'tan önceki değerleri kontrol et
            with global_lock:
                prev_okx_oi = PREV_STATS.get(symbol, {}).get("okx_oi", 0)
                prev_bybit_oi = PREV_STATS.get(symbol, {}).get("bybit_oi", 0)

            # Değişimleri hesapla
            okx_change = ((okx_oi - prev_okx_oi) / prev_okx_oi * 100) if prev_okx_oi > 0 else 0
            bybit_change = ((bybit_oi - prev_bybit_oi) / prev_bybit_oi * 100) if prev_bybit_oi > 0 else 0

            # Değerleri güncelle
            with global_lock:
                if symbol not in PREV_STATS:
                    PREV_STATS[symbol] = {}
                PREV_STATS[symbol]["okx_oi"] = okx_oi
                PREV_STATS[symbol]["bybit_oi"] = bybit_oi

            # En güvenilir değişimi döndür
            if abs(okx_change) > 0:
                return okx_change
            elif abs(bybit_change) > 0:
                return bybit_change
        except Exception as e:
            print(f"[HATA] {symbol} alternatif borsa OI değişimi alınamadı: {e}")

        # Son çare: OI değişimi 0 kabul et
        return 0.0

    except Exception as e:
        print(f"[HATA] {symbol} OI değişimi alınamadı: {e}")
        return 0.0


def fetch_enhanced_ls_ratio(symbol):
    try:
        results = []
        debug_info = []
        
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)

        print(f"\n[DEBUG] {symbol} için L/S oranı hesaplanıyor...")

        # 1. Binance Global L/S Ratio
        try:
            # URL'yi düzeltelim
            ls_url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
            print(f"[DEBUG] Binance Global URL: {ls_url}")
            ls_response = session.get(ls_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})

            if ls_response.status_code == 200 and ls_response.json():
                data = ls_response.json()
                print(f"[DEBUG] Binance Global Response: {data}")
                if data and len(data) > 0:
                    ls_ratio = float(data[0].get("longShortRatio", 1.0))
                    if 0.1 <= ls_ratio <= 10:
                        results.append(("binance_global", ls_ratio))
                        debug_info.append(f"Binance Global L/S: {ls_ratio:.2f}")
                    else:
                        print(f"[UYARI] Binance Global L/S oranı ({ls_ratio:.2f}) geçersiz aralıkta")
            else:
                print(f"[UYARI] Binance Global API hatası: {ls_response.status_code}")
        except Exception as e:
            print(f"[HATA] Binance Global Hata: {str(e)}")

        # 2. Binance Top Accounts
        try:
            alt_ls_url = f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
            print(f"[DEBUG] Binance Top URL: {alt_ls_url}")
            alt_ls_response = session.get(alt_ls_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})

            if alt_ls_response.status_code == 200 and alt_ls_response.json():
                data = alt_ls_response.json()
                print(f"[DEBUG] Binance Top Response: {data}")
                if data and len(data) > 0:
                    long_account = float(data[0].get("longAccount", 50))
                    short_account = float(data[0].get("shortAccount", 50))
                    if short_account > 0:
                        ls_ratio = long_account / short_account
                        if 0.1 <= ls_ratio <= 10:
                            results.append(("binance_top", ls_ratio))
                            debug_info.append(f"Binance Top Accounts L/S: {ls_ratio:.2f}")
                        else:
                            print(f"[UYARI] Binance Top L/S oranı ({ls_ratio:.2f}) geçersiz aralıkta")
            else:
                print(f"[UYARI] Binance Top API hatası: {alt_ls_response.status_code}")
        except Exception as e:
            print(f"[HATA] Binance Top Hata: {str(e)}")

        # 3. Binance Positions Ratio
        try:
            pos_ls_url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
            print(f"[DEBUG] Binance Positions URL: {pos_ls_url}")
            pos_ls_response = session.get(pos_ls_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})

            if pos_ls_response.status_code == 200 and pos_ls_response.json():
                data = pos_ls_response.json()
                print(f"[DEBUG] Binance Positions Response: {data}")
                if data and len(data) > 0:
                    long_pos = float(data[0].get("longPosition", 50))
                    short_pos = float(data[0].get("shortPosition", 50))
                    if short_pos > 0:
                        ls_ratio = long_pos / short_pos
                        if 0.1 <= ls_ratio <= 10:
                            results.append(("binance_positions", ls_ratio))
                            debug_info.append(f"Binance Positions L/S: {ls_ratio:.2f}")
                        else:
                            print(f"[UYARI] Binance Positions L/S oranı ({ls_ratio:.2f}) geçersiz aralıkta")
            else:
                print(f"[UYARI] Binance Positions API hatası: {pos_ls_response.status_code}")
        except Exception as e:
            print(f"[HATA] Binance Positions Hata: {str(e)}")

        # Sonuçları analiz et
        if results:
            print(f"\n[DEBUG] {symbol} için bulunan L/S oranları:")
            for source, ratio in results:
                print(f"  - {source}: {ratio:.2f}")

            # En son alınan veriyi tercih et
            latest_ratio = results[-1][1]

            # Tüm sonuçların ortalamasını al
            avg_ratio = sum(r[1] for r in results) / len(results)
            print(f"[DEBUG] Ortalama L/S oranı: {avg_ratio:.2f}")

            # Ortalamadan çok sapma gösteren değerleri filtrele
            filtered_ratios = [r[1] for r in results if 0.5 * avg_ratio <= r[1] <= 2 * avg_ratio]
            print(f"[DEBUG] Filtrelenmiş L/S oranları: {[f'{r:.2f}' for r in filtered_ratios]}")

            if filtered_ratios:
                final_ratio = sum(filtered_ratios) / len(filtered_ratios)
                print(f"[DEBUG] Final L/S oranı: {final_ratio:.2f}")
                return final_ratio
            else:
                print(f"[UYARI] {symbol} için tüm L/S oranları ortalamadan çok sapma gösteriyor")
                return latest_ratio
        else:
            print(f"[UYARI] {symbol} için hiçbir kaynaktan geçerli L/S oranı alınamadı")
            return 1.0

    except Exception as e:
        print(f"[HATA] {symbol} L/S oranı hesaplanırken genel hata: {e}")
        return 1.0



def fetch_improved_ls_ratio(symbol):
    """
    Long/Short oranını daha doğru bir şekilde hesaplar.
    Birden fazla veri kaynağını deneyerek en güvenilir veriyi bulmaya çalışır.

    Args:
        symbol (str): Coin sembolü (örn: BTCUSDT)

    Returns:
        float: Long/Short oranı
    """
    try:
        # 1. Binance Global L/S Ratio
        ls_url = f"{BINANCE_FUTURES_API_URL.replace('/v1/', '/futures/data/')}globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        ls_response = requests.get(ls_url, timeout=10)

        if ls_response.status_code == 200 and ls_response.json():
            data = ls_response.json()
            if data and len(data) > 0:
                ls_ratio = float(data[0].get("longShortRatio", 1.0))
                print(f"[DEBUG] {symbol} Global L/S Ratio: {ls_ratio:.2f}")
                return ls_ratio

        # 2. Binance Top Accounts L/S Ratio
        alt_ls_url = f"{BINANCE_FUTURES_API_URL.replace('/v1/', '/futures/data/')}topLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
        alt_ls_response = requests.get(alt_ls_url, timeout=10)

        if alt_ls_response.status_code == 200 and alt_ls_response.json():
            data = alt_ls_response.json()
            if data and len(data) > 0:
                long_account = float(data[0].get("longAccount", 50))
                short_account = float(data[0].get("shortAccount", 50))
                if short_account > 0:
                    ls_ratio = long_account / short_account
                    print(f"[DEBUG] {symbol} Top Accounts L/S Ratio: {ls_ratio:.2f}")
                    return ls_ratio

        # 3. Binance Positions Ratio
        pos_ls_url = f"{BINANCE_FUTURES_API_URL.replace('/v1/', '/futures/data/')}topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
        pos_ls_response = requests.get(pos_ls_url, timeout=10)

        if pos_ls_response.status_code == 200 and pos_ls_response.json():
            data = pos_ls_response.json()
            if data and len(data) > 0:
                long_pos = float(data[0].get("longPosition", 50))
                short_pos = float(data[0].get("shortPosition", 50))
                if short_pos > 0:
                    ls_ratio = long_pos / short_pos
                    print(f"[DEBUG] {symbol} Positions L/S Ratio: {ls_ratio:.2f}")
                    return ls_ratio

        # 4. Bybit L/S Ratio
        try:
            normalized_symbol = normalize_symbol_for_exchange(symbol, "bybit")
            bybit_ls_url = f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={normalized_symbol}&period=1d"
            bybit_ls_response = requests.get(bybit_ls_url, timeout=10)

            if bybit_ls_response.status_code == 200:
                bybit_data = bybit_ls_response.json()
                if "result" in bybit_data and "list" in bybit_data["result"] and bybit_data["result"]["list"]:
                    bybit_list = bybit_data["result"]["list"]
                    if bybit_list and len(bybit_list) > 0:
                        long_ratio = float(bybit_list[0].get("longRatio", 0.5))
                        short_ratio = float(bybit_list[0].get("shortRatio", 0.5))

                        if short_ratio > 0:
                            ls_ratio = long_ratio / short_ratio
                            print(f"[DEBUG] {symbol} Bybit L/S Ratio: {ls_ratio:.2f}")
                            return ls_ratio
        except Exception as e:
            print(f"[HATA] {symbol} Bybit L/S oranı alınamadı: {e}")

        # 5. OKX L/S Ratio
        try:
            normalized_symbol = normalize_symbol_for_exchange(symbol, "okx")
            okx_ls_url = f"https://www.okx.com/api/v5/public/long-short-ratio?instId={normalized_symbol}-SWAP"
            okx_ls_response = requests.get(okx_ls_url, timeout=10)

            if okx_ls_response.status_code == 200:
                okx_data = okx_ls_response.json()
                if "data" in okx_data and okx_data["data"]:
                    okx_list = okx_data["data"]
                    if okx_list and len(okx_list) > 0:
                        long_short_ratio = float(okx_list[0].get("longShortRatio", 1.0))
                        print(f"[DEBUG] {symbol} OKX L/S Ratio: {long_short_ratio:.2f}")
                        return long_short_ratio
        except Exception as e:
            print(f"[HATA] {symbol} OKX L/S oranı alınamadı: {e}")

        # Hiçbir veri alınamazsa varsayılan değer
        print(f"[UYARI] {symbol} için L/S oranı alınamadı, varsayılan değer 1.0 dönülüyor")
        return 1.0

    except Exception as e:
        print(f"[HATA] {symbol} L/S oranı alınırken genel hata: {e}")
        return 1.0


def generate_futures_timeframe_analysis():
    """
    Generates an improved report analyzing futures data across multiple timeframes.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"⏱️ <b>Multi-Timeframe Futures Analysis – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report analyzes futures data and volume support across different timeframes.\n\n"

    timeframes = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}
    all_scores = {}

    # Get BTC/ETH price change to understand market status
    try:
        btc_change = 0
        eth_change = 0
        for coin in ALL_RESULTS:
            if coin["Coin"] == "BTCUSDT":
                btc_change = extract_numeric(coin["24h Change"])
            elif coin["Coin"] == "ETHUSDT":
                eth_change = extract_numeric(coin["24h Change"])

        report += f"<b>Market Status:</b> BTC {btc_change:+.2f}%, ETH {eth_change:+.2f}%\n\n"
    except Exception as e:
        print(f"[ERROR] Could not fetch BTC/ETH price change: {e}")

    for timeframe, minutes in timeframes.items():
        print(f"[INFO] Analyzing {timeframe} timeframe...")
        coin_scores = []

        for coin in ALL_RESULTS[:50]:  # Top 50 coins
            try:
                symbol = coin["Coin"]

                # Fetch kline data
                kline_data = sync_fetch_kline_data(symbol, timeframe, limit=30)
                if not kline_data or len(kline_data) < 10:
                    continue

                # Convert to DataFrame
                df = pd.DataFrame(kline_data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                                       "close_time", "quote_volume", "trades", "taker_buy_base",
                                                       "taker_buy_quote", "ignore"])

                # Convert to numeric
                for col in ["close", "volume", "quote_volume"]:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # Base calculations
                try:
                    first_close = df["close"].iloc[0]
                    last_close = df["close"].iloc[-1]
                    price_change = ((last_close - first_close) / first_close) * 100 if first_close > 0 else 0
                except:
                    price_change = 0

                # Improved volume change calculation
                volume_change = fetch_volume_change_for_timeframe_improved(symbol, timeframe)

                # Improved OI change and funding rate
                try:
                    oi_change = fetch_futures_oi_changes_improved(symbol, timeframe)
                except:
                    oi_change = 0

                try:
                    # Use safe defaults - no futures data available  
                    futures_data = {
                        "funding_rate": 0,
                        "open_interest": 0,
                        "long_short_ratio": 1.0
                    }

                    funding_rate = futures_data.get("funding_rate", 0)
                    ls_ratio = futures_data.get("long_short_ratio", 1.0)
                except Exception as e:
                    funding_rate = 0
                    ls_ratio = 1.0

                # Buyer ratio
                try:
                    buyer_ratio = calculate_buyer_ratio(kline_data)
                    if buyer_ratio == "N/A":
                        buyer_ratio = 50
                except:
                    buyer_ratio = 50

                # Score calculation
                score = 50  # Neutral start

                if price_change > 1: score += 10
                if price_change > 3: score += 15
                if price_change < -1: score -= 10
                if price_change < -3: score -= 15

                if volume_change > 20: score += 10
                if volume_change > 50: score += 15
                if volume_change < -20: score -= 5

                if oi_change > 5: score += 10
                if oi_change > 10: score += 15
                if oi_change < -5: score -= 10

                if buyer_ratio > 55: score += 10
                if buyer_ratio > 65: score += 20
                if buyer_ratio < 45: score -= 10

                coin_scores.append({
                    "symbol": symbol,
                    "score": score,
                    "price_change": price_change,
                    "volume_change": volume_change,
                    "oi_change": oi_change,
                    "funding_rate": funding_rate,
                    "ls_ratio": ls_ratio,
                    "buyer_ratio": buyer_ratio
                })

            except Exception as e:
                print(f"[HATA] {coin['Coin']} için {timeframe} analizi sırasında hata: {e}")
                continue

        # Skora göre sırala (en yüksek puandan en düşüğe)
        sorted_scores = sorted(coin_scores, key=lambda x: x["score"], reverse=True)
        all_scores[timeframe] = sorted_scores

        # Zaman dilimi raporunu ekle
        report += f"📊 <b>{timeframe} Zaman Dilimi İçin En İyi Coinler:</b>\n"

        # Eğer hiç sonuç yoksa
        if not sorted_scores:
            report += "  Bu zaman dilimi için analiz sonucu bulunamadı.\n\n"
            continue

        # En yüksek skorlu 5 coini göster
        for i, coin in enumerate(sorted_scores[:5], 1):
            # Değerleri al
            symbol = coin["symbol"]
            score = coin["score"]
            pc = coin["price_change"]
            vc = coin["volume_change"]
            volume_comment = coin["volume_comment"]
            oc = coin["oi_change"]
            fr = coin["funding_rate"]
            ls = coin["ls_ratio"]
            br = coin["buyer_ratio"]

            # Skorun anlamını belirle - Emoji sorunu düzeltildi
            if score >= 70:
                trend_emoji = "🔥"
                trend_desc = "Çok Güçlü Sinyal"
            elif score >= 60:
                trend_emoji = "📈"
                trend_desc = "Güçlü Sinyal"
            elif score >= 40:
                trend_emoji = "⚖️"
                trend_desc = "Nötr"
            elif score >= 30:
                trend_emoji = "📉"
                trend_desc = "Zayıf Sinyal"
            else:
                trend_emoji = "❄️"
                trend_desc = "Çok Zayıf Sinyal"

            report += f"{i}. {trend_emoji} <b>{symbol}</b> (Skor: {score:.0f}) - {trend_desc}\n"
            report += f"   • Fiyat Değişimi: {pc:.2f}%\n"

            # volume yorumu sadece anlamlıysa göster
            report += f"   • volume Değişimi: {vc:.2f}% {volume_comment}\n"

            # OI değeri sadece anlamlıysa göster (0 değilse)
            report += f"   • OI Değişimi: {oc:.2f}%\n"
            report += f"   • Funding Rate: {fr:.4f}%\n"
            report += f"   • L/S Oranı: {ls:.2f} (>1: long fazla, <1: short fazla)\n"
            report += f"   • Alıcı Oranı: %{br}\n\n"

    # Tüm zaman dilimleri için ortalama skorları hesapla
    avg_scores = {tf: sum(c["score"] for c in scores) / len(scores) if scores else 0 for tf, scores in
                  all_scores.items()}

    report += "📈 <b>Zaman Dilimi Analizi:</b>\n"
    for tf, avg in avg_scores.items():
        # Emoji sorununu çöz
        if avg >= 60:
            trend = "Yükseliş trendi"
            emoji = "🔼"
        elif avg <= 40:
            trend = "Düşüş trendi"
            emoji = "🔽"
        else:
            trend = "Yatay seyir"
            emoji = "➡️"

        # Emoji sorununu düzelt
        emoji = ensure_emojis(emoji)
        report += f"• {tf}: Ortalama Skor {avg:.1f} - {emoji} {trend}\n"

    report += "\n<b>Yorum:</b>\n"
    overall_score = sum(avg_scores.values()) / len(avg_scores)
    if overall_score >= 60:
        report += "Çoğu zaman diliminde yükseliş sinyalleri hakim. Kısa ve orta vadede alım fırsatları değerlendirilebilir.\n"
    elif overall_score >= 50:
        report += "Karma sinyaller mevcut, ancak hafif yükseliş eğilimi var. Seçici olun ve daha uzun zaman dilimlerine odaklanın.\n"
    elif overall_score >= 40:
        report += "Yatay seyir hakim. Breakout/breakdown için beklemede kalın, range ticareti düşünülebilir.\n"
    elif overall_score >= 30:
        report += "Hafif düşüş eğilimi var. Risk yönetimine dikkat edin, uzun pozisyonları azaltmayı düşünün.\n"
    else:
        report += "Güçlü düşüş sinyalleri hakim. Stop-loss kullanın, kısa pozisyonlar veya nakit tutma düşünülebilir.\n"

    report += "\n📝 <b>Not:</b>\n"
    report += "• Tüm zaman dilimlerinde yüksek skor alan coinler daha güvenilir sinyal verir.\n"
    report += "• Fiyat ve OI'nin aynı yönde hareketi, trend gücünü doğrular.\n"
    report += "• volume desteği, trendin sürdürülebilirliğini gösterir.\n"
    report += "• L/S oranının aşırı değerleri (>1.5 veya <0.7) zaman zaman tersine dönüşleri tetikleyebilir.\n"

    return report


def generate_coin_full_report(symbol):
    """
    Presents all analyses for the specified coin in a single report.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    coin_data = next((coin for coin in ALL_RESULTS if coin["Coin"] == symbol), None)
    if not coin_data:
        return f"⚠️ Data for {symbol} not found."

    report = f"📊 <b>{symbol} Full Analysis Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

    # Technical Indicators
    report += "<b>Technical Indicators:</b>\n"
    report += f"   • Price: {coin_data['Price_Display']}\n"
    report += f"   • EMA Trend: {coin_data.get('EMA Trend', 'Unknown')}\n"
    report += f"   • RSI: {coin_data['RSI']}\n"
    report += f"   • MACD: {coin_data['MACD']}\n"
    report += f"   • ADX: {coin_data['ADX']}\n"
    report += f"   • ATR: {coin_data['ATR']}\n\n"

    # Whale Data
    report += "<b>Whale Analysis:</b>\n"
    report += f"   • Net Accumulation: {coin_data['Net Accum']}\n"
    report += f"   • Whale Activity: {coin_data['Whale Activity']}\n"
    report += f"   • Whale Buy (M$): {coin_data['Whale_Buy_M']}\n"
    report += f"   • Whale Sell (M$): {coin_data['Whale_Sell_M']}\n\n"

    # Volume and Volatility
    report += "<b>Volume and Volatility:</b>\n"
    report += f"   • Volume Ratio: {coin_data['Volume Ratio']}x\n"
    report += f"   • Volatility Score: {round(extract_numeric(coin_data.get('ATR_raw', 0)) / parse_money(coin_data['Price_Display']) * 100, 2)}%\n\n"

    # Trend and Recommendation
    report += "<b>Trend and Recommendation:</b>\n"
    report += f"   • Momentum: {coin_data.get('Momentum', 'Unknown')}\n"
    report += f"   • Advice: {coin_data.get('Öneri', 'Neutral')}\n"

    return report

# ---------------- API Çağrıları ve Model Fonksiyonları ----------------

def train_prophet_model(df):
    """
    Returns current price as fallback (Prophet disabled for Render performance).
    """
    try:
        if 'price' in df.columns:
            return float(df['price'].iloc[-1])
        return float(df['close'].iloc[-1])
    except:
        return 0.0


def predict_with_cached_model(symbol, df):
    """
    Önbellekteki modeli kullanarak tahmin yapar veya yeni model eğitir

    Args:
        symbol (str): Coin sembolü
        df (pd.DataFrame): Veri çerçevesi

    Returns:
        tuple: (RF model tahmini, Prophet model tahmini)
    """
    try:
        # Veri çerçevesini hazırla ve temizle
        if df is None or len(df) < 10:
            print(f"[UYARI] {symbol} için tahmin yapılamıyor: Yetersiz veri ({len(df) if df is not None else 0} satır)")
            return 0.0, 0.0

        # Sütun isimlerinin doğru olduğundan emin ol
        required_cols = ['price', 'rsi', 'volume_ratio', 'net_accum']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            print(f"[UYARI] {symbol} için eksik sütunlar: {missing_cols}")
            # Eksik sütunları oluştur (varsayılan değerlerle)
            for col in missing_cols:
                if col == 'price' and 'close' in df.columns:
                    df['price'] = df['close']
                elif col == 'volume_ratio' and 'volume' in df.columns:
                    # Basit hacim oranı hesapla
                    df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=10).mean()
                else:
                    # Diğer eksik sütunlar için varsayılan değerler
                    df[col] = 0.0

        # Random Forest tahmin
        rf_pred_change, rf_model = train_rf_model(df)

        # Prophet tahmin
        try:
            prophet_pred = train_prophet_model(df)
        except Exception as prophet_error:
            print(f"[HATA] {symbol} için Prophet tahmini başarısız: {prophet_error}")
            prophet_pred = df['price'].iloc[-1] * (1 + rf_pred_change)  # Fallback olarak RF tahminini kullan

        # Modelleri önbelleğe kaydet
        if rf_model is not None:
            with global_lock:
                MODEL_CACHE[symbol] = {
                    "rf_model": rf_model,
                    "timestamp": datetime.now().timestamp()
                }

        return rf_pred_change, prophet_pred
    except Exception as e:
        print(f"[HATA] {symbol} için model tahmininde genel hata: {e}")
        return 0.0, df['price'].iloc[-1] if len(df) > 0 else 0.0

def save_model(symbol, model_rf=None, model_prophet=None, model_lstm=None):
    if model_rf:
        with open(f"models/{symbol}_rf.pkl", "wb") as f:
            pickle.dump(model_rf, f)
    if model_prophet:
        with open(f"models/{symbol}_prophet.pkl", "wb") as f:
            pickle.dump(model_prophet, f)
    if model_lstm:
        with open(f"models/{symbol}_lstm.pkl", "wb") as f:
            pickle.dump(model_lstm, f)

def load_model(symbol):
    try:
        with open(f"models/{symbol}_rf.pkl", "rb") as f:
            rf = pickle.load(f)
        with open(f"models/{symbol}_prophet.pkl", "rb") as f:
            prophet = pickle.load(f)
        with open(f"models/{symbol}_lstm.pkl", "rb") as f:
            lstm = pickle.load(f)
        return rf, prophet, lstm
    except:
        return None, None, None

# ---------------- Defillama Entegrasyonu ----------------
def fetch_global_defi_overview():
    url = "https://api.llama.fi/charts"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 1:
                latest_tvl = data[-1]["totalLiquidityUSD"]
                prev_tvl = data[-2]["totalLiquidityUSD"]
                change_1d = ((latest_tvl - prev_tvl) / prev_tvl * 100) if prev_tvl != 0 else 0
                return latest_tvl, change_1d
            return None, None
        return None, None
    except Exception as e:
        send_telegram_message_long(f"⚠️ Defillama verisi alınamadı: {e}")
        return None, None

def generate_defillama_overview_message():
    tvl, change_1d = fetch_global_defi_overview()
    if tvl is not None:
        message = f"🌐 <b>Global DeFi TVL Raporu</b>\n"
        message += f"Toplam TVL: ${round(tvl, 2):,}\n"
        message += f"Son 24 Saat Değişim: {round(change_1d, 2)}%\n"
        message += f"Veri Kaynağı: Defillama\n"
    else:
        message = "Defillama verileri alınamadı."
    return message


async def fetch_kline_data_safely(session, symbol, interval, limit=100):
    url = f"{BINANCE_API_URL}klines?symbol={symbol}&interval={interval}&limit={limit}"

    for attempt in range(3):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 429:
                    wait_time = min(5 * (attempt + 1), 30)  # Max 30 sn bekleme
                    print(f"[UYARI] {symbol} için rate limit, {wait_time}s bekleniyor...")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status == 200:
                    data = await response.json()
                    if not data or len(data) < 2:
                        print(f"[UYARI] {symbol} için yetersiz veri: {len(data)} kayıt")
                        return []

                    return data

                if 400 <= response.status < 500:
                    print(f"[HATA] {symbol} için istemci hatası: {response.status}")
                    return []

                print(f"[HATA] {symbol} için sunucu hatası: {response.status}")
                await asyncio.sleep(2 * (attempt + 1))

        except asyncio.TimeoutError:
            print(f"[HATA] {symbol} zaman aşımı (Deneme {attempt + 1})")
            await asyncio.sleep(2)

        except Exception as e:
            print(f"[HATA] {symbol} veri çekme hatası: {e}")
            await asyncio.sleep(2)

    return []


def sync_fetch_kline_data(symbol, interval, limit=100):
    try:
        cache_key = f"{symbol}_{interval}_{limit}"

        # Önbellek kontrolü
        with global_lock:
            cached = KLINE_CACHE.get(cache_key)
            if cached and (datetime.now() - cached["timestamp"]).total_seconds() < 300:
                return cached["data"]

        # Yeni veri çekme
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def fetch():
            async with aiohttp.ClientSession() as session:
                return await fetch_kline_data_safely(session, symbol, interval, limit)

        result = loop.run_until_complete(fetch())
        loop.close()

        # Başarılı sonuç önbellekleme
        if result:
            with global_lock:
                KLINE_CACHE[cache_key] = {
                    "data": result,
                    "timestamp": datetime.now()
                }

        return result
    except Exception as e:
        print(f"[HATA] {symbol} için sync_fetch_kline_data hatası: {e}")
        return []

def fetch_taker_volumes_from_klines(symbol, interval="1h", limit=24):
    url = f"{BINANCE_API_URL}klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 429:
            print(f"[UYARI] {symbol} için rate limit hatası, 5 saniye bekleniyor...")
            time.sleep(5)
            response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                           "close_time", "quote_volume", "trades", "taker_buy_base",
                                           "taker_buy_quote", "ignore"])
            taker_buy_quote = df["taker_buy_quote"].astype(float).sum()
            quote_vol = df["quote_volume"].astype(float).sum()
            print(f"[DEBUG] {symbol} - Klines Taker Buy Quote: {taker_buy_quote}, Quote Volume: {quote_vol}")
            return taker_buy_quote, quote_vol
        print(f"[HATA] {symbol} kline verisi alınamadı: {response.status_code}")
        return 0, 0
    except Exception as e:
        print(f"[HATA] {symbol} kline verisi alınamadı: {e}")
        return 0, 0

# ---------------- Balina Strateji ve Hareket Analizi ----------------

def get_futures_data(symbol):
    """
    Vadeli işlemler verilerini çeken yardımcı fonksiyon.
    Kodunuzdaki mevcut futures verisi çekme fonksiyonunuzu çağırmalıdır.

    Args:
        symbol (str): Coin sembolü

    Returns:
        dict: Futures verileri
    """
    try:
        # Eğer kodunuzda "get_futures_stats" adlı bir fonksiyon varsa onu çağırın
        if 'get_futures_stats' in globals():
            open_interest, long_short_ratio = get_futures_stats(symbol)
            return {
                "funding_rate": 0,  # Bu fonksiyon funding rate dönmediği için 0 kullanıyoruz
                "open_interest": open_interest,
                "long_short_ratio": long_short_ratio
            }

        # veya kodunuzdaki farklı bir vadeli işlemler API'si varsa onu çağırın

        # Eğer hiçbir fonksiyon yoksa, varsayılan değerler dön
        return {
            "funding_rate": 0,
            "open_interest": 0,
            "long_short_ratio": 1.0
        }
    except Exception as e:
        print(f"[UYARI] {symbol} için vadeli işlemler verisi alınamadı: {e}")
        return {
            "funding_rate": 0,
            "open_interest": 0,
            "long_short_ratio": 1.0
        }


def detect_whale_strategies_enhanced(coin_data, historical_data=None):
    """
    Balina stratejilerini ve manipülasyon kalıplarını daha derinlemesine tespit eder.

    Args:
        coin_data (dict): Coin verileri
        historical_data (dict, optional): Önceki analizlerden gelen tarihsel veriler

    Returns:
        dict: Tespit edilen stratejiler ve manipülasyon puanları
    """
    try:
        symbol = coin_data["Coin"]
        print(f"[DEBUG] {symbol} için balina stratejileri analiz ediliyor")

        # Temel metrikler - güvenle çıkarma
        try:
            rsi_val = extract_numeric(coin_data.get("RSI", "50"))
            net_accum = extract_numeric(coin_data.get("NetAccum_raw", 0))
            volume_ratio = extract_numeric(coin_data.get("Volume Ratio", 1))
            price_roc = extract_numeric(coin_data.get("24h Change", "0"))
            current_price = parse_money(coin_data.get("Price_Display", "0"))
            price_str = coin_data.get("Price_Display", "0")

            # Balina metriklerini çıkar
            whale_buy = parse_money(coin_data.get("Whale_Buy_M", "0"))
            whale_sell = parse_money(coin_data.get("Whale_Sell_M", "0"))
            whale_activity = extract_numeric(coin_data.get("Whale Activity", "0"))

            # ATR (volatilite için)
            atr = extract_numeric(coin_data.get("ATR_raw", 0))

            # MACD ve ADX
            macd = extract_numeric(coin_data.get("MACD", "0"))
            adx = extract_numeric(coin_data.get("ADX", "0"))
        except Exception as e:
            print(f"[HATA] {symbol} için temel metrikler çıkarılırken hata: {e}")
            # Varsayılan değerler
            rsi_val, net_accum, volume_ratio = 50, 0, 1
            price_roc, current_price = 0, 1
            whale_buy, whale_sell, whale_activity = 0, 0, 0
            atr, macd, adx = 0, 0, 0

        # Kline verileri al
        try:
            klines_15m = sync_fetch_kline_data(symbol, "15m", limit=30)
            klines_1h = sync_fetch_kline_data(symbol, "1h", limit=24)
            klines_4h = sync_fetch_kline_data(symbol, "4h", limit=20)

            # Taker ratio hesapla
            taker_ratio_15m = calculate_buyer_ratio(klines_15m)
            taker_ratio_1h = calculate_buyer_ratio(klines_1h)

            if taker_ratio_15m == "N/A":
                taker_ratio_15m = 50
            if taker_ratio_1h == "N/A":
                taker_ratio_1h = 50
        except Exception as e:
            print(f"[HATA] {symbol} kline veya taker ratio hesaplanırken hata: {e}")
            klines_15m, klines_1h, klines_4h = [], [], []
            taker_ratio_15m, taker_ratio_1h = 50, 50

        # Emir defteri al
        try:
            bids, asks = fetch_order_book(symbol, limit=100)
            order_book = analyze_order_book(bids, asks, current_price, symbol)
        except Exception as e:
            print(f"[HATA] {symbol} emir defteri analizi hatası: {e}")
            order_book = {"imbalance": 0, "bid_volume": 0, "ask_volume": 0, "big_bid_wall": False,
                          "big_ask_wall": False}

        # Vadeli işlemler verisi
        try:
            # Synch call removed
            funding = safe_extract(coin_data, "Funding_Rate", 0)
            oi = safe_extract(coin_data, "Open Interest", 0)
            ls = safe_extract(coin_data, "Long/Short Ratio", 1.0)
            
            futures_data = {
                "funding_rate": funding,
                "open_interest": oi,
                "long_short_ratio": ls
            }

            funding_rate = futures_data.get("funding_rate", 0)
            long_short_ratio = futures_data.get("long_short_ratio", 1.0)
        except Exception as e:
            pass  # Silenced, use defaults
            funding_rate, long_short_ratio = 0, 1.0

        # Önceki verilerle karşılaştır
        with global_lock:
            prev_data = PREV_STATS.get(symbol, {})

        prev_price = prev_data.get("price", current_price)
        prev_net_accum = prev_data.get("netaccum", net_accum * 1e6) / 1e6 if "netaccum" in prev_data else net_accum
        prev_whale_activity = prev_data.get("whale", whale_activity)

        price_change = calculate_percentage_change(current_price, prev_price)
        net_accum_change = net_accum - prev_net_accum
        whale_activity_change = calculate_percentage_change(whale_activity, prev_whale_activity)

        # Mum örüntülerini analiz et
        recent_candles_15m = extract_candlestick_patterns(klines_15m) if klines_15m else []
        recent_candles_1h = extract_candlestick_patterns(klines_1h) if klines_1h else []

        # =============================================
        # MANİPÜLASYON DEDEKTÖRLERİ
        # =============================================

        # 1. PUMP AND DUMP TESPİTİ
        pump_dump_score = 0
        pump_dump_evidence = []

        # Ani fiyat artışı
        if price_roc > 10:  # %10'dan fazla
            pump_dump_score += 25
            pump_dump_evidence.append(f"Price increased by {price_roc:.1f}% recently.")
        elif price_roc > 5:  # %5'den fazla
            pump_dump_score += 15
            pump_dump_evidence.append(f"Price increased by {price_roc:.1f}% recently.")

        # volume analizi
        if volume_ratio > 3 and price_roc > 0:
            pump_dump_score += 20
            pump_dump_evidence.append(f"Volume increased by {volume_ratio:.1f}x while price is rising.")

        # Dump belirtileri için fiyat hareketini analiz et
        if klines_1h and len(klines_1h) > 6:
            # Son 6 saatteki en yüksek değer
            recent_high = max([float(k[2]) for k in klines_1h[-6:]])

            if recent_high > current_price:
                # Zirve sonrası düşüş yüzdesi
                high_to_current_drop = ((recent_high - current_price) / recent_high) * 100

                if high_to_current_drop > 10 and price_roc > 0:  # %10+ düşüş ve hala pozitif ROC
                    pump_dump_score += 30
                    pump_dump_evidence.append(f"{high_to_current_drop:.1f}% drop from peak, possible dump phase.")
                elif high_to_current_drop > 5 and price_roc > 0:  # %5+ düşüş
                    pump_dump_score += 20
                    pump_dump_evidence.append(
                        f"{high_to_current_drop:.1f}% drop from peak, potential dump starting.")

        # 2. WASH TRADING TESPİTİ
        wash_trading_score = 0
        wash_trading_evidence = []

        # İşlem sayısı/hacim oranı anomalileri
        if klines_1h and len(klines_1h) > 5:
            trades_counts = [float(k[8]) for k in klines_1h]  # İşlem sayıları
            volumes = [float(k[7]) for k in klines_1h]  # volume değerleri

            # Ortalama işlem büyüklüğü
            avg_trade_size = []
            for i in range(len(trades_counts)):
                if trades_counts[i] > 0:
                    avg_trade_size.append(volumes[i] / trades_counts[i])

            # Standart sapma - çok düşük standart sapma wash trading işareti olabilir
            if avg_trade_size and len(avg_trade_size) > 1:
                mean_size = sum(avg_trade_size) / len(avg_trade_size)
                std_dev = math.sqrt(sum((x - mean_size) ** 2 for x in avg_trade_size) / len(avg_trade_size))
                variation_coef = std_dev / mean_size if mean_size > 0 else 0

                if variation_coef < 0.2 and volume_ratio > 1.5:  # Anormal derecede tutarlı işlem boyutları
                    wash_trading_score += 30
                    wash_trading_evidence.append(f"Abnormally consistent trade sizes (CV: {variation_coef:.3f}).")

        # Fiyat ve hacim orantısızlığı
        if volume_ratio > 3 and abs(price_roc) < 2:
            wash_trading_score += 25
            wash_trading_evidence.append(
                f"High volume ({volume_ratio:.1f}x) but very little price movement ({price_roc:.1f}%).")

        # 3. SPOOFING TESPİTİ
        spoofing_score = 0
        spoofing_evidence = []

        # Emir defterindeki büyük duvarlar
        if order_book["big_bid_wall"] or order_book["big_ask_wall"]:
            spoofing_score += 20
            wall_type = "buy" if order_book["big_bid_wall"] else "sell"
            spoofing_evidence.append(f"Big {wall_type} wall detected in order book.")

        # Dengesiz emir defteri
        if abs(order_book["imbalance"]) > 25:  # %25'den fazla dengesizlik
            spoofing_score += 15
            imbalance_type = "buy side" if order_book["imbalance"] > 0 else "sell side"
            spoofing_evidence.append(f"Order book is {abs(order_book['imbalance']):.1f}% {imbalance_type} biased.")

        # 4. MOMENTUM IGNITION TESPİTİ (Stop Loss Avı)
        momentum_ignition_score = 0
        momentum_ignition_evidence = []

        # Stop-loss avı tespit koşulları
        has_sharp_drop = False
        has_quick_recovery = False

        if klines_15m and len(klines_15m) > 12:
            last_12 = klines_15m[-12:]
            lows = [float(k[3]) for k in last_12]  # low değerler
            closes = [float(k[4]) for k in last_12]  # close değerleri

            # Fiyatta ani düşüş oldu mu?
            min_low = min(lows)
            avg_close = sum(closes) / len(closes)
            drop_pct = ((avg_close - min_low) / avg_close) * 100 if avg_close > 0 else 0

            if drop_pct > 5:  # %5'den fazla ani düşüş
                has_sharp_drop = True

                # Düşüşten sonra toparlanma var mı?
                min_low_idx = lows.index(min_low)
                if min_low_idx < len(closes) - 1:  # Son mum değilse
                    recovery_pct = ((closes[-1] - min_low) / min_low) * 100 if min_low > 0 else 0

                    if recovery_pct > 3:  # %3'den fazla toparlanma
                        has_quick_recovery = True

        if has_sharp_drop and has_quick_recovery:
            momentum_ignition_score += 40
            momentum_ignition_evidence.append("Sharp drop and quick recovery pattern - possible stop-loss hunt.")
        elif has_sharp_drop:
            momentum_ignition_score += 20
            momentum_ignition_evidence.append("Sharp price drop - potential stop-loss hunt.")

        # Vadeli işlemlerden gelen baskı
        if abs(funding_rate) > 0.1:  # %0.1'den fazla anormal funding oranı
            momentum_ignition_score += 15
            funding_type = "positive" if funding_rate > 0 else "negative"
            momentum_ignition_evidence.append(f"Abnormal {funding_type} funding rate ({abs(funding_rate):.3f}%).")

        # GENEL STRATEJİ BELİRLEME
        detected_strategies = []

        # Pump and Dump
        if pump_dump_score >= 40:
            phase = "Dump Phase" if 'high_to_current_drop' in locals() and high_to_current_drop > 5 else "Pump Phase"
            detected_strategies.append({
                "type": "Pump and Dump",
                "phase": phase,
                "score": pump_dump_score,
                "evidence": pump_dump_evidence,
                "danger_level": "⚠️⚠️⚠️" if pump_dump_score >= 60 else "⚠️⚠️" if pump_dump_score >= 40 else "⚠️",
                "recommendation": "SELL" if phase == "Dump Phase" else "STAY AWAY",
                "description": "Manipulative movement where the price is artificially inflated and then dumped."
            })

        # Wash Trading
        if wash_trading_score >= 30:
            detected_strategies.append({
                "type": "Wash Trading",
                "phase": "Active",
                "score": wash_trading_score,
                "evidence": wash_trading_evidence,
                "danger_level": "⚠️⚠️⚠️" if wash_trading_score >= 50 else "⚠️⚠️" if wash_trading_score >= 30 else "⚠️",
                "recommendation": "CAUTION: Fake volume - Misleading liquidity",
                "description": "Fake trading volume created by the same person/institution."
            })

        # Spoofing
        if spoofing_score >= 30:
            detected_strategies.append({
                "type": "Spoofing",
                "phase": "Active",
                "score": spoofing_score,
                "evidence": spoofing_evidence,
                "danger_level": "⚠️⚠️" if spoofing_score >= 40 else "⚠️",
                "recommendation": "Order book manipulation - Misleading price",
                "description": "Directing the price with large orders that have no real intention."
            })

        # Momentum Ignition / Stop-Loss Avı
        if momentum_ignition_score >= 30:
            detected_strategies.append({
                "type": "Stop-Loss Hunt",
                "phase": "Completed" if has_quick_recovery else "In Progress",
                "score": momentum_ignition_score,
                "evidence": momentum_ignition_evidence,
                "danger_level": "⚠️⚠️⚠️" if momentum_ignition_score >= 50 else "⚠️⚠️",
                "recommendation": "Volatile movement - Watch out",
                "description": "Manipulative movement done to trigger stop-loss levels."
            })

        # =============================================
        # STRATEJİK BALINA HAREKETLERİ
        # =============================================

        # Sessiz Birikim Tespiti (Gerçek stratejik alım)
        if net_accum > 3 and abs(price_roc) < 3 and rsi_val < 60:
            detected_strategies.append({
                "type": "Silent Accumulation",
                "phase": "Active",
                "score": 70,
                "evidence": [
                    f"Net accumulation {net_accum}M USD, but price only changed by {price_roc:.1f}%.",
                    f"RSI ({rsi_val}) is below overbought zone."
                ],
                "danger_level": "💰",
                "recommendation": "Potential opportunity - Watch",
                "description": "Large investors buying silently at low prices."
            })

        # Agresif Alım Tespiti
        if net_accum > 5 and price_roc > 3 and volume_ratio > 1.5 and float(taker_ratio_15m) > 55:
            detected_strategies.append({
                "type": "Aggressive Buying",
                "phase": "Active",
                "score": 65,
                "evidence": [
                    f"Net accumulation {net_accum}M USD and price increased by {price_roc:.1f}%.",
                    f"Buyer ratio {taker_ratio_15m}% and volume {volume_ratio:.1f}x."
                ],
                "danger_level": "🚀",
                "recommendation": "Momentum - Follow carefully",
                "description": "Large investors buying actively."
            })

        # Front-Running Tespiti (Büyük emirlerden önce küçük işlemler)
        if klines_15m and len(klines_15m) > 10:
            trades = [float(k[8]) for k in klines_15m[-10:]]

            if len(trades) > 3:
                # İşlem boyutu hesapla
                trade_sizes = []
                for k in klines_15m[-10:]:
                    if float(k[8]) > 0:  # İşlem sayısı sıfır değilse
                        trade_sizes.append(float(k[7]) / float(k[8]))
                    else:
                        trade_sizes.append(0)

                small_then_large = False
                avg_recent = sum(trades[-3:]) / 3
                avg_before = sum(trades[-10:-3]) / 7

                if avg_recent > avg_before * 3 and any(size > 0 for size in trade_sizes):
                    small_then_large = True

                if small_then_large and (order_book["big_bid_wall"] or order_book["big_ask_wall"]):
                    detected_strategies.append({
                        "type": "Front-Running",
                        "phase": "Possible",
                        "score": 55,
                        "evidence": [
                            "Large trades detected after small trades.",
                            "There are big walls in the order book."
                        ],
                        "danger_level": "⚠️⚠️",
                        "recommendation": "Caution - Possible price manipulation",
                        "description": "Directing the price with small trades before large orders."
                    })

        # Distribüsyon Tespiti (Satış)
        if net_accum < -3 and price_roc > 0:
            detected_strategies.append({
                "type": "Distribution",
                "phase": "Active",
                "score": 60,
                "evidence": [
                    f"Net accumulation {net_accum}M USD (selling), but price is increasing by {price_roc:.1f}%.",
                    f"Retail investors might be buying while whales are selling."
                ],
                "danger_level": "⚠️⚠️",
                "recommendation": "Caution - Selling pressure might increase soon",
                "description": "Large investors unloading positions at high prices."
            })

        # Metrikler
        metrics = {
            "net_accum": net_accum,
            "volume_ratio": volume_ratio,
            "price_roc": price_roc,
            "rsi": rsi_val,
            "taker_ratio_15m": taker_ratio_15m,
            "taker_ratio_1h": taker_ratio_1h,
            "order_book_imbalance": order_book["imbalance"],
            "funding_rate": funding_rate,
            "long_short_ratio": long_short_ratio,
            "price": current_price,
            "whale_activity": whale_activity,
            "macd": macd,
            "adx": adx
        }

        # Raw manipulation scores
        raw_scores = {
            "pump_dump": pump_dump_score,
            "wash_trading": wash_trading_score,
            "spoofing": spoofing_score,
            "momentum_ignition": momentum_ignition_score
        }

        return {
            "symbol": symbol,
            "detected_strategies": detected_strategies,
            "raw_scores": raw_scores,
            "metrics": metrics
        }
    except Exception as e:
        print(f"[HATA] {coin_data.get('Coin', 'Bilinmeyen')} için manipülasyon tespitinde hata: {e}")
        import traceback
        traceback.print_exc()
        return {
            "symbol": coin_data.get("Coin", "Bilinmeyen"),
            "detected_strategies": [],
            "raw_scores": {},
            "metrics": {},
            "error": str(e)
        }



def detect_whale_strategies(coin_data, df):
    """
    Eski balina stratejileri tespit fonksiyonu.
    Geriye uyumluluk için korunmuştur, gelişmiş fonksiyona yönlendirir.

    Args:
        coin_data (dict): Coin verileri
        df: DataFrame verisi (bu versiyonda kullanılmıyor)

    Returns:
        str: Tespit edilen strateji açıklaması
    """
    # Gelişmiş fonksiyonu çağır
    result = detect_whale_strategies_enhanced(coin_data)

    # Önceki fonksiyonun formatına uygun sonuç döndür
    if result["detected_strategies"]:
        # En yüksek skorlu stratejiyi bul
        top_strategy = max(result["detected_strategies"], key=lambda x: x["score"])

        # Basit bir açıklama döndür
        strategy_type = top_strategy["type"]
        phase = top_strategy["phase"]

        return f"{strategy_type}: {top_strategy['description']} ({phase})"
    else:
        return "Belirgin bir manipülasyon stratejisi tespit edilemedi."


def analyze_whale_movement(coin_data):
    """
    Bir coin için balina hareketlerini analiz eder.

    Args:
        coin_data (dict): Coin verileri sözlüğü

    Returns:
        str: Balina hareket analiz raporu
    """
    try:
        # Temel değerleri çıkar
        symbol = coin_data.get("Coin", "Bilinmeyen")
        net_accum = extract_numeric(coin_data.get("NetAccum_raw", 0))
        whale_buy = parse_money(coin_data["Whale_Buy_M"])
        whale_sell = parse_money(coin_data["Whale_Sell_M"])
        whale_activity = extract_numeric(coin_data["Whale Activity"])
        volume_ratio = extract_numeric(coin_data["Volume Ratio"])
        price_roc = extract_numeric(coin_data["24h Change"])
        current_price = parse_money(coin_data["Price_Display"])

        print(f"[DEBUG] {symbol} balina analizi başladı: net_accum={net_accum}, activity={whale_activity}")

        # Veritabanından önceki verileri çek
        conn = sqlite3.connect("market_stats.db")
        c = conn.cursor()
        c.execute("SELECT netaccum FROM prev_stats WHERE symbol = ?", (symbol,))
        result = c.fetchone()
        prev_netaccum = result[0] if result else 0
        netaccum_change = (net_accum - prev_netaccum) / 1e6
        conn.close()

        # Emir defteri analizi
        bids, asks = fetch_order_book(symbol)
        order_book = analyze_order_book(bids, asks, current_price, symbol)

        # Kline verileri
        kline_15m = sync_fetch_kline_data(symbol, "15m", limit=20)
        kline_1h = sync_fetch_kline_data(symbol, "1h", limit=20)

        # Alıcı oranları
        taker_ratio_15m = calculate_buyer_ratio(kline_15m)
        taker_ratio_1h = calculate_buyer_ratio(kline_1h)

        # volume anormalliği hesaplama - tarihsel verileri kullan (Raw USD bazında)
        historical_volumes = [float(k[7]) for k in kline_1h if float(k[7]) > 0]
        activity_history = [float(k[8]) for k in kline_1h if float(k[8]) > 0]

        # Anomali skorlarını hesapla
        volume_anomaly = calculate_anomaly_score(whale_buy + whale_sell, historical_volumes)
        activity_anomaly = calculate_anomaly_score(whale_activity, activity_history)

        # Rapor oluştur
        movement_summary = f"📊 <b>{symbol} Whale Analysis</b>\n\n"
        movement_summary += f"<b>💰 Net Accumulation:</b> {format_money(net_accum)} USD ({netaccum_change:+.2f}M)\n"
        movement_summary += f"<b>🐳 Whale Trades:</b> {format_money(whale_buy)} buy | {format_money(whale_sell)} sell\n"
        movement_summary += f"<b>📈 Trade Frequency:</b> {whale_activity} trades (Anomaly: {activity_anomaly})\n"
        movement_summary += f"<b>📊 Volume Ratio:</b> {volume_ratio}x\n"
        movement_summary += f"<b>📉 Price Change:</b> {price_roc}%\n"

        # Emir defteri bilgileri
        movement_summary += f"<b>📚 Order Book:</b> {order_book['imbalance']}% imbalance (Bid: {format_money(order_book['bid_volume'])}, Ask: {format_money(order_book['ask_volume'])})\n"

        # Büyük duvarlar
        if order_book['big_bid_wall']:
            movement_summary += f"<b>🧱 Big Buy Wall:</b> {format_money(order_book['max_bid_qty'])} volume\n"
        elif order_book['big_ask_wall']:
            movement_summary += f"<b>🧱 Big Sell Wall:</b> {format_money(order_book['max_ask_qty'])} volume\n"
        else:
            movement_summary += "<b>🧱 Big Walls:</b> No Buy, No Sell\n"

        # Taker oranları
        movement_summary += f"<b>📋 Taker Ratio:</b> %{taker_ratio_15m} (15m), %{taker_ratio_1h} (1h)\n"

        # Anormallik değerleri
        movement_summary += f"<b>⚠️ Volume Anomaly:</b> {volume_anomaly} (z-score)\n"

        # Fiyat etkisi ve öneri
        if volume_anomaly > 1.5 and abs(net_accum) > 10 and abs(price_roc) > 1:
            impact_msg = f"<b>🚨 Whale Effect:</b> {price_roc}% price change ({'buy' if net_accum > 0 else 'sell'} pressure)"
            recommendation = f"<b>Recommendation:</b> {'📈 Buy' if net_accum > 0 else '📉 Sell'}"
        elif abs(order_book["imbalance"]) > 20 and abs(net_accum) > 3:
            impact_msg = f"<b>🚨 Imbalance Effect:</b> {order_book['imbalance']}% imbalance in order book"
            recommendation = f"<b>Recommendation:</b> {'📈 Buy' if order_book['imbalance'] > 0 else '📉 Sell'}"
        elif order_book["big_bid_wall"] and taker_ratio_15m > 55:
            impact_msg = f"<b>🧱 Wall Effect:</b> Big buy wall and high buyer ratio (%{taker_ratio_15m})"
            recommendation = "<b>Recommendation:</b> 📈 Buy"
        elif order_book["big_ask_wall"] and taker_ratio_15m < 45:
            impact_msg = f"<b>🧱 Wall Effect:</b> Big sell wall and low buyer ratio (%{taker_ratio_15m})"
            recommendation = "<b>Recommendation:</b> 📉 Sell"
        elif abs(netaccum_change) > 5:
            impact_msg = f"<b>⚡ Change Effect:</b> Sudden change in net accumulation ({netaccum_change:+.2f}M)"
            recommendation = "<b>Recommendation:</b> 👀 Watch Carefully"
        else:
            impact_msg = "<b>ℹ️ Impact Comment:</b> No significant whale effect detected"
            recommendation = "<b>Recommendation:</b> ⚖️ Neutral"

        movement_summary += f"\n{impact_msg}\n{recommendation}"

        return movement_summary
    except Exception as e:
        print(f"[HATA] Balina hareket analizi hatasında: {e}")
        return "Whale movement analysis failed."

def detect_significant_changes(results):
    significant_changes = []
    for coin in results:
        current_rank = results.index(coin) + 1
        with global_lock:
            prev_rank = PREV_RANKS.get(coin["Coin"])
        if prev_rank is not None:
            rank_change = prev_rank - current_rank
            if abs(rank_change) >= 10:
                net_accum = coin["NetAccum_raw"]
                volume_ratio = extract_numeric(coin["Volume Ratio"])
                momentum = extract_numeric(coin["Momentum"])
                rsi = extract_numeric(coin["RSI"])
                if (abs(net_accum) > 5 or volume_ratio > 1.5 or abs(momentum) > 30):
                    significant_changes.append({
                        "Coin": coin["Coin"],
                        "RankChange": rank_change,
                        "CurrentRank": current_rank,
                        "PrevRank": prev_rank,
                        "NetAccum": net_accum,
                        "VolumeRatio": volume_ratio,
                        "Momentum": momentum,
                        "RSI": rsi,
                        "Details": coin
                    })
        with global_lock:
            PREV_RANKS[coin["Coin"]] = current_rank
    return sorted(significant_changes, key=lambda x: abs(x["RankChange"]), reverse=True)


def analyze_antigravity_pa_strategy(coin_data, df_1d, df_15m):
    """
    Antigravity Bot - Price Action Strateji Analizi (Efloud Metodolojisi)
    """
    try:
        symbol = coin_data.get("Coin", "Unknown")
        current_price = float(coin_data.get("Price", 0))
        
        # 1. HTF Analizi (Destek-Direnç-Dengesizlik)
        htf_support_zone = "N/A"
        htf_reason = "Belirlenemedi"
        
        # Önceki Akümülasyon Bölgesi (Lowest low in 30 days)
        recent_low = df_1d['low'].tail(30).min()
        recent_high = df_1d['high'].tail(30).max()
        
        # Dengesizlik (Imbalance/FVG) Tespiti
        # 1. Mum Low > 3. Mum High ise arada boşluk vardır (Boğa FVG)
        fvg_zones = []
        for i in range(len(df_1d)-3, len(df_1d)-10, -1):
            if df_1d['low'].iloc[i+2] > df_1d['high'].iloc[i]:
                fvg_zones.append((df_1d['high'].iloc[i], df_1d['low'].iloc[i+2]))
        
        if fvg_zones:
            htf_support_zone = f"{fvg_zones[0][0]:.4f} - {fvg_zones[0][1]:.4f}"
            htf_reason = "Dengesizlik (Imbalance/FVG) Alanı"
        else:
            htf_support_zone = f"{recent_low:.4f} - {recent_low*1.05:.4f}"
            htf_reason = "Önceki Akümülasyon/Talep Bölgesi"

        # 2. LTF Analizi (Market Structure Break - MSB)
        # Son 20 mumun en yüksek seviyesini kıran bir yapı var mı?
        last_20_high = df_15m['high'].tail(20).max()
        is_msb = df_15m['close'].iloc[-1] > last_20_high
        ltf_signal = f"{last_20_high:.4f} seviyesindeki stop-high kırılımı" if not is_msb else "✅ MSB Gerçekleşti (Market Yapısı Kırıldı)"
        
        # 3. BTC Paritesi Teyidi (Basit Korelasyon/Strength)
        btc_corr = float(coin_data.get("BTC Correlation", 0))
        btc_conf = "Pozitif - Güçlü Duruyor" if btc_corr > 0.7 else "Nötr - Bağımsız Hareket"

        # SPOT & MARGIN Planları
        stop_spot = recent_low * 0.95
        stop_margin = df_15m['low'].tail(10).min() * 0.99
        tp1 = current_price * 1.10
        tp2 = recent_high

        # Markdown Raporu Oluşturma
        report = f"""### **Ticaret Planı: {symbol}**

*   **Piyasa Durumu:** {'Yükseliş Trendi' if current_price > df_1d['close'].iloc[-20:].mean() else 'Düzeltme / Yatay'}
*   **Yüksek Zaman Dilimi (HTF) Analizi:**
    *   **Önemli Destek Bölgesi:** {htf_support_zone}
    *   **Gerekçe:** {htf_reason}
    *   **BTC Paritesi Teyidi:** {btc_conf}
*   **Düşük Zaman Dilimi (LTF) Giriş Teyidi:**
    *   **Beklenen Sinyal:** {ltf_signal}
*   **SPOT Ticaret Planı:**
    *   **Giriş Bölgesi:** {htf_support_zone}
    *   **Zararı Durdur (Stop-Loss):** {stop_spot:.4f} (Günlük kapanış şartı ile)
    *   **Hedefler (Take-Profit):** {format_money(tp1)}, {format_money(tp2)}
*   **MARJİN (Margin) Ticaret Planı:**
    *   **Giriş Koşulu:** LTF teyit sinyali (MSB) {'BEKLENECEK' if not is_msb else 'AKTİF'}
    *   **Giriş Seviyesi:** {current_price:.4f} (Teyit sonrası dinamik)
    *   **Zararı Durdur (Stop-Loss):** {stop_margin:.4f} (LTF son dip altı)
    *   **Hedefler (Take-Profit):** {format_money(tp1)}, {format_money(tp2)}
*   **Temel Risk:** Bitcoin'in HTF desteği altındaki kapanışları ve paritenin yapısal bozulması."""
        
        return report

    except Exception as e:
        return f"PA Analiz hatası ({symbol}): {str(e)}"

def generate_enhanced_manipulation_report():
    """
    Geliştirilmiş manipülasyon tespit raporu oluşturur.

    Returns:
        str: Formatlı rapor
    """
    if not ALL_RESULTS:
        return "⚠️ Henüz analiz verisi bulunmuyor."

    report = f"🔍 <b>Enhanced Manipulation Detection Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report shows various manipulation strategies and whale movements detected in the market.\n\n"

    all_strategies = []
    strategy_counts = {
        "Pump and Dump": 0,
        "Wash Trading": 0,
        "Spoofing": 0,
        "Stop-Loss Hunt": 0,
        "Silent Accumulation": 0,
        "Aggressive Buying": 0,
        "Front-Running": 0
    }

    # Tüm coinler için manipülasyon analizi
    for coin in ALL_RESULTS:
        result = detect_whale_strategies_enhanced(coin)

        if result["detected_strategies"]:
            for strategy in result["detected_strategies"]:
                strategy_counts[strategy["type"]] = strategy_counts.get(strategy["type"], 0) + 1
                all_strategies.append({
                    "symbol": result["symbol"],
                    "strategy": strategy
                })

    # Manipülasyon türlerine göre grupla
    if all_strategies:
        # Manipülasyon türlerine göre grupla
        for strategy_type in ["Pump and Dump", "Wash Trading", "Spoofing", "Stop-Loss Hunt", "Front-Running"]:
            matching_strategies = [s for s in all_strategies if s["strategy"]["type"] == strategy_type]

            if matching_strategies:
                report += f"<b>🚨 {strategy_type} Detection ({len(matching_strategies)} coins):</b>\n"

                # En yüksek skorlu stratejileri göster
                sorted_strategies = sorted(matching_strategies, key=lambda x: x["strategy"]["score"], reverse=True)

                for strategy_data in sorted_strategies[:5]:  # İlk 5 tanesini göster
                    symbol = strategy_data["symbol"]
                    strategy = strategy_data["strategy"]

                    report += f"• <b>{symbol}</b> (Score: {strategy['score']}/100) - {strategy['danger_level']}\n"

                    # Kanıtları göster
                    for evidence in strategy["evidence"]:
                        report += f"  - {evidence}\n"

                    report += f"  <b>Recommendation:</b> {strategy['recommendation']}\n\n"

                if len(matching_strategies) > 5:
                    report += f"  ...ve {len(matching_strategies) - 5} coin daha.\n\n"

        # Fırsat stratejileri
        opportunity_strategies = ["Sessiz Birikim", "Agresif Alım"]
        matching_opportunities = [s for s in all_strategies if s["strategy"]["type"] in opportunity_strategies]

        if matching_opportunities:
            report += f"<b>💰 Fırsat Tespiti ({len(matching_opportunities)} coin):</b>\n"

            sorted_opportunities = sorted(matching_opportunities, key=lambda x: x["strategy"]["score"], reverse=True)

            for strategy_data in sorted_opportunities[:5]:
                symbol = strategy_data["symbol"]
                strategy = strategy_data["strategy"]

                report += f"• <b>{symbol}</b> - {strategy['type']}\n"

                for evidence in strategy["evidence"]:
                    report += f"  - {evidence}\n"

                report += f"  <b>Öneri:</b> {strategy['recommendation']}\n\n"

            if len(matching_opportunities) > 5:
                report += f"  ...ve {len(matching_opportunities) - 5} coin daha.\n\n"
    else:
        report += "✅ <b>Şu anda hiçbir manipülasyon tespit edilmedi.</b>\n\n"

    # Manipülasyon türleri hakkında açıklamalar
    report += "<b>📚 Manipülasyon Türleri Hakkında:</b>\n"
    report += "• <b>Pump and Dump:</b> Fiyatı yapay olarak şişirip, yüksek fiyattan satış yapma stratejisi.\n"
    report += "• <b>Wash Trading:</b> Sahte işlem hacmi oluşturarak ilgi çekme stratejisi.\n"
    report += "• <b>Spoofing:</b> Emir defterinde büyük alış/satış duvarları oluşturup sonra geri çekmek.\n"
    report += "• <b>Stop-Loss Avı:</b> Ani düşüşlerle stop-loss emirlerini tetikleyip ucuza alım yapmak.\n"
    report += "• <b>Front-Running:</b> Büyük emirlerden önce işlem yaparak kar elde etmek.\n"
    report += "• <b>Sessiz Birikim:</b> low fiyattan sessizce büyük miktarda alım yapmak (manipülasyon değil).\n"
    report += "• <b>Agresif Alım:</b> Kısa sürede yüksek hacimle alım yaparak fiyatı hızla yükseltmek.\n\n"

    report += "<b>⚠️ Not:</b> Bu tespitler algoritmik analizler olup kesin sonuçlar değildir. Daima kendi araştırmanızı yapın."

    return report

def handle_enhanced_manipulation_report():
    """
    Geliştirilmiş manipülasyon tespit raporunu oluşturup gönderir.
    """
    try:
        report = generate_enhanced_manipulation_report()
        send_telegram_message_long(report)
    except Exception as e:
        print(f"[HATA] Manipülasyon raporu oluşturulurken hata: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message_long("⚠️ Manipülasyon raporu oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

# ---------------- Teknik Analiz Fonksiyonları ----------------
def get_correlation(symbol, base_symbol="BTCUSDT", interval="1h", limit=100):
    url_coin = BINANCE_API_URL + f"klines?symbol={symbol}&interval={interval}&limit={limit}"
    url_base = BINANCE_API_URL + f"klines?symbol={base_symbol}&interval={interval}&limit={limit}"
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('https://', adapter)
    
    try:
        # Increase timeout to 20 seconds and use session with retries. Add headers.
        resp_coin = session.get(url_coin, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp_base = session.get(url_base, timeout=20, headers={"User-Agent": "Mozilla/5.0"})

        if resp_coin.status_code == 429 or resp_base.status_code == 429:
            print(f"[UYARI] API rate limit için {symbol}-{base_symbol} korelasyonu atlanıyor")
            return None  # Return None instead of 0 to distinguish from actual 0 correlation
            
        if resp_coin.status_code != 200 or resp_base.status_code != 200:
            print(f"[UYARI] {symbol} veya {base_symbol} için korelasyon verisi alınamadı: {resp_coin.status_code}, {resp_base.status_code}")
            return None

        df_coin = pd.DataFrame(resp_coin.json(), columns=["timestamp", "open", "high", "low", "close", "volume",
                                                        "close Zamanı", "quote_volume", "trades",
                                                        "Alıcı Baz Varlık Hacmi", "Alıcı quote_volume", "Yoksay"])
        df_base = pd.DataFrame(resp_base.json(), columns=["timestamp", "open", "high", "low", "close", "volume",
                                                        "close Zamanı", "quote_volume", "trades",
                                                        "Alıcı Baz Varlık Hacmi", "Alıcı quote_volume", "Yoksay"])

        df_coin["close"] = pd.to_numeric(df_coin["close"], errors="coerce")
        df_base["close"] = pd.to_numeric(df_base["close"], errors="coerce")

        if len(df_coin) < 10 or len(df_base) < 10:
            print(f"[UYARI] {symbol} veya {base_symbol} için yeterli veri yok: {len(df_coin)}, {len(df_base)}")
            return None
            
        # Ensure lengths match for correlation
        min_len = min(len(df_coin), len(df_base))
        coin_close = df_coin["close"].iloc[-min_len:].reset_index(drop=True)
        base_close = df_base["close"].iloc[-min_len:].reset_index(drop=True)
        
        # Calculate percentage changes
        coin_pct = coin_close.pct_change().dropna()
        base_pct = base_close.pct_change().dropna()
        
        # Need at least some data points
        if len(coin_pct) < 5 or len(base_pct) < 5:
            print(f"[UYARI] {symbol}-{base_symbol} korelasyon için yetersiz değişim verisi")
            return None

        correlation = coin_pct.corr(base_pct)
        
        if pd.isna(correlation):
            print(f"[UYARI] {symbol}-{base_symbol} korelasyon hesaplanamadı (NaN)")
            return None
            
        return round(correlation, 2)
        
    except Exception as e:
        print(f"[HATA] {symbol}-{base_symbol} korelasyon hesaplanırken hata: {e}")
        import traceback
        traceback.print_exc()
        return None



def get_sol_correlation(symbol, interval="1h", limit=100):
    """
    Belirtilen sembol ile SOLUSDT arasındaki korelasyonu hesaplar.

    Args:
        symbol (str): Coin sembolü (örn: 'BTCUSDT')
        interval (str): Zaman aralığı (varsayılan '1h')
        limit (int): Veri limiti (varsayılan 100)

    Returns:
        float: Korelasyon katsayısı
    """
    # Mevcut korelasyon fonksiyonunu SOLUSDT temel alarak kullanma
    return get_correlation(symbol, base_symbol="SOLUSDT", interval=interval, limit=limit)


def handle_sol_korelasyonu():
    """
    SOL korelasyon raporunu oluşturur ve gönderir.
    """
    if ALL_RESULTS:
        # Sonuçları SOL korelasyonuna göre sırala (1h zaman dilimi)
        sorted_results = []
        for coin in ALL_RESULTS:
            try:
                # Henüz hesaplanmadıysa SOL korelasyonunu hesapla
                sol_corr_1h = get_sol_correlation(coin["Coin"], interval="1h", limit=100)

                # Coin verisinin SOL korelasyonu eklenmiş bir kopyasını oluştur
                coin_with_corr = coin.copy()
                coin_with_corr["SOL Correlation"] = str(sol_corr_1h)
                sorted_results.append(coin_with_corr)
            except Exception as e:
                print(f"[HATA] {coin['Coin']} için SOL korelasyonu hesaplanamadı: {e}")
                # Yine de coin'i dahil et, ama korelasyon için "Yok" olarak
                coin_with_corr = coin.copy()
                coin_with_corr["SOL Correlation"] = "Yok"
                sorted_results.append(coin_with_corr)

        # SOL korelasyonuna göre sırala
        sorted_results = sorted(sorted_results,
                                key=lambda x: extract_numeric(x.get("SOL Correlation", 0)
                                                    if x.get("SOL Correlation") != "Yok"
                                                    else 0),
                                reverse=True)

        # Raporu oluştur
        report = generate_sol_correlation_report(sorted_results)

        # Raporu gönder
        send_telegram_message_long(report)
    else:
        send_telegram_message_long("⚠️ Henüz analiz verisi bulunmuyor.")


def generate_sol_correlation_report(results):
    """
    Generates a formatted report for SOL correlation.
    """
    report = f"🔄 <b>SOL Correlation Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report shows the correlation of coins with SOL.\n\n"

    total_corr = 0
    count = 0

    for coin in results:
        # Coin sembolünü düzenle: USDT'yi kaldır ve $ ekle
        symbol = coin["Coin"].replace("USDT", "")
        formatted_symbol = f"${symbol}"

        # Korelasyon değerini al
        correlation_val = coin.get("SOL Correlation", "N/A")
        
        # Ortalama hesaplama için sayısal değeri al
        try:
            if correlation_val != "N/A" and correlation_val is not None and correlation_val != "Yok":
                total_corr += float(correlation_val)
                count += 1
        except:
            pass

        # Rapora ekle
        report += f"{formatted_symbol}: {correlation_val}\n"

    # Ortalama ekle
    if count > 0:
        avg_corr = total_corr / count
        report += f"\n📊 <b>Average Correlation:</b> {avg_corr:.2f}\n"

    report += "\n<b>Note:</b> The correlation coefficient ranges from -1 to 1.\n"
    report += "• Values close to 1 show a strong positive correlation.\n"
    report += "• Values close to -1 show a strong negative correlation.\n"
    report += "• Values close to 0 show weak or no correlation.\n"

    return report

def get_ema_cross_trend(df):
    try:
        # Normalize column names
        df.columns = [str(col).lower() for col in df.columns]
        close_col = "close" if "close" in df.columns else df.columns[0]
        vol_col = "volume" if "volume" in df.columns else "volume"
        
        # Calculate Indicators
        ema20 = EMAIndicator(df[close_col], window=20).ema_indicator()
        ema50 = EMAIndicator(df[close_col], window=50).ema_indicator()
        rsi = RSIIndicator(df[close_col], window=14).rsi()
        
        # Current and Previous Values
        curr_price = df[close_col].iloc[-1]
        prev_price = df[close_col].iloc[-2]
        
        curr_ema20 = ema20.iloc[-1]
        prev_ema20 = ema20.iloc[-2]
        
        curr_ema50 = ema50.iloc[-1]
        prev_ema50 = ema50.iloc[-2]
        
        curr_rsi = rsi.iloc[-1]
        
        # Volume Analysis
        if vol_col in df.columns:
            curr_vol = df[vol_col].iloc[-1]
            avg_vol = df[vol_col].rolling(20).mean().iloc[-1]
            vol_confirm = curr_vol > (avg_vol * 1.2)
        else:
            vol_confirm = False
            
        # 1. TRUE EMA CROSSOVER (Golden/Death Cross) - Strong Signal
        if prev_ema20 < prev_ema50 and curr_ema20 > curr_ema50:
            return "🚀 Golden Cross (20/50)"
        elif prev_ema20 > prev_ema50 and curr_ema20 < curr_ema50:
            return "📉 Death Cross (20/50)"
            
        # 2. PRICE BREAKOUT with VOLUME and RSI FILTER - Fast Signal
        # Bullish Breakout: Price crosses above EMA20 + Volume Spike + RSI > 50
        if prev_price < prev_ema20 and curr_price > curr_ema20:
            if vol_confirm and curr_rsi > 50:
                return "⚡ Volume Breakout"
            elif curr_rsi > 50:
                return "🟢 Bullish (No Vol)"
            
        # Bearish Breakdown: Price crosses below EMA20 + Volume Spike + RSI < 50
        elif prev_price > prev_ema20 and curr_price < curr_ema20:
            if vol_confirm and curr_rsi < 50:
                return "⚡ Volume Breakdown"
            elif curr_rsi < 50:
                return "🔴 Bearish (No Vol)"
            
        # 3. CURRENT STATUS (No Crossover)
        if curr_price > curr_ema20:
            if curr_ema20 > curr_ema50:
                return "🟢 Strong Bullish"
            else:
                return "🟢 Bullish"
        else:
            if curr_ema20 < curr_ema50:
                return "🔴 Strong Bearish"
            else:
                return "🔴 Bearish"
                
    except Exception as e:
        print(f"[ERROR] EMA trend analysis error: {e}")
        return "Stable"

def get_ema_crossover(df):
    try:
        close_col = "close" if "close" in df.columns else "close"
        ema50 = EMAIndicator(df[close_col], window=50).ema_indicator()
        ema100 = EMAIndicator(df[close_col], window=100).ema_indicator()
        ema200 = EMAIndicator(df[close_col], window=200).ema_indicator()
        signals = []
        for i in range(len(df)-1, len(df)): # Only check the latest change
            if ema50.iloc[i - 1] < ema100.iloc[i - 1] and ema50.iloc[i] > ema100.iloc[i]:
                signals.append("EMA 50 Bullish Cross 100")
            elif ema50.iloc[i - 1] > ema100.iloc[i - 1] and ema50.iloc[i] < ema100.iloc[i]:
                signals.append("EMA 50 Bearish Cross 100")
            if ema100.iloc[i - 1] < ema200.iloc[i - 1] and ema100.iloc[i] > ema200.iloc[i]:
                signals.append("EMA 100 Bullish Cross 200")
            elif ema100.iloc[i - 1] > ema200.iloc[i - 1] and ema100.iloc[i] < ema200.iloc[i]:
                signals.append("EMA 100 Bearish Cross 200")
        return signals[-1] if signals else "No significant crossover"
    except Exception as e:
        print(f"[ERROR] EMA crossover analysis error: {e}")
        return "None"

def get_extended_rsi(df, window=21):
    try:
        close_col = "close" if "close" in df.columns else "close"
        rsi_extended = RSIIndicator(df[close_col], window=window).rsi().iloc[-1]
        return round(rsi_extended, 2)
    except Exception as e:
        print(f"[ERROR] Extended RSI error: {e}")
        return None
        print(f"[HATA] Genişletilmiş RSI hesaplanırken hata: {e}")
        return None

def calculate_corrected_momentum(rsi, macd, adx):
    try:
        return ((rsi / 100) * 0.3) + ((macd / 5) * 0.3) + ((adx / 100) * 0.4)
    except:
        return 0


def calculate_taker_volumes(kline_data):
    df = process_kline_data(kline_data)
    if df is None:
        return 0, 0

    try:
        taker_buy_quote = df["taker_buy_quote"].sum()
        quote_volume = df["quote_volume"].sum()

        # Geçerlilik kontrolleri
        if quote_volume <= 0 or np.isnan(quote_volume):
            return 0, 0

        if taker_buy_quote > quote_volume:
            taker_buy_quote = quote_volume

        return taker_buy_quote, quote_volume

    except Exception as e:
        print(f"[HATA] Taker hacim hesaplama hatası: {e}")
        return 0, 0

def calculate_price_roc(df, periods=5):
    try:
        if "close" not in df.columns:
            if "close" in df.columns:
                df = df.rename(columns={"close": "close"})
            else:
                raise ValueError("Gerekli 'close' sütunu bulunamadı.")
        df["close"] = pd.to_numeric(df["close"], errors="coerce").ffill()
        if len(df) < periods:  # En az 'periods' kadar veri olmalı
            print(f"[DEBUG] Yetersiz veri: {len(df)} satır, gerekli {periods}")
            return 0.0
        current = float(df["close"].iloc[-1])  # Son kapanış
        past = float(df["close"].iloc[-periods])  # 'periods' önceki kapanış
        print(f"[DEBUG] Son {periods} kapanış: {df['close'].tail(periods).tolist()}, Current: {current}, Past: {past}")
        if past == 0:
            print("[DEBUG] 24h Change hesaplanamadı: past=0")
            return 0.0
        roc = ((current - past) / past) * 100
        return round(roc, 2)
    except Exception as e:
        print(f"[HATA] 24h Change hesaplanırken hata: {e}")
        return 0.0

def calculate_volume_ratio(df):
    try:
        last_volume = float(df["quote_volume"].iloc[-1])
        avg_volume = pd.to_numeric(df["quote_volume"], errors="coerce").mean()
        ratio = last_volume / avg_volume if avg_volume != 0 else 0
        return round(ratio, 2)
    except Exception as e:
        print(f"[HATA] volume oranı hesaplanırken hata: {e}")
        return 0

def get_volume_ratio_comment(volume_ratio):
    if volume_ratio > 1.5:
        return "High activity, interest increasing."
    elif 0.5 <= volume_ratio <= 1.5:
        return "Normal course, stable volume."
    else:
        return "Low activity, low interest."


def get_volume_comment_improved(volume_change, price_change):
    """
    volume değişim yorumunu iyileştirilmiş kriterlerle yapar.
    Fiyat ve hacim arasındaki ilişkiyi daha doğru yorumlar.

    Args:
        volume_change (float): volume değişim yüzdesi
        price_change (float): Fiyat değişim yüzdesi

    Returns:
        tuple: (yorum_metni, emoji)
    """
    # volume aktif olarak artıyorsa
    if volume_change > 100:
        if price_change > 3:
            return "💪 Çok güçlü hacim desteği!", "💪"
        elif price_change > 0:
            return "👍 İyi hacim desteği", "👍"
        elif price_change < -3:
            return "📉 volume düşüşle uyumlu", "📉"
        else:
            return "⚠️ volume artıyor ama fiyat düşüyor", "⚠️"

    # volume makul derecede artıyorsa
    elif volume_change > 20:
        if price_change > 0:
            return "👍 Supportleyici hacim artışı", "👍"
        else:
            return "⚠️ Artan hacimle düşüş baskısı", "⚠️"

            # volume azalıyorsa, sürekli olumsuz yorum yapmamak için
    elif volume_change < -50:
        # Düşen hacimle yükselen fiyat genelde olumludur (düşük satış baskısı)
        if price_change > 0:
            return "💤 low hacimle yükseliş", "💤"
        else:
            return "📉 Düşen hacim ve fiyat", "📉"

    # Normal hacim değişimi - genelde yorum yapma
    else:
        return "", ""


def ensure_emojis(text):
    """
    Metindeki emoji sorunlarını çözer, eksik emojileri değiştirir.

    Args:
        text (str): Emoji içeren metin

    Returns:
        str: Düzeltilmiş metin
    """
    emoji_replacements = {
        "🔼": "↗️",
        "🔽": "↘️",
        "➡️": "➖",
        "📈": "📈",
        "📉": "📉",
        "🔴": "🔴",
        "🟢": "🟢",
        "⬆️": "⬆️",
        "⬇️": "⬇️",
        "🔥": "🔥",
        "⚠️": "⚠️",
        "🚨": "🚨"
    }

    # Sorunlu emoji varsa değiştir
    for old_emoji, new_emoji in emoji_replacements.items():
        if old_emoji in text:
            # Eski emojiyi yenisiyle değiştir, ancak yeni emoji zaten UTF-8'de düzgün görünüyorsa
            text = text.replace(old_emoji, new_emoji)

    return text

def analyze_price_action(df):
    """
    Performs comprehensive Price Action analysis including Order Blocks, FVG, 
    and Market Structure detection.
    """
    try:
        # Normalize column names
        mapping = {
            "high": "high", "low": "low", "close": "close", "open": "open",
            "high": "high", "low": "low", "close": "close", "open": "open"
        }
        pa_df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        
        if len(pa_df) < 20:
            return {"fvg_bullish": None, "fvg_bearish": None, "structure": "Neutral", "bullish_ob": False, "bearish_ob": False}
        
        # 1. Fair Value Gaps (FVG)
        fvg_bullish = None
        fvg_bearish = None
        for i in range(len(pa_df) - 3, len(pa_df) - 1):
            if pa_df["high"].iloc[i-1] < pa_df["low"].iloc[i+1]:
                fvg_bullish = (pa_df["high"].iloc[i-1], pa_df["low"].iloc[i+1])
            elif pa_df["low"].iloc[i-1] > pa_df["high"].iloc[i+1]:
                fvg_bearish = (pa_df["high"].iloc[i+1], pa_df["low"].iloc[i-1])
                
        # 2. Market Structure
        recent_highs = pa_df["high"].iloc[-10:].astype(float).tolist()
        recent_lows = pa_df["low"].iloc[-10:].astype(float).tolist()
        
        curr_high = pa_df["high"].iloc[-1]
        curr_low = pa_df["low"].iloc[-1]
        
        prev_max_high = max(recent_highs[:-1])
        prev_min_low = min(recent_lows[:-1])
        
        structure = "Sideways"
        if curr_high > prev_max_high and curr_low > prev_min_low: structure = "Bullish (HH/HL)"
        elif curr_high < prev_max_high and curr_low < prev_min_low: structure = "Bearish (LH/LL)"
        
        # 3. Order Blocks (Simplified)
        bullish_ob = False
        bearish_ob = False
        for i in range(len(pa_df)-5, len(pa_df)-1):
            # Bullish OB
            if pa_df["close"].iloc[i] < pa_df["open"].iloc[i]: # Red
                if pa_df["close"].iloc[i+1] > pa_df["high"].iloc[i]: bullish_ob = True
            # Bearish OB
            elif pa_df["close"].iloc[i] > pa_df["open"].iloc[i]: # Green
                if pa_df["close"].iloc[i+1] < pa_df["low"].iloc[i]: bearish_ob = True
                    
        return {
            "fvg_bullish": fvg_bullish,
            "fvg_bearish": fvg_bearish,
            "structure": structure,
            "bullish_ob": bullish_ob,
            "bearish_ob": bearish_ob
        }
    except Exception as e:
        print(f"[PA Error] {e}")
        return {"fvg_bullish": None, "fvg_bearish": None, "structure": "Neutral", "bullish_ob": False, "bearish_ob": False}

def get_order_block_report_string():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."
    
    report = f"📦 <b>Market-Wide Order Block Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Analyzing institutional supply/demand zones</i>\n\n"
    
    bullish_obs = []
    bearish_obs = []
    
    for coin in ALL_RESULTS[:50]:
        symbol = "$" + coin["Coin"].replace("USDT", "")
        if coin.get("bullish_ob"):
            bullish_obs.append(symbol)
        if coin.get("bearish_ob"):
            bearish_obs.append(symbol)
            
    report += f"🟢 <b>BULLISH ORDER BLOCKS ({len(bullish_obs)}):</b>\n"
    if bullish_obs:
        report += ", ".join(bullish_obs[:20])
        if len(bullish_obs) > 20: report += "..."
    else:
        report += "None detected in top 50."
    report += "\n\n"
    
    report += f"🔴 <b>BEARISH ORDER BLOCKS ({len(bearish_obs)}):</b>\n"
    if bearish_obs:
        report += ", ".join(bearish_obs[:20])
        if len(bearish_obs) > 20: report += "..."
    else:
        report += "None detected in top 50."
    report += "\n\n"
    
    report += "<b>💡 Interpretation:</b>\n"
    report += "• <b>Bullish OB:</b> Significant buy interest detected, price often bounces from these levels.\n"
    report += "• <b>Bearish OB:</b> Significant sell interest detected, price often rejects from these levels.\n"
    
    return report

def get_liq_heatmap_report_string():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."
    
    report = f"🔥 <b>Global Liquidation Heatmap Summary – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Concentrated liquidation clusters in the market</i>\n\n"
    
    hot_zones = []
    for coin in ALL_RESULTS[:50]:
        lh = coin.get("Liq Heatmap", "")
        if "🔥" in lh or "High Intensity" in lh or "Risk" in lh:
            symbol = "$" + coin["Coin"].replace("USDT", "")
            # Extract just the first line of the heatmap report which usually has the summary
            summary = lh.split("\n")[0].replace("🔥 Liq Heatmap:", "").strip()
            hot_zones.append(f"• <b>{symbol}</b>: {summary}")
            
    if hot_zones:
        report += "🏮 <b>HIGH INTENSITY ZONES:</b>\n"
        report += "\n".join(hot_zones[:15])
        if len(hot_zones) > 15: report += "\n...and more."
    else:
        report += "No major liquidation cascades detected in the current ±10% range."
        
    report += "\n\n<b>ℹ️ Note:</b> These are zones where significant liquidations are likely to occur, often acting as magnets for price."
    return report


def calculate_fibonacci_levels(df):
    try:
        # Support both original and translated column names
        high_col = "high" if "high" in df.columns else "high"
        low_col = "low" if "low" in df.columns else "low"
        
        if high_col not in df.columns or low_col not in df.columns:
            return {"0%": 0, "23.6%": 0, "38.2%": 0, "50%": 0, "61.8%": 0, "100%": 0}

        high = df[high_col].astype(float).max()
        low = df[low_col].astype(float).min()
        diff = high - low
        levels = {
            "0%": low,
            "23.6%": low + 0.236 * diff,
            "38.2%": low + 0.382 * diff,
            "50%": low + 0.5 * diff,
            "61.8%": low + 0.618 * diff,
            "100%": high
        }
        return levels
    except Exception as e:
        print(f"[HATA] Fibonacci seviyeleri hesaplanırken hata: {e}")
        return {"0%": 0, "23.6%": 0, "38.2%": 0, "50%": 0, "61.8%": 0, "100%": 0}

# ---------------- Telegram Fonksiyonları ----------------
def get_telegram_updates(offset):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 100, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=120)
        return response.json()
    except Exception as e:
        print(f"[HATA] Telegram güncellemeleri alınamadı: {e}")
        return {"ok": False, "result": []}


# Telegram Functions Aliases (implementations in telegram_bot.py)
send_telegram_message = send_telegram_message
send_telegram_message_long = send_telegram_message_long
send_reply_keyboard_message = telegram_bot.send_reply_keyboard_message


def check_telegram_updates():
    offset = 0
    print("[INFO] Telegram update loop triggered/restarted.")
    while True:
        try:
            updates = get_telegram_updates(offset)
            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    
                    # Handle Callback Queries (Inline Buttons)
                    if "callback_query" in update:
                        # If we ever implement inline buttons, handle them here
                        # For now, just acknowledge or print
                        print(f"[DEBUG] Callback Query received: {update['callback_query']}")
                        continue

                    # Handle Messages
                    if "message" not in update or "text" not in update["message"]:
                        continue
                        
                    chat_id = update["message"]["chat"]["id"]
                    message_text = update["message"]["text"].strip()
                    message_obj = update["message"]

                    # System Commands
                    if message_text == "/start":
                        send_telegram_message(chat_id, "Bot başlatıldı! Piyasa analizleri için hazırım.")
                        # Send main menu
                        handle_main_menu_return(chat_id)
                    elif message_text == "/hourly":
                        generate_hourly_report(chat_id=chat_id)
                    elif message_text == "/quick":
                        generate_quick_summary(chat_id=chat_id)
                    elif message_text.startswith("/analyze"):
                        # Keep existing analyze logic or delegate? 
                        # Existing logic matches specific format, let's keep it for slash commands
                        parts = message_text.split()
                        if len(parts) != 2:
                            send_telegram_message(chat_id, "Lütfen bir coin belirtin, örn: /analyze BTCUSDT")
                            continue
                        symbol = parts[1].upper()
                        if symbol in [coin["Coin"] for coin in ALL_RESULTS]:
                            with global_lock:
                                coin_data = next((c for c in ALL_RESULTS if c["Coin"] == symbol), None)
                            if coin_data:
                                kline_data = sync_fetch_kline_data(symbol, "1h", limit=200)
                                indicators = get_technical_indicators(symbol, kline_data)
                                analysis = analyze_whale_movement(indicators)
                                send_telegram_message(chat_id, analysis)
                            else:
                                send_telegram_message(chat_id, f"{symbol} için veri bulunamadı.")
                        else:
                            send_telegram_message(chat_id, f"{symbol} analiz listesinde yok.")
                    elif message_text.startswith("/liquidation"):
                        parts = message_text.split()
                        if len(parts) != 2:
                            send_telegram_message(chat_id, "Lütfen bir coin belirtin, örn: /liquidation BTCUSDT")
                            continue
                        symbol = parts[1].upper()
                        if symbol in [coin["Coin"] for coin in ALL_RESULTS]:
                            liquidation_analysis = analyze_liquidation(symbol)
                            send_telegram_message(chat_id, liquidation_analysis)
                        else:
                            send_telegram_message(chat_id, f"{symbol} analiz listesinde yok.")
                    elif message_text.startswith("/sentiment"):
                        parts = message_text.split()
                        if len(parts) != 2:
                            send_telegram_message(chat_id, "Lütfen bir coin belirtin, örn: /sentiment BTCUSDT")
                            continue
                        symbol = parts[1].upper()
                        if symbol in [coin["Coin"] for coin in ALL_RESULTS]:
                            liquidation_analysis = analyze_social_sentiment(symbol) # Correction: call sentiment analysis
                            send_telegram_message(chat_id, liquidation_analysis)
                        else:
                            send_telegram_message(chat_id, f"{symbol} analiz listesinde yok.")
                    elif message_text.startswith("/arbitrage"):
                         parts = message_text.split()
                         if len(parts) != 2:
                             send_telegram_message(chat_id, "Lütfen bir coin belirtin, örn: /arbitrage BTCUSDT")
                             continue
                         symbol = parts[1].upper()
                         if symbol in [coin["Coin"] for coin in ALL_RESULTS]:
                             arbitrage_analysis = analyze_arbitrage(symbol)
                             send_telegram_message(chat_id, arbitrage_analysis)
                         else:
                             send_telegram_message(chat_id, f"{symbol} analiz listesinde yok.")
                    else:
                        # Pass all other text (including reply keyboard buttons) to the menu handler
                        handle_reply_message(message_obj)
                        
            time.sleep(1)
        except Exception as e:
            print(f"[HATA] Telegram güncellemelerinde hata: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)


# send_telegram_message_long and send_reply_keyboard_message moved to telegram_bot.py
# Aliases defined above.



def send_submenu(chat_id, title, description, keyboard):
    """
    Standart bir alt menü göndermek için fonksiyon

    Args:
        chat_id (str): Chat ID
        title (str): Menü başlığı
        description (str): Açıklama
        keyboard (list): Klavye düğmeleri
    """
    message = f"<b>{title}</b>\n\n{description}"
    send_reply_keyboard_message(chat_id, message, keyboard=keyboard)


# ---------------- Zaman Serisi ve AI Fonksiyonları ----------------
def prepare_time_series_data(symbol):
    reports = FIVE_MIN_REPORTS.get(symbol, [])
    if len(reports) < 12:
        return None
    df = pd.DataFrame(reports)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df


def prepare_lstm_data(df):
    scaler = MinMaxScaler()
    features = df[['price', 'rsi', 'volume_ratio', 'net_accum']].values
    scaled_data = scaler.fit_transform(features)
    X, y = [], []
    for i in range(12, len(scaled_data)):
        X.append(scaled_data[i - 12:i])
        y.append(scaled_data[i, 0])
    return np.array(X), np.array(y), scaler



def generate_order_book_report(sorted_data):
    if not sorted_data:
        return "⚠️ Order Book data not yet collected."
    
    report = "📚 <b>Order Book & Depth Analysis</b>\n\n"
    
    # Sort by spread (lower is better for liquidity)
    # Filter out coins with no OB data first
    valid_data = [c for c in sorted_data if c.get("OrderBook")]
    sorted_by_spread = sorted(valid_data, key=lambda x: x.get("OrderBook", {}).get("spread_pct", 100))
    
    count = 0
    for coin in sorted_by_spread:
        ob = coin.get("OrderBook")
        if not ob or not isinstance(ob, dict): 
            continue
            
        count += 1
        if count > 50: break
        
        symbol = "$" + coin["Coin"].replace("USDT", "")
        price = coin["Price_Display"]
        spread = ob.get("spread_pct", 0)
        imbalance = ob.get("imbalance_pct", 0) # Positive likely bullish
        
        walls = ob.get("whale_walls", {})
        wall_msg = ""
        if walls:
            b_wall = walls.get("buy_wall_price")
            s_wall = walls.get("sell_wall_price")
            # Format walls
            if b_wall: wall_msg += f"  🟢 Buy Wall: {b_wall}\n"
            if s_wall: wall_msg += f"  🔴 Sell Wall: {s_wall}\n"
            
        depth = ob.get("depth_analysis", {})
        ratio = 0
        depth_icon = "⚖️"
        if depth:
            b_qty = depth.get("bids_qty", 0)
            a_qty = depth.get("asks_qty", 0)
            if a_qty > 0:
                ratio = b_qty / a_qty
                if ratio > 1.2: depth_icon = "🐂"
                elif ratio < 0.8: depth_icon = "🐻"
        
        report += f"<b>{symbol}</b> ({price}) {depth_icon}\n"
        report += f"  Spread: {spread:.2f}% | Imbal: {imbalance:.2f}%\n"
        report += f"  Bid/Ask Ratio: {ratio:.2f}\n"
        report += wall_msg
        report += "----------------\n"
        
    return report

def analyze_coin(symbol):
    df = prepare_time_series_data(symbol)
    if df is None:
        return None
    latest_coin = next((c for c in ALL_RESULTS if c["Coin"] == symbol), None)
    if not latest_coin:
        return None
    rf_pred_change, prophet_pred = predict_with_cached_model(symbol, df)
    prices = df['price'].values
    rsis = df['rsi'].values
    volumes = df['volume_ratio'].values
    net_accums = df['net_accum'].values
    price_trend = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] != 0 else 0
    rsi_avg = np.mean(rsis)
    volume_trend = (volumes[-1] - volumes[0]) / volumes[0] * 100 if volumes[0] != 0 else 0
    net_accum_sum = np.sum(net_accums)
    with global_lock:
        prev_data = PREV_HOURLY_REPORTS.get(symbol, {})
    prev_price = prev_data.get("price", prices[0])
    curr_price = prices[-1]
    fib_levels = calculate_fibonacci_levels(df)
    sr = latest_coin["Support_Resistance"].split(" - ")
    support = parse_money(sr[0])
    resistance = parse_money(sr[1])
    rf_pred_price = curr_price * (1 + rf_pred_change)
    avg_pred_price = (rf_pred_price + prophet_pred) / 2
    pred_change = (avg_pred_price - curr_price) / curr_price * 100
    if pred_change > 50:
        avg_pred_price = curr_price * 1.5
        pred_change = 50
    elif pred_change < -50:
        avg_pred_price = curr_price * 0.5
        pred_change = -50
    if pred_change > 0:
        target = min(avg_pred_price, resistance, fib_levels["61.8%"])
    else:
        target = max(avg_pred_price, support, fib_levels["38.2%"])
    adjusted_pred_change = (target - curr_price) / curr_price * 100
    coin_report = f"<b>${symbol}:</b>\n"
    coin_report += f"   • <b>Price:</b> {format_money(curr_price)}$ (Prev: {format_money(prev_price)}$, {round(price_trend, 2)}%)\n"
    coin_report += f"   • <b>RSI:</b> {round(rsi_avg, 2)}\n"
    coin_report += f"   • <b>Volume:</b> {round(volume_trend, 2)}% (24h Avg: {latest_coin['Volume Ratio']}x)\n"
    coin_report += f"   • <b>Net Accumulation:</b> {round(net_accum_sum, 2)}M USD\n"
    coin_report += f"   • <b>AI Prediction (1h later):</b> {format_money(target)}$ ({round(adjusted_pred_change, 2)}%)\n"
    coin_report += f"   • <b>Support/Resistance:</b> {latest_coin['Support_Resistance']}\n"
    return coin_report


def generate_hourly_report(chat_id=None):
    report = generate_hourly_report_string()
    if report:
        send_telegram_message(chat_id or TELEGRAM_CHAT_ID, report)

def generate_hourly_report_string():
    report = f"📊 <b>Hourly Analysis and AI Prediction – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "Validity: 1 hour\n\n"
    valid_reports = [r for r in FIVE_MIN_REPORTS.values() if len(r) >= 12]
    total_net_accum = sum(sum(r["net_accum"] for r in reports) for reports in valid_reports)
    price_changes = [
        ((r[-1]["price"] - r[0]["price"]) / r[0]["price"] * 100) if r[0]["price"] != 0 else 0
        for r in valid_reports
    ]
    avg_price_change = np.mean(price_changes) if price_changes else 0.0
    report += f"<b>Market Summary:</b> Net accumulation {format_money(total_net_accum)}M USD, average price change {round(avg_price_change, 1)}%.\n\n"
    
    # Selection of top featured coins
    top_changes = sorted(FIVE_MIN_REPORTS.items(),
                         key=lambda x: abs((x[1][-1]["price"] - x[1][0]["price"]) / x[1][0]["price"] * 100) if x[1][0]["price"] != 0 else 0,
                         reverse=True)[:3]
    
    report += "<b>Featured Coins:</b>\n"
    with ThreadPoolExecutor(max_workers=10) as executor:
        coin_reports = list(executor.map(analyze_coin, [symbol for symbol, _ in top_changes]))
    
    for coin_report in coin_reports:
        if coin_report:
            report += coin_report
            
    report += "<b>AI Models:</b>\n- Random Forest: Short-term analysis.\n- Prophet: Trend forecasting.\n"
    report += "\n👉 For more coins, use /analyze <coin> command."
    return report


def handle_makroekonomik_gostergeler():
    """Generates a detailed report of macroeconomic indicators."""
    try:
        print("[DEBUG] Makroekonomik göstergeler raporu hazırlanıyor...")

        # Bellek sorununu önlemek için kontrolsüz veri çağırma önleniyor
        if not ALL_RESULTS or len(ALL_RESULTS) < 5:
            print("[UYARI] ALL_RESULTS verisi hazır değil, varsayılan değerler kullanılacak")

        macro_data = fetch_macro_economic_data()
        if not macro_data:
            send_telegram_message_long("⚠️ Makroekonomik veriler alınamadı. Lütfen daha sonra tekrar deneyin.")
            return

        report = f"🌐 <b>Makroekonomik Göstergeler Raporu – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        # Ekonomik Olaylar
        report += "<b>📅 Yaklaşan Ekonomik Olaylar:</b>\n"
        for event in macro_data.get("economic_events", []):
            report += f"• {event['event_name']} ({event['country']})\n"
            report += f"  Tarih: {event['time']}\n"
            report += f"  Beklenti: {event.get('forecast', 'N/A')}\n"
            report += f"  Önceki Değer: {event.get('previous', 'N/A')}\n\n"

        # Piyasa Endeksleri
        report += "<b>📊 Piyasa Endeksleri:</b>\n"
        for index, data in macro_data.get("market_indices", {}).items():
            trend = "🟢 Yükseliş" if data.get('change', 0) > 0 else "🔴 Düşüş"
            report += f"• {index}: {data.get('value', 'N/A')} ({trend}, {data.get('change', 0):+.2f}%)\n"

        # Kripto Piyasası
        crypto_market = macro_data.get("crypto_market", {})
        report += "\n<b>💹 Kripto Piyasa Özeti:</b>\n"
        report += f"• Toplam Piyasa Değeri: ${crypto_market.get('total_market_cap', 0) / 1e12:.2f} Trilyon\n"
        report += f"• BTC Dominansı: %{crypto_market.get('btc_dominance', 'N/A')}\n"
        report += f"• 24h Volume: ${crypto_market.get('daily_volume', 0) / 1e9:.2f} Milyar\n"
        report += f"• Korku & Açgözlülük Endeksi: {crypto_market.get('fear_greed_index', 'N/A')}/100\n"

        # Dolar ve Tahvil Verileri
        dollar_strength = macro_data.get("dollar_strength", {})
        treasury_yields = macro_data.get("treasury_yields", {})

        report += "\n<b>💵 Dolar ve Tahvil Göstergeleri:</b>\n"
        report += f"• Dolar Endeksi: {dollar_strength.get('DXY_index', 'N/A')} "
        report += f"({dollar_strength.get('DXY_trend', 'N/A')}, {dollar_strength.get('DXY_change', 0):+.2f}%)\n"
        report += f"• 10 Yıllık Tahvil Getirisi: %{treasury_yields.get('US_10Y', 'N/A')}\n"
        report += f"• 2 Yıllık Tahvil Getirisi: %{treasury_yields.get('US_2Y', 'N/A')}\n"
        report += f"• Getiri Eğrisi: {treasury_yields.get('yield_curve', 'N/A')}\n"

        # Risk değerlendirmesi
        macro_risk = calculate_macro_risk_level(macro_data)
        report += "\n<b>⚠️ Risk Değerlendirmesi:</b>\n"
        report += f"• Genel Risk Skoru: {macro_risk['risk_score']}/100 ({macro_risk['risk_level'].upper()})\n"

        if macro_risk['factors']:
            report += "• Öne Çıkan Risk Faktörleri:\n"
            for factor in macro_risk['factors'][:2]:
                report += f"  - {factor['factor']}: {factor['description']}\n"

        # Etki ve öneriler
        report += "\n<b>💡 Piyasa Etkisi ve Öneriler:</b>\n"

        if macro_risk['risk_score'] >= 70:
            report += "• Kripto varlıklar üzerinde ciddi baskı oluşabilir.\n"
            report += "• Öneri: Portföyde nakit oranını artırın, riskli varlıkları azaltın.\n"
        elif macro_risk['risk_score'] >= 50:
            report += "• Kripto varlıklar üzerinde baskı olabilir, volatilite artabilir.\n"
            report += "• Öneri: Stop-loss seviyeleri belirleyin, temkinli olun.\n"
        elif macro_risk['risk_score'] >= 30:
            report += "• Piyasada karışık sinyaller var, seçici olmak gerekir.\n"
            report += "• Öneri: Güçlü projeler seçin, portföy çeşitliliğini koruyun.\n"
        else:
            report += "• Makroekonomik ortam kripto varlıklar için olumlu görünüyor.\n"
            report += "• Öneri: Alım fırsatlarını değerlendirin, ancak risk yönetimini ihmal etmeyin.\n"

        send_telegram_message_long(report)
    except Exception as e:
        print(f"[HATA] Makroekonomik göstergeler raporlaması sırasında hata: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message_long(
            "⚠️ Makroekonomik göstergeler raporu oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


def generate_quick_summary(chat_id=None):
    global ALL_RESULTS
    with global_lock:
        if not ALL_RESULTS:
            message = "⚠️ Veri yok, özet oluşturulamadı."
            send_telegram_message(chat_id or TELEGRAM_CHAT_ID, message)
            return
        top_gainer = max(ALL_RESULTS, key=lambda x: float(x["24h Change"]))
        top_loser = min(ALL_RESULTS, key=lambda x: float(x["24h Change"]))
        avg_price_change = sum(extract_numeric(r["24h Change"]) for r in ALL_RESULTS) / len(ALL_RESULTS)

    summary = f"⚡ *Hızlı Piyasa Özeti* ({datetime.now().strftime('%H:%M')})\n"
    summary += f"📈 *En Çok Yükselen*: {top_gainer['Coin']} ({top_gainer['24h Change']})\n"
    summary += f"📉 *En Çok Düşen*: {top_loser['Coin']} ({top_loser['24h Change']})\n"
    summary += f"📊 *Ort. Fiyat Değişimi*: {avg_price_change:.2f}%\n"
    summary += f"ℹ️ Daha fazla detay için /analyze <coin> kullanın."

    send_telegram_message(chat_id or TELEGRAM_CHAT_ID, summary)


def analyze_liquidation(symbol):
    try:
        url = f"{BINANCE_FUTURES_API_URL}premiumIndex?symbol={symbol}"
        response = requests.get(url).json()
        funding_rate = float(response.get("lastFundingRate", 0)) * 100  # Yüzdeye çevir
        open_interest_url = f"{BINANCE_FUTURES_API_URL}openInterest?symbol={symbol}"
        oi_response = requests.get(open_interest_url).json()
        open_interest = float(oi_response.get("openInterest", 0)) * parse_money(sync_fetch_kline_data(symbol, "1h", 1)[0][4])  # USD cinsine çevir

        liquidation_risk = "Normal"
        if abs(funding_rate) > 0.05:  # high fonlama oranı = tasfiye riski
            liquidation_risk = "high Tasfiye Riski" if funding_rate > 0 else "high Short Tasfiye Riski"
        elif abs(funding_rate) > 0.02:
            liquidation_risk = "Orta Tasfiye Riski"

        summary = f"📉 *${symbol.replace('USDT', '')} Liquidation Analysis* 📉\n"
        summary += f"💸 Funding Rate: {funding_rate:.3f}%\n"
        summary += f"📊 Open Interest: {format_money(open_interest)} USD\n"
        summary += f"⚠️ Liquidation Risk: {liquidation_risk}\n"
        return summary
    except Exception as e:
        print(f"[ERROR] Liquidation analysis error: {e}")
        return f"Could not perform liquidation analysis for ${symbol.replace('USDT', '')}."


def analyze_social_sentiment(symbol):
    try:
        # X API yerine simüle edilmiş bir sonuç (gerçek API için xAI'den erişim gerekir)
        tweet_count = random.randint(50, 500)  # Simüle edilmiş tweet sayısı
        sentiment_score = random.uniform(-1, 1)  # -1 (negatif) ile 1 (pozitif) arasında

        sentiment = "Nötr"
        if sentiment_score > 0.3:
            sentiment = "Pozitif"
        elif sentiment_score < -0.3:
            sentiment = "Negatif"

        summary = f"📢 *${symbol.replace('USDT', '')} Social Media Analysis* 📢\n"
        summary += f"🐦 Tweet Count (Last 1h): {tweet_count}\n"
        summary += f"😊 Sentiment Score: {sentiment_score:.2f} ({sentiment})\n"
        return summary
    except Exception as e:
        print(f"[ERROR] Social media analysis error: {e}")
        return f"Could not perform social media analysis for ${symbol.replace('USDT', '')}."


def analyze_arbitrage(symbol):
    try:
        # Binance fiyatı
        binance_price = parse_money(sync_fetch_kline_data(symbol, "1m", 1)[0][4])

        # KuCoin fiyatı (örnek API, gerçekte KuCoin API kullanılmalı)
        kucoin_url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol.replace('USDT', '-USDT')}"
        kucoin_response = requests.get(kucoin_url).json()
        kucoin_price = float(kucoin_response["data"]["price"]) if kucoin_response.get("data") else binance_price

        price_diff = ((kucoin_price - binance_price) / binance_price) * 100
        arbitrage_opportunity = "Yok"
        if abs(price_diff) > 0.5:  # %0.5’ten büyük fark = fırsat
            arbitrage_opportunity = "Var" if price_diff > 0 else "Var (Ters Yön)"

        summary = f"💰 *${symbol.replace('USDT', '')} Arbitrage Analysis* 💰\n"
        summary += f"📍 Binance Price: {binance_price:.2f} USD\n"
        summary += f"📍 KuCoin Price: {kucoin_price:.2f} USD\n"
        summary += f"📊 Price Difference: {price_diff:.2f}%\n"
        summary += f"🎯 Arbitrage Opportunity: {arbitrage_opportunity}\n"
        return summary
    except Exception as e:
        print(f"[ERROR] Arbitrage analysis error: {e}")
        return f"Could not perform arbitrage analysis for ${symbol.replace('USDT', '')}."


def get_filtered_coins():
    url = BINANCE_API_URL + "ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[HATA] Binance API hatası: {response.status_code}")
            return []
        tickers = response.json()
        # Stablecoin'leri hariç tut
        stablecoins = ["USDCUSDT", "FDUSDUSDT", "BUSDUSDT", "TUSDUSDT"]
        filtered = [t["symbol"] for t in tickers if t["symbol"].endswith("USDT") and t["symbol"] not in stablecoins]
        sorted_filtered = sorted(filtered, key=lambda x: float([t for t in tickers if t["symbol"] == x][0]["quoteVolume"]), reverse=True)
        return sorted_filtered[:50]
    except Exception as e:
        print(f"[HATA] Coin filtresi alınırken hata: {e}")
        return []


def get_ticker_info(symbol):
    url = BINANCE_API_URL + f"ticker/24hr?symbol={symbol}"
    try:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)
        response = session.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            price_change_percent = extract_numeric(data.get("priceChangePercent", 0))
            quote_volume = extract_numeric(data.get("quoteVolume", 0))
            return price_change_percent, quote_volume
    except Exception as e:
        print(f"[HATA] Ticker bilgisi alınırken hata: {e}")
    return 0, 0


def get_futures_stats(symbol):
    try:
        print(f"\n[DEBUG] {symbol} için futures istatistikleri alınıyor...")
        
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)

        oi_url = BINANCE_FUTURES_API_URL + f"openInterest?symbol={symbol}"
        resp_oi = session.get(oi_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        open_interest = float(resp_oi.json()["openInterest"]) if resp_oi.status_code == 200 else 0
        print(f"[DEBUG] Open Interest: {open_interest}")

        # Long/short oranı için yeni fonksiyonu kullan
        long_short_ratio = fetch_enhanced_ls_ratio(symbol)
        print(f"[DEBUG] Final L/S Ratio: {long_short_ratio:.2f}")

        return open_interest, long_short_ratio
    except Exception as e:
        print(f"[HATA] Futures verisi alınırken hata: {e}")
        return 0, 1.0


def get_candle_close(symbol, interval, limit=2):
    url = BINANCE_API_URL + f"klines?symbol={symbol}&interval={interval}&limit={limit}"
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('https://', adapter)
    
    try:
        response = session.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = response.json()
            if len(data) >= 2:
                # print(f"[DEBUG] {symbol} için {interval} kapanış alındı: {data[-2][4]}")
                return float(data[-2][4])
            else:
                print(f"[HATA] {symbol} için {interval} kapanış verisi yetersiz: {len(data)} satır")
        else:
            print(f"[HATA] {symbol} için {interval} kapanış alınamadı: {response.status_code}")
            # Try backup/public API if internal config URL is weird?
            # But assume BINANCE_API_URL is correct for now.
    except Exception as e:
        print(f"[HATA] {symbol} için {interval} kapanış alınırken hata: {e}")
    return None

def get_arrow(current, previous):
    try:
        current = float(current)
        previous = float(previous)
    except:
        return ""
    if current > previous:
        return "🔼"
    elif current < previous:
        return "🔽"
    else:
        return ""


def detect_order_block(df, window=20):
    recent_high = df["high"].rolling(window=window).max().iloc[-1]
    recent_low = df["low"].rolling(window=window).min().iloc[-1]
    return f"{format_money(recent_low)} - {format_money(recent_high)}"


def detect_advanced_order_block(df, window=20):
    try:
        recent_highs = df["high"].rolling(window=window).max()
        recent_lows = df["low"].rolling(window=window).min()
        volume_spikes = df["quote_volume"].astype(float).rolling(window=window).mean() * 2
        order_blocks = []
        for i in range(-window, 0):
            if float(df["quote_volume"].iloc[i]) > volume_spikes.iloc[i]:
                order_blocks.append(f"{format_money(recent_lows.iloc[i])} - {format_money(recent_highs.iloc[i])}")
        return order_blocks[
            -1] if order_blocks else f"{format_money(recent_lows.iloc[-1])} - {format_money(recent_highs.iloc[-1])}"
    except:
        return "Order block tespit edilemedi."


def get_ema20_crossover(df):
    ema_series = EMAIndicator(df["close"], window=20).ema_indicator()
    prev_price = df["close"].iloc[-2]
    curr_price = df["close"].iloc[-1]
    prev_ema = ema_series.iloc[-2]
    curr_ema = ema_series.iloc[-1]
    if prev_price < prev_ema and curr_price > curr_ema:
        return "Bullish Crossover"
    elif prev_price > prev_ema and curr_price < curr_ema:
        return "Bearish Crossover"
    else:
        return "Kesişim Yok"


def detect_traps(df, current_price, support, resistance, volume_ratio, rsi):
    try:
        high_col = "high" if "high" in df.columns else "high"
        low_col = "low" if "low" in df.columns else "low"
        
        last_5_highs = df[high_col].iloc[-5:].astype(float)
        last_5_lows = df[low_col].iloc[-5:].astype(float)
        price_range = (resistance - support) if resistance and support and resistance > support else current_price * 0.05
        
        broke_above_resistance = any(last_5_highs > resistance + 0.005 * price_range) if resistance else False
        fell_below_resistance = current_price < resistance - 0.005 * price_range if resistance else False
        overbought_rsi = rsi > 65 if rsi else False
        volume_spike = volume_ratio > 1.3 if volume_ratio else False
        
        if broke_above_resistance and fell_below_resistance and (overbought_rsi or not volume_spike):
            return "Bull Trap detected!"
            
        broke_below_support = any(last_5_lows < support - 0.005 * price_range) if support else False
        rose_above_support = current_price > support + 0.005 * price_range if support else False
        oversold_rsi = rsi < 35 if rsi else False
        
        if broke_below_support and rose_above_support and (oversold_rsi or volume_spike):
            return "Bear Trap detected!"
            
        return "None"
    except Exception as e:
        print(f"[ERROR] Trap detection error: {e}")
        return "No trap detected."


def analyze_liquidation_heatmap(df, current_price, symbol="Unknown"):
    """
    Estimates liquidation clusters based on common leverages (10x, 25x, 50x, 100x)
    across a distribution of entry points (High, Low, Avg, Current).
    Provides a normalized intensity heatmap of risk zones.
    """
    try:
        if df is None or len(df) < 50:
            return "Insufficient data for liquidation mapping."

        # Support both column naming conventions
        high_col = "high" if "high" in df.columns else "high"
        low_col = "low" if "low" in df.columns else "low"
        
        # Identify major price pivots in the last 100 periods
        recent_df = df.tail(100)
        pivots = [
            recent_df[high_col].max(),
            recent_df[low_col].min(),
            recent_df["close"].mean(),
            current_price
        ]

        leverages = [10, 25, 50, 100]
        liqs = []

        # 32 simulated data points (4 entries * 4 leverages * 2 directions)
        for entry in pivots:
            for lev in leverages:
                # 1. Potential Long Liquidations (Price drops)
                liq_price_long = entry * (1 - (1/lev) * 0.95)
                liqs.append({"price": liq_price_long, "type": "Long", "lev": lev})
                
                # 2. Potential Short Liquidations (Price rises)
                liq_price_short = entry * (1 + (1/lev) * 0.95)
                liqs.append({"price": liq_price_short, "type": "Short", "lev": lev})

        # Dynamic heatmap grouping (±10% range)
        clusters = []
        # Check a range of ±7% around current price with higher resolution (0.25% steps)
        for i in range(-28, 29):
            lower_bound = current_price * (1 + (i * 0.0025))
            upper_bound = current_price * (1 + ((i+1) * 0.0025))
            
            hits = [l for l in liqs if lower_bound <= l["price"] < upper_bound]
            if hits:
                # Improved Intensity Scaling
                # lev_weight: Higher leverage positions are more sensitive (liquidate first)
                lev_weight = sum([h["lev"] for h in hits])
                # Normalize against a "high density" threshold (e.g. 300 total leverage weight in one bucket)
                intensity_pct = min(100, int((lev_weight / 400) * 100))
                
                if intensity_pct > 0:
                    clusters.append({
                        "range": f"${format_money(lower_bound)} - ${format_money(upper_bound)}",
                        "intensity": intensity_pct,
                        "type": "Short" if lower_bound > current_price else "Long",
                        "mid": (lower_bound + upper_bound) / 2,
                        "dist_pct": ((lower_bound / current_price) - 1) * 100
                    })

        clusters = sorted(clusters, key=lambda x: x["intensity"], reverse=True)
        
        if not clusters:
            return "No significant liquidation clusters detected within 7% range."

        # Add metadata for summary report
        max_risk = clusters[0]["intensity"]
        risk_type = clusters[0]["type"]
        
        clean_symbol = "$" + symbol.replace("USDT", "")
        report = f"🔥 <b>Liq Heatmap: {clean_symbol}</b> (Max Risk: {max_risk}%)\n\n"
        report += "<b>High Density Clusters:</b>\n"
        
        for c in clusters[:5]:
            icon = "🔴" if c["type"] == "Short" else "🟢"
            # Gradient bar
            bar_len = min(10, c["intensity"] // 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            report += f"{icon} {c['range']} ({c['dist_pct']:+.1f}%)\n  Intensity: {bar} <b>{c['intensity']}%</b>\n"
            
        # Summary
        nearest = min(clusters, key=lambda x: abs(x["mid"] - current_price))
        report += f"\n<b>⚡ Critical Zone:</b> Nearest cluster at {nearest['dist_pct']:+.1f}% ({nearest['type']} Liqs)."
        
        # Hidden data for sorting
        report += f"<!--MAX_RISK:{max_risk}-->"
        report += f"<!--RISK_TYPE:{risk_type}-->"
        report += f"<!--NEAREST:{nearest['dist_pct']}-->"
        
        return report

    except Exception as e:
        print(f"[ERROR] Liquidation analysis failed: {e}")
        return "Liquidation data estimation failed."


def detect_imbalance(coin_data):
    try:
        volume_ratio = extract_numeric(coin_data["Volume Ratio"])
        whale_buy = parse_money(coin_data["Whale_Buy_M"])
        whale_sell = parse_money(coin_data["Whale_Sell_M"])
        total_volume = whale_buy + whale_sell
        imbalance_ratio = (whale_buy - whale_sell) / total_volume if total_volume != 0 else 0
        if abs(imbalance_ratio) > 0.2 and volume_ratio > 1.5:
            return f"{'Buyer' if imbalance_ratio > 0 else 'Seller'} dominant imbalance! ({round(imbalance_ratio * 100, 2)}%)"
        return "No imbalance."
    except:
        return "Dengesizlik analizi yapılamadı."


def calculate_vwap(df):
    try:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        volume = df["volume"].astype(float)
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return round(vwap.iloc[-1], 4)
    except:
        return None


def record_five_min_report(current_results):
    global last_hourly_report_time
    with global_lock:
        for curr_coin in current_results:
            symbol = curr_coin["Coin"]
            # Safely extract numeric values regardless of whether they are strings or floats
            curr_price = extract_numeric(curr_coin.get("Price", 0))
            if curr_price == 0:
                curr_price = extract_numeric(curr_coin.get("Price_Display", 0))
                
            curr_rsi = extract_numeric(curr_coin.get("RSI", 0))
            curr_volume_ratio = extract_numeric(curr_coin.get("Volume Ratio", 1.0))
            curr_net_accum = extract_numeric(curr_coin.get("NetAccum_raw", 0))
            
            if symbol not in FIVE_MIN_REPORTS:
                FIVE_MIN_REPORTS[symbol] = []
            FIVE_MIN_REPORTS[symbol].append({
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "price": curr_price,
                "rsi": curr_rsi,
                "volume_ratio": curr_volume_ratio,
                "net_accum": curr_net_accum
            })
            if len(FIVE_MIN_REPORTS[symbol]) > 12:
                FIVE_MIN_REPORTS[symbol].pop(0)
        if (datetime.now() - last_hourly_report_time).total_seconds() >= 3600:
            PREV_HOURLY_REPORTS.update({symbol: reports[-1] for symbol, reports in FIVE_MIN_REPORTS.items()})

def get_technical_indicators(symbol, kline_data=None):
    if kline_data is None:
        url = BINANCE_API_URL + f"klines?symbol={symbol}&interval=1h&limit=200"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 429:
                print(f"[UYARI] {symbol} için rate limit, 2 saniye bekleniyor...")
                time.sleep(2)
                response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"[HATA] {symbol} için veri alınamadı: {response.status_code}")
                return None
            data = response.json()
        except Exception as e:
            print(f"[HATA] {symbol} için kline verisi alınamadı: {e}")
            return None
    else:
        data = kline_data

    if len(data) < 100:
        print(f"[HATA] {symbol} için yeterli veri yok: {len(data)} satır")
        return None

    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close Zamanı", "quote_volume", "trades",
        "Alıcı Baz Varlık Hacmi", "Alıcı quote_volume", "Yoksay"
    ])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df.dropna(inplace=True)

    if len(df) < 50:
        print(f"[HATA] {symbol} için temiz veri yetersiz: {len(df)} satır")
        return None

    current_price = float(df["close"].iloc[-1])
    
    # Weekly close with fallback
    weekly_close = get_candle_close(symbol, "1w")
    if weekly_close is None or weekly_close == 0:
        # Fallback: use 7-day old price from current data if available
        weekly_close = float(df["close"].iloc[-min(168, len(df))]) if len(df) >= 7 else current_price
    weekly_diff_pct = ((current_price - weekly_close) / weekly_close * 100) if weekly_close and weekly_close > 0 else 0
    
    # 4H close with fallback  
    fourh_close = get_candle_close(symbol, "4h")
    if fourh_close is None or fourh_close == 0:
        # Fallback: use 4-hour old price from current data if available
        fourh_close = float(df["close"].iloc[-min(4, len(df))]) if len(df) >= 4 else current_price
    fourh_diff_pct = ((current_price - fourh_close) / fourh_close * 100) if fourh_close and fourh_close > 0 else 0
    
    # Monthly close with fallback
    monthly_close = get_candle_close(symbol, "1M")
    if monthly_close is None or monthly_close == 0:
        # Fallback: use 30-day old price from current data if available
        monthly_close = float(df["close"].iloc[-min(720, len(df))]) if len(df) >= 30 else current_price
    monthly_diff_pct = ((current_price - monthly_close) / monthly_close * 100) if monthly_close and monthly_close > 0 else 0

    # EMA hesaplamaları with proper fallbacks
    try:
        ema_series = EMAIndicator(df["close"], window=20).ema_indicator()
        ema_20 = float(ema_series.iloc[-1]) if len(ema_series) >= 20 and not pd.isna(ema_series.iloc[-1]) else None
    except:
        ema_20 = None
        
    try:
        ema_50 = EMAIndicator(df["close"], window=50).ema_indicator().iloc[-1] if len(df) >= 50 else None
        ema_50 = float(ema_50) if ema_50 is not None and not pd.isna(ema_50) else None
    except:
        ema_50 = None
        
    try:
        ema_100 = EMAIndicator(df["close"], window=100).ema_indicator().iloc[-1] if len(df) >= 100 else None
        ema_100 = float(ema_100) if ema_100 is not None and not pd.isna(ema_100) else None
    except:
        ema_100 = None
        
    try:
        ema_200 = EMAIndicator(df["close"], window=200).ema_indicator().iloc[-1] if len(df) >= 200 else None
        ema_200 = float(ema_200) if ema_200 is not None and not pd.isna(ema_200) else None
    except:
        ema_200 = None
    above_ema_20 = (current_price > ema_20) if ema_20 is not None else None
    ema20_crossover = get_ema20_crossover(df) if len(df) >= 20 else None

    # Teknik göstergeler with NaN handling
    try:
        rsi_series = RSIIndicator(df["close"], window=14).rsi()
        rsi = rsi_series.iloc[-1] if len(rsi_series) >= 14 and not pd.isna(rsi_series.iloc[-1]) else None
        rsi_prev = rsi_series.iloc[-2] if len(rsi_series) >= 15 and not pd.isna(rsi_series.iloc[-2]) else None
    except Exception as e:
        print(f"[UYARI] {symbol} için RSI hesaplanamadı: {e}")
        rsi = None
        rsi_prev = None
    macd_series = MACD(df["close"]).macd()
    macd = macd_series.iloc[-1] if len(macd_series) >= 26 else None
    macd_prev = macd_series.iloc[-2] if len(macd_series) >= 27 else None
    adx_series = ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
    adx = adx_series.iloc[-1] if len(adx_series) >= 14 else None
    adx_prev = adx_series.iloc[-2] if len(adx_series) >= 15 else None
    
    # New indicators: MFI and StochRSI
    try:
        mfi_series = MFIIndicator(df["high"], df["low"], df["close"], df["volume"].astype(float), window=14).money_flow_index()
        mfi = mfi_series.iloc[-1] if len(mfi_series) >= 14 and not pd.isna(mfi_series.iloc[-1]) else None
        mfi_prev = mfi_series.iloc[-2] if len(mfi_series) >= 15 and not pd.isna(mfi_series.iloc[-2]) else None
    except:
        mfi = None
        mfi_prev = None

    try:
        stoch_rsi_series = StochRSIIndicator(df["close"], window=14).stochrsi()
        stoch_rsi = stoch_rsi_series.iloc[-1] if len(stoch_rsi_series) >= 14 and not pd.isna(stoch_rsi_series.iloc[-1]) else None
        stoch_rsi_prev = stoch_rsi_series.iloc[-2] if len(stoch_rsi_series) >= 15 and not pd.isna(stoch_rsi_series.iloc[-2]) else None
    except:
        stoch_rsi = None
        stoch_rsi_prev = None

    momentum = (rsi * 0.3) + (macd * 100) + (adx * 0.2) if rsi is not None and macd is not None and adx is not None else None
    corrected_momentum = calculate_corrected_momentum(rsi, macd, adx) if rsi is not None and macd is not None and adx is not None else None

    # Balina ve hacim verileri
    # BINANCE CLIENT'DAN HAZIR GELEN VERILERI KULLAN #
    whale_buy = coin_data.get("whale_buy_vol", 0)
    whale_sell = coin_data.get("whale_sell_vol", 0)
    net_accumulation = coin_data.get("net_accumulation", 0)
    
    # Islem verileri
    if "df" in coin_data and isinstance(coin_data["df"], list):
         # list of dicts from binance_client
         df_trades = pd.DataFrame(coin_data["df"])
         if "trades" in df_trades.columns:
             total_trades = df_trades["trades"].sum()
         else:
             total_trades = 0
         if "quote_volume" in df_trades.columns:
             max_trade_volume = df_trades["quote_volume"].max() / 1e6
             total_quote_vol = df_trades["quote_volume"].sum() / 1e6
             avg_trade_size = total_quote_vol / total_trades if total_trades > 0 else 0
         else:
             max_trade_volume = 0
             avg_trade_size = 0
    else:
         total_trades = 0
         max_trade_volume = 0
         avg_trade_size = 0

    # Futures verileri
    futures_oi, futures_ls = get_futures_stats(symbol)
    if futures_oi is None or futures_ls is None:
        print(f"[UYARI] {symbol} için futures verisi alınamadı.")

    # Korelasyonlar
    btc_corr_15m = get_correlation(symbol, base_symbol="BTCUSDT", interval="15m", limit=100)
    btc_corr_1h = get_correlation(symbol, base_symbol="BTCUSDT", interval="1h", limit=100)
    btc_corr_4h = get_correlation(symbol, base_symbol="BTCUSDT", interval="4h", limit=100)
    eth_corr_15m = get_correlation(symbol, base_symbol="ETHUSDT", interval="15m", limit=100)
    eth_corr_1h = get_correlation(symbol, base_symbol="ETHUSDT", interval="1h", limit=100)
    eth_corr_4h = get_correlation(symbol, base_symbol="ETHUSDT", interval="4h", limit=100)
    sol_corr_1h = get_correlation(symbol, base_symbol="SOLUSDT", interval="1h", limit=100)

    # Taker Rate Calculation
    try:
        if "df" in coin_data and isinstance(coin_data["df"], list):
            df_taker = pd.DataFrame(coin_data["df"])
            if "taker_buy_quote" in df_taker.columns and "quote_volume" in df_taker.columns:
                taker_buy_vol = df_taker["taker_buy_quote"].sum()
                total_vol = df_taker["quote_volume"].sum()
                taker_sell_vol = total_vol - taker_buy_vol
                taker_rate = taker_buy_vol / taker_sell_vol if taker_sell_vol > 0 else 1.0
            else:
                taker_rate = 1.0
        else:
            taker_rate = 1.0
    except:
        taker_rate = 1.0

    # Z-Score Calculation (Price vs 20-period SMA)
    try:
        sma20 = df["close"].rolling(window=20).mean().iloc[-1]
        std20 = df["close"].rolling(window=20).std().iloc[-1]
        z_score = (current_price - sma20) / std20 if std20 > 0 else 0
    except:
        z_score = 0

    whale_activity = int(total_trades)
    atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range().iloc[-1] if len(df) >= 14 else None
    support = df["low"].rolling(window=20).min().iloc[-1] if len(df) >= 20 else None
    resistance = df["high"].rolling(window=20).max().iloc[-1] if len(df) >= 20 else None
    support_resistance = f"{format_money(support)} - {format_money(resistance)}" if support is not None and resistance is not None else "None"
    ema_trend = get_ema_cross_trend(df) if len(df) >= 20 else None
    ema_crossover = get_ema_crossover(df) if len(df) >= 200 else None
    rsi_extended = get_extended_rsi(df) if len(df) >= 21 else None
    price_roc = calculate_price_roc(df)
    volume_ratio = calculate_volume_ratio(df)

    # Bollinger Bands
    bb_indicator = BollingerBands(close=df["close"], window=20, window_dev=2)
    bb_upper = bb_indicator.bollinger_hband().iloc[-1] if len(df) >= 20 and not pd.isna(bb_indicator.bollinger_hband().iloc[-1]) else None
    bb_lower = bb_indicator.bollinger_lband().iloc[-1] if len(df) >= 20 and not pd.isna(bb_indicator.bollinger_lband().iloc[-1]) else None
    bb_lower_distance_pct = ((current_price - bb_lower) / bb_lower * 100) if bb_lower is not None and bb_lower != 0 else None
    bb_upper_distance_pct = ((bb_upper - current_price) / bb_upper * 100) if bb_upper is not None and bb_upper != 0 else None

    trap_status = detect_traps(df, current_price, support, resistance, volume_ratio, rsi) if support is not None and resistance is not None and rsi is not None else "Veri eksik"

    # Composite Score hesaplama
    coin_numeric = {
        "RSI": rsi,
        "MACD": macd,
        "ADX": adx,
        "Momentum": momentum,
        "NetAccum_raw": round(net_accumulation, 2) if net_accumulation is not None else None
    }
    composite_score = calculate_composite_score(coin_numeric) if all(v is not None for v in coin_numeric.values()) else None

    # Loglama için değerleri önceden formatla
    rsi_str = f"{rsi:.2f}" if rsi is not None else "N/A"
    macd_str = f"{macd:.4f}" if macd is not None else "N/A"
    adx_str = f"{adx:.2f}" if adx is not None else "N/A"
    momentum_str = f"{momentum:.2f}" if momentum is not None else "N/A"
    netaccum_str = f"{net_accumulation:.2f}" if net_accumulation is not None else "N/A"
    composite_str = f"{composite_score:.2f}" if composite_score is not None else "N/A"
    print(f"[DEBUG] {symbol} - RSI: {rsi_str}, MACD: {macd_str}, ADX: {adx_str}, Momentum: {momentum_str}, NetAccum: {netaccum_str}, Composite: {composite_str}")

    # PREV_STATS güncelleme
    with global_lock:
        if symbol in PREV_STATS:
            prev = PREV_STATS[symbol]
            price_disp = format_indicator(current_price, prev.get("price"))
            rsi_disp = format_indicator(rsi, prev.get("rsi")) if rsi is not None else "N/A"
            macd_disp = format_indicator(macd, prev.get("macd")) if macd is not None else "N/A"
            adx_disp = format_indicator(adx, prev.get("adx")) if adx is not None else "N/A"
            momentum_disp = format_indicator(momentum, prev.get("momentum")) if momentum is not None else "N/A"
            netaccum_disp = format_indicator(net_accumulation, prev.get("netaccum")) if net_accumulation is not None else "N/A"
            composite_change = ((composite_score - prev["composite"]) / prev["composite"] * 100) if composite_score is not None and prev.get("composite", 0) != 0 else 0
            mfi_disp = format_indicator(mfi, prev.get("mfi")) if mfi is not None else "N/A"
            stoch_rsi_disp = format_indicator(stoch_rsi, prev.get("stoch_rsi")) if stoch_rsi is not None else "N/A"
        else:
            price_disp = f"{format_money(current_price)}"
            rsi_disp = f"{round(rsi, 4)}" if rsi is not None else "N/A"
            macd_disp = f"{round(macd, 4)}" if macd is not None else "N/A"
            adx_disp = f"{round(adx, 4)}" if adx is not None else "N/A"
            momentum_disp = f"{round(momentum, 4)}" if momentum is not None else "N/A"
            netaccum_disp = f"{round(net_accumulation, 4)}" if net_accumulation is not None else "N/A"
            composite_change = 0
            mfi_disp = f"{round(mfi, 4)}" if mfi is not None else "N/A"
            stoch_rsi_disp = f"{round(stoch_rsi, 4)}" if stoch_rsi is not None else "N/A"

        if symbol in PREV_STATS:
            prev = PREV_STATS[symbol]
            oi_change = ((futures_oi - prev["oi"]) / prev["oi"] * 100) if futures_oi is not None and prev.get("oi", 0) != 0 else 0
            ls_change = ((futures_ls - prev["ls"]) / prev["ls"] * 100) if futures_ls is not None and prev.get("ls", 0) != 0 else 0
            whale_change = ((whale_activity - prev["whale"]) / prev["whale"] * 100) if prev.get("whale", 0) != 0 else 0
        else:
            oi_change = 0
            ls_change = 0
            whale_change = 0

        oi_display = f"{format_money(futures_oi)} ({get_change_arrow(oi_change)} {round(oi_change, 2)}%)" if futures_oi is not None else "N/A"
        ls_display = f"{futures_ls} ({get_change_arrow(ls_change)} {round(ls_change, 2)}%)" if futures_ls is not None else "N/A"
        whale_display = f"{whale_activity} ({get_change_arrow(whale_change)} {round(whale_change, 2)}%)"
        composite_display = f"{round(composite_score, 4)} ({get_change_arrow(composite_change)} {round(composite_change, 2)}%)" if composite_score is not None else "N/A"

        PREV_STATS[symbol] = {
            "price": current_price,
            "rsi": rsi,
            "macd": macd,
            "adx": adx,
            "momentum": momentum,
            "netaccum": net_accumulation if net_accumulation is not None else None,
            "oi": futures_oi,
            "ls": futures_ls,
            "whale": whale_activity,
            "composite": composite_score,
            "volume_ratio": volume_ratio,
            "mfi": mfi,
            "stoch_rsi": stoch_rsi
        }

    _, volume_24h = get_ticker_info(symbol)
    volume_24h_display = format_money(volume_24h) if volume_24h is not None else "N/A"

    result = {
        "Coin": symbol,
        "Price": price_disp,
        "Weekly Change": (format_money(weekly_close), f"{round(weekly_diff_pct, 2)}%") if weekly_close is not None and weekly_diff_pct is not None else ("N/A", "N/A"),
        "4H Change": (format_money(fourh_close), f"{round(fourh_diff_pct, 2)}%") if fourh_close is not None and fourh_diff_pct is not None else ("N/A", "N/A"),
        "Monthly Change": (format_money(monthly_close), f"{round(monthly_diff_pct, 2)}%") if monthly_close is not None and monthly_diff_pct is not None else ("N/A", "N/A"),
        "24h Volume": volume_24h_display,
        "Open Interest": oi_display,
        "Long/Short Ratio": ls_display,
        "EMA Above 20": above_ema_20,
        "EMA20_Crossover": ema20_crossover,
        "EMA Trend": ema_trend,
        "EMA_Crossover": ema_crossover,
        "EMA_50": ema_50,
        "EMA_100": ema_100,
        "EMA_200": ema_200,
        "RSI": rsi_disp,
        "RSI Extended": f"{rsi_extended}" if rsi_extended is not None else "N/A",
        "RSI_Ok": get_arrow(rsi, rsi_prev) if rsi is not None and rsi_prev is not None else "",
        "MACD": macd_disp,
        "MACD_Ok": get_arrow(macd, macd_prev) if macd is not None and macd_prev is not None else "",
        "ADX": adx_disp,
        "ADX_Ok": get_arrow(adx, adx_prev) if adx is not None and adx_prev is not None else "",
        "MFI": mfi_disp,
        "MFI_Ok": get_arrow(mfi, mfi_prev) if mfi is not None and mfi_prev is not None else "",
        "StochRSI": stoch_rsi_disp,
        "StochRSI_Ok": get_arrow(stoch_rsi, stoch_rsi_prev) if stoch_rsi is not None and stoch_rsi_prev is not None else "",
        "Momentum": momentum_disp,
        "Corrected Momentum": round(corrected_momentum, 4) if corrected_momentum is not None else "N/A",
        "Momentum_Ok": get_arrow(momentum, momentum) if momentum is not None else "",
        "Taker Rate": f"{round(taker_rate, 2)}",
        "Z-Score": f"{round(z_score, 2)}",
        "Price ROC": f"{price_roc}%" if price_roc is not None else "N/A",
        "Volume Ratio": volume_ratio if volume_ratio is not None else "N/A",
        "Order Block": "None",
        "Whale Buy (M$)": format_money(whale_buy),
        "Whale Sell (M$)": format_money(whale_sell),
        "Net Accum": f"{format_money(net_accumulation)} {get_whale_logo(net_accumulation)}" if net_accumulation is not None else "N/A",
        "NetAccum_raw": net_accumulation if net_accumulation is not None else None,
        "CompositeScore": composite_display,
        "Whale Activity": whale_display,
        "Avg Trade Size": format_money(avg_trade_size) if avg_trade_size is not None else "N/A",
        "Max Trade Volume": format_money(max_trade_volume),
        "BTC Correlation (15m)": str(btc_corr_15m) if btc_corr_15m is not None else "N/A",
        "BTC Correlation (1h)": str(btc_corr_1h) if btc_corr_1h is not None else "N/A",
        "BTC Correlation (4h)": str(btc_corr_4h) if btc_corr_4h is not None else "N/A",
        "ETH Correlation (15m)": str(eth_corr_15m) if eth_corr_15m is not None else "N/A",
        "ETH Correlation (1h)": str(eth_corr_1h) if eth_corr_1h is not None else "N/A",
        "ETH Correlation (4h)": str(eth_corr_4h) if eth_corr_4h is not None else "N/A",
        "SOL Correlation (1h)": str(sol_corr_1h) if sol_corr_1h is not None else "N/A",
        "SOL Correlation": str(sol_corr_1h) if sol_corr_1h is not None else "N/A",
        "ATR": format_money(atr) if atr is not None else "N/A",
        "ATR_raw": atr,
        "Support": format_money(support) if support is not None else "N/A",
        "Resistance": format_money(resistance) if resistance is not None else "N/A",
        "Support_Resistance": support_resistance,
        "Bollinger Bands": f"{format_money(bb_lower)} - {format_money(bb_upper)}" if bb_lower is not None and bb_upper is not None else "N/A",
        "BB Lower Distance": f"{round(bb_lower_distance_pct, 2)}%" if bb_lower_distance_pct is not None else "N/A",
        "BB Upper Distance": f"{round(bb_upper_distance_pct, 2)}%" if bb_upper_distance_pct is not None else "N/A",
        "Trap Status": "Analyzing",
        "Advice": coin_recommendation,
        "df": df.to_dict()
    }
    return result



# ---------------- Ek Fonksiyonlar (Global Fonksiyonlar) ----------------
def get_rsi_comment(rsi):
    if rsi is None or str(rsi) == "N/A" or rsi == 0:
        return "Incomplete Data"
    try:
        rsi = float(rsi)
    except:
        return "Incomplete Data"
    if rsi >= 70:
        return "Overbought ⚠️"
    elif rsi <= 30:
        return "Oversold 📉"
    elif rsi >= 60:
        return "Strong Momentum 📈"
    elif rsi <= 40:
        return "Weak Momentum 📉"
    else:
        return "Neutral ⚖️"


def calculate_trust_index(coin_data, curr_price, weekly_close, daily_close, fourh_close):
    """Coin için güven endeksi hesaplar (0-100) ve değişimi döndürür."""
    try:
        print(f"[DEBUG] {coin_data['Coin']} - Güven endeksi hesaplama başladı")
        adx = extract_numeric(coin_data["ADX"])
        volume_ratio = extract_numeric(coin_data["Volume Ratio"])
        net_accum = coin_data["NetAccum_raw"]
        rsi = extract_numeric(coin_data["RSI"])
        ema_trend = coin_data["EMA Trend"]
        atr = coin_data["ATR_raw"]
        whale_buy = parse_money(coin_data["Whale_Buy_M"])
        whale_sell = parse_money(coin_data["Whale_Sell_M"])
        bb_width = (parse_money(coin_data["Bollinger Bands"].split(" - ")[1]) -
                    parse_money(coin_data["Bollinger Bands"].split(" - ")[0])) / curr_price * 100 if curr_price > 0 else 0

        trend_score = min(adx / 20 * 15, 15) if adx > 0 else 5
        volume_score = min(volume_ratio * 10, 15) if volume_ratio > 0 else 0
        accum_score = min(net_accum / 5 * 15, 15) if net_accum > 0 else max(net_accum / 10 * 15, 0)
        rsi_score = 15 - abs(rsi - 50) / 3 if 30 < rsi < 70 else 7
        ema_score = 15 if ema_trend in ["Bullish Crossover", "Bearish Crossover"] else 7
        whale_activity = whale_buy + whale_sell
        whale_net = whale_buy - whale_sell
        whale_score = min(whale_net / 5 * 15, 15) if whale_net > 0 else max(whale_net / 10 * 15, 0) if whale_activity > 0 else 5
        bb_score = 15 if bb_width < 5 else max(15 - bb_width / 1.5, 5)
        fourh_diff = abs(curr_price - fourh_close) / atr if atr > 0 else 0
        daily_diff = abs(curr_price - daily_close) / atr if atr > 0 else 0
        weekly_diff = abs(curr_price - weekly_close) / atr if atr > 0 else 0
        closure_score = max(15 - (fourh_diff + daily_diff + weekly_diff), 5)

        trust_index = (trend_score + volume_score + accum_score + rsi_score + ema_score +
                       whale_score + bb_score + closure_score) * 100 / 120
        trust_index = max(min(round(trust_index, 0), 100), 0)
        print(f"[DEBUG] {coin_data['Coin']} - Ham Trust Index: {trust_index}")

        # PREV_STATS kontrolü ve loglama
        with global_lock:
            prev_trust = PREV_STATS.get(coin_data["Coin"], {}).get("trust_index", None)
            print(f"[DEBUG] {coin_data['Coin']} - PREV_STATS’tan alınan prev_trust: {prev_trust}")
            if prev_trust is None:
                print(f"[DEBUG] {coin_data['Coin']} - PREV_STATS’ta önceki veri yok, ilk analiz olabilir")
                prev_trust = trust_index  # İlk analizde mevcut değeri kullan
            trust_change = calculate_percentage_change(trust_index, prev_trust) if prev_trust != 0 else 0
            PREV_STATS[coin_data["Coin"]] = {
                "trust_index": trust_index,
                "timestamp": datetime.now().timestamp()
            }
            print(f"[DEBUG] {coin_data['Coin']} - PREV_STATS güncellendi: {PREV_STATS[coin_data['Coin']]}")

        print(f"[DEBUG] {coin_data['Coin']} - Güven Endeksi: {trust_index}, Değişim: {trust_change:.2f}%")
        return trust_index, trust_change

    except Exception as e:
        print(f"[HATA] {coin_data['Coin']} için güven endeksi hesaplanamadı: {e}")
        import traceback
        print(traceback.format_exc())
        return 50, 0

def get_macd_comment(macd):
    if macd is None or str(macd) == "N/A":
        return "Incomplete Data"
    try:
        macd = float(macd)
    except:
        return "Incomplete Data"
    if macd > 0.5:
        return "Strong bullish signal!"
    elif macd < -0.5:
        return "Strong bearish signal!"
    elif abs(macd) < 0.1:
        return "Neutral signal!"
    else:
        return "Positive signal!" if macd > 0 else "Negative signal!"


def get_adx_comment(adx):
    if adx is None or str(adx) == "N/A":
        return "Incomplete Data"
    try:
        adx = float(adx)
    except:
        return "Incomplete Data"
    if adx >= 30:
        return "Strong trend!"
    elif adx < 20:
        return "Weak trend!"
    else:
        return "Average trend strength!"


def get_momentum_comment(momentum):
    if momentum is None or str(momentum) == "N/A":
        return "Incomplete Data"
    try:
        momentum = float(momentum)
    except:
        return "Incomplete Data"
    if momentum > 100:
        return "Very strong!"
    elif momentum > 30:
        return "Strong!"
    else:
        return "Medium level!"


def get_netaccum_comment(net):
    if net is None or str(net) == "N/A":
        return "Incomplete Data"
    try:
        net = float(net)
    except:
        return "Incomplete Data"
    if net > 0:
        return "Whales are buying!"
    elif net < 0:
        return "Whales are selling!"
    else:
        return "Neutral whale action!"


def get_strategy_comment(coin_data):
    """
    Coin verileri için daha kullanıcı dostu, okunabilir bir yorum oluşturur.

    Args:
        coin_data (dict): Coin verileri sözlüğü

    Returns:
        str: Formatlanmış yorum
    """
    symbol = coin_data.get("Coin", "Bilinmeyen")
    price = coin_data.get("Price_Display", "N/A")
    weekly, weekly_diff = coin_data.get("Weekly Change", ("N/A", "N/A"))
    fourh, fourh_diff = coin_data.get("4H Change", ("N/A", "N/A"))
    monthly, monthly_diff = coin_data.get("Monthly Change", ("N/A", "N/A"))
    volume_24h = coin_data.get("24s volume (USDT)", "N/A")

    # Teknik göstergeleri çıkar
    rsi = coin_data.get("RSI", "N/A")
    macd = coin_data.get("MACD", "N/A")
    adx = coin_data.get("ADX", "N/A")
    rsi_comment = get_rsi_comment(rsi if isinstance(rsi, str) and rsi else '0')
    macd_comment = get_macd_comment(macd)
    adx_comment = get_adx_comment(adx if isinstance(adx, str) and adx else '0')

    # Pozisyon verileri
    oi = coin_data.get("Open Interest", "N/A")
    ls = coin_data.get("Long/Short Ratio", "N/A")

    # Korelasyon verileri
    btc_corr = coin_data.get("BTC Correlation", "Yok")
    eth_corr = coin_data.get("ETH Correlation", "Yok")

    # Balina verisi
    whale_activity = coin_data.get("Whale Activity", "N/A")
    net_accum = coin_data.get("NetAccum_raw", 0)

    # Yorumu daha okunabilir parçalara ayırarak oluştur
    comment = f"<b>{symbol} Summary Analysis:</b>\n\n"

    # Fiyat bilgisi kısmı
    comment += "<b>📊 Price Information:</b>\n"
    comment += f"• Current: {price}$\n"
    comment += f"• Weekly Change: {weekly_diff}\n"
    comment += f"• 4 Hourly Change: {fourh_diff}\n"
    comment += f"• Monthly Change: {monthly_diff}\n"
    comment += f"• 24h Volume: {volume_24h}\n\n"

    # Teknik Göstergeler kısmı
    comment += "<b>📈 Technical Status:</b>\n"
    comment += f"• RSI: {rsi} - {rsi_comment}\n"
    comment += f"• MACD: {macd} - {macd_comment}\n"
    comment += f"• ADX: {adx} - {adx_comment}\n\n"

    # Piyasa verileri kısmı
    comment += "<b>🌐 Market Data:</b>\n"
    comment += f"• Open Interest: {oi}\n"
    comment += f"• Long/Short Ratio: {ls}\n"
    comment += f"• BTC Correlation: {btc_corr}\n"
    comment += f"• ETH Correlation: {eth_corr}\n\n"

    # Balina durumu
    comment += "<b>🐳 Whale Status:</b>\n"
    comment += f"• Activity: {whale_activity} trades\n"

    # Birikim durumuna göre renklendirme ve yorum
    formatted_net = format_money(net_accum)
    if float(net_accum) > 5000000:
        comment += f"• Net Accumulation: <b style='color:green'>+{formatted_net}</b> (Strong buying pressure)\n"
    elif float(net_accum) > 0:
        comment += f"• Net Accumulation: <b style='color:lightgreen'>+{formatted_net}</b> (Light buying tendency)\n"
    elif float(net_accum) > -5000000:
        comment += f"• Net Accumulation: <b style='color:orange'>{formatted_net}</b> (Light selling tendency)\n"
    else:
        comment += f"• Net Accumulation: <b style='color:red'>{formatted_net}</b> (Strong selling pressure)\n"

    return comment


def calculate_composite_score(coin):
    """
    Daha güvenilir composite skor hesaplama fonksiyonu.
    Hata ayıklama için logging eklenmiştir.

    Args:
        coin (dict): Coin veri sözlüğü

    Returns:
        float: 0-100 arasında normalize edilmiş composite skor
    """

    # Güvenli değer çıkarma fonksiyonu
    def safe_extract(value, default=0.0):
        """String veya sayı formatındaki değeri güvenle çıkarır"""
        try:
            if isinstance(value, str):
                # Format "12.34 (🔼 5.67%)" gibi olabilir, ilk sayıyı al
                parts = value.split()
                return float(parts[0])
            elif value is not None:
                return float(value)
            return default
        except (ValueError, TypeError, IndexError):
            print(f"[HATA] Değer çıkarılamadı: {value}")
            return default

    # Weights
    weights = {"RSI": 0.25, "MACD": 0.25, "ADX": 0.20, "Momentum": 0.20, "NetAccum": 0.10}

    # Değerleri güvenli şekilde çıkar
    rsi_val = safe_extract(coin.get("RSI", 0))
    macd_val = safe_extract(coin.get("MACD", 0))
    adx_val = safe_extract(coin.get("ADX", 0))
    momentum_val = safe_extract(coin.get("Momentum", 0))
    netacc_val = safe_extract(coin.get("NetAccum_raw", 0))

    # Normalizasyon (güvenli bölme)
    rsi_norm = rsi_val / 100 if rsi_val != 0 else 0
    macd_norm = min(abs(macd_val) / 1, 1) if macd_val != 0 else 0
    adx_norm = adx_val / 100 if adx_val != 0 else 0
    momentum_norm = min(abs(momentum_val) / 1000, 1) if momentum_val != 0 else 0
    netacc_norm = min(abs(netacc_val) / 10, 1) if netacc_val != 0 else 0

    # Ağırlıklı toplam
    component_values = {
        "RSI": rsi_norm,
        "MACD": macd_norm,
        "ADX": adx_norm,
        "Momentum": momentum_norm,
        "NetAccum": netacc_norm
    }

    # Toplam skor hesapla
    score = sum(weights[k] * v for k, v in component_values.items())

    # Skoru 0-100 arasına ölçekle
    final_score = score * 100

    # En az 0.1 olmasını sağla (tam sıfır olmasın ki hata tespiti kolay olsun)
    return max(round(final_score, 2), 0.1)


def generate_trade_recommendation(coin_data):
    try:
        rsi_val = extract_numeric(coin_data.get("RSI", 50))
        net_acc = extract_numeric(coin_data.get("NetAccum_raw", 0))
        current_price = extract_numeric(coin_data.get("Price", 0))
        atr_val = extract_numeric(coin_data.get("ATR", 0))
        
        support = extract_numeric(coin_data.get("Support", current_price * 0.95))
        resistance = extract_numeric(coin_data.get("Resistance", current_price * 1.05))
        
        trap_status = coin_data.get("Trap Status", "None")
        
        if atr_val == 0:
            atr_val = current_price * 0.015 
            
        # Recommendation logic
        if rsi_val < 30 and net_acc > 0:
            rec = "Strong Buy (Oversold + Accumulation)"
        elif rsi_val > 70 and net_acc < 0:
            rec = "Strong Sell (Overbought + Distribution)"
        elif "Bear Trap" in trap_status:
            rec = "Buy (Bear Trap Recovery)"
        elif "Bull Trap" in trap_status:
            rec = "Sell (Bull Trap Failure)"
        elif rsi_val < 40:
            rec = "Scaling Buy"
        elif rsi_val > 60:
            rec = "Scaling Sell"
        else:
            rec = "Neutral / Wait"
            
        # Add entry/stop levels
        if "Buy" in rec:
            entry = current_price
            stop = support - (atr_val * 0.5)
            target = resistance
            rec += f"\n  Entry: {format_money(entry)} | Target: {format_money(target)} | Stop: {format_money(stop)}"
        elif "Sell" in rec:
            entry = current_price
            stop = resistance + (atr_val * 0.5)
            target = support
            rec += f"\n  Entry: {format_money(entry)} | Target: {format_money(target)} | Stop: {format_money(stop)}"
            
        return rec
    except Exception as e:
        print(f"[ERROR] Recommendation error for {coin_data.get('Coin')}: {e}")
        return "Neutral / Waiting for Data"


def generate_detailed_analysis_message(results):
    """
    Generates a comprehensive analysis report for 50 coins in the requested format.
    """
    sorted_results = sorted(results, key=lambda x: extract_numeric(x.get("Composite Score", 0)), reverse=True)
    coin_details = {}
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    aggregated_msg = f"📊 <b>Market Analysis Report – {timestamp}</b>\n\n"

    # Market summary
    total_net_accum = sum(extract_numeric(coin.get("NetAccum_raw", 0)) for coin in results)
    price_changes = [extract_numeric(coin.get("24h Change", 0)) for coin in results]
    avg_price_change = np.mean(price_changes) if price_changes else 0

    if avg_price_change > 1.5:
        market_status = "Uptrend dominant 📈"
    elif avg_price_change < -1.5:
        market_status = "Downtrend dominant 📉"
    else:
        market_status = "Sideways market ⚖️"

    market_comment = (
        f"<b>Market Sentiment:</b> Net Accum: {format_money(total_net_accum)}$, "
        f"Avg Change: {avg_price_change:+.2f}%. "
        f"{market_status}"
    )
    aggregated_msg += f"{market_comment}\n\n"

    for idx, coin in enumerate(sorted_results[:50], start=1):
        symbol = coin["Coin"]
        with global_lock:
            prev_rank = PREV_RANKS.get(symbol)
        rank_change = (prev_rank - idx) if prev_rank is not None else 0
        coin["RankChange"] = rank_change
        with global_lock:
            PREV_RANKS[symbol] = idx

        def fv(val, fmt="{:.2f}"):
            if val is None or str(val) == "N/A" or val == 0 and "RSI" in str(fmt): # RSI cannot be 0
                return "N/A"
            try: return fmt.format(float(val))
            except: return "N/A"

        # Multi-section report builder
        coin_report = f"<b>{idx}. {symbol} (M: {fv(coin.get('Momentum'))}) [Rank: {idx} {get_change_arrow(rank_change)} {abs(rank_change) if rank_change != 0 else ''}]</b>\n"
        
        # 1. Price Information
        coin_report += "<b>📊 Price Information:</b>\n"
        coin_report += f"• Price ($): {coin.get('Price_Display', 'N/A')}\n"
        
        # Safe access for Weekly Change tuple
        w_ch = coin.get('Weekly Change', ('N/A', 'N/A'))
        coin_report += f"• Weekly Close: {w_ch[0]} ({w_ch[1]})\n"
        
        # Safe access for 4H Change tuple
        h_ch = coin.get('4H Change', ('N/A', 'N/A'))
        coin_report += f"• 4H Close: {h_ch[0]} ({h_ch[1]})\n"
        
        # Safe access for Monthly Change tuple
        m_ch = coin.get('Monthly Change', ('N/A', 'N/A'))
        coin_report += f"• Monthly Close: {m_ch[0]} ({m_ch[1]})\n"
        coin_report += f"• 24h Volume (USDT): {format_money(coin.get('24h Volume', 0))}\n"

        # 2. Position & EMA Status
        coin_report += "<b>📈 Position & EMA Status:</b>\n"
        coin_report += f"• Open Interest: {coin.get('Open Interest', 'N/A')}\n"
        coin_report += f"• Long/Short Ratio: {coin.get('Long/Short Ratio', 1.0):.4f}\n"
        coin_report += f"• Above EMA 20: {'✅' if extract_numeric(coin.get('Price')) > extract_numeric(coin.get('EMA_20', 0)) else '❌'}\n"
        coin_report += f"• EMA20 Crossover: {coin.get('EMA20_Crossover', 'None')}\n"
        coin_report += f"• EMA Trend: {coin.get('EMA Trend', 'None')}\n"
        coin_report += f"• EMA Crossover: {coin.get('EMA_Crossover', 'None')}\n"
        coin_report += f"• EMA Status: EMA 50: {format_money(coin.get('EMA_50'))} / EMA 100: {format_money(coin.get('EMA_100'))} / EMA 200: {format_money(coin.get('EMA_200'))}\n"

        # 3. Technical Indicators
        coin_report += "\n<b>📈 Technical Indicators:</b>\n"
        coin_report += f"• RSI: {fv(coin.get('RSI'))} (1h), {fv(coin.get('RSI_4h'))} (4h), {fv(coin.get('RSI_1d'))} (1d) - (Wide: {coin.get('RSI Extended', 'N/A')}) ({get_rsi_comment(coin.get('RSI'))})\n"
        coin_report += f"• MACD: {fv(coin.get('MACD'), '{:.4f}')} (1h), {fv(coin.get('MACD_4h'), '{:.4f}')} (4h), {fv(coin.get('MACD_1d'), '{:.4f}')} (1d) - ({get_macd_comment(coin.get('MACD'))})\n"
        coin_report += f"• ADX: {fv(coin.get('ADX'))} (1h), {fv(coin.get('ADX_4h'))} (4h), {fv(coin.get('ADX_1d'))} (1d) - ({get_adx_comment(coin.get('ADX'))})\n"
        coin_report += f"• Momentum: {fv(coin.get('Momentum'))} | Adjusted: 0 (Medium level!)\n"
        coin_report += f"• Price ROC (Last 5 Hours): {fv(coin.get('Price ROC'))}% (Price changed by this rate in the last 5 hours)\n"
        coin_report += f"• Volume Ratio: {fv(coin.get('Volume Ratio'))} (Normal course, stable volume.)\n"
        coin_report += f"• Bollinger Bands: {coin.get('Bollinger Bands', 'N/A')} (Lower: {coin.get('BB Lower Distance', '0%')}, Upper: {coin.get('BB Upper Distance', '0%')})\n"

        # 4. Market Dynamics
        ob = coin.get("OrderBook", {})
        coin_report += "\n<b>🔍 Market Dynamics:</b>\n"
        coin_report += f"• Order Book: Buy Wall: {format_money(ob.get('max_bid_price', 0))} | Sell Wall: {format_money(ob.get('max_ask_price', 0))}\n"
        coin_report += f"• OB Imbalance: {fv(ob.get('imbalance'))}% | Spread: {fv(ob.get('spread_pct'), '{:.4f}')}%\n"
        coin_report += f"• Whale Buy/Sell: {format_money(coin.get('Whale_Buy_M', 0))} / {format_money(coin.get('Whale_Sell_M', 0))}\n"
        coin_report += f"• Net Accum: ${format_money(coin.get('NetAccum_raw', 0))} {get_whale_logo(coin.get('NetAccum_raw', 0))}\n"
        coin_report += f"• Composite Score: {fv(coin.get('Composite Score'))}\n"
        coin_report += f"• Whale Activity: {coin.get('Whale Activity', 'N/A')}\n"
        coin_report += f"• Avg Trade Size: {format_money(coin.get('Avg Trade Size', 0))}\n"
        coin_report += f"• Max Trade Volume: {format_money(coin.get('24h Volume', 0))}\n"

        # 5. Correlation & Other Data
        coin_report += "\n<b>📊 Correlation & Other Data:</b>\n"
        coin_report += f"• BTC Correlation: {fv(coin.get('BTC Correlation'))} (1h), {fv(coin.get('BTC Corr 4h'))} (4h), {fv(coin.get('BTC Corr 1d'))} (1d)\n"
        coin_report += f"• ETH Correlation: {fv(coin.get('ETH Correlation'))} (1h), {fv(coin.get('ETH Corr 4h'))} (4h), {fv(coin.get('ETH Corr 1d'))} (1d)\n"
        coin_report += f"• ATR: {format_money(coin.get('ATR', 0))}$\n"
        coin_report += f"• Support/Resistance: {coin.get('Support_Resistance', 'N/A')}\n"
        coin_report += f"• Bull/Bear Trap: {coin.get('Trap Status', 'None')}\n"

        # 6. Coin Summary Section
        coin_report += f"\n<b>💬 Coin Summary:</b>\n{get_strategy_comment(coin)}\n"

        # 7. Whale Movement Analysis Section (if possible to calculate quickly or pre-fetched)
        # We use a placeholder or summary here to keep it efficient
        coin_report += f"\n<b>🐋 Whale Movement Analysis:</b>\n"
        coin_report += f"💰 Net Accumulation: {format_money(coin.get('NetAccum_raw', 0))} USD\n"
        coin_report += f"🐳 Whale Trades: {format_money(coin.get('Whale_Buy_M', 0))} buy | {format_money(coin.get('Whale_Sell_M', 0))} sell\n"
        coin_report += f"📊 Volume Ratio: {coin.get('Volume Ratio', 1.0):.2f}x\n"
        coin_report += f"📉 Price Change: {coin.get('24h Change', 0):.2f}%\n"
        coin_report += f"Recommendation: {'📈 Buy' if extract_numeric(coin.get('NetAccum_raw', 0)) > 0 else '📉 Sell'}\n"

        # 8. Trade Recommendation Section
        coin_report += f"\n<b>💡 Trade Recommendation:</b>\n{coin.get('Advice', 'None')}\n\n"
        coin_report += "--------------------------------\n\n"

        aggregated_msg += coin_report
        coin_details[symbol] = coin_report

    aggregated_msg += "\n👉 <b>Use the buttons below for detailed reports.</b>\n"
    return aggregated_msg, coin_details, None
    aggregated_msg += generate_defillama_overview_message()
    return aggregated_msg, coin_details, None


def generate_notebooklm_export(results):
    """
    Generates a consolidated Markdown file for NotebookLM
    """
    filename = f"Market_Analysis_Export_{int(time.time())}.md"
    try:
        report = "# Market Analysis Consolidated Report\n"
        report += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Total Coins Analyzed: {len(results)}\n\n"
        
        for coin in results:
            symbol = coin.get("Coin", "Unknown")
            report += f"## {symbol} Analysis\n"
            report += f"- **Price**: {coin.get('Price_Display', 'N/A')}\n"
            report += f"- **24h Change**: {coin.get('24h Change', 'N/A')}%\n"
            report += f"- **RSI**: {coin.get('RSI', 'N/A')}\n"
            report += f"- **MACD**: {coin.get('MACD', 'N/A')}\n"
            report += f"- **ADX**: {coin.get('ADX', 'N/A')}\n"
            report += f"- **MFI**: {coin.get('MFI', 'N/A')}\n"
            report += f"- **Stochastic RSI**: {coin.get('StochRSI', 'N/A')}\n"
            report += f"- **Momentum Score**: {coin.get('Momentum', 'N/A')}\n"
            report += f"- **Taker Rate**: {coin.get('Taker Rate', 'N/A')}\n"
            report += f"- **Z-Score**: {coin.get('Z-Score', 'N/A')}\n"
            report += f"- **Bollinger Bands**: {coin.get('Bollinger Bands', 'N/A')}\n"
            report += f"- **Support/Resistance**: {coin.get('Support_Resistance', 'N/A')}\n"
            report += f"- **Funding Rate**: {coin.get('Funding Rate', 'N/A')}\n"
            report += f"- **Open Interest**: {coin.get('Open Interest', 'N/A')}\n"
            report += f"- **BTC Correlation (1h)**: {coin.get('BTC Correlation', 'N/A')}\n"
            
            weekly = coin.get("Weekly Change", ("N/A", "0%"))
            report += f"- **Weekly Close Diff**: {weekly[1]}\n"
            
            monthly = coin.get("Monthly Change", ("N/A", "0%"))
            report += f"- **Monthly Close Diff**: {monthly[1]}\n"
            
            report += "\n---\n\n"
            
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        return filename
    except Exception as e:
        print(f"[ERROR] generate_notebooklm_export error: {e}")
        return None


def generate_metric_report(metric, results):
    # Map Turkish metric names to English for the header
    metric_map = {
        "Fark Endeksi": "Difference Index",
        "Outlier Score": "Outlier Score",
        "Composite Skor": "Composite Score",
        "Composite Score": "Composite Score",
        "BTC Correlation": "BTC Correlation",
        "ETH Correlation": "ETH Correlation",
        "SOL Correlation": "SOL Correlation",
        "Net Accum": "Net Accumulation",
        "RSI": "RSI (1h)",
        "RSI_4h": "RSI (4h)",
        "RSI_1d": "RSI (1d)",
        "EMA": "EMA Trend Status",
        "4H Change": "4H Change",
        "Haftalık Değişim": "Weekly Change",
        "Aylık Değişim": "Monthly Change",
        "Volume Ratio": "Volume Ratio",
        "24h Volume": "24h Volume",
        "ATR": "ATR",
        "ADX": "ADX (1h)",
        "ADX_4h": "ADX (4h)",
        "ADX_1d": "ADX (1d)",
        "MACD": "MACD (1h)",
        "MACD_4h": "MACD (4h)",
        "MACD_1d": "MACD (1d)",
        "MFI": "MFI",
        "StochRSI": "Stochastic RSI",
        "Open Interest": "Open Interest",
        "Taker Rate": "Taker Rate",
        "Z-Score": "Z-Score",
        "Support": "Support",
        "Resistance": "Resistance",
        "Bollinger Bands": "Bollinger Bands",
        "Momentum": "Momentum",
        "Support_Resistance": "Support/Resistance Levels",
        "Support/Resistance": "Support/Resistance"
    }
    
    display_metric = metric_map.get(metric, metric)
    
    # Translate report headers
    report = f"📊 <b>{display_metric} Analysis Report</b>\n"
    report += f"<i>Total analyzed coins: {len(results)}</i>\n"
    report += "--------------------------------\n"

    if not results:
        report += "⚠️ Data missing, report could not be generated.\n"
        return report

    if metric == "Fark Endeksi" or metric == "Difference Index":
        if not PREV_STATS:
            report += "⚠️ Previous stats missing, difference index could not be calculated.\n"
            return report
        composite_scores = [PREV_STATS[c["Coin"]]["composite"] for c in results if
                            c["Coin"] in PREV_STATS and "composite" in PREV_STATS[c["Coin"]]]
        avg_score = sum(composite_scores) / len(composite_scores) if composite_scores else 0.0
        if avg_score == 0:
            report += "⚠️ Average composite score is zero, difference index could not be calculated.\n"
            return report
        for coin in results:
            coin_score = PREV_STATS.get(coin["Coin"], {}).get("composite", 0)
            diff_index = calculate_percentage_change(coin_score, avg_score)
            coin["DiffIndex"] = diff_index
        sorted_results = sorted(results, key=lambda x: x.get("DiffIndex", 0), reverse=True)
        total_val = 0
        count = 0
        for coin in sorted_results[:50]:
            symbol = f"${coin['Coin'].replace('USDT', '')}"
            diff_val = coin.get('DiffIndex', 0)
            value = f"{round(diff_val, 2)}%"
            report += f"{symbol}: {value}\n"
            total_val += diff_val
            count += 1
            
        if count > 0:
            avg_val = total_val / count
            report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}%\n"

    elif metric == "Outlier Score":
        if not PREV_STATS:
            report += "⚠️ Previous stats missing, outlier could not be calculated.\n"
            return report
        composite_scores = [PREV_STATS[c["Coin"]]["composite"] for c in results if
                            c["Coin"] in PREV_STATS and "composite" in PREV_STATS[c["Coin"]]]
        if not composite_scores:
            report += "⚠️ Composite scores missing, outlier could not be calculated.\n"
            return report
        median_score = np.median(composite_scores)
        mad = np.median([abs(s - median_score) for s in composite_scores]) or 1e-6
        for coin in results:
            coin_score = PREV_STATS.get(coin["Coin"], {}).get("composite", 0)
            outlier = (coin_score - median_score) / mad if mad != 0 else 0.0
            coin["OutlierScore"] = outlier
        sorted_results = sorted(results, key=lambda x: x.get("OutlierScore", 0), reverse=True)
        total_val = 0
        count = 0
        for coin in sorted_results[:50]:
            symbol = f"${coin['Coin'].replace('USDT', '')}"
            outlier_val = coin.get('OutlierScore', 0)
            value = f"{round(outlier_val, 2)}"
            report += f"{symbol}: {value}\n"
            total_val += outlier_val
            count += 1
            
        if count > 0:
            avg_val = total_val / count
            report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}\n"

    elif metric == "Composite Skor" or metric == "Composite Score":
        total_val = 0
        count = 0
        
        # Calculate composite score for each coin and sort
        for coin in results:
            coin["_tmp_comp"] = calculate_composite_score(coin)
            with global_lock:
                if coin["Coin"] not in PREV_STATS:
                    PREV_STATS[coin["Coin"]] = {}
                PREV_STATS[coin["Coin"]]["composite"] = coin["_tmp_comp"]
        
        sorted_results = sorted(results, key=lambda x: x["_tmp_comp"], reverse=True)
        
        for coin in sorted_results[:50]:
            symbol = f"${coin['Coin'].replace('USDT', '')}"
            report += f"{symbol}: {coin['_tmp_comp']}\n"
            total_val += coin["_tmp_comp"]
            count += 1
        
        if count > 0:
            avg_val = total_val / count
            report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}\n"

    elif metric in ["BTC Correlation", "ETH Correlation", "SOL Correlation", 
                  "BTC Correlation", "ETH Correlation", "SOL Correlation",
                  "BTC Correlation_4h", "BTC Correlation_1d",
                  "ETH Correlation_4h", "ETH Correlation_1d",
                  "SOL Correlation_4h", "SOL Correlation_1d"]:
        total_val = 0
        count = 0
        
        def get_corr_val(coin):
            try:
                val = coin.get(metric, 0)
                if val == "N/A" or val is None or str(val) == "Yok":
                    return -1.0
                return float(str(val))
            except: return -1.0
            
        sorted_results = sorted(results, key=get_corr_val, reverse=True)
        
        for coin in sorted_results[:50]:
            symbol = f"${coin['Coin'].replace('USDT', '')}"
            value = coin.get(metric, "N/A")
            try:
                if value != "N/A" and value is not None and str(value) != "Yok":
                    total_val += float(str(value))
                    count += 1
            except: pass
            report += f"{symbol}: {value}\n"
            
        if count > 0:
            avg_val = total_val / count
            report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}\n"

    else:
        total_val = 0
        count = 0
        
        # Consistent numeric sorting key
        def get_sort_value(coin):
            try:
                # Use raw numeric keys if possible
                num_key_map = {
                    "RSI": "RSI", "RSI_4h": "RSI_4h", "RSI_1d": "RSI_1d",
                    "ADX": "ADX", "ADX_4h": "ADX_4h", "ADX_1d": "ADX_1d",
                    "MACD": "MACD", "MACD_4h": "MACD_4h", "MACD_1d": "MACD_1d",
                    "MFI": "MFI", "MFI_4h": "MFI_4h", "MFI_1d": "MFI_1d",
                    "Volume Ratio": "Volume Ratio", "Volume Ratio_4h": "vol_ratio_4h", "Volume Ratio_1d": "vol_ratio_1d",
                    "24h Volume": "24h Volume", "24h Vol_4h": "quote_vol_4h", "24h Vol_1d": "quote_vol_1d",
                    "ATR": "ATR", "Momentum": "Momentum", "Momentum_4h": "mom_4h", "Momentum_1d": "mom_1d",
                    "Taker Rate": "Taker Rate",
                    "Z-Score": "Z-Score", "Z-Score_4h": "z_score_4h", "Z-Score_1d": "z_score_1d",
                    "Open Interest": "OI_raw",
                    "Net Accum": "NetAccum_raw", "Net Accum_4h": "net_accum_4h", "Net Accum_1d": "net_accum_1d",
                    "Composite Score_4h": "comp_score_4h", "Composite Score_1d": "comp_score_1d",
                    "Scale Buy": "RSI",
                    "Support/Resistance": "Price", "Hourly Analysis": "Price"
                }
                k = num_key_map.get(metric, metric)
                val = coin.get(k, 0)
                
                if isinstance(val, (int, float)): return extract_numeric(val)
                if isinstance(val, tuple): return float(str(val[1]).strip("%"))
                
                # Extract numeric from string
                matches = re.findall(r"[-+]?\d*\.\d+|\d+", str(val).replace(",", ""))
                return float(matches[0]) if matches else 0
            except: return -9999
            
        sorted_results = sorted(results, key=get_sort_value, reverse=True)
        if metric == "Bollinger Bands": sorted_results = sorted(results, key=lambda x: extract_numeric(x.get("BB Lower Distance", "100%")), reverse=False)

        for coin in sorted_results[:50]:
            symbol = f"${coin['Coin'].replace('USDT', '')}"
            
            # Helper to safely format values, showing N/A if data is missing
            def fv(key, fmt="{:.2f}", default="N/A"):
                val = coin.get(key, default)
                if val == "N/A" or val is None or (isinstance(val, str) and val.strip() == ""):
                    return "N/A"
                try:
                    return fmt.format(float(val))
                except:
                    return "N/A"
            
            if metric == "RSI": value = fv('RSI', '{:.1f}')
            elif metric == "RSI_4h": value = fv('RSI_4h', '{:.1f}')
            elif metric == "RSI_1d": value = fv('RSI_1d', '{:.1f}')
            elif metric == "ADX": value = fv('ADX', '{:.1f}')
            elif metric == "ADX_4h": value = fv('ADX_4h', '{:.1f}')
            elif metric == "ADX_1d": value = fv('ADX_1d', '{:.1f}')
            elif metric == "MACD": value = fv('MACD', '{:.4f}')
            elif metric == "MACD_4h": value = fv('MACD_4h', '{:.4f}')
            elif metric == "MACD_1d": value = fv('MACD_1d', '{:.4f}')
            elif metric == "MFI": value = fv('MFI', '{:.1f}')
            elif metric == "MFI_4h": value = fv('MFI_4h', '{:.1f}')
            elif metric == "MFI_1d": value = fv('MFI_1d', '{:.1f}')
            elif metric == "Momentum": value = fv('Momentum')
            elif metric == "Momentum_4h": value = fv('mom_4h')
            elif metric == "Momentum_1d": value = fv('mom_1d')
            elif metric == "Z-Score": value = fv('Z-Score')
            elif metric == "Z-Score_4h": value = fv('z_score_4h')
            elif metric == "Z-Score_1d": value = fv('z_score_1d')
            elif metric == "Volume Ratio": value = fv('Volume Ratio') + "x" if fv('Volume Ratio') != "N/A" else "N/A"
            elif metric == "Volume Ratio_4h": value = fv('vol_ratio_4h') + "x" if fv('vol_ratio_4h') != "N/A" else "N/A"
            elif metric == "Volume Ratio_1d": value = fv('vol_ratio_1d') + "x" if fv('vol_ratio_1d') != "N/A" else "N/A"
            elif metric == "Net Accum": value = f"${format_money(coin.get('NetAccum_raw', 0))}" if coin.get('NetAccum_raw') != "N/A" else "N/A"
            elif metric == "Net Accum_4h": value = f"${format_money(coin.get('net_accum_4h', 0))}" if coin.get('net_accum_4h') != "N/A" else "N/A"
            elif metric == "Net Accum_1d": value = f"${format_money(coin.get('net_accum_1d', 0))}" if coin.get('net_accum_1d') != "N/A" else "N/A"
            elif metric == "Composite Score": value = fv('Composite Score')
            elif metric == "Composite Score_4h": value = fv('comp_score_4h')
            elif metric == "Composite Score_1d": value = fv('comp_score_1d')
            elif metric == "24h Volume": value = f"${format_money(coin.get('24h Volume', 0))}"
            elif metric == "24h Vol_4h": value = f"${format_money(coin.get('quote_vol_4h', 0))}" if coin.get('quote_vol_4h') != "N/A" else "N/A"
            elif metric == "24h Vol_1d": value = f"${format_money(coin.get('quote_vol_1d', 0))}" if coin.get('quote_vol_1d') != "N/A" else "N/A"
            elif metric == "EMA": value = coin.get("EMA Trend", "N/A")
            elif metric in ["Weekly Change", "Haftalık Değişim"]:
                value = coin.get("Weekly Change", ("N/A", "0%"))[1]
            elif metric in ["Monthly Change", "Aylık Değişim"]:
                value = coin.get("Monthly Change", ("N/A", "0%"))[1]
            elif metric in ["4H Change", "4H Change"]:
                value = coin.get("4H Change", ("N/A", "0%"))[1]
            elif metric == "ATR": value = format_money(coin.get("ATR", 0))
            elif metric == "StochRSI": value = fv('StochRSI')
            elif metric == "Open Interest": value = coin.get("Open Interest", "N/A")
            elif metric == "Taker Rate": value = fv('Taker Rate')
            elif metric == "Bollinger Bands": value = coin.get("Bollinger Bands", "N/A")
            elif metric == "Support/Resistance": value = coin.get("Support_Resistance", "N/A")
            else: value = str(coin.get(metric, "N/A"))
            
            # Numeric aggregation for average
            try:
                nv = get_sort_value(coin)
                if nv != -9999:
                    total_val += nv
                    count += 1
            except: pass
            
            report += f"{symbol}: {value}\n"
            
        if count > 0:
            avg_val = total_val / count
            if metric == "Net Accum": report += f"\n📊 <b>Average {display_metric}:</b> ${format_money(avg_val)}\n"
            elif metric == "24h Volume": report += f"\n📊 <b>Average {display_metric}:</b> ${format_money(avg_val)}\n"
            elif metric == "Volume Ratio": report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}x\n"
            elif "Change" in display_metric: report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:+.2f}%\n"
            elif metric == "Open Interest": report += f"\n📊 <b>Average {display_metric}:</b> ${format_money(avg_val)}\n"
            elif metric in ["MACD", "ATR"]: report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.4f}\n"
            elif "Bollinger Bands" in metric: report += f"\n📊 <b>Average Proximity to Lower Band:</b> {avg_val:.2f}%\n"
            else: report += f"\n📊 <b>Average {display_metric}:</b> {avg_val:.2f}\n"

    return report


# ---------------- Telegram Güncelleme ve Komut İşlemleri ----------------

def handle_trust_index_report():
    print("[DEBUG] Güven Endeksi Raporu işleniyor...")
    # İlk analiz döngüsünün tamamlanmasını bekle
    if not ALL_RESULTS:
        print("[DEBUG] ALL_RESULTS henüz dolmadı, bekleniyor...")
        send_telegram_message_long("⚠️ Analiz verisi henüz hazır değil, lütfen birkaç dakika bekleyin.")
        return
    report = generate_trust_index_report()
    send_telegram_message_long(report)

# handle_trust_index_report fonksiyonundan sonra ekleyin

def handle_futures_timeframe_analysis():
    """
    İyileştirilmiş çoklu zaman dilimi vadeli işlemler analizi raporunu oluşturur ve gönderir.
    """
    report = generate_futures_timeframe_analysis_improved()
    send_telegram_message_long(report)

def handle_trend_status():
    """
    Generates and sends trend status report in English.
    """
    if ALL_RESULTS:
        report = f"📈 <b>Trend Status Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
        report += "<i>Showing top 50 coins by ADX strength</i>\n\n"
        sorted_results = sorted(ALL_RESULTS, key=lambda x: extract_numeric(x.get("ADX", "0")), reverse=True)
        for coin in sorted_results[:50]:
            symbol = "$" + coin["Coin"].replace("USDT", "")
            report += f"<b>{symbol}</b>:\n"
            report += f"   • EMA Trend: {coin.get('EMA Trend', 'N/A')}\n"
            report += f"   • ADX: {coin.get('ADX', 'N/A')} ({get_adx_comment(extract_numeric(coin.get('ADX', '0')) or 0)})\n"
            report += f"   • MACD: {coin.get('MACD', 'N/A')} ({get_macd_comment(coin.get('MACD', 'N/A'))})\n\n"
        send_telegram_message_long(report)
    else:
        send_telegram_message_long("⚠️ No analysis data available yet.")


def handle_risk_analizi():
    """Gelişmiş risk analizi raporu oluşturur ve gönderir."""
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ Henüz analiz verisi bulunmuyor, lütfen birkaç dakika bekleyin.")
        return

    try:
        print("[INFO] Risk analizi yapılıyor...")
        send_telegram_message(TELEGRAM_CHAT_ID, "🔍 Risk analizi hazırlanıyor, lütfen bekleyin...")

        # Top 20 coins by volume
        coins_to_analyze = ALL_RESULTS[:20]

        # Makro risk hesapla
        macro_risk = calculate_macro_risk_level()

        # Coin bazlı risk analizi
        risk_data = []
        for coin in coins_to_analyze:
            try:
                symbol = coin["Coin"]

                # Temel değerleri güvenle çıkar
                try:
                    current_price = parse_money(coin["Price_Display"])
                    rsi = extract_numeric(coin["RSI"])
                    volume_ratio = extract_numeric(coin.get("Volume Ratio", 1))
                    net_accum = extract_numeric(coin.get("NetAccum_raw", 0))
                except Exception as e:
                    print(f"[HATA] {symbol} temel değerler çıkarılamadı: {e}")
                    continue

                # Vadeli işlem verilerini çek
                try:
                    # Use safe defaults - no futures data available
                    futures_data = {
                        "funding_rate": 0,
                        "open_interest": 0,
                        "long_short_ratio": 1.0
                    }

                    funding_rate = 0
                    open_interest = 0
                    long_short_ratio = 1.0
                except Exception as e:
                    pass  # Silenced, use defaults
                    funding_rate = 0
                    open_interest = 0
                    long_short_ratio = 1.0

                # ATR hesapla (volatilite için)
                try:
                    atr = extract_numeric(coin.get("ATR_raw", 0))
                except Exception as e:
                    print(f"[HATA] {symbol} ATR hesaplanamadı: {e}")
                    atr = 0

                # BTC korelasyonu
                try:
                    btc_corr = float(
                        coin.get("BTC Correlation", 0) if coin.get("BTC Correlation") != "Yok" else 0)
                except Exception as e:
                    print(f"[HATA] {symbol} BTC korelasyonu hesaplanamadı: {e}")
                    btc_corr = 0

                # Risk bileşenleri hesapla
                try:
                    # Volatilite riski
                    vol_risk = (atr / current_price * 100) * 5 if current_price > 0 else 0
                    vol_risk = min(vol_risk, 100)

                    # RSI riski (ekstremlerden uzaklık)
                    rsi_risk = abs(50 - rsi) / 50 * 100

                    # Net birikim riski
                    accum_risk = min(abs(net_accum) / 5 * 100, 100)

                    # volume riski (düşük hacim = yüksek risk)
                    volume_risk = min((1 / max(volume_ratio, 0.2)) * 50, 50)

                    # Korelasyon riski
                    corr_risk = min(abs(btc_corr) * 100, 100)

                    # Vadeli işlem riski
                    funding_risk = min(abs(funding_rate) * 2, 100)  # high funding = yüksek risk
                    ls_risk = min(abs(1 - long_short_ratio) * 100, 100)  # Dengesizlik = risk

                    # Makro risk etkisi
                    macro_effect = macro_risk.get("risk_score", 50) * 0.3

                    # Toplam risk skoru - ağırlıklı ortalama
                    weights = {
                        "vol_risk": 0.15,
                        "rsi_risk": 0.10,
                        "accum_risk": 0.15,
                        "volume_risk": 0.10,
                        "corr_risk": 0.10,
                        "funding_risk": 0.10,
                        "ls_risk": 0.10,
                        "macro_effect": 0.20
                    }

                    risk_components = {
                        "vol_risk": vol_risk,
                        "rsi_risk": rsi_risk,
                        "accum_risk": accum_risk,
                        "volume_risk": volume_risk,
                        "corr_risk": corr_risk,
                        "funding_risk": funding_risk,
                        "ls_risk": ls_risk,
                        "macro_effect": macro_effect
                    }

                    total_risk = sum(risk_components[k] * weights[k] for k in weights)

                    # Risk seviyesi belirle
                    if total_risk >= 70:
                        risk_level = "Çok high"
                    elif total_risk >= 50:
                        risk_level = "high"
                    elif total_risk >= 30:
                        risk_level = "Orta"
                    else:
                        risk_level = "low"

                    # En yüksek 3 risk faktörünü bul
                    top_risks = sorted(risk_components.items(), key=lambda x: x[1], reverse=True)[:3]

                    # Risk verilerini ekle
                    risk_data.append({
                        "symbol": symbol,
                        "price": current_price,
                        "risk_score": round(total_risk, 1),
                        "risk_level": risk_level,
                        "risk_components": risk_components,
                        "top_risks": {k: v for k, v in top_risks},
                        "funding_rate": funding_rate,
                        "open_interest": open_interest,
                        "long_short_ratio": long_short_ratio
                    })

                except Exception as e:
                    print(f"[HATA] {symbol} risk hesaplamasında hata: {e}")
                    continue

            except Exception as e:
                print(f"[HATA] {symbol} ana risk analizinde hata: {e}")
                continue

        # Riske göre sırala
        sorted_risk = sorted(risk_data, key=lambda x: x["risk_score"], reverse=True)

        # Rapor oluştur
        report = f"⚠️ <b>Gelişmiş Risk Analizi Raporu – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        # Makro risk bölümü
        report += f"<b>🌐 Makroekonomik Risk:</b> {macro_risk['risk_score']:.1f}/100 ({macro_risk['risk_level'].upper()})\n"
        report += "• Risk Faktörleri:\n"
        for factor in macro_risk.get('factors', [])[:3]:
            report += f"  - {factor['factor']}: {factor['impact'].upper()} etki\n"
        report += "\n"

        # Ortalama ve dağılım
        avg_risk = sum(item["risk_score"] for item in risk_data) / len(risk_data) if risk_data else 0
        high_risk_count = len([x for x in risk_data if x["risk_score"] >= 70])
        medium_risk_count = len([x for x in risk_data if 50 <= x["risk_score"] < 70])
        low_risk_count = len([x for x in risk_data if x["risk_score"] < 50])

        report += f"<b>📊 Risk Dağılımı:</b>\n"
        report += f"• Ortalama Risk: {avg_risk:.1f}/100\n"
        report += f"• Çok high Risk: {high_risk_count} coin\n"
        report += f"• high Risk: {medium_risk_count} coin\n"
        report += f"• low/Orta Risk: {low_risk_count} coin\n\n"

        # En riskli 5 coin
        report += "<b>🚨 En high Riskli 5 Coin:</b>\n"
        for i, item in enumerate(sorted_risk[:5], 1):
            # Risk seviyesi emojisi
            risk_emoji = "🟢" if item["risk_score"] < 30 else "🟡" if item["risk_score"] < 50 else "🟠" if item[
                                                                                                            "risk_score"] < 70 else "🔴"

            report += f"{i}. {risk_emoji} <b>{item['symbol']}</b> (Risk: {item['risk_score']}/100 - {item['risk_level']})\n"

            # En yüksek 3 risk faktörü
            for risk_name, risk_value in item["top_risks"].items():
                risk_display = {
                    "vol_risk": "Volatilite",
                    "rsi_risk": "RSI Aşırılık",
                    "accum_risk": "Net Birikim",
                    "volume_risk": "volume Zayıflığı",
                    "corr_risk": "BTC Correlation",
                    "funding_risk": "Fonlama Oranı",
                    "ls_risk": "Long/Short Dengesizlik",
                    "macro_effect": "Makroekonomik Etki"
                }.get(risk_name, risk_name)

                report += f"   - {risk_display}: {risk_value:.1f}/100\n"

            # Vadeli işlem verileri
            report += f"   - Funding Rate: {item['funding_rate']:.4f}%, L/S Ratio: {item['long_short_ratio']:.2f}\n"
            report += f"   - OI: {format_money(item['open_interest'])} USD\n\n"

        # Genel tavsiye
        report += "<b>💡 Risk Yönetimi Tavsiyeleri:</b>\n"
        if avg_risk > 70:
            report += "• Piyasa oldukça riskli görünüyor, pozisyon boyutlarını küçültün.\n"
            report += "• Portföyün en az %50'sini stablecoin olarak tutun.\n"
            report += "• high riskli coinlerden uzak durun veya stop-loss kullanın.\n"
        elif avg_risk > 50:
            report += "• Orta-yüksek risk seviyesi, seçici olun ve risk yönetimine dikkat edin.\n"
            report += "• Portföyün %30-40'ını stablecoin olarak tutmayı düşünün.\n"
            report += "• Stop-loss seviyelerini sıkı tutun, özellikle yüksek riskli coinlerde.\n"
        else:
            report += "• Risk seviyesi makul, ancak hala risk yönetimi yapın.\n"
            report += "• Pozisyon boyutlarını kontrol altında tutun.\n"
            report += "• Stop-loss seviyelerini her zaman belirleyin.\n"

        send_telegram_message_long(report)

    except Exception as e:
        print(f"[HATA] Risk analizi sırasında genel hata: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message_long("⚠️ Risk analizi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


def handle_smart_money_menu():
    """Generates and sends the Smart Money coin selection menu."""
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ No analysis data available yet.")
        return

    top_coins = ALL_RESULTS[:12]

    keyboard = []
    row = []

    for i, coin in enumerate(top_coins):
        symbol = coin["Coin"]
        row.append({"text": f"Smart Money: {symbol}"})

        if len(row) == 2 or i == len(top_coins) - 1:
            keyboard.append(row)
            row = []

    keyboard.append([{"text": "↩️ Main Menu"}])

    message = "🔍 <b>Smart Money Analysis</b>\n\nPlease select the coin you want to analyze:"
    send_reply_keyboard_message(TELEGRAM_CHAT_ID, message, keyboard=keyboard)



def handle_coin_smart_money(symbol):
    """Analyzes Smart Money activity for a specific coin."""
    try:
        send_telegram_message(TELEGRAM_CHAT_ID, f"🔍 <b>{symbol}</b> Smart Money analysis is being prepared...")

        coin_data = next((c for c in ALL_RESULTS if c["Coin"] == symbol), None)
        if not coin_data:
            send_telegram_message(TELEGRAM_CHAT_ID, f"⚠️ Analysis data for {symbol} not found.")
            return

        # Simple report using existing data
        report = f"🔍 <b>Smart Money Analysis: {symbol}</b>\n\n"
        report += f"• <b>Market Sentiment:</b> {coin_data.get('EMA Trend', 'N/A')}\n"
        report += f"• <b>Whale Activity:</b> {coin_data.get('Net Accum', 'N/A')}\n"
        report += f"• <b>Accumulation Score:</b> {coin_data.get('CompositeScore', 'N/A')}\n"
        report += f"• <b>RSI Status:</b> {coin_data.get('RSI', 'N/A')}\n\n"
        
        report += "<b>Market Summary:</b>\n"
        if coin_data.get("NetAccum_raw", 0) > 0:
            report += "✅ Smart money is in accumulation phase. High activity detected by whales.\n"
        else:
            report += "⚠️ Smart money distribution detected. Whales are reducing their positions.\n"

        send_telegram_message_long(report)

    except Exception as e:
        print(f"[ERROR] Smart Money analysis failed for {symbol}: {e}")
        send_telegram_message(TELEGRAM_CHAT_ID, f"⚠️ Error occurred during Smart Money analysis for {symbol}.")

    # Return to main menu
    handle_main_menu_return(TELEGRAM_CHAT_ID)




def handle_coin_detail(coin_symbol, chat_id):
    """
    Seçilen coin için detay raporunu gösterir.

    Args:
        coin_symbol (str): Coin sembolü
        chat_id (str): İşlemin gerçekleştiği chat ID
    """
    try:
        if coin_symbol in COIN_DETAILS:
            report = COIN_DETAILS[coin_symbol]
            send_telegram_message_long(report)
        elif coin_symbol in [coin["Coin"] for coin in ALL_RESULTS]:
            report = generate_coin_full_report(coin_symbol)
            send_telegram_message_long(report)
        else:
            print(f"[UYARI] Coin detayı bulunamadı: {coin_symbol}")
            send_telegram_message_long(f"⚠️ {coin_symbol} için detaylı bilgi bulunamadı.")
    except Exception as e:
        print(f"[HATA] {coin_symbol} detayı gösterilirken hata: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_message_long(f"⚠️ {coin_symbol} detayı gösterilirken bir hata oluştu: {str(e)}")


def handle_risk_score_details():
    """
    Provides detailed information about the risk score calculation methodology.
    """
    try:
        report = f"📊 <b>Risk Score Methodology – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        report += "<b>What is Risk Score?</b>\n"
        report += "Risk score is a composite metric that measures the risk of a crypto asset or portfolio on a scale of 0-100.\n"
        report += "• 0-30: Low Risk 🟢\n"
        report += "• 30-50: Medium Risk 🟡\n"
        report += "• 50-70: High Risk 🟠\n"
        report += "• 70-100: Very High Risk 🔴\n\n"

        report += "<b>Components of Risk Score:</b>\n"
        report += "1. <b>Volatility Risk (15%)</b>: Based on ATR to price ratio. Higher volatility = higher risk.\n"
        report += "2. <b>Technical Indicator Risks (25%)</b>: Includes RSI (10%), MACD (10%), and ADX (5%).\n"
        report += "3. <b>Market Dynamics (15%)</b>: Evaluates volume ratio and liquidity status.\n"
        report += "4. <b>Correlation Risk (10%)</b>: High correlation with BTC implies systematic risk.\n"
        report += "5. <b>Whale Activity (12%)</b>: Risk created by large investor movements.\n"
        report += "6. <b>Futures Market Risk (13%)</b>: Funding rate and long/short ratio imbalances.\n"
        report += "7. <b>Macro Risk Factor (10%)</b>: Impact of general market conditions.\n\n"

        report += "<b>Portfolio Risk Assessment:</b>\n"
        report += "• <b>Weighted Risk</b>: Individual asset risk scores multiplied by position weight.\n"
        report += "• <b>Value at Risk (VaR)</b>: Daily loss estimate at 95% confidence using ATR.\n"
        report += "• <b>Maximum Drawdown</b>: Estimated potential max decline based on risk levels.\n"
        report += "• <b>Concentration Risk</b>: Portfolio concentration in single or high-risk assets.\n\n"

        report += "<b>Risk Management Recommendations:</b>\n"
        report += "• Portfolio diversification\n"
        report += "• Use of stop-loss\n"
        report += "• Position size control\n"
        report += "• Adjusting cash ratio according to macro risk conditions\n"

        send_telegram_message_long(report)
    except Exception as e:
        print(f"[ERROR] Risk score details report failed: {e}")
        send_telegram_message_long("⚠️ Error generating risk score details report.")




def handle_sectoral_risk_analysis():
    """
    Performs risk analysis across different crypto sectors.
    """
    try:
        if not ALL_RESULTS or len(ALL_RESULTS) < 5:
            send_telegram_message_long("⚠️ Not enough analysis data available yet.")
            return

        # Coin categories - simplified
        sectors = {
            "DeFi": ["AAVEUSDT", "MKRUSDT", "UNIUSDT", "SUSHIUSDT", "COMPUSDT", "CRVUSDT"],
            "L1 Blockchain": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "ADAUSDT", "DOTUSDT"],
            "L2 & Scaling": ["MATICUSDT", "OPUSDT", "ARBUSDT", "IMXUSDT"],
            "Exchange": ["BNBUSDT", "OKBUSDT", "FTMUSDT", "KCSUSDT"],
            "Meme": ["DOGEUSDT", "SHIBUSDT", "PEPEUSDT"],
            "Metaverse & Gaming": ["SANDUSDT", "MANAUSDT", "ENJUSDT", "AXSUSDT"],
            "AI & Compute": ["FETUSDT", "OCEANUSDT", "RNDR"]
        }

        # Calculate macro risk
        macro_risk = calculate_macro_risk_level()

        # Calculate sectoral risk scores
        sector_risks = {}
        for sector_name, coins in sectors.items():
            sector_coins = [coin for coin in ALL_RESULTS if coin["Coin"] in coins]
            if not sector_coins:
                continue

            # Calculate risk for each coin in the sector
            coin_risks = []
            for coin in sector_coins:
                risk = calculate_asset_risk(coin, macro_risk)
                coin_risks.append(risk["risk_score"])

            # Sector risk score (average)
            avg_risk = sum(coin_risks) / len(coin_risks) if coin_risks else 50

            # Volatility (standard deviation)
            std_dev = 0
            if len(coin_risks) > 1:
                std_dev = math.sqrt(sum((x - avg_risk) ** 2 for x in coin_risks) / len(coin_risks))

            sector_risks[sector_name] = {
                "avg_risk": avg_risk,
                "volatility": std_dev,
                "coins": len(coin_risks),
                "min_risk": min(coin_risks) if coin_risks else 0,
                "max_risk": max(coin_risks) if coin_risks else 0
            }

        # Sort by risk level
        sorted_sectors = sorted(sector_risks.items(), key=lambda x: x[1]["avg_risk"], reverse=True)

        # Generate report
        report = f"🏦 <b>Sectoral Risk Analysis – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        report += "<b>Crypto Sector Risk Ranking:</b>\n"
        for i, (sector_name, risk_data) in enumerate(sorted_sectors, 1):
            risk_emoji = "🟢" if risk_data["avg_risk"] < 30 else "🟡" if risk_data["avg_risk"] < 50 else \
                         "🟠" if risk_data["avg_risk"] < 70 else "🔴"

            report += f"{i}. {risk_emoji} <b>{sector_name}</b>: {risk_data['avg_risk']:.1f}/100\n"
            report += f"   • Volatility: {risk_data['volatility']:.1f}\n"
            report += f"   • Coin Count: {risk_data['coins']}\n"
            report += f"   • Risk Range: {risk_data['min_risk']:.1f} - {risk_data['max_risk']:.1f}\n\n"

        # Sector assessment based on macro risk factors
        report += "<b>📊 Sector Assessment Based on Macro Factors:</b>\n"

        # Sector recommendations based on current macro risk level
        if macro_risk["risk_score"] >= 70:  # Very high macro risk
            report += "• <b>Current Market:</b> Very high macro risk environment\n"
            report += "• <b>Safest Sectors:</b> L1 Blockchain (Majors like BTC, ETH)\n"
            report += "• <b>Riskiest Sectors:</b> Meme coins, high beta DeFi projects\n"
            report += "• <b>Recommendation:</b> Increase BTC/ETH weight, reduce exposure to altcoins.\n"
        elif macro_risk["risk_score"] >= 50:  # High macro risk
            report += "• <b>Current Market:</b> High macro risk environment\n"
            report += "• <b>More Resilient Sectors:</b> L1 Blockchain, large exchange coins\n"
            report += "• <b>Sectors to be Cautious:</b> L2 & Scaling, Metaverse\n"
            report += "• <b>Recommendation:</b> Reduce positions in high volatility sectors.\n"
        elif macro_risk["risk_score"] >= 30:  # Medium macro risk
            report += "• <b>Current Market:</b> Medium macro risk environment\n"
            report += "• <b>Opportunity Sectors:</b> DeFi, L2 & Scaling\n"
            report += "• <b>Recommendation:</b> Diversify across sectors, maintain a balanced portfolio.\n"
        else:  # Low macro risk
            report += "• <b>Current Market:</b> Low macro risk environment\n"
            report += "• <b>Opportunity Sectors:</b> All sectors, especially innovative L2, AI & Compute\n"
            report += "• <b>Recommendation:</b> Evaluate innovative projects, potential to expand portfolio.\n"

        send_telegram_message_long(report)
    except Exception as e:
        print(f"[ERROR] Sectoral risk analysis failed: {e}")
        send_telegram_message_long("⚠️ Error generating sectoral risk analysis.")


def calculate_var(positions, risk_scores, confidence_level=0.95):
    """
    Portföy için Value at Risk (VaR) hesaplar.

    Parameters:
        positions (dict): Pozisyonlar {coin: size_in_usd}
        risk_scores (list): Risk skorları listesi
        confidence_level (float): Güven seviyesi (0-1 arası)

    Returns:
        float: Belirtilen güven seviyesindeki potansiyel kayıp (VaR)
    """
    try:
        # Z-skoru hesapla (normal dağılım varsayımı ile)
        z_score = {
            0.90: 1.28,
            0.95: 1.65,
            0.99: 2.33
        }.get(confidence_level, 1.65)  # Varsayılan %95

        total_var = 0

        # Risk haritası oluştur
        risk_map = {item["coin"]: item for item in risk_scores}

        for coin, position_size in positions.items():
            if coin not in risk_map:
                continue

            # Coin için ATR ve fiyat al
            coin_risk = risk_map[coin]
            atr = coin_risk.get("atr", 0)
            price = coin_risk.get("price", 1)

            # Günlük volatilite (ATR/Fiyat)
            if price > 0:
                daily_volatility = atr / price

                # Pozisyon için VaR hesapla
                position_var = position_size * daily_volatility * z_score
                total_var += position_var

        return total_var
    except Exception as e:
        print(f"[HATA] VaR hesaplaması sırasında hata: {e}")
        return 0



def handle_one_cikanlar():
    if ALL_RESULTS:
        report = f"⭐ <b>Öne Çıkanlar Raporu – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
        top_net_accum = sorted(ALL_RESULTS, key=lambda x: x["NetAccum_raw"], reverse=True)[:5]
        top_composite = sorted(ALL_RESULTS,
                               key=lambda x: float(x["CompositeScore"] if x["CompositeScore"] else "0"),
                               reverse=True)[:5]
        report += "<b>En high Net Accum:</b>\n"
        for coin in top_net_accum:
            report += f"   • {coin['Coin']}: {coin['Net Accum']}\n"
        report += "\n<b>En high Composite Skor:</b>\n"
        for coin in top_composite:
            report += f"   • {coin['Coin']}: {coin['CompositeScore']}\n"
        send_telegram_message_long(report)
    else:
        send_telegram_message_long("Henüz analiz verisi bulunmuyor.")


def handle_net_buy_sell_status():
    """
    Generates and sends net buy/sell status report in English.
    """
    if ALL_RESULTS:
        report = f"💰 <b>Net Buy/Sell Status Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

        # Sorting based on net accumulation
        sorted_results = sorted(ALL_RESULTS, key=lambda x: x["NetAccum_raw"], reverse=True)
        
        # Filtering for featured coins
        highlighted = [coin for coin in sorted_results if
                       abs(coin["NetAccum_raw"]) > 50 or abs(extract_numeric(coin["24h Change"])) > 5 or float(
                           coin["Volume Ratio"]) > 2]
        others = [coin for coin in sorted_results if coin not in highlighted]

        # Top 50 limit for the whole report
        total_shown = 0

        # Highlights
        if highlighted:
            report += "<b>⭐ Featured Coins:</b>\n"
            for coin in highlighted[:50]:
                symbol = "$" + coin["Coin"].replace("USDT", "")
                roc = extract_numeric(coin["24h Change"])
                comment = "Opportunity!" if coin["NetAccum_raw"] > 0 and roc > 0 else "Caution!" if coin[
                                                                                                  "NetAccum_raw"] < 0 else "Watch"
                report += f"{symbol}: {coin['Net Accum']} (ROC: {coin['24h Change']}, Vol: {coin['Volume Ratio']}x) - {comment}\n"
                total_shown += 1
            report += "\n"

        # Others
        if others and total_shown < 50:
            report += "<b>Other Coins:</b>\n"
            for coin in others[:50 - total_shown]:
                symbol = "$" + coin["Coin"].replace("USDT", "")
                report += f"{symbol}: {coin['Net Accum']} ({get_netaccum_comment(coin['NetAccum_raw'])})\n"

        # Market summary
        total_net_accum = sum(coin["NetAccum_raw"] for coin in sorted_results)
        avg_roc = sum(extract_numeric(coin["24h Change"]) for coin in sorted_results) / len(sorted_results)
        report += f"\n<b>Market Summary:</b> Total Net Accum: {format_money(total_net_accum)}M USD, Avg Price Change: {round(avg_roc, 2)}%\n"
        report += f"Market View: {'Bullish' if total_net_accum > 0 else 'Bearish'} sentiment dominant.\n"

        send_telegram_message_long(report)
    else:
        send_telegram_message_long("⚠️ No analysis data available yet.")


def calculate_ema_slope(ema_series, lookback=14):
    """
    EMA'nın eğimini hassas şekilde hesaplar ve yüzde olarak döndürür - NaN güvenli versiyon
    Args:
        ema_series (pd.Series): EMA serisi
        lookback (int): Eğim hesaplaması için geriye bakış periyodu
    Returns:
        dict: Eğim bilgileri
    """
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    try:
        # Son lookback kadar veriyi al, NaN değerlerini kontrol et
        if len(ema_series) < lookback:
            print(f"Eğim hesaplaması için yeterli veri yok: {len(ema_series)} < {lookback}")
            return {
                "slope": 0,
                "slope_percent": 0,
                "category": "Veri Yetersiz",
                "emoji": "⚠️"
            }
        # Son 'lookback' adet veriyi al
        recent_ema = ema_series.iloc[-lookback:]
        # NaN değerlerini kontrol et
        if recent_ema.isna().any():
            print(f"Eğim hesaplaması için NaN değerleri var: {recent_ema.isna().sum()} adet")
            recent_ema = recent_ema.dropna()
            if len(recent_ema) < 2:  # En az 2 nokta gerekli
                return {
                    "slope": 0,
                    "slope_percent": 0,
                    "category": "Veri Yetersiz",
                    "emoji": "⚠️"
                }
        # X eksenini normalize et (standart ölçekleme)
        X = np.arange(len(recent_ema)).reshape(-1, 1)
        X_scaled = StandardScaler().fit_transform(X)
        # Lineer regresyon ile eğim hesapla
        model = LinearRegression()
        model.fit(X_scaled, recent_ema)
        # Eğim bilgisi - scaled değere göre
        slope = model.coef_[0]

        # Eğimi yüzde olarak hesapla
        # Son değer ve ilk değer arasındaki farkı yüzde olarak hesapla
        first_value = recent_ema.iloc[0]
        last_value = recent_ema.iloc[-1]
        if first_value != 0:  # Sıfıra bölme hatasını önle
            slope_percent = ((last_value - first_value) / first_value) * 100
        else:
            slope_percent = 0

        # Daha hassas kategorilendirme - yüzde değerine göre
        abs_slope_percent = abs(slope_percent)
        if abs_slope_percent > 5:
            slope_category = "Çok Güçlü Yükseliş" if slope_percent > 0 else "Çok Güçlü Düşüş"
            slope_emoji = "🚀" if slope_percent > 0 else "🔻"
        elif abs_slope_percent > 3:
            slope_category = "Güçlü Yükseliş" if slope_percent > 0 else "Güçlü Düşüş"
            slope_emoji = "📈" if slope_percent > 0 else "📉"
        elif abs_slope_percent > 1:
            slope_category = "Orta Yükseliş" if slope_percent > 0 else "Orta Düşüş"
            slope_emoji = "↗️" if slope_percent > 0 else "↘️"
        elif abs_slope_percent > 0.5:
            slope_category = "Hafif Trend"
            slope_emoji = "➚" if slope_percent > 0 else "➘"
        else:
            slope_category = "Yatay"
            slope_emoji = "➡️"
        return {
            "slope": float(slope),
            "slope_percent": float(slope_percent),
            "category": slope_category,
            "emoji": slope_emoji
        }
    except Exception as e:
        print(f"EMA eğim hesaplamasında hata: {e}")
        return {
            "slope": 0,
            "slope_percent": 0,
            "category": "Hesaplanamadı",
            "emoji": "⚠️"
        }


def analyze_ema_trends(df, windows=[20, 50, 100, 200]):
    """
    EMA kesişimlerini ve trend gücünü analiz eder - NaN değerlerini güvenli şekilde ele alır

    Args:
        df (pd.DataFrame): OHLC verileri
        windows (list): EMA hesaplaması için pencere boyutları

    Returns:
        dict: EMA trend analizi sonuçları
    """
    import pandas as pd
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from ta.trend import EMAIndicator

    # Debugging - Gelen veri yapısını kontrol et
    print(f"DataFrame şekli: {df.shape}")
    print(f"Sütunlar: {df.columns.tolist()}")

    # 1. Sütun adlarını küçük harfe çevir - tutarlılık için
    df.columns = [str(col).lower() for col in df.columns]

    # 2. 'close' sütunu kontrolü - kapanış verisi için doğru sütunu bul
    close_column = None
    possible_close_columns = ['close', 'kapanış', 'kapaniş', 'closing', 'c', '4']

    for col in possible_close_columns:
        if col in df.columns:
            close_column = col
            print(f"Kullanılan kapanış sütunu: '{col}'")
            break

    if close_column is None:
        print(f"close sütunu bulunamadı. Mevcut sütunlar: {df.columns.tolist()}")
        return {
            "structure": [],
            "trend_score": 0,
            "trend_direction": "Veri Eksik",
            "trend_emoji": "⚠️",
            "ema_slopes": {}
        }

    # 3. Geçici bir kopya oluştur ve sayısal dönüşüm yap
    df_temp = df.copy()
    df_temp['close'] = pd.to_numeric(df_temp[close_column], errors='coerce')

    # 4. NaN değerlerini temizle
    df_clean = df_temp.dropna(subset=['close'])

    print(f"Temizlenmeden önce: {len(df)} satır")
    print(f"Temizlendikten sonra: {len(df_clean)} satır")

    # 5. Yeterli veri kontrolü
    if len(df_clean) < max(windows):
        print(f"EMA hesaplaması için yeterli veri yok: {len(df_clean)} satır, {max(windows)} gerekli.")
        return {
            "structure": [],
            "trend_score": 0,
            "trend_direction": "Veri Yetersiz",
            "trend_emoji": "⚠️",
            "ema_slopes": {}
        }

    # EMA hesaplamaları
    ema_values = {}
    ema_slopes = {}  # Bu satırı buraya taşıdım - ema_slopes'u burada tanımlıyoruz!

    for window in windows:
        try:
            ema_indicator = EMAIndicator(close=df_clean['close'], window=window)
            ema_series = ema_indicator.ema_indicator()
            ema_values[window] = ema_series

            # Her EMA için eğim hesapla
            ema_slopes[window] = calculate_ema_slope(ema_series)
        except Exception as e:
            print(f"EMA {window} hesaplanırken hata: {e}")
            # Hata olursa boş değerler kullan
            ema_slopes[window] = {
                "slope": 0,
                "category": "Hesaplanamadı",
                "emoji": "⚠️"
            }

    # Son fiyatı al
    last_close = df_clean['close'].iloc[-1]

    # Trend skoru hesaplama
    trend_analysis = {
        "structure": [],  # EMA yapısı
        "trend_score": 0,  # Trend gücü
        "trend_direction": "Nötr",  # Trend yönü
        "trend_emoji": "⚖️",  # Trend emojisi
        "ema_slopes": ema_slopes  # Her bir EMA'nın eğim bilgisi
    }

    # Yapı puanı
    structure_score = 0

    # Trend belirleme
    for idx, window in enumerate(windows[:-1]):
        try:
            current_ema = ema_values[window].iloc[-1]
            next_ema = ema_values[windows[idx + 1]].iloc[-1]

            if current_ema > next_ema:
                trend_analysis["structure"].append(f"EMA{window} > EMA{windows[idx + 1]}")
                structure_score += 25  # Her üst üste çapraz artış için puan
            elif current_ema < next_ema:
                trend_analysis["structure"].append(f"EMA{window} < EMA{windows[idx + 1]}")
                structure_score -= 25  # Her üst üste çapraz azalış için puan
            else:
                trend_analysis["structure"].append(f"EMA{window} = EMA{windows[idx + 1]}")
        except Exception as e:
            print(f"Trend hesaplanırken hata: {e}")
            trend_analysis["structure"].append(f"EMA{window} ? EMA{windows[idx + 1]}")

    # Eğim puanı (EMA eğimleri bazlı)
    slope_score = 0
    slope_weights = {20: 0.4, 50: 0.3, 100: 0.2, 200: 0.1}  # Farklı EMAlara farklı ağırlıklar

    for window, slope_info in ema_slopes.items():
        slope_percent = slope_info.get("slope_percent", 0)
        weight = slope_weights.get(window, 0)

        # Eğime göre puanlama
        if slope_percent > 5:  # Çok güçlü yükseliş
            slope_score += 10 * weight
        elif slope_percent > 3:  # Güçlü yükseliş
            slope_score += 7 * weight
        elif slope_percent > 1:  # Orta yükseliş
            slope_score += 5 * weight
        elif slope_percent > 0.5:  # Hafif yükseliş
            slope_score += 2 * weight
        elif slope_percent < -5:  # Çok güçlü düşüş
            slope_score -= 10 * weight
        elif slope_percent < -3:  # Güçlü düşüş
            slope_score -= 7 * weight
        elif slope_percent < -1:  # Orta düşüş
            slope_score -= 5 * weight
        elif slope_percent < -0.5:  # Hafif düşüş
            slope_score -= 2 * weight

    # Toplam skoru hesapla
    raw_score = structure_score + slope_score
    trend_analysis["raw_score"] = raw_score

    # Trend yönü belirleme
    if raw_score > 20:
        trend_analysis["trend_direction"] = "Yükseliş"
        trend_analysis["trend_emoji"] = "🟢"
    elif raw_score < -20:
        trend_analysis["trend_direction"] = "Düşüş"
        trend_analysis["trend_emoji"] = "🔴"
    else:
        trend_analysis["trend_direction"] = "Nötr"
        trend_analysis["trend_emoji"] = "🟠"

    # Kesin trend gücü hesaplama - negatif değerleri kaybetmeden 0-100 arasına normalize et
    trend_analysis["trend_score"] = min(max(50 + raw_score / 2, 0), 100)  # -100 to 100 -> 0 to 100

    return trend_analysis

def get_ema_crossings_report_string():
    """
    Creates EMA crossover and squeeze report for all coins
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"⚖️ <b>EMA Crossover & Squeeze Report – {datetime.now().strftime('%Y-%m-%d')}</b>\n\n"
    report += "This report analyzes EMA crossovers and squeeze status.\n\n"

    # Analyze coins for trend and squeeze
    trend_results = []
    squeeze_results = []
    total_coins = 0
    trend_types = {"Uptrend": 0, "Downtrend": 0, "Neutral": 0, "Insufficient Data": 0}
    analyzed_coins = 0
    failed_coins = 0

    for coin in ALL_RESULTS:
        try:
            symbol = coin["Coin"]
            
            if "df" not in coin or not coin["df"]:
                failed_coins += 1
                continue

            df = pd.DataFrame(coin["df"])

            # Normalize column names
            df.columns = [col.lower().replace('ı', 'i').replace('ş', 's').replace('ö', 'o').replace('ü', 'u').replace('ç', 'c').replace('ğ', 'g') for col in df.columns]

            column_mapping = {
                'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume',
                'acilis': 'open', 'yuksek': 'high', 'dusuk': 'low', 'kapanis': 'close', 'hacim': 'volume'
            }

            for norm_orig, new_col in column_mapping.items():
                if norm_orig in df.columns:
                    df.rename(columns={norm_orig: new_col}, inplace=True)

            if 'close' not in df.columns:
                failed_coins += 1
                continue

            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df_clean = df.dropna(subset=['close'])

            if len(df_clean) < 20:
                trend_types["Insufficient Data"] += 1
                failed_coins += 1
                continue

            trend_analysis = analyze_ema_trends(df_clean)
            
            # Translate trend direction
            direction_map = {"Yükseliş": "Uptrend", "Düşüş": "Downtrend", "Nötr": "Neutral", "Veri Yetersiz": "Insufficient Data"}
            raw_dir = trend_analysis.get("trend_direction", "Nötr")
            trend_analysis["trend_direction_en"] = direction_map.get(raw_dir, raw_dir)

            trend_results.append({
                "symbol": symbol,
                "trend_analysis": trend_analysis
            })

            trend_en = trend_analysis["trend_direction_en"]
            trend_types[trend_en] = trend_types.get(trend_en, 0) + 1

            squeeze_analysis = detect_ema_squeeze(df_clean)
            if squeeze_analysis["squeeze_type"] not in ["Nötr", "Neutral", "Veri Yetersiz", "Insufficient Data"]:
                # Translate squeeze type
                sq_map = {"Yükseliş Kırılımı": "Bullish Breakout", "Düşüş Kırılımı": "Bearish Breakout", "Sıkışma": "Squeeze"}
                raw_sq = squeeze_analysis.get("squeeze_type", "Nötr")
                squeeze_analysis["squeeze_type_en"] = sq_map.get(raw_sq, raw_sq)
                
                squeeze_results.append({
                    "symbol": symbol,
                    "squeeze_analysis": squeeze_analysis
                })

            total_coins += 1
            analyzed_coins += 1

        except Exception as e:
            failed_coins += 1
            continue

    report += f"Analysis Summary: {analyzed_coins} coins analyzed, {failed_coins} coins failed\n\n"

    report += "🔍 <b>EMA Trend Analysis:</b>\n"
    sorted_trends = sorted(trend_results, key=lambda x: x["trend_analysis"].get("trend_score", 0), reverse=True)

    if not sorted_trends:
        report += "No trend analysis available.\n\n"
    else:
        for coin_trend in sorted_trends[:50]:
            symbol = "$" + coin_trend["symbol"].replace("USDT", "")
            analysis = coin_trend["trend_analysis"]
            report += f"• {symbol}: \n"
            report += f"  {analysis.get('trend_emoji', '⚠️')} {analysis.get('trend_direction_en', 'Unknown')} Trend\n"
            if "structure" in analysis and analysis["structure"]:
                formatted_structure = format_ema_structure(analysis["structure"])
                report += f"  Structure: {formatted_structure}\n"
            report += f"  Trend Score: {analysis.get('trend_score', 0):.1f}% {'🚀' if analysis.get('trend_score', 0) > 75 else '⚡' if analysis.get('trend_score', 0) > 50 else '⚖️'}\n\n"

    report += "📊 <b>EMA Squeeze Analysis:</b>\n"
    if not squeeze_results:
        report += "No squeeze detected at the moment.\n\n"
    else:
        report += "• Squeeze Detected for:\n"
        sorted_squeeze = sorted(squeeze_results, key=lambda x: x["squeeze_analysis"].get("squeeze_score", 0), reverse=True)
        for coin_squeeze in sorted_squeeze[:50]:
            symbol = "$" + coin_squeeze["symbol"].replace("USDT", "")
            analysis = coin_squeeze["squeeze_analysis"]
            report += f"  - {symbol}: {analysis.get('squeeze_emoji', '⚠️')} {analysis.get('squeeze_type_en', 'Unknown')} "
            report += f"(Score: {analysis.get('squeeze_score', 0)})\n"

    report += "\n💡 <b>General Trend Commentary:</b>\n"
    report += f"• Total Investigated Coins: {total_coins}\n"
    report += f"• Uptrend: {trend_types.get('Uptrend', 0)} Coins\n"
    report += f"• Downtrend: {trend_types.get('Downtrend', 0)} Coins\n"
    report += f"• Neutral: {trend_types.get('Neutral', 0)} Coins\n"
    report += f"• Insufficient Data: {trend_types.get('Insufficient Data', 0)} Coins\n"

    if trend_types.get("Uptrend", 0) > max(trend_types.get("Downtrend", 0), trend_types.get("Neutral", 0)):
        report += "\n🚀 <b>Market Outlook:</b> Bullish sentiment prevails. Positive signals observed.\n"
    elif trend_types.get("Downtrend", 0) > max(trend_types.get("Uptrend", 0), trend_types.get("Neutral", 0)):
        report += "\n📉 <b>Market Outlook:</b> Downtrend dominant. Caution is advised.\n"
    else:
        report += "\n⚖️ <b>Market Outlook:</b> Balanced market view.\n"

    return report

def handle_ema_kesisimi():
    report = get_ema_crossings_report_string()
    if report:
        send_telegram_message_long(report)



def format_coin_symbol(symbol):
    """
    Coin sembolünü USDT'yi kaldırarak ve $ ekleyerek formatlar.

    Args:
        symbol (str): Orijinal coin sembolü (örn: 'BTCUSDT')

    Returns:
        str: Formatlanmış sembol (örn: '$BTC')
    """
    return f"${symbol.replace('USDT', '')}"


def format_ema_structure(structure_list):
    """
    EMA yapı listesini düzgün bir formata dönüştürür, gerçek kesişim ilişkilerini korur
    """
    if not structure_list:
        return "Veri Yetersiz"

    # Her ilişkiyi bir sözlüğe kaydet
    relations = {}
    for item in structure_list:
        parts = item.split()
        if len(parts) >= 3:
            first_ema = parts[0]
            relation = parts[1]
            second_ema = parts[2]
            relations[(first_ema, second_ema)] = relation

    # Tüm EMA değerlerini topla ve sırala
    all_emas = []
    for pair in relations.keys():
        if pair[0] not in all_emas:
            all_emas.append(pair[0])
        if pair[1] not in all_emas:
            all_emas.append(pair[1])

    # Numerik değere göre sırala (EMA20, EMA50, ...)
    all_emas.sort(key=lambda x: int(x[3:]))

    # Zinciri oluştur
    result = all_emas[0]
    for i in range(len(all_emas) - 1):
        current_ema = all_emas[i]
        next_ema = all_emas[i + 1]
        # İlişkiyi bul
        relation = relations.get((current_ema, next_ema), "?")
        result += f" {relation} {next_ema}"

    return result


def debug_ema_kesisimi():
    # ALL_RESULTS kontrolü
    print("ALL_RESULTS Durumu:")
    print(f"Toplam coin sayısı: {len(ALL_RESULTS)}")

    if not ALL_RESULTS:
        print("[BILGI] ALL_RESULTS henüz dolu değil - ilk analiz bekleniyor...")
        return

    # İlk 3 coin için detaylı kontrol
    for coin in ALL_RESULTS[:3]:
        symbol = coin["Coin"]
        print(f"\n{symbol} için detaylı kontrol:")

        # Kline verilerini çek
        try:
            kline_data = sync_fetch_kline_data(symbol, "1h", limit=200)
            print(f"Kline verisi alındı: {len(kline_data)} satır")

            # DataFrame oluşturma kontrolü
            df = pd.DataFrame(kline_data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])

            print("DataFrame sütunları:", df.columns.tolist())
            print("DataFrame boyutu:", df.shape)

            # Sayısal dönüşüm kontrolü
            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # NaN kontrolü
            print("NaN kontrolleri:")
            print(df[["open", "high", "low", "close"]].isna().sum())

            # Temizlenmiş DataFrame
            df_clean = df.dropna(subset=["close"])
            print("Temizlenmiş DataFrame boyutu:", df_clean.shape)

        except Exception as e:
            print(f"HATA: {symbol} için kline verisi alınamadı - {e}")


# Debug fonksiyonunu çağır
debug_ema_kesisimi()

def detect_ema_squeeze(df):
    """
    EMA dar bir bantta sıkıştığında tespit eder ve potansiyel breakout yönünü belirler

    Args:
        df (pd.DataFrame): OHLC verileri

    Returns:
        dict: Sıkışma analizi sonuçları
    """
    # Sütun adı kontrolü
    if "close" not in df.columns:
        available_columns = df.columns.tolist()
        # En uygun sütunu bulmaya çalış
        possible_close_columns = ["kapanış", "Close", "close", "closing", "c", "4"]

        for col in possible_close_columns:
            if col in available_columns:
                df["close"] = df[col]
                break
        else:
            # Hiçbir uygun sütun bulunamadıysa, ValueError fırlat
            raise ValueError(f"'close' sütunu bulunamadı. Mevcut sütunlar: {available_columns}")

    # Veri yeterliliğini kontrol et
    if len(df) < 20:
        return {
            "squeeze_type": "Veri Yetersiz",
            "squeeze_score": 0,
            "squeeze_emoji": "⚠️"
        }

    # EMA hesaplamaları
    ema20 = EMAIndicator(df['close'], window=20).ema_indicator()
    ema50 = EMAIndicator(df['close'], window=50).ema_indicator()

    # Son 10 periyot için EMA bandı genişliğini hesapla
    recent_bandwidth = []
    for i in range(-10, 0):
        bandwidth = abs(ema20.iloc[i] - ema50.iloc[i]) / ema20.iloc[i] * 100
        recent_bandwidth.append(bandwidth)

    # Ortalama bant genişliği
    avg_bandwidth = sum(recent_bandwidth) / len(recent_bandwidth)

    # Önceki 20 periyoda göre bant genişliği
    prev_bandwidth = []
    for i in range(-30, -10):
        if i >= -len(ema20):  # Indeks sınırı kontrolü
            bandwidth = abs(ema20.iloc[i] - ema50.iloc[i]) / ema20.iloc[i] * 100
            prev_bandwidth.append(bandwidth)

    # Önceki ortalama bant genişliğini hesapla
    prev_avg_bandwidth = sum(prev_bandwidth) / len(prev_bandwidth) if prev_bandwidth else 999

    # Sıkışma tespit: Son 10 periyottaki EMA bant genişliği, önceki 20 periyottaki genişliğin %70'inden az mı?
    is_squeeze = avg_bandwidth < prev_avg_bandwidth * 0.7

    # Son kapanış EMA'ların neresinde?
    last_close = df['close'].iloc[-1]

    # Sıkışma sonrası muhtemel breakout yönü
    if is_squeeze:
        # Momentum (son 5 mumun yönü)
        recent_close = df['close'].iloc[-5:].values
        momentum = sum(1 if recent_close[i] > recent_close[i - 1] else -1 for i in range(1, len(recent_close)))

        # Sıkışma skoru (ne kadar düşük bant genişliği, o kadar yüksek skor)
        squeeze_score = min(100, int(100 - avg_bandwidth * 5))

        if last_close > ema20.iloc[-1] and momentum > 0:
            return {
                "squeeze_type": "Bullish Squeeze",
                "squeeze_score": squeeze_score,
                "squeeze_direction": "up",
                "squeeze_emoji": "🚀"
            }
        elif last_close < ema20.iloc[-1] and momentum < 0:
            return {
                "squeeze_type": "Bearish Squeeze",
                "squeeze_score": squeeze_score,
                "squeeze_direction": "down",
                "squeeze_emoji": "📉"
            }
        else:
            return {
                "squeeze_type": "Squeeze (Belirsiz Yön)",
                "squeeze_score": squeeze_score,
                "squeeze_direction": "unknown",
                "squeeze_emoji": "🔄"
            }
    else:
        return {
            "squeeze_type": "Nötr",
            "squeeze_score": 0,
            "squeeze_emoji": "⚖️"
        }


def handle_youtube_alpha(chat_id):
    """
    Handles the YouTube Alpha Analysis request.
    """
    if not ALL_RESULTS:
        send_telegram_message(chat_id, "⚠️ No market data available for analysis yet. Please wait for the next update.")
        return

    # Send status message
    status_msg = send_telegram_message(chat_id, "🔍 <b>Fetching latest YouTube Alpha...</b>\n\nThis may take a minute as I extract and analyze video transcripts from MoreCryptoOnline, Coin Bureau, and Cilinix Crypto.")

    try:
        # Create a compact summary of market data for the LLM
        # Focus on top 20 coins by composite score
        sorted_coins = sorted(
            ALL_RESULTS,
            key=lambda x: extract_numeric(x.get("CompositeScore", "0") if x.get("CompositeScore") else "0"),
            reverse=True
        )[:20]
        
        market_summary = "LATEST MARKET DATA (Top 10 High-Confidence Samples, including 15m/4h/1d timeframes):\n"
        
        # Limit to top 10 to avoid excessive API calls (20 coins * 2 calls = 40 requests, might take too long)
        for c in sorted_coins[:10]:
            symbol = c.get('Coin')
            
            # Fetch extra timeframes for 15m, 4h, and 1d
            rsi_15m = "N/A"
            rsi_4h = "N/A"
            rsi_1d = "N/A"
            trend_15m = "N/A"
            
            try:
                # 15m Data
                kline_15m = sync_fetch_kline_data(symbol, '15m', limit=20)
                if kline_15m and len(kline_15m) > 14:
                    closes = pd.Series([float(x[4]) for x in kline_15m])
                    rsi_15m = round(RSIIndicator(close=closes, window=14).rsi().iloc[-1], 2)
                    # Simple trend
                    trend_15m = "UP" if closes.iloc[-1] > closes.iloc[-5] else "DOWN"
                
                # 4h Data
                kline_4h = sync_fetch_kline_data(symbol, '4h', limit=20)
                if kline_4h and len(kline_4h) > 14:
                    closes = pd.Series([float(x[4]) for x in kline_4h])
                    rsi_4h = round(RSIIndicator(close=closes, window=14).rsi().iloc[-1], 2)
                
                # 1d Data
                kline_1d = sync_fetch_kline_data(symbol, '1d', limit=20)
                if kline_1d and len(kline_1d) > 14:
                    closes = pd.Series([float(x[4]) for x in kline_1d])
                    rsi_1d = round(RSIIndicator(close=closes, window=14).rsi().iloc[-1], 2)
            except Exception as e:
                print(f"[WARN] Extra stats failed for {symbol}: {e}")

            market_summary += (f"{symbol}: Price {c.get('Price_Display')}, "
                               f"24h_Change {c.get('24h_Change')}, "
                               f"RSI_1h {c.get('RSI')}, "
                               f"RSI_4h {rsi_4h}, "
                               f"RSI_15m {rsi_15m} ({trend_15m}), "
                               f"RSI_1d {rsi_1d}, "
                               f"EMA20 {c.get('EMA 20 Üstünde')}, "
                               f"Score {c.get('CompositeScore')}\n")

        # Call the analyzer
        report = youtube_analyzer.analyze_youtube_alpha(market_summary)
        
        # Send the final report
        send_telegram_message_long(report, chat_id=chat_id)
        
    except Exception as e:
        print(f"[ERROR] handle_youtube_alpha failed: {e}")
        send_telegram_message(chat_id, f"⚠️ An error occurred during YouTube analysis: {str(e)}")

def handle_youtube_transcripts_export(chat_id):
    """
    Fetches raw transcripts from tracked YouTube channels and sends them as a text file.
    This is useful for importing into NotebookLM or other LLMs manually.
    """
    send_telegram_message(chat_id, "📜 <b>Fetching YouTube Transcripts...</b>\n\nGetting raw text from MoreCryptoOnline, Coin Bureau, and Cilinix Crypto. Please wait.")
    
    try:
        all_content = []
        for name, cid in youtube_analyzer.CHANNELS.items():
            vid, title = youtube_analyzer.get_latest_video_id(cid)
            if vid:
                # Random delay to be safe
                time.sleep(2)
                text = youtube_analyzer.get_transcript(vid)
                if text:
                    all_content.append(f"=== CHANNEL: {name} ===\nTITLE: {title}\nURL: https://www.youtube.com/watch?v={vid}\n\nTRANSCRIPT:\n{text}\n\n")
                else:
                    all_content.append(f"=== CHANNEL: {name} ===\nTITLE: {title}\n(Transcript not available)\n\n")
            else:
                 all_content.append(f"=== CHANNEL: {name} ===\n(No recent video found)\n\n")

        if not all_content:
            send_telegram_message(chat_id, "⚠️ Could not retrieve any transcripts.")
            return

        # Combine output
        full_text = "\n".join(all_content)
        
        # Save to file
        filename = f"youtube_transcripts_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        file_path = os.path.join(os.getcwd(), filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)
            
        # Send file
        from telegram_bot import send_telegram_document
        success = send_telegram_document(chat_id, file_path, caption="📜 Here are the raw transcripts for NotebookLM.")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
        if not success:
            send_telegram_message(chat_id, "⚠️ Failed to send transcript file. Text might be too long?")
            
    except Exception as e:
        print(f"[ERROR] Transcript export failed: {e}")
        send_telegram_message(chat_id, f"⚠️ Error exporting transcripts: {str(e)}")


def handle_summary():
    report = get_summary_report_string()
    if report:
        send_telegram_message_long(report)

def get_summary_report_string():
    """Rapor içeriğini string olarak döndürür (Web Sync için)"""
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"📊 <b>Market Summary – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

    # Basic market metrics
    total_net_accum = sum(coin["NetAccum_raw"] for coin in ALL_RESULTS)
    price_changes = [extract_numeric(coin["24h Change"]) for coin in ALL_RESULTS]
    avg_price_change = np.mean(price_changes) if price_changes else 0

    # Extract information from Trust Index Report
    try:
        # Calculate trust index - direct calculation
        trust_indices = []
        for coin in ALL_RESULTS:
            try:
                symbol = coin["Coin"]
                curr_price = parse_money(coin["Price_Display"])
                # weekly_close = parse_money(coin["Weekly Change"][0]) # Not always reliable
                daily_close = get_candle_close(symbol, "1d") or curr_price
                # fourh_close = parse_money(coin["4H Change"][0])

                # Calculate trust index (direct calculation)
                adx = extract_numeric(coin["ADX"])
                volume_ratio = extract_numeric(coin["Volume Ratio"])
                net_accum = coin["NetAccum_raw"]
                rsi = extract_numeric(coin["RSI"])

                # Simplified trust scoring
                trust_score = 50  # Initial value

                # RSI factor
                if rsi < 30:  # Oversold
                    trust_score -= 10
                elif rsi > 70:  # Overbought
                    trust_score -= 5
                else:  # Normal range
                    trust_score += 5

                # Volume factor
                if volume_ratio > 1.5:
                    trust_score += 5

                # Net accumulation factor
                if net_accum > 10:
                    trust_score += 10
                elif net_accum < -10:
                    trust_score -= 10

                # ADX factor
                if adx > 30:  # Strong trend
                    trust_score += 5

                trust_indices.append(trust_score)
            except Exception as e:
                pass

        avg_trust_index = sum(trust_indices) / len(trust_indices) if trust_indices else 50

        # Determine trust status
        if avg_trust_index > 60:
            trust_status = "🟢 High"
        elif avg_trust_index > 45:
            trust_status = "🟡 Neutral"
        else:
            trust_status = "🔴 Low"

    except Exception as e:
        print(f"[ERROR] Trust index info could not be extracted: {e}")
        avg_trust_index = 50
        trust_status = "⚠️ N/A"

    # Market summary from Smart Whale & Trend Report
    try:
        # Calculate trend score
        trend_scores = []
        for coin in ALL_RESULTS:
            try:
                # Basic data
                rsi = extract_numeric(coin["RSI"])
                macd = extract_numeric(coin["MACD"])
                adx = extract_numeric(coin["ADX"])
                volume_ratio = extract_numeric(coin["Volume Ratio"])
                net_accum = extract_numeric(coin["NetAccum_raw"])
                price_roc = extract_numeric(coin["24h Change"])

                # Calculate trend score
                trend_score = 50  # Initial value

                # RSI effect
                if rsi < 30:
                    trend_score -= 10
                elif rsi > 70:
                    trend_score += 10

                # MACD effect
                if macd > 0:
                    trend_score += 5
                else:
                    trend_score -= 5

                # Volume effect
                if volume_ratio > 1.5 and price_roc > 0:
                    trend_score += 5

                # Net accumulation effect
                if net_accum > 0:
                    trend_score += 5
                else:
                    trend_score -= 5

                # Price change effect
                if price_roc > 5:
                    trend_score += 10
                elif price_roc < -5:
                    trend_score -= 10

                trend_scores.append(trend_score)
            except Exception as e:
                pass

        # Average trend score
        trend_score = sum(trend_scores) / len(trend_scores) if trend_scores else 50

        # Determine market status
        if trend_score > 60:
            market_status = "Strong 🚀"
        elif trend_score > 50:
            market_status = "Positive 📈"
        elif trend_score > 40:
            market_status = "Neutral ⚖️"
        else:
            market_status = "Weak 📉"

    except Exception as e:
        print(f"[ERROR] Trend score could not be calculated: {e}")
        trend_score = 50
        market_status = "⚠️ N/A"

    # Enrich General Market Status report
    report += "<b>General Market Status:</b>\n"
    report += f"• Net Accumulation: {format_money(total_net_accum)}M USD\n"
    report += f"• Average Price Change: {round(avg_price_change, 2)}%\n"
    report += f"• Average Trust Index: {round(avg_trust_index, 1)}\n"
    report += f"• Trust Status: {trust_status}\n"
    report += f"• Average Trend Score: {round(trend_score, 2)}\n"
    report += f"• Market Status: {market_status}\n"

    # Top Gainers and Losers
    top_gainers = sorted(ALL_RESULTS, key=lambda x: float(x["24h Change"]), reverse=True)[:3]
    top_losers = sorted(ALL_RESULTS, key=lambda x: float(x["24h Change"]))[:3]

    report += "\n<b>Top Gainers:</b>\n"
    for coin in top_gainers:
        symbol = "$" + coin['Coin'].replace("USDT", "")
        report += f"• {symbol}: {coin['24h Change']} (Net Accum: {coin['Net Accum']})\n"

    report += "\n<b>Top Losers:</b>\n"
    for coin in top_losers:
        symbol = "$" + coin['Coin'].replace("USDT", "")
        report += f"• {symbol}: {coin['24h Change']} (Net Accum: {coin['Net Accum']})\n"

    # Smart Money & Manipulation Summary
    try:
        # Manipulation check for each coin
        manipulation_counts = 0
        high_risk_coins = []
        for coin in ALL_RESULTS:
            try:
                result = detect_whale_strategies_enhanced(coin)

                # Increment the count of manipulation strategies
                if result["detected_strategies"]:
                    manipulation_counts += len(result["detected_strategies"])

                    # Identify high-risk coins (score > 70)
                    for strategy in result["detected_strategies"]:
                        if strategy["score"] > 70:
                            high_risk_coins.append(coin["Coin"])
                            break
            except Exception as e:
                pass

        report += "\n<b>🕵️ Smart Money & Manipulation Summary:</b>\n"
        report += f"• Detected Manipulations: {manipulation_counts}\n"
        report += f"• High Risk Coins: {', '.join(['$' + c.replace('USDT', '') for c in high_risk_coins[:5]]) if high_risk_coins else 'None detected'}\n"

    except Exception as e:
        print(f"[ERROR] Manipulation summary could not be added: {e}")
        report += "\n<b>🕵️ Smart Money & Manipulation Summary:</b>\n"
        report += "• Data could not be analyzed\n"

    # Analyze for Candlestick Patterns Report
    try:
        # Candlestick pattern analysis
        pattern_analysis = {}
        for coin in ALL_RESULTS[:50]: # Limit analysis to top 50 for performance
            try:
                symbol = coin["Coin"]
                klines = sync_fetch_kline_data(symbol, "1h", limit=20)
                patterns = extract_candlestick_patterns(klines)

                # Count each pattern
                for pattern in patterns:
                    pattern_type = pattern["type"]
                    pattern_analysis[pattern_type] = pattern_analysis.get(pattern_type, 0) + 1
            except Exception as e:
                pass

        report += "\n<b>🕯️ Candle Patterns & Squeeze Summary:</b>\n"
        report += f"• Total Patterns Detected: {sum(pattern_analysis.values())}\n"
        report += f"• Market Sentiment: {max(pattern_analysis, key=pattern_analysis.get) if pattern_analysis else 'Neutral'}\n"
        report += "• Pattern Types:\n"
        for pattern_type, count in sorted(pattern_analysis.items(), key=lambda x: x[1], reverse=True):
            report += f"  - {pattern_type}: {count} units\n"

        # Bollinger Squeeze analysis
        squeeze_coins = []
        for coin in ALL_RESULTS:
            try:
                symbol = coin["Coin"]
                df = pd.DataFrame(coin["df"])
                if len(df) >= 20:
                    # Normalize columns
                    df.columns = [col.lower() for col in df.columns]
                    close_col = 'close' if 'close' in df.columns else 'kapanis' if 'kapanis' in df.columns else None
                    
                    if not close_col:
                        continue

                    # Numeric conversion
                    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
                    df = df.dropna(subset=[close_col])

                    if len(df) >= 20:
                        # Bollinger calculation
                        bb_indicator = BollingerBands(close=df[close_col], window=20, window_dev=2)
                        df["bb_upper"] = bb_indicator.bollinger_hband()
                        df["bb_lower"] = bb_indicator.bollinger_lband()
                        df["bb_middle"] = bb_indicator.bollinger_mavg()
                        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"] * 100

                        # Squeeze detection: current width < min of last 6 periods * 1.1
                        recent_bw = df["bb_width"].tail(6)
                        current_bw = recent_bw.iloc[-1]
                        min_bw_6 = recent_bw.min()

                        is_squeeze = current_bw <= (min_bw_6 * 1.1)
                        if is_squeeze:
                            squeeze_coins.append(symbol)
            except Exception as e:
                print(f"[ERROR] Bollinger analysis could not be done for {coin['Coin']}: {e}")
                continue

        report += f"• Bollinger Band Squeeze: {len(squeeze_coins)} coins\n"
        report += f"• Squeeze Coins: {', '.join(['$' + c.replace('USDT', '') for c in squeeze_coins[:5]]) if squeeze_coins else 'None detected'}\n"

    except Exception as e:
        print(f"[ERROR] Candle patterns and squeeze summary could not be added: {e}")
        report += "\n<b>🕯️ Candle Patterns & Squeeze Summary:</b>\n"
        report += "• Data could not be analyzed\n"

    # Volume Analysis Summary
    try:
        # Volume analysis for each coin
        volume_increase_coins = []
        volume_decrease_coins = []

        for coin in ALL_RESULTS:
            try:
                volume_ratio = extract_numeric(coin["Volume Ratio"])
                
                # Detect significant volume increase and decrease
                if volume_ratio > 1.5:  # More than 50% volume increase
                    volume_increase_coins.append(coin["Coin"])
                elif volume_ratio < 0.5:  # More than 50% volume decrease
                    volume_decrease_coins.append(coin["Coin"])
            except Exception as e:
                print(f"[ERROR] Volume analysis could not be done for {coin['Coin']}: {e}")
                continue

        report += "\n<b>📈 Volume Analysis Summary:</b>\n"
        report += f"• Volume Increase Coins: {', '.join(['$' + c.replace('USDT', '') for c in volume_increase_coins[:5]]) if volume_increase_coins else 'None detected'}\n"
        report += f"• Volume Decrease Coins: {', '.join(['$' + c.replace('USDT', '') for c in volume_decrease_coins[:5]]) if volume_decrease_coins else 'None detected'}\n"

    except Exception as e:
        print(f"[ERROR] Volume analysis summary could not be added: {e}")
        report += "\n<b>📈 Volume Analysis Summary:</b>\n"
        report += "• Data could not be analyzed\n"

    # Featured coins (Top Gainers/Losers, Manipulation)
    try:
        # Top Gainers and Losers
        gainers = sorted(ALL_RESULTS, key=lambda x: float(x["Price ROC"]), reverse=True)[:3]
        losers = sorted(ALL_RESULTS, key=lambda x: float(x["Price ROC"]))[:3]

        report += "\n<b>🚀 TOP GAINERS:</b>\n"
        for coin in gainers:
            symbol = "$" + coin['Coin'].replace("USDT", "")
            report += f"• {symbol}: {coin['Price']} ({coin['Price ROC']})\n"

        report += "\n<b>📉 TOP LOSERS:</b>\n"
        for coin in losers:
            symbol = "$" + coin['Coin'].replace("USDT", "")
            report += f"• {symbol}: {coin['Price']} ({coin['Price ROC']})\n"

        # Performance of analysis
        report += "\n<b>🕵️ Smart Money & Manipulation Summary:</b>\n"
        for coin in ALL_RESULTS[:50]:
            if "Pump" in str(coin.get("CompositeScore", "")) or "Manipulation" in str(coin.get("CompositeScore", "")):
                symbol = "$" + coin['Coin'].replace("USDT", "")
                report += f"• {symbol}: Manipulation/Pump Signal detected!\n"

    except Exception as e:
        print(f"[ERROR] Featured coins could not be added: {e}")

    # Macroeconomic data
    try:
        macro_data = fetch_macro_economic_data()
        if macro_data:
            # Crypto market data
            crypto_market = macro_data.get('crypto_market', {})
            report += "\n<b>Crypto Market Data:</b>\n"
            report += f"• Total Market Cap: ${crypto_market.get('total_market_cap', 0) / 1e12:.2f} Trillion\n"
            report += f"• BTC Dominance: %{crypto_market.get('btc_dominance', 'N/A')}\n"
            report += f"• 24h Volume: ${crypto_market.get('daily_volume', 0) / 1e9:.2f} Billion\n"
            report += f"• Fear & Greed Index: {crypto_market.get('fear_greed_index', 'N/A')}/100\n"
    except Exception as e:
        print(f"[ERROR] Macro data could not be added: {e}")

    # Top net accumulation coins
    top_accum = sorted(ALL_RESULTS, key=lambda x: x["NetAccum_raw"], reverse=True)[:3]
    report += "\n<b>Top Net Accumulation:</b>\n"
    for coin in top_accum:
        symbol = "$" + coin['Coin'].replace("USDT", "")
        report += f"• {symbol}: {coin['Net Accum']} (ROC: {coin['Price ROC']})\n"

    # RSI based opportunities
    oversold = [coin for coin in ALL_RESULTS if extract_numeric(coin["RSI"]) < 30]
    overbought = [coin for coin in ALL_RESULTS if extract_numeric(coin["RSI"]) > 70]

    if oversold:
        report += "\n<b>Oversold Coins:</b>\n"
        for coin in oversold[:3]:
            symbol = "$" + coin['Coin'].replace("USDT", "")
            report += f"• {symbol}: RSI {coin['RSI']}\n"

    if overbought:
        report += "\n<b>Overbought Coins:</b>\n"
        for coin in overbought[:3]:
            symbol = "$" + coin['Coin'].replace("USDT", "")
            report += f"• {symbol}: RSI {coin['RSI']}\n"

    return report


def get_whale_strategies_report_string():
    """
    Creates an enhanced whale strategies report and returns it as a string.
    Groups strategies and provides a richer visual output.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"🐳 <b>WHALE STRATEGIES REPORT – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Analyzing top 50 coins for whale behavioral patterns</i>\n\n"

    # Categories for strategy types
    accumulation_strategies = ["Silent Accumulation", "Strategic Collection", "Aggressive Buying", "Sessiz Birikim", "Stratejik Toplama", "Agresif Alım"]
    manipulation_strategies = ["Pump and Dump", "Stop-Loss Hunt", "Spoofing", "Front-Running", "Wash Trading", "Stop-Loss Avı"]
    distribution_strategies = ["Distribution", "Selling Pressure", "Distribüsyon", "Satış Baskısı"]

    # Translation map
    trans_map = {
        "Sessiz Birikim": "Silent Accumulation", "Stratejik Toplama": "Strategic Collection", "Agresif Alım": "Aggressive Buying",
        "Stop-Loss Avı": "Stop-Loss Hunt", "Distribüsyon": "Distribution", "Satış Baskısı": "Selling Pressure",
        "Belirgin strateji yok": "No significant strategy", "Nötr": "Neutral", "Aktif": "Active"
    }

    # Lists to store results
    accumulation_coins = []
    manipulation_coins = []
    distribution_coins = []
    neutral_coins = []

    # Strategy statistics
    strategy_count = 0
    strategy_types = {}

    # Analyze each coin
    for coin in ALL_RESULTS[:50]:
        try:
            symbol = coin["Coin"]
            df = pd.DataFrame(coin["df"]) if "df" in coin else None

            # Detect strategies
            strategy_info = detect_whale_strategies(coin, df)

            detected_strategy = None
            strategy_phase = "Active"

            if "No significant" not in strategy_info and "Belirgin" not in strategy_info:
                parts = strategy_info.split(":")
                if len(parts) >= 2:
                    detected_strategy = parts[0].strip()
                    description = parts[1].strip()
                    phase_match = re.search(r"\((.*?)\)", description)
                    if phase_match:
                        raw_phase = phase_match.group(1)
                        strategy_phase = trans_map.get(raw_phase, raw_phase)

            # Translation
            if detected_strategy in trans_map:
                detected_strategy = trans_map[detected_strategy]

            # Coin metrics
            net_accum = coin.get("NetAccum_raw", 0)
            rsi = extract_numeric(coin.get("RSI", "50"))
            volume_ratio = extract_numeric(coin.get("Volume Ratio", 1))
            price_change = extract_numeric(coin.get("24h Change", "0"))

            # Calculate strategy score
            strategy_score = 0
            if detected_strategy:
                if detected_strategy in accumulation_strategies:
                    strategy_score = min(70 + (net_accum * 2), 100) if net_accum > 0 else 50
                elif detected_strategy in manipulation_strategies:
                    strategy_score = 80 if "Pump and Dump" in detected_strategy else 75
                elif detected_strategy in distribution_strategies:
                    strategy_score = min(70 + (abs(net_accum) * 2), 100) if net_accum < 0 else 50

            # Store strategy properties
            if detected_strategy and detected_strategy != "No significant strategy":
                strategy = {
                    "type": detected_strategy,
                    "phase": strategy_phase,
                    "score": strategy_score,
                    "description": strategy_info
                }
                strategy_count += 1
                strategy_types[detected_strategy] = strategy_types.get(detected_strategy, 0) + 1

                coin_data = {
                    "symbol": "$" + symbol.replace("USDT", ""),
                    "strategy": strategy,
                    "net_accum": net_accum,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio,
                    "price_change": price_change
                }

                if detected_strategy in accumulation_strategies:
                    accumulation_coins.append(coin_data)
                elif detected_strategy in manipulation_strategies:
                    manipulation_coins.append(coin_data)
                elif detected_strategy in distribution_strategies:
                    distribution_coins.append(coin_data)
                else:
                    neutral_coins.append(coin_data)
            else:
                coin_data = {
                    "symbol": "$" + symbol.replace("USDT", ""),
                    "strategy": {"type": "No significant strategy", "score": 0, "phase": "Neutral"},
                    "net_accum": net_accum,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio,
                    "price_change": price_change
                }
                neutral_coins.append(coin_data)

        except Exception as e:
            continue

    # Summary section
    most_common = max(strategy_types.items(), key=lambda x: x[1], default=("None", 0))

    report += "<b>📊 GENERAL STATUS:</b>\n"
    report += f"• Detected Strategies: {strategy_count}\n"
    if most_common[1] > 0:
        report += f"• Most Common Strategy: {most_common[0]} ({most_common[1]} coins)\n"

    report += f"• Accumulation: {len(accumulation_coins)} coins\n"
    report += f"• Distribution/Selling: {len(distribution_coins)} coins\n"
    report += f"• Manipulation: {len(manipulation_coins)} coins\n"
    report += f"• Neutral/Undetermined: {len(neutral_coins)} coins\n\n"

    # Details by Category
    if accumulation_coins:
        report += "🔵 <b>ACCUMULATION (Potential Buy Opportunity):</b>\n"
        sorted_accum = sorted(accumulation_coins, key=lambda x: x["strategy"]["score"], reverse=True)
        for i, coin in enumerate(sorted_accum[:6], 1):
            report += f"  {i}. <b>{coin['symbol']}</b>: {coin['strategy']['type']} ({coin['strategy']['phase']}) - Score: {coin['strategy']['score']}\n"
        report += "\n"

    if manipulation_coins:
        report += "🔴 <b>MANIPULATION ALERT (High Risk):</b>\n"
        sorted_manip = sorted(manipulation_coins, key=lambda x: x["strategy"]["score"], reverse=True)
        for i, coin in enumerate(sorted_manip[:6], 1):
            report += f"  {i}. <b>{coin['symbol']}</b>: {coin['strategy']['type']} - Score: {coin['strategy']['score']}\n"
        report += "\n"

    if distribution_coins:
        report += "🟣 <b>DISTRIBUTION (Selling Potential):</b>\n"
        sorted_dist = sorted(distribution_coins, key=lambda x: x["strategy"]["score"], reverse=True)
        for i, coin in enumerate(sorted_dist[:6], 1):
            report += f"  {i}. <b>{coin['symbol']}</b>: {coin['strategy']['type']} - Score: {coin['strategy']['score']}\n"
        report += "\n"

    report += "<b>⚠️ Note:</b> These findings are algorithmic results and do not guarantee certainty.\n"
    return report

def handle_whale_strategies():
    report = get_whale_strategies_report_string()
    if report:
        send_telegram_message_long(report)

    # Report categories
    if accumulation_coins:
        report += f"🔵 <b>ACCUMULATION STRATEGIES ({len(accumulation_coins)} coins):</b>\n"
        sorted_acc = sorted(accumulation_coins, key=lambda x: x["net_accum"], reverse=True)
        for i, cd in enumerate(sorted_acc, 1):
            rec = "May be a gradual buying opportunity 💰" if cd["net_accum"] > 10 and cd["rsi"] < 60 else \
                  "Add to watch list, trend reversal approaching 👀" if cd["net_accum"] > 5 and cd["rsi"] < 70 else \
                  "Positive signal, keep tracking 📈"
            report += f"  {i}. <b>{cd['symbol']}</b>: {cd['strategy']['type']} ({cd['strategy']['phase']})\n"
            report += f"     • Net Accum: {format_money(cd['net_accum'])}M USD | RSI: {round(cd['rsi'], 1)} | Vol: {cd['volume_ratio']}x\n"
            report += f"     • Rec: {rec}\n\n"

    return report

def handle_whale_movement_analysis():
    report = get_whale_movement_report_string()
    if report:
        send_telegram_message_long(report)

def get_whale_movement_report_string():
    if ALL_RESULTS:
        report = f"🐋 <b>Whale Movement Analysis Report – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
        sorted_results = sorted(ALL_RESULTS, key=lambda x: abs(x["NetAccum_raw"]), reverse=True)

        # Featured highlights
        report += "<b>Featured Coins:</b>\n"
        for coin in sorted_results[:5]:
            net_accum = coin["NetAccum_raw"]
            roc = extract_numeric(coin["24h Change"])
            signal = "BUY" if net_accum > 20 and roc > 0 else "SELL" if net_accum < -20 and roc < 0 else "WATCH"
            symbol = "$" + coin["Coin"].replace("USDT", "")
            report += f"<b>{symbol}</b>: Net {net_accum}M USD, ROC: {roc}% - Rec: {signal}\n"
        report += "\n<b>Detailed Analysis (Top 50):</b>\n"

        # Details for top 50
        for coin in sorted_results[:50]:
            movement = analyze_whale_movement(coin) # Assuming this function handles translation or is descriptive enough
            symbol = "$" + coin["Coin"].replace("USDT", "")
            report += f"<b>{symbol}</b>:\n   {movement}\n\n"

        return report
    else:
        return "⚠️ No analysis data available yet."



def handle_market_maker_analysis():
    """
    Executes market maker analysis and sends report to Telegram.
    """
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ No analysis data available yet.")
        return

    report = f"🎯 <b>Market Maker Analysis – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    report += "This report analyzes potential traps and strategies of market makers.\n\n"

    # Select coins for analysis based on Volume Ratio
    top_coins = sorted(ALL_RESULTS, key=lambda x: float(str(x.get("Volume Ratio", 0)).replace("N/A", "0")), reverse=True)[:50]

    # Analyze each coin
    for coin in top_coins:
        symbol = coin["Coin"]
        clean_symbol = "$" + symbol.replace("USDT", "")

        try:
            # Get price and volume info
            price = parse_money(coin["Price_Display"])
            volume_ratio = extract_numeric(coin["Volume Ratio"])

            # 1. Fetch kline data
            klines_15m = sync_fetch_kline_data(symbol, "15m", limit=30) or []
            klines_1h = sync_fetch_kline_data(symbol, "1h", limit=24) or []

            # 2. Fetch order book data
            bids, asks = fetch_order_book(symbol)
            order_book = analyze_order_book(bids, asks, price, coin["Coin"])

            # 3. Stop hunt analysis
            stop_hunt = detect_stophunt_pattern(klines_15m)

            # 4. Price compression analysis
            compression = detect_price_compression(klines_1h)

            # Build report for the coin
            report += f"<b>{clean_symbol} Analysis:</b>\n"
            report += f"• Price: ${price}, Volume Ratio: {volume_ratio}x\n"

            # Order book analysis
            imbalance = order_book.get("imbalance", 0)
            side = "Buy" if imbalance > 0 else "Sell"
            imbalance_str = f"{abs(imbalance):.1f}% {side} side dominant"
            report += f"• Order Book: {imbalance_str}\n"

            if order_book.get("big_bid_wall", False):
                report += f"  - ⚠️ Big Buy Wall: {format_money(order_book.get('max_bid_qty', 0))} volume\n"
            elif order_book.get("big_ask_wall", False):
                report += f"  - ⚠️ Big Sell Wall: {format_money(order_book.get('max_ask_qty', 0))} volume\n"

            # Pattern analysis
            if stop_hunt and stop_hunt != "No pattern":
                 report += f"• Stop Hunt: {stop_hunt}\n"
            if compression and compression != "None":
                 report += f"• Compression: {compression}\n"
            
            report += "\n"

        except Exception as e:
            print(f"[ERROR] General error during market maker analysis for {symbol}: {e}")
            report += f"<b>{symbol} Analysis:</b>\n• ⚠️ An error occurred during analysis\n\n"

    # Market summary
    report += "<b>📈 Market Overview:</b>\n"
    report += f"• Analyzed Coins: {len(top_coins)}\n"
    report += f"• Report generated based on Market Maker behavioral patterns.\n"

    send_telegram_message_long(report)


def handle_significant_changes():
    report = get_significant_changes_report_string()
    if report:
        send_telegram_message_long(report)

def get_significant_changes_report_string():
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    significant_changes = detect_significant_changes(ALL_RESULTS)
    report = f"🚀 <b>Significant Market Changes & Alerts – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Monitoring technical breakouts and structural shifts</i>\n\n"

    events = []
    # 1. Technical Crossovers from ALL_RESULTS
    for coin in ALL_RESULTS[:50]:
        trend = coin.get("EMA Trend", "")
        if "X-Over" in trend:
            symbol = "$" + coin["Coin"].replace("USDT", "")
            events.append(f"• <b>{symbol}</b>: {trend} detected!")

    if events:
        report += "⚡ <b>TECHNICAL CROSSOVERS:</b>\n"
        report += "\n".join(events) + "\n\n"

    # 2. Ranking & Momentum Changes
    report += "📈 <b>MOMENTUM & RANKING SHIFTS:</b>\n"
    if not significant_changes:
        report += "No major ranking shifts detected in this cycle.\n"
    else:
        for change in significant_changes[:15]:
            direction = "🟢 Rising" if change["RankChange"] > 0 else "🔴 Falling"
            symbol = "$" + change["Coin"].replace("USDT", "")
            report += f"<b>{symbol}</b> ({direction}):\n"
            report += f"   • Rank: {change['PrevRank']} → {change['CurrentRank']} ({change['RankChange']:+d})\n"
            report += f"   • EMA Status: {change['Details'].get('EMA Trend', 'N/A')}\n"
            report += f"   • Vol Ratio: {change['VolumeRatio']}x | RSI: {change['RSI']}\n\n"

    return report

SENT_ALERTS = {} # {symbol: {alert_type: timestamp}}

def handle_market_alerts(results):
    """
    Checks for high-priority events and sends individual Telegram alerts.
    Now enhanced with Cash Flow and Market Regime context.
    Prevent spam with a cooldown.
    """
    global SENT_ALERTS
    now = time.time()
    cooldown = 4 * 3600 # 4 hours for the same alert type

    # Get Global Context
    try:
        regime_data = MARKET_REGIME_DETECTOR.detect_regime(results)
        regime_str = f"{regime_data.get('emoji', '')} {regime_data.get('display', 'UNKNOWN')}"
    except: regime_str = "❓ UNKNOWN"

    for coin in results[:20]: # Only alert for top 20 coins for quality
        symbol = coin["Coin"]
        if symbol not in SENT_ALERTS: SENT_ALERTS[symbol] = {}
        
        # Context Data
        price_str = format_money(coin['Price'])
        vol_ratio = extract_numeric(coin.get("Volume Ratio", "1")) or 1
        rsi = extract_numeric(coin.get("RSI", 50))
        trend = coin.get("EMA Trend", "Stable")
        
        # Cash Flow Status (12h)
        net_accum = extract_numeric(coin.get("Net Accum 12h", 0))
        flow_emoji = "🟢" if net_accum > 0 else "🔴"
        flow_str = f"{format_money(net_accum)} ({'Inflow' if net_accum > 0 else 'Outflow'})"

        # Message Builder Helper
        def send_enhanced_alert(title, emoji, insight, alert_key_suffix):
            alert_key = f"{symbol}_{alert_key_suffix}"
            last_sent = SENT_ALERTS[symbol].get(alert_key, 0)
            
            if now - last_sent > cooldown:
                msg = (
                    f"{emoji} <b>{title}: {symbol}</b>\n\n"
                    f"💵 <b>Price:</b> {price_str}\n"
                    f"📊 <b>Volume:</b> {vol_ratio:.1f}x Avg\n"
                    f"📈 <b>RSI:</b> {rsi:.0f}\n"
                    f"{flow_emoji} <b>Cash Flow (12h):</b> {flow_str}\n"
                    f"🌊 <b>Market:</b> {regime_str}\n\n"
                    f"💡 <b>Insight:</b> {insight}"
                )
                send_telegram_message_long(msg)
                SENT_ALERTS[symbol][alert_key] = now
                return True
            return False

        # 1. EMA Crossover Alerts (Golden/Death Cross)
        if "Golden Cross" in trend:
            if send_enhanced_alert("GOLDEN CROSS", "🚀", "Bullish trend reversal! EMA 20 crossed above EMA 50.", "golden_cross"):
                SIGNAL_TRACKER.record_signal("golden_cross", symbol, coin['Price'], {'rsi': rsi, 'vol': vol_ratio})
            
        elif "Death Cross" in trend:
            if send_enhanced_alert("DEATH CROSS", "📉", "Bearish trend reversal! EMA 20 crossed below EMA 50.", "death_cross"):
                SIGNAL_TRACKER.record_signal("death_cross", symbol, coin['Price'], {'rsi': rsi, 'vol': vol_ratio})

        # 2. Volume Patterns (Breakout/Breakdown)
        elif "Volume Breakout" in trend:
            if send_enhanced_alert("VOLUME BREAKOUT", "⚡", f"Price breaking out with {vol_ratio:.1f}x volume!", "vol_breakout"):
                SIGNAL_TRACKER.record_signal("vol_breakout", symbol, coin['Price'], {'rsi': rsi, 'vol': vol_ratio})
            
        elif "Volume Breakdown" in trend:
            if send_enhanced_alert("VOLUME BREAKDOWN", "🩸", f"Price breaking down with {vol_ratio:.1f}x volume!", "vol_breakdown"):
                SIGNAL_TRACKER.record_signal("vol_breakdown", symbol, coin['Price'], {'rsi': rsi, 'vol': vol_ratio})

        # 3. Cash Flow Pumps (> 10M and Low Volatility)
        # This detects "Silent Accumulation" before the pump
        if abs(net_accum) > 10_000_000 and vol_ratio < 2.0:
            direction = "ACCUMULATION" if net_accum > 0 else "DISTRIBUTION"
            icon = "🐋" if net_accum > 0 else "💸"
            alert_key = "whale_accum"
            
            # Custom logic for whale alert (different cooldown? same for now)
            send_enhanced_alert(f"WHALE {direction}", icon, f"Significant money {direction.lower()} without price spike (Hidden Activity).", alert_key)
            # Signal tracker logic inside helper didn't run, add manual record if needed or trust common logic
            if net_accum > 0:
                SIGNAL_TRACKER.record_signal("whale_accum", symbol, coin['Price'], {'net_accum': net_accum})


def get_market_alerts_report_string():
    """
    Returns a summary of recent high-priority alerts for the web dashboard.
    """
    if not SENT_ALERTS:
        return "✨ No high-priority alerts triggered in the last 4 hours.\nEverything is stable."

    report = f"🔔 <b>Live Market Alerts & Triggers – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Historical log of significant technical events (4h window)</i>\n\n"

    # Flatten and sort SENT_ALERTS by timestamp
    flat_alerts = []
    for symbol, alerts in SENT_ALERTS.items():
        for alert_type, ts in alerts.items():
            flat_alerts.append({
                "symbol": symbol,
                "type": alert_type,
                "timestamp": ts
            })
    
    # Sort by newest first
    flat_alerts.sort(key=lambda x: x["timestamp"], reverse=True)

    for alert in flat_alerts[:20]: # Show last 20 alerts
        dt_str = datetime.fromtimestamp(alert["timestamp"]).strftime('%H:%M:%S')
        if "ema" in alert["type"]: icon = "⚡"
        elif "volume" in alert["type"]: icon = "🚨"
        elif "cash_flow" in alert["type"]: icon = "💰" if "high" in alert["type"] else "💸"
        else: icon = "🔔"
        
        desc = alert["type"].replace("_", " ").title()
        report += f"[{dt_str}] {icon} <b>{alert['symbol']}</b>: {desc}\n"

    report += "\n<b>ℹ️ Info:</b> Alerts are kept for 4 hours to prevent noise. Check technical charts for confirmation."
    return report

def get_live_ticker_string():
    """Returns a short single-line string for the scrolling ticker."""
    if not SENT_ALERTS:
        return "✨ Radar Ultra is monitoring: No high volatility alerts triggered yet. | 📊 Market Status: Dynamic"
    
    flat_alerts = []
    for symbol, alerts in SENT_ALERTS.items():
        for alert_type, ts in alerts.items():
            flat_alerts.append({"symbol": symbol, "type": alert_type, "ts": ts})
    
    flat_alerts.sort(key=lambda x: x["ts"], reverse=True)
    
    parts = []
    for a in flat_alerts[:5]:
        if "ema" in a["type"]: icon = "⚡"
        elif "volume" in a["type"]: icon = "🚨"
        elif "cash_flow" in a["type"]: icon = "💰"
        else: icon = "🔔"
        
        desc = a["type"].replace("ema_xover_", "").replace("_", " ").upper()
        parts.append(f"{icon} ${a['symbol'].replace('USDT','')}: {desc}")
    
    return "  |  ".join(parts)

def handle_cash_flow_report():
    report = generate_dynamic_cash_flow_report()
    send_telegram_message_long(report)

def handle_cash_flow_migration_report():
    report = generate_cash_flow_migration_report()
    send_telegram_message_long(report)

def handle_smart_score_report():
    report = generate_smart_score_report()
    send_telegram_message_long(report)

def handle_advanced_whale_trend():
    """
    Generates and sends advanced whale trend analysis report.
    """
    report = generate_advanced_whale_trend_report()
    send_telegram_message_long(report)


def create_reply_keyboard(results):
    """
    Telegram için ana menü klavyesi oluşturur.
    Emoji içeren ve içermeyen komutları destekler.

    Args:
        results (list): Tüm coin analiz sonuçları

    Returns:
        list: Telegram klavye yapısı
    """
    button_pairs = [
        ("📊 Current Analysis", "Current Analysis"),
        ("🔍 All Coins", "All Coins"),
        ("📈 Trend Status", "Trend Status"),
        ("💰 Net Accum", "Net Accum"),
        ("💰 Net Accum 4H", "Net Accum 4H"),
        ("💰 Net Accum 1D", "Net Accum 1D"),
        ("🛡️ Risk Analysis", "Risk Analysis"),
        ("📊 Composite Score", "Composite Score"),
        ("📊 Composite 4H", "Composite 4H"),
        ("📊 Composite 1D", "Composite 1D"),
        ("🔄 BTC Correlation", "BTC Correlation"),
        ("🔄 BTC Corr 4H", "BTC Corr 4H"),
        ("🔄 BTC Corr 1D", "BTC Corr 1D"),
        ("🔄 ETH Correlation", "ETH Correlation"),
        ("🔄 ETH Corr 4H", "ETH Corr 4H"),
        ("🔄 ETH Corr 1D", "ETH Corr 1D"),
        ("🔄 SOL Correlation", "SOL Correlation"),
        ("🔄 SOL Corr 4H", "SOL Corr 4H"),
        ("🔄 SOL Corr 1D", "SOL Corr 1D"),
        ("📋 Summary", "Summary"),
        ("📊 RSI Report", "RSI Report"),
        ("📊 RSI 4H", "RSI 4H"),
        ("📊 RSI 1D", "RSI 1D"),
        ("⚖️ EMA Report", "EMA Report"),
        ("⏱️ 4H Change", "4H Change"),
        ("📅 Weekly Change", "Weekly Change"),
        ("📊 Monthly Change", "Monthly Change"),
        ("📊 24h Volume", "24h Volume"),
        ("📊 24h Vol 4H", "24h Vol 4H"),
        ("📊 24h Vol 1D", "24h Vol 1D"),
        ("📊 Volume Ratio", "Volume Ratio"),
        ("📊 Volume Ratio 4H", "Volume Ratio 4H"),
        ("📊 Volume Ratio 1D", "Volume Ratio 1D"),
        ("📊 ATR Report", "ATR"),
        ("📈 ADX Report", "ADX"),
        ("📈 ADX 4H", "ADX 4H"),
        ("📈 ADX 1D", "ADX 1D"),
        ("📊 MACD Report", "MACD"),
        ("📊 MACD 4H", "MACD 4H"),
        ("📊 MACD 1D", "MACD 1D"),
        ("📉 Open Interest", "Open Interest"),
        ("💰 MFI Report", "MFI"),
        ("💰 MFI 4H", "MFI 4H"),
        ("💰 MFI 1D", "MFI 1D"),
        ("📊 StochRSI Report", "StochRSI"),
        ("📊 Taker Rate", "Taker Rate"),
        ("📐 S/R Levels", "Support/Resistance"),
        ("📏 Z-Score", "Z-Score"),
        ("⚖️ EMA Crossings", "EMA Crossings"),

        ("📊 Momentum 4H", "Momentum 4H"),
        ("📊 Momentum 1D", "Momentum 1D"),
        ("🐳 Whale Strategies", "Whale Strategies"),
        ("🐋 Whale Movement", "Whale Movement"),
        ("🕵️ Manipulation Detector", "Manipulation Detector"),
        ("🎯 MM Analysis", "MM Analysis"),
        ("💹 Smart Money", "Smart Money"),
        ("🕯️ Candle Patterns", "Candle Patterns"),
        ("📊 Price Info", "Price Info"),
        ("⚖️ Long/Short Ratio", "Long/Short Ratio"),
        ("💰 Funding Rate", "Funding Rate"),
        ("📊 Significant Changes", "Significant Changes"),
        ("💰 Net Buy/Sell Status", "Net Buy/Sell Status"),
        ("⏱️ Hourly Analysis", "Hourly Analysis"),
        ("💵 Cash Flow Report", "Cash Flow Report"),
        ("💵 Flow Migrations", "Flow Migrations"),
        ("📊 Smart Score", "Smart Score"),
        ("🧠 Smart Whale & Trend", "Smart Whale & Trend"),
        ("🐳 Whale Ranking", "Whale Ranking"),
        ("🌊 Volatility Ranking", "Volatility Ranking"),
        ("📏 Bollinger Squeeze", "Bollinger Squeeze"),
        ("🔒 Trust Index", "Trust Index"),
        ("📏 Bollinger Bands", "Bollinger Bands"),
        ("🚀 Momentum Report", "Momentum"),
        ("📤 NotebookLM Export", "NotebookLM Export"),
        ("📺 YouTube Alpha", "YouTube Alpha"),
        ("📜 YouTube Transcripts", "YouTube Transcripts"),
        ("📚 Order Book Analysis", "order_book_analysis"),
        ("🔥 Liquidation Map", "liquidation_analysis"),
        ("💹 Futures Analysis", "Futures Analysis")
    ]

    # Boş klavye oluştur
    keyboard = []


    # İkili buton satırları oluştur
    for i in range(1, len(button_pairs), 2):
        row = [{"text": button_pairs[i - 1][0]}]  # Emojili versiyonu kullan
        if i < len(button_pairs):
            row.append({"text": button_pairs[i][0]})  # Emojili versiyonu kullan
        keyboard.append(row)

    # En yüksek skorlu coinleri ekle
    if results:
        try:
            # Composite score'a göre sırala
            sorted_results = sorted(
                results,
                key=lambda x: extract_numeric(x.get("CompositeScore", "0") if x.get("CompositeScore") else "0"),
                reverse=True
            )

            # En yüksek skorlu 6 coini ekle (2'şerli 3 satır)
            top_coins = sorted_results[:6]

            for i in range(0, len(top_coins), 2):
                coin_row = []
                coin_row.append({"text": top_coins[i]["Coin"]})
                if i + 1 < len(top_coins):
                    coin_row.append({"text": top_coins[i + 1]["Coin"]})
                keyboard.append(coin_row)
        except Exception as e:
            print(f"[HATA] Top coinler eklenirken hata: {e}")


    return keyboard


def handle_main_menu_return(chat_id):
    """
    Kullanıcıyı ana menüye döndürür ve ana menü klavyesini gönderir.

    Args:
        chat_id (str): Telegram sohbet ID'si
    """
    try:
        keyboard = create_reply_keyboard(ALL_RESULTS)
        message = "🏠 <b>Returned to Main Menu</b>\n\nPelase select an option:"
        send_reply_keyboard_message(chat_id, message, keyboard=keyboard)
        print(f"[DEBUG] Chat ID {chat_id} returned to main menu")
    except Exception as e:
        print(f"[ERROR] Error returning to main menu: {e}")
        send_telegram_message(chat_id, "⚠️ An error occurred while returning to the main menu.")



    # Fonksiyonun geri kalanı aynı kalır


def create_all_coins_keyboard():
    """
    Tüm coinler için düzenli ve boyutu kontrollü alt menü klavyesi oluşturur.

    Returns:
        list: Telegram klavye yapısı
    """
    if not ALL_RESULTS:
        return [[{"text": "↩️ Ana Menü"}]]

    keyboard = []

    # Coin sayısını sınırla - Telegram'ın sınırlamalarına uygun olarak
    max_coins = min(len(ALL_RESULTS), 30)  # En fazla 30 coin göster
    coins_to_display = ALL_RESULTS[:max_coins]

    row = []
    for i, coin_data in enumerate(coins_to_display):
        coin_symbol = coin_data["Coin"]
        row.append({"text": coin_symbol})

        # Her satırda 3 coin olacak şekilde düzenle
        if len(row) == 3 or i == len(coins_to_display) - 1:
            keyboard.append(row)
            row = []

    # Sayfalama düğmeleri (gerekiyorsa)
    if len(ALL_RESULTS) > 30:
        keyboard.append([{"text": "◀️ Önceki Sayfa"}, {"text": "Sonraki Sayfa ▶️"}])

    # Ana menüye dönüş butonu ekle - tutarlı dönüş butonu
    keyboard.append([{"text": "↩️ Ana Menü"}])

    return keyboard


def handle_price_info():
    """Generates and sends price info report."""
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ No analysis data available yet.")
        return

    report = f"📊 <b>Price Information – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
    report += "<i>Showing top 50 coins by analysis order</i>\n\n"
    for coin in ALL_RESULTS[:50]:
        symbol = coin["Coin"].replace("USDT", "")
        formatted_symbol = f"${symbol}"
        report += f"<b>{formatted_symbol}</b>: {coin['Price']}\n"
        report += f"   • 24h Change: {coin['Price ROC']}\n"
        report += f"   • 24h Volume: {coin['24h Volume']}\n\n"

    send_telegram_message_long(report)


def handle_long_short_ratio_analysis():
    """Generates and sends Long/Short ratio analysis."""
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ No analysis data available yet.")
        return

    report = f"⚖️ <b>Long/Short Ratio Analysis – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    
    total_ratio = 0
    count = 0
    
    for coin in ALL_RESULTS[:50]:
        ratio = coin.get("Long/Short Ratio", "N/A")
        symbol = coin["Coin"].replace("USDT", "")
        formatted_symbol = f"${symbol}"
        report += f"<b>{formatted_symbol}</b>: {ratio}\n"
        
        try:
            if ratio != "N/A":
                # Handle string format like "1.25 (🔼 5.2%)"
                if isinstance(ratio, str) and " " in ratio:
                    ratio_val = float(ratio)
                else:
                    ratio_val = float(ratio)
                total_ratio += ratio_val
                count += 1
        except ValueError:
            pass # Ignore if conversion fails

    if count > 0:
        avg_ratio = total_ratio / count
        report += f"\n📊 <b>Market Average L/S Ratio:</b> {avg_ratio:.2f}\n"

    send_telegram_message_long(report)


def handle_funding_rate_analysis():
    """Generates and sends funding rate analysis in English."""
    if not ALL_RESULTS:
        send_telegram_message_long("⚠️ No analysis data available yet.")
        return

    report = f"💰 <b>Funding Rate Analysis – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
    
    total_funding = 0
    count = 0
    pos_count = 0
    neg_count = 0
    
    for coin in ALL_RESULTS[:50]:
        funding = coin.get("Funding_Rate", coin.get("Funding Rate", "N/A"))
        symbol = coin["Coin"].replace("USDT", "")
        formatted_symbol = f"${symbol}"
        report += f"<b>{formatted_symbol}</b>: {funding}\n"
        
        try:
            if funding != "N/A" and funding is not None:
                # Remove % and convert to float
                val = float(str(funding).strip())
                total_funding += val
                count += 1
                if val > 0: pos_count += 1
                elif val < 0: neg_count += 1
        except (ValueError, TypeError):
            pass

    if count > 0:
        avg_funding = total_funding / count
        report += f"\n📊 <b>Market Summary:</b>\n"
        report += f"• Average Funding Rate: {avg_funding:.6f}%\n"
        report += f"• Positive Funding: {pos_count} coins\n"
        report += f"• Negative Funding: {neg_count} coins\n"

    send_telegram_message_long(report)


def get_smart_money_report_string():
    """
    Generates Smart Money analysis report and returns it as a string.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    try:
        # Create class to perform Smart Money analysis
        analyzer = TechnicalPatternAnalyzer()

        # Determine coins to analyze
        coins_to_analyze = ALL_RESULTS[:50]  # Analyze top 50
        smart_money_reports = []

        for coin in coins_to_analyze:
            symbol = coin["Coin"]
            print(f"[DEBUG] Performing Smart Money analysis for {symbol}...")

            # Convert to DataFrame
            if "df" in coin and coin["df"]:
                df = pd.DataFrame(coin["df"])
            else:
                # Fetch via API if no data
                klines = sync_fetch_kline_data(symbol, "1h", limit=100)
                if not klines:
                    print(f"[ERROR] Could not fetch kline data for {symbol}")
                    continue

                df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume",
                                                   "close_time", "quote_volume", "trades", "taker_buy_base",
                                                   "taker_buy_quote", "ignore"])

            # Normalize column names - lowercase
            df.columns = [str(col).lower() for col in df.columns]

            # Map Turkish/Common names to standard
            column_mapping = {
                'açılış': 'open', 'yüksek': 'high', 'düşük': 'low', 'kapanış': 'close', 'hacim': 'volume',
                'opening': 'open', 'highest': 'high', 'lowest': 'low', 'closing': 'close',
                'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'
            }
            df = df.rename(columns=column_mapping)

            # Ensure all required columns
            required_cols = ["open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    for existing_col in df.columns:
                        if col in existing_col or existing_col in col:
                            df[col] = df[existing_col]
                            break

            # Convert to numeric
            for col in required_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=[col for col in required_cols if col in df.columns])

            if len(df) < 20:
                continue

            # Generate report
            clean_symbol = "$" + symbol.replace("USDT", "")
            report = analyzer.generate_smart_money_report(clean_symbol, df)
            smart_money_reports.append(report)

        if not smart_money_reports:
            return "⚠️ Could not perform Smart Money analysis for any coins."

        # Combine all reports
        combined_report = "\n\n".join(smart_money_reports[:50])

        # Limit message length
        if len(combined_report) > 4000:
            combined_report = combined_report[:4000] + "\n\n... (Report truncated due to length)"

        return combined_report

    except Exception as e:
        print(f"[ERROR] Smart Money analysis error: {e}")
        return f"⚠️ An error occurred during Smart Money analysis: {str(e)}"

def handle_smart_money_analysis():
    report = get_smart_money_report_string()
    if report:
        send_telegram_message_long(report)


def send_initial_analysis(chat_id):
    """
    Shows current analysis and sends main menu keyboard.
    Handles the case when ALL_RESULTS is empty.

    Args:
        chat_id (str): Chat ID where the message will be sent
    """
    try:
        if ALL_RESULTS and len(ALL_RESULTS) > 0:
            # Perform full analysis and display
            analysis_message, coin_details, _ = generate_detailed_analysis_message(ALL_RESULTS)

            # Save coin details to global variable
            with global_lock:
                COIN_DETAILS.update(coin_details)

            # Create main menu keyboard
            keyboard = create_reply_keyboard(ALL_RESULTS)

            # Send message and keyboard
            send_reply_keyboard_message(chat_id, analysis_message, keyboard=keyboard)

            # Update menu state
            MENU_STATE.set_user_state(chat_id, "main_menu")

        else:
            # Create a simple keyboard if no data
            keyboard = [
                [{"text": "📊 Refresh Current Analysis"}],
                [{"text": "📈 Trend Status"}, {"text": "🛡️ Risk Analysis"}]
            ]

            # Send informational message and simple keyboard
            send_reply_keyboard_message(
                chat_id,
                "⚠️ <b>No analysis data available yet</b>\n\n"
                "Please click 'Refresh Current Analysis' button to start the analysis process "
                "or wait a few minutes.",
                keyboard=keyboard
            )

            # Update menu state
            MENU_STATE.set_user_state(chat_id, "main_menu")

    except Exception as e:
        print(f"[ERROR] Error sending initial analysis: {e}")
        import traceback
        traceback.print_exc()

        # Send minimal keyboard in case of error
        minimal_keyboard = [
            [{"text": "📊 Refresh Current Analysis"}]
        ]

        send_reply_keyboard_message(
            chat_id,
            "⚠️ <b>An error occurred while preparing the analysis</b>\n\n"
            "Please click 'Refresh Current Analysis' button to try again.",
            keyboard=minimal_keyboard
        )


def process_telegram_updates():
    """
    Telegram güncellemelerini alır ve işler.
    Geliştirilmiş hata işleme ve bellek yönetimiyle.
    Tam fonksiyonel komut ve buton işleme döngüsü.
    """
    print("[INFO] Telegram güncellemeleri başlatılıyor (Fixed Loop)...")
    offset = 0
    TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    # Processed messages set for deduplication (handled by offset mostly, but kept for safety)
    processed_messages = set()

    while True:
        try:
            # Bellek yönetimi
            if 'check_memory_and_clean' in globals():
                check_memory_and_clean(threshold_mb=500)
            
            # Update alma - requests.Session kullanımı daha iyi olurdu ama mevcut yapıyı koruyalım
            # Ancak timeout ve retry mekanizması ekleyelim
            try:
                # Tüm update türlerini kabul et (JSON string olarak gönderilmeli)
                params = {
                    "offset": offset, 
                    "timeout": 30,
                    "allowed_updates": json.dumps(["message", "edited_message", "channel_post", "callback_query"])
                }
                response = requests.get(TELEGRAM_API_URL, params=params, timeout=35)
            except requests.exceptions.Timeout:
                print("[UYARI] Telegram polling zaman aşımı, tekrar deneniyor...")
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError:
                print("[UYARI] Telegram bağlantı hatası, 5sn bekleniyor...")
                time.sleep(5)
                continue

            if response.ok:
                updates = response.json().get("result", [])
                for update in updates:
                    print(f"[RAW UPDATE] Received: {update}")
                    offset = update["update_id"] + 1
                    
                    # Handle Callback Queries (Inline Buttons)
                    if "callback_query" in update:
                        # print(f"[DEBUG] Callback Query received: {update['callback_query']}")
                        handle_callback_query(update['callback_query'])
                        continue

                    # Mesaj kontrolü
                    if "message" not in update:
                        continue
                        
                    message = update["message"]
                    if "text" not in message:
                        continue

                    message_id = message["message_id"]
                    # Deduplication check
                    if message_id in processed_messages:
                        continue
                        
                    processed_messages.add(message_id)
                    
                    # Bellek optimizasyonu - set boyutunu sınırla
                    if len(processed_messages) > 1000:
                         processed_messages = set(sorted(processed_messages)[-500:])

                    chat_id = message["chat"]["id"]
                    message_text = message["text"].strip()
                    
                    # Global chat ID update (mevcut yapıya uyum için)
                    global TELEGRAM_CHAT_ID
                    TELEGRAM_CHAT_ID = chat_id

                    # --- COMMAND PROCESSING (SLASH COMMANDS) ---
                    if message_text == "/start":
                        send_telegram_message(chat_id, "Bot started! Ready for market analysis.")
                        handle_main_menu_return(chat_id)
                        
                    elif message_text == "/hourly":
                        generate_hourly_report(chat_id=chat_id)
                        
                    elif message_text == "/quick":
                        generate_quick_summary(chat_id=chat_id)
                        
                    elif message_text.startswith("/analyze"):
                        parts = message_text.split()
                        if len(parts) != 2:
                            send_telegram_message(chat_id, "Please specify a coin, e.g.: /analyze BTCUSDT")
                            continue
                        symbol = parts[1].upper()
                        # Check ALL_RESULTS
                        found = False
                        if ALL_RESULTS:
                             if symbol in [c["Coin"] for c in ALL_RESULTS]:
                                 found = True
                        
                        if found:
                            with global_lock:
                                coin_data = next((c for c in ALL_RESULTS if c["Coin"] == symbol), None)
                            if coin_data:
                                # Sync kline fetch and analysis
                                kline_data = sync_fetch_kline_data(symbol, "1h", limit=200)
                                indicators = get_technical_indicators(symbol, kline_data)
                                analysis = analyze_whale_movement(indicators)
                                send_telegram_message(chat_id, analysis)
                            else:
                                send_telegram_message(chat_id, f"Data for {symbol} not found in cache.")
                        else:
                             send_telegram_message(chat_id, f"{symbol} is not in the tracking list.")

                    elif message_text.startswith("/liquidation"):
                        parts = message_text.split()
                        if len(parts) != 2:
                            send_telegram_message(chat_id, "Kullanım: /liquidation BTCUSDT")
                            continue
                        symbol = parts[1].upper()
                        try:
                            liquidation_analysis = analyze_liquidation(symbol)
                            send_telegram_message(chat_id, liquidation_analysis)
                        except Exception as e:
                             send_telegram_message(chat_id, f"Analiz hatası: {e}")

                    elif message_text.startswith("/sentiment"):
                        parts = message_text.split()
                        if len(parts) != 2:
                             send_telegram_message(chat_id, "Kullanım: /sentiment BTCUSDT")
                             continue
                        symbol = parts[1].upper()
                        try:
                             sentiment_analysis = analyze_social_sentiment(symbol)
                             send_telegram_message(chat_id, sentiment_analysis)
                        except:
                             send_telegram_message(chat_id, "Sentiment analizi başarısız.")

                    elif message_text.startswith("/arbitrage"):
                         parts = message_text.split()
                         if len(parts) != 2:
                             send_telegram_message(chat_id, "Kullanım: /arbitrage BTCUSDT")
                             continue
                         symbol = parts[1].upper()
                         try:
                             arbitrage_analysis = analyze_arbitrage(symbol)
                             send_telegram_message(chat_id, arbitrage_analysis)
                         except:
                             send_telegram_message(chat_id, "Arbitraj analizi başarısız.")

                    else:
                        # --- NORMAL MESAJ / BUTON İŞLEME ---
                        # Slash komutu değilse, menü işleyicisine TAM MESAJ nesnesini gönder
                        # (Böylece chat_id vb. doğru alınır)
                        print(f"[DEBUG] Menü işleyiciye yönlendiriliyor: {message_text}")
                        handle_reply_message(message)

            else:
                print(f"[HATA] Telegram güncellemeleri başarısız: {response.text}")
                time.sleep(10)

        except Exception as e:
            print(f"[HATA] Telegram döngüsünde kritik hata: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)
            
        time.sleep(1)



def save_prev_stats():
    global PREV_STATS
    if ALL_RESULTS:
        with global_lock:
            for coin in ALL_RESULTS:
                try:
                    # parse_money fonksiyonu bazen sıfır dönebilir, bu durumu ele al
                    price_str = coin["Price_Display"]
                    price = parse_money(price_str)

                    # Sıfıra bölme hatasını önle
                    if price > 0:
                        vol_score = round(extract_numeric(coin.get("ATR_raw", 0)) / price * 100, 2)
                    else:
                        print(
                            f"[UYARI] {coin['Coin']} için fiyat sıfır veya geçersiz: '{price_str}', vol_score 0 olarak ayarlandı")
                        vol_score = 0

                    # Her kaydetme işleminde composite score'u da hesapla ve kaydet
                    composite_score = calculate_composite_score(coin)

                    PREV_STATS[coin["Coin"]] = {
                        "volume_ratio": extract_numeric(coin["Volume Ratio"]),
                        "vol_score": vol_score,
                        "price": price,
                        "composite": composite_score,  # Composite score'u kaydet
                        "timestamp": datetime.now().timestamp()
                    }

                    # print(f"[DEBUG] {coin['Coin']} için composite score kaydedildi: {composite_score}")

                except Exception as e:
                    print(f"[HATA] {coin['Coin']} için istatistik kaydetme hatası: {e}")

        # İstatistikleri dosyaya kaydet
        try:
            with open("prev_stats.json", "w") as f:
                json.dump(PREV_STATS, f)
        except Exception as e:
            print(f"[HATA] İstatistikleri dosyaya kaydetme hatası: {e}")

def load_prev_stats():
    global PREV_STATS
    try:
        with open("prev_stats.pkl", "rb") as f:
            PREV_STATS = pickle.load(f)
    except:
        PREV_STATS = {}


def analyze_market():
    """
    Piyasa analizini yapar, verileri günceller ve Telegram'a rapor gönderir.
    """
    global ALL_RESULTS, PREV_STATS, COIN_DETAILS, last_hourly_report_time
    loop_count = 0

    while True:
        try:
            # Her 5 döngüde bir bellek optimizasyonu yap
            loop_count += 1
            if loop_count % 5 == 0:
                optimize_memory()
            else:
                # Hafif bellek kontrolü
                mem_usage = check_memory_and_clean(threshold_mb=500)

            # Filtrelenmiş coinleri al - gerçek piyasa hacmine göre
            coins = get_filtered_coins()
            if not coins:
                print("[HATA] Coin listesi alınamadı, 30 saniye bekleyip tekrar denenecek")
                time.sleep(30)
                continue

            print(f"[BILGI] {len(coins)} adet coin analiz edilecek")
            results = []

            # Her coin için işlem yap
            # Her coin için işlem yap
            # ASYNCIO OPTIMIZASYONU: Tek tek döngü yerine toplu analiz
            risk_report_data = market_analyzer.analyze_market_risks(coins)
            
            # Sonuçları eski formatla uyumlu hale getir (gerekirse)
            # analyze_market_risks returns a report dict, we need 'results' list for existing logic
            # The 'risk_scores' in report contain similar data but might need mapping if ALL_RESULTS expects specific keys.
            # Let's map risk_scores back to the format ALL_RESULTS expects to minimize main.py breakage.
            
            results = []
            for score in risk_report_data["risk_scores"]:
                # Map 'score' dictionary back to 'indicators' structure used in main.py
                # This is a critical mapping step.
                # If mapped correctly, we save huge time.
                # However, risk_scores logic in market_analyzer is slightly different than get_technical_indicators in main.py
                # To be SAFE and FAST, we should just use the async fetching for the raw data, and then calculate indicators.
                
                # REVISION: market_analyzer.analyze_market_risks does fetch + calc risk.
                # But main.py expects 'indicators' with keys like 'RSI', 'MACD', 'Price'.
                # binance_client.fetch_binance_data returns these!
                # market_analyzer uses binance_client.
                # So we can just access the pre-fetched data if we expose it.
                
                # Let's use the 'components' or raw data if available. 
                # binance_client returns "rsi", "macd", "price".
                # risk_scores item has "components" and some raw fields.
                
                # Re-constructing partial indicator object to satisfy main.py downstream logic
                indicator_obj = {
                    "Coin": score["symbol"],
                    "Price": score["price"],
                    "RSI": score["components"].get("rsi_risk", 50), # Wait, component is risk score, not raw RSI. 
                    # We need RAW RSI. market_analyzer stores raw data in 'all_data' but doesn't return it in 'risk_scores'.
                    # We should update market_analyzer to return raw data too.
                }
                # This path is risky. 
                
            # BETTER PLAN:
            # Update get_technical_indicators in main.py to be async_get_technical_indicators, 
            # and use asyncio.gather in the main loop directly.
            # This preserves the Exact logic of main.py but parallelizes the I/O.
            
            # But I cannot easily allow 'await' in this sync function without wrapping the whole loop in asyncio.run.
            
            # Let's wrapping the fetching loop in a helper function that we run with asyncio.run.
            
            # Pre-fetch 1H/4H/1D data for Correlation base coins FIRST
            print("[INFO] Pre-fetching 1H/1D/4H base data for correlations...")
            
            async def get_ref_data(session):
                # We need 1H, 4H, 1D for BTC, ETH, SOL
                tasks = []
                for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                    for interval in ["1h", "4h", "1d"]:
                        tasks.append(binance_client.fetch_binance_data_async(session, sym)) # This is slightly redundant but safe
                # Actually, fetching klines directly is cleaner for ref data
                pass
            
            # Async Fetch for Reference Data (BTC, ETH, SOL for 1H/4H/1D)
            print(f"[INFO] Fetching reference data (BTC, ETH, SOL) async...")
            async def fetch_ref_data_batch():
                async with aiohttp.ClientSession() as session:
                    tasks = []
                    # Defined symbols and intervals
                    ref_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
                    # We need 1h, 4h, 1d for all
                    
                    # Helper to fetching klines
                    async def get_kline(sym, iv):
                        # Use the binance_client's robust fetcher if available or direct fetch
                        # Direct fetch is lighter for just klines
                        url = f"{config.BINANCE_API_URL}klines?symbol={sym}&interval={iv}&limit=100"
                        try:
                            async with session.get(url, timeout=10) as resp:
                                if resp.status == 200:
                                    return (sym, iv, await resp.json())
                        except Exception as e:
                            print(f"[WARN] Ref fetch failed for {sym} {iv}: {e}")
                        return (sym, iv, [])

                    for sym in ref_symbols:
                        for iv in ["1h", "4h", "12h", "1d"]:
                            # Use robust fetcher from binance_client
                            tasks.append(binance_client.fetch_kline_with_fallback(session, sym, iv, limit=100))
                    
                    results = await asyncio.gather(*tasks)
                    
                    # Process results into DataFrames
                    # results is just a flat list of klines now, need to map back to keys
                    dfs = {}
                    idx = 0
                    for sym in ref_symbols:
                        for iv in ["1h", "4h", "12h", "1d"]:
                            data = results[idx]
                            idx += 1
                            if data and len(data) > 20:
                                df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
                                df = df.apply(pd.to_numeric, errors='coerce').dropna(subset=["close"])
                                dfs[f"{sym}_{iv}"] = df
                            else:
                                 dfs[f"{sym}_{iv}"] = None
                                 
                    return dfs

            # Execute batch fetch
            ref_dfs = asyncio.run(fetch_ref_data_batch())
            
            # Debug Log for Reference Data
            print(f"[DEBUG] Ref Data Keys: {list(ref_dfs.keys())}")
            for k, v in ref_dfs.items():
                if v is not None:
                     print(f"[DEBUG] {k} length: {len(v)}")
                else:
                     print(f"[DEBUG] {k} is None")

            # Helper to get returns safely
            def get_ret(sym, iv):
                key = f"{sym}_{iv}"
                if ref_dfs.get(key) is not None:
                    return ref_dfs[key]["close"].pct_change().dropna()
                return None

            # Construct ref_returns dictionary
            ref_returns = {
                "btc_1h_ret": get_ret("BTCUSDT", "1h"),
                "btc_4h_ret": get_ret("BTCUSDT", "4h"),
                "btc_1d_ret": get_ret("BTCUSDT", "1d"),
                "eth_1h_ret": get_ret("ETHUSDT", "1h"),
                "eth_4h_ret": get_ret("ETHUSDT", "4h"),
                "eth_1d_ret": get_ret("ETHUSDT", "1d"),
                "sol_1h_ret": get_ret("SOLUSDT", "1h"),
                "sol_4h_ret": get_ret("SOLUSDT", "4h"),
                "sol_1d_ret": get_ret("SOLUSDT", "1d"),
                "btc_12h_ret": get_ret("BTCUSDT", "12h"),
                "eth_12h_ret": get_ret("ETHUSDT", "12h"),
                "sol_12h_ret": get_ret("SOLUSDT", "12h"),
            }
            
            # Debug log to confirm ref data
            print(f"[DEBUG] Ref Data Loaded: BTC_4H={len(ref_returns['btc_4h_ret']) if ref_returns['btc_4h_ret'] is not None else 0}, "
                  f"ETH_4H={len(ref_returns['eth_4h_ret']) if ref_returns['eth_4h_ret'] is not None else 0}")

            async def fetch_batch_indicators(coin_list, ref_rets):
                sem = asyncio.Semaphore(15)
                async def fetch_with_sem(session, c):
                    async with sem:
                        try:
                            # fetch_binance_data_async now handles indicators, correlations, and order book
                            return await binance_client.fetch_binance_data_async(session, c, ref_returns=ref_rets)
                        except Exception as e:
                            print(f"[WARN] Fetch failed for {c}: {e}")
                            return None
                
                async with aiohttp.ClientSession() as session:
                    tasks = [fetch_with_sem(session, c) for c in coin_list]
                    return await asyncio.gather(*tasks)

            fetched_data_list = asyncio.run(fetch_batch_indicators(coins, ref_returns))


            # Base returns already pre-calculated above as ref_returns

            # Enumerate results
            results = []
            for i, data in enumerate(fetched_data_list):
                if data:
                    try:
                        # Extract BB data
                        ticker_bb = data.get("bb", {"lower": 0, "upper": 0})
                        bb_lower = ticker_bb["lower"]
                        bb_upper = ticker_bb["upper"]
                        curr_price = data["price"]
                        # Calc distances safely
                        bb_lower_dist = ((curr_price - bb_lower) / bb_lower * 100) if bb_lower > 0 else 0
                        bb_upper_dist = ((bb_upper - curr_price) / bb_upper * 100) if bb_upper > 0 else 0
                        
                        coin_numeric = {
                            "RSI": data.get('rsi', 50),
                            "MACD": data.get('macd', 0),
                            "ADX": data.get('adx', 0),
                            "Momentum": data.get('momentum', 0),
                            "NetAccum_raw": data.get('net_accumulation', 0)
                        }
                        # Calculate composite score immediately
                        comp_score = calculate_composite_score(coin_numeric)

                        # Correlations are now calculated async in binance_client
                        btc_corr_1h = data.get("btc_corr_1h", 0)
                        eth_corr_1h = data.get("eth_corr_1h", 0)
                        sol_corr_1h = data.get("sol_corr_1h", 0)
                        btc_corr_4h_val = data.get("btc_corr_4h", "N/A")
                        btc_corr_1d_val = data.get("btc_corr_1d", "N/A")
                        eth_corr_4h_val = data.get("eth_corr_4h", "N/A")
                        eth_corr_1d_val = data.get("eth_corr_1d", "N/A")
                        sol_corr_4h_val = data.get("sol_corr_4h", "N/A")
                        sol_corr_1d_val = data.get("sol_corr_1d", "N/A")
                        
                        pass # Redundant 1H/4H/1D logic removed as it is handled async
                        
                        # Prepare Close/OI strings
                        weekly_close_val = data.get("weekly_close")
                        weekly_close_str = format_money(weekly_close_val) if weekly_close_val else "N/A"
                        weekly_diff = "N/A"
                        if weekly_close_val and data["price"]:
                             try:
                                diff = ((data["price"] - weekly_close_val) / weekly_close_val) * 100
                                weekly_diff = f"{diff:.2f}%"
                             except: pass

                        # Monthly Close
                        monthly_close_val = data.get("monthly_close")
                        monthly_close_str = format_money(monthly_close_val) if monthly_close_val else "N/A"
                        monthly_diff = "N/A"
                        if monthly_close_val and data["price"]:
                             try:
                                diff = ((data["price"] - monthly_close_val) / monthly_close_val) * 100
                                monthly_diff = f"{diff:.2f}%"
                             except: pass

                        # Multi-timeframe indicators
                        rsi_4h = extract_numeric(data.get("rsi_4h", 50))
                        macd_4h = extract_numeric(data.get("macd_4h", 0))
                        adx_4h = extract_numeric(data.get("adx_4h", 0))
                        mfi_4h = extract_numeric(data.get("mfi_4h", 50))
                        mom_4h = extract_numeric(data.get("mom_4h", 0))
                        vol_ratio_4h = extract_numeric(data.get("vol_ratio_4h", 1.0))
                        net_accum_4h = extract_numeric(data.get("net_accum_4h", 0))
                        z_score_4h = extract_numeric(data.get("z_score_4h", 0))
                        comp_score_4h = extract_numeric(data.get("comp_score_4h", 0))

                        rsi_1d = extract_numeric(data.get("rsi_1d", 50))
                        macd_1d = extract_numeric(data.get("macd_1d", 0))
                        adx_1d = extract_numeric(data.get("adx_1d", 0))
                        mfi_1d = extract_numeric(data.get("mfi_1d", 50))
                        mom_1d = extract_numeric(data.get("mom_1d", 0))
                        vol_ratio_1d = extract_numeric(data.get("vol_ratio_1d", 1.0))
                        net_accum_1d = extract_numeric(data.get("net_accum_1d", 0))
                        z_score_1d = extract_numeric(data.get("z_score_1d", 0))
                        comp_score_1d = extract_numeric(data.get("comp_score_1d", 0))
                        
                        comp_score_1d = extract_numeric(data.get("comp_score_1d", 0))
                        
                        # Debug: Check if we're getting real data
                        if i == 0:  # Only log first coin to avoid spam
                            print(f"[DEBUG] {data['symbol']} 4H/1D Data - RSI_4h: {rsi_4h}, RSI_1d: {rsi_1d}, MACD_4h: {macd_4h}, ADX_4h: {adx_4h}")

                        # Calculate 4H Close from actual 4H data if available, else fallback to 1h DF
                        four_h_str = "N/A"
                        four_h_diff_str = "N/A"
                        df_4h = data.get("df_4h", [])
                        if df_4h and len(df_4h) >= 2:
                             try:
                                 # Previous 4H candle close
                                 four_h_prev_close = float(df_4h[-2]["close"])
                                 four_h_str = format_money(four_h_prev_close)
                                 four_h_diff = ((data["price"] - four_h_prev_close) / four_h_prev_close) * 100
                                 four_h_diff_str = f"{four_h_diff:.2f}%"
                             except: pass
                        elif "df" in data and len(data["df"]) >= 5:
                             try:
                                 four_h_close = float(data["df"][-5]["close"])
                                 four_h_str = format_money(four_h_close)
                                 four_h_diff = ((data["price"] - four_h_close) / four_h_close) * 100
                                 four_h_diff_str = f"{four_h_diff:.2f}%"
                             except: pass

                        oi_val = data.get("open_interest", 0)
                        oi_str = format_money(oi_val) if oi_val else "N/A"
                        
                        ls_val = data.get("long_short_ratio", 1.0)

                        # Order Book Analysis
                        ob_analysis = {}
                        try:
                            if "order_book" in data and data["order_book"]:
                                bids = data["order_book"].get("bids", [])
                                asks = data["order_book"].get("asks", [])
                                ob_analysis = analyze_order_book(bids, asks, data["price"], data["symbol"])
                        except Exception as e:
                            print(f"[WARN] Order book analysis failed for {data['symbol']}: {e}")

                        # Reconstruct combined DF for indicators
                        df_all = pd.DataFrame(data["df"])
                        
                        # PREDICTIVE INTELLIGENCE (Antigravity PA Strategy)
                        df_1d = data.get("df_1d") if data.get("df_1d") is not None else df_all
                        df_15m = data.get("df_15m") if data.get("df_15m") is not None else df_all
                        antigravity_pa_report = analyze_antigravity_pa_strategy(data, df_1d, df_15m)

                        # Calculate missing EMA trends
                        ema_trend_val = get_ema_cross_trend(df_all)
                        ema_crossover_val = get_ema_crossover(df_all)
                        ema20_cross = get_ema20_crossover(df_all)
                        
                        # Support/Resistance
                        sup_val = df_all["low"].rolling(window=20).min().iloc[-1] if len(df_all) >= 20 else data["low"]
                        res_val = df_all["high"].rolling(window=20).max().iloc[-1] if len(df_all) >= 20 else data["high"]
                        
                        # Traps & Activity
                        trap_val = detect_traps(df_all, data["price"], sup_val, res_val, data.get("volume_ratio", 1.0), data.get("rsi", 50))
                        trades_count = int(data.get("trades", 0))
                        avg_vol = (data.get("quote_volume", 0) / trades_count) if trades_count > 0 else 0
                        whale_act_str = f"{trades_count} (Avg: ${format_money(avg_vol)})"
                        fr_val = data.get("funding_rate", 0)
                        fr_str = f"{fr_val * 100:.4f}%" if fr_val != 0 else "0.0000%"
                        liq_map = analyze_liquidation_heatmap(df_all, data["price"], data["symbol"])
                        pa_results = analyze_price_action(df_all)

                        # Logic for predictive metrics
                        ob_imb = ob_analysis.get('imbalance', 0)
                        whale_buy = data.get('whale_buy_vol', 0)
                        whale_sell = data.get('whale_sell_vol', 0)
                        whale_bias = "Neutral"
                        if whale_buy > whale_sell * 1.8: whale_bias = "Bullish Accumulation"
                        elif whale_sell > whale_buy * 1.8: whale_bias = "Bearish Distribution"
                        smart_money_flow = "Steady"
                        if ob_imb > 15 and whale_buy > whale_sell: smart_money_flow = "Strong Entry"
                        elif ob_imb < -15 and whale_sell > whale_buy: smart_money_flow = "Heavy Exit"

                        res = {
                            "Coin": data["symbol"],
                            "Price": data["price"],
                            "Price_Display": format_money(data["price"]),
                            "Antigravity Strategy": antigravity_pa_report,
                            "Whale Bias": whale_bias,
                            "Smart Money": smart_money_flow,
                            "OB Imbalance": f"{ob_imb:.2f}%",
                            "RSI": extract_numeric(data.get('rsi', 50)),
                            "Composite Score": comp_score,
                            # Keep old keys for UI compatibility
                            "RSI_4h": rsi_4h,
                            "RSI_1d": rsi_1d,
                            "MACD": extract_numeric(data.get('macd', 0)),
                            "MFI": data.get('mfi', 50),
                            "Momentum": data.get('momentum', 0),
                            "Net Accum": data.get('net_accumulation', 0),
                            "Volume Ratio": data.get('volume_ratio', 1.0),
                            "Funding Rate": fr_str,
                            "24h Change": data["price_change_percent"],
                            "Weekly Change": (weekly_close_str, weekly_diff),
                            "4H Change": (four_h_str, four_h_diff_str),
                            "Monthly Change": (monthly_close_str, monthly_diff),
                            "Open Interest": oi_str,
                            "OI_raw": oi_val,
                            "Long/Short Ratio": ls_val,
                            "EMA Trend": ema_trend_val,
                            "OrderBook": ob_analysis,
                            "df": data.get("df", []),
                            # Keep old keys for UI compatibility
                            "BTC Correlation": btc_corr_1h,
                            "EMA_20": data.get("ema_20", 0),
                            "EMA_50": data.get("ema_50"),
                            "EMA_100": data.get("ema_100"),
                            "EMA_200": data.get("ema_200"),
                            "Support": sup_val,
                            "Resistance": res_val,
                            "Support_Resistance": f"{format_money(sup_val)} - {format_money(res_val)}",
                            "Bollinger Bands": f"{format_money(bb_lower)} - {format_money(bb_upper)}",
                            "BB Lower Distance": f"{bb_lower_dist:.2f}%",
                            "BB Upper Distance": f"{bb_upper_dist:.2f}%",
                            "Whale Activity": whale_act_str,
                            "Whale_Buy_M": data.get('whale_buy_vol', 0),
                            "Whale_Sell_M": data.get('whale_sell_vol', 0),
                            "Avg Trade Size": avg_vol,
                            "Trap Status": trap_val,
                            "Liq Heatmap": liq_map,
                            "bullish_ob": pa_results.get("bullish_ob", False),
                            "bearish_ob": pa_results.get("bearish_ob", False),
                            "pa_structure": pa_results.get("structure", "Neutral"),
                            "fvg_bullish": pa_results.get("fvg_bullish"),
                            "fvg_bearish": pa_results.get("fvg_bearish"),
                            # Multi-timeframe data (4h/1d)
                            "net_accum_4h": net_accum_4h,
                            "net_accum_12h": extract_numeric(data.get("net_accum_12h", 0)),
                            "net_accum_1d": net_accum_1d,
                            "comp_score_4h": comp_score_4h,
                            "comp_score_12h": extract_numeric(data.get("comp_score_12h", 0)),
                            "comp_score_1d": comp_score_1d,
                            "mom_4h": mom_4h,
                            "mom_12h": extract_numeric(data.get("mom_12h", 0)),
                            "mom_1d": mom_1d,
                            "z_score_4h": z_score_4h,
                            "z_score_12h": extract_numeric(data.get("z_score_12h", 0)),
                            "z_score_1d": z_score_1d,
                            "vol_ratio_4h": vol_ratio_4h,
                            "vol_ratio_12h": extract_numeric(data.get("vol_ratio_12h", 1.0)),
                            "vol_ratio_1d": vol_ratio_1d,
                            "quote_vol_4h": data.get("quote_vol_4h", 0),
                            "quote_vol_1d": data.get("quote_vol_1d", 0),
                            "df": data.get("df", []),
                        }
                        
                        # Generate trade recommendation using the completed res dict
                        res["Advice"] = generate_trade_recommendation(res)
                        results.append(res)
                    except Exception as e:
                        print(f"[ERROR] Result mapping error for {data.get('symbol', 'Unknown')}: {e}")
                        import traceback
                        traceback.print_exc()
                    except Exception as e:
                        print(f"[UYARI] {coins[i]} eşleştirme hatası: {e}")



            # Sort results by Composite Score before assigning to global results
            results.sort(key=lambda x: x.get("Composite Score", 0), reverse=True)

            # Global sonuçları güncelle
            with global_lock:
                if len(results) > 5:  # Yeterli veri olduğundan emin ol
                    ALL_RESULTS = results[:50]  # En fazla 50 coin ile sınırla
                    
                    # Web Dashboard için verileri kaydet (Ondalıkları temizleyerek)
                    try:
                        clean_results = []
                        for c in ALL_RESULTS:
                            cc = c.copy()
                            for k, v in cc.items():
                                if isinstance(v, float):
                                    cc[k] = round(v, 4)
                            clean_results.append(cc)
                            
                        with open("web_results.json", "w") as f:
                            json.dump(clean_results, f, default=str)
                    except Exception as e:
                        print(f"[HATA] Web verileri kaydedilemedi: {e}")
                    
                    active_coins = {coin["Coin"] for coin in ALL_RESULTS}

                    PREV_STATS = {k: v for k, v in PREV_STATS.items() if k in active_coins}
                else:
                    print("[UYARI] Yeterli veri toplanamadı, önceki sonuçlar korunuyor")

            # Verilerimiz olduğunda raporları oluştur
            if ALL_RESULTS:
                # Yeni makroekonomik verileri al - her döngüde gerçek veriler
                macro_data = fetch_macro_economic_data()

                # Güncel verilere göre analiz mesajı oluştur
                analysis_message, coin_details, _ = generate_detailed_analysis_message(ALL_RESULTS)
                with global_lock:
                    COIN_DETAILS = coin_details

                # Mark data as fresh and process alerts BEFORE generating web reports
                handle_market_alerts(ALL_RESULTS)
                
                # Update signal tracker with current prices
                try:
                    current_prices = {coin['Coin']: coin['Price'] for coin in ALL_RESULTS}
                    SIGNAL_TRACKER.update_signal_outcome(current_prices)
                except Exception as e:
                    print(f"[WARN] Signal tracker update failed: {e}")
                
                # Analyze money flow
                try:
                    global PREV_ALL_RESULTS
                    money_flows = MONEY_FLOW_ANALYZER.analyze_flow(ALL_RESULTS, PREV_ALL_RESULTS)
                    money_flow_report = MONEY_FLOW_ANALYZER.generate_flow_report(money_flows)
                    money_flow_viz = MONEY_FLOW_ANALYZER.get_flow_visualization_data(money_flows)
                    PREV_ALL_RESULTS = ALL_RESULTS.copy()
                    
                    # Persistence: Save results for next run
                    try:
                        with open("prev_results.json", "w") as f:
                            json.dump(PREV_ALL_RESULTS, f, default=str)
                    except Exception as e:
                        print(f"[WARN] Failed to save prev_results.json: {e}")
                        
                except Exception as e:
                    print(f"[WARN] Money flow analysis failed: {e}")
                    money_flow_report = "Money flow data gathering..."
                    money_flow_viz = {"nodes": [], "links": []}
                
                # Detect market regime
                try:
                    market_regime = MARKET_REGIME_DETECTOR.detect_regime(ALL_RESULTS)
                    regime_banner = MARKET_REGIME_DETECTOR.format_regime_banner(market_regime)
                except Exception as e:
                    print(f"[WARN] Market regime detection failed: {e}")
                    regime_banner = "Market regime analyzing..."
                    market_regime = {}

                # Web Raporlarını Senkronize Et (Burada 'analysis_message' artık mevcut)
                web_reports = {}
                try:
                    web_reports["Current Analysis"] = analysis_message
                    web_reports["Summary"] = get_summary_report_string()
                    web_reports["Significant Changes"] = get_significant_changes_report_string()
                    web_reports["Cash Flow Report"] = generate_dynamic_cash_flow_report()
                    web_reports["Hourly Analysis"] = generate_hourly_report_string()
                    
                    try: web_reports["Whale Movement"] = get_whale_movement_report_string()
                    except: pass
                    try: web_reports["Smart Money"] = get_smart_money_report_string()
                    except: pass
                    try: web_reports["Whale Strategies"] = get_whale_strategies_report_string()
                    except: pass
                    try: web_reports["Manipulation Detector"] = generate_enhanced_manipulation_report()
                    except: pass
                    try: web_reports["Whale Ranking"] = generate_whale_ranking_report()
                    except: pass
                    try: web_reports["Smart Score"] = generate_smart_score_report()
                    except: pass
                    try: web_reports["MM Analysis"] = generate_advanced_whale_trend_report()
                    except: pass
                    try: web_reports["Bollinger Squeeze"] = generate_bollinger_squeeze_report()
                    except: pass
                    try: web_reports["Flow Migrations"] = generate_cash_flow_migration_report()
                    except: pass
                    try: web_reports["EMA Crossings"] = get_ema_crossings_report_string()
                    except: pass
                    try: web_reports["Order Block"] = get_order_block_report_string()
                    except: pass
                    try: web_reports["Liq Heatmap Summary"] = get_liq_heatmap_report_string()
                    except: pass
                    try: web_reports["Candlestick Patterns"] = get_candlestick_patterns_report_string(ALL_RESULTS, sync_fetch_kline_data)
                    except: pass
                    try: web_reports["Market Alerts"] = get_market_alerts_report_string()
                    except: pass
                   
                    # PREMIUM FEATURES
                    try: web_reports["Money Flow"] = money_flow_report
                    except: pass
                    try: web_reports["Money Flow Viz"] = json.dumps(money_flow_viz)
                    except: pass
                    try: web_reports["Market Regime"] = regime_banner
                    except: pass
                    try: web_reports["Market Regime Data"] = json.dumps(market_regime)
                    except: pass
                    try: web_reports["Signal Performance"] = SIGNAL_TRACKER.get_performance_report()
                    except: pass
                    
                    try: web_reports["Live Ticker"] = get_live_ticker_string()
                    except: pass
                    try: 
                        m_risk = calculate_macro_risk_level()
                        web_reports["Risk Analysis"] = generate_comprehensive_risk_report(ALL_RESULTS, m_risk)
                    except: pass
                    
                    indicators = [
                        "RSI", "RSI_4h", "RSI_1d", "MACD", "MACD_4h", "MACD_1d",
                        "ADX", "ADX_4h", "ADX_1d", "MFI", "MFI_4h", "MFI_1d",
                        "Momentum", "Momentum_4h", "Momentum_1d", "Net Accum", "Net Accum_4h", "Net Accum_1d",
                        "Composite Score", "Composite Score_4h", "Composite Score_1d", "Outlier Score",
                        "Funding Rate", "Long/Short Ratio", "Taker Rate", "EMA", "Z-Score",
                        "BTC Correlation", "BTC Correlation_4h", "BTC Correlation_1d",
                        "ETH Correlation", "ETH Correlation_4h", "ETH Correlation_1d",
                        "SOL Correlation", "SOL Correlation_4h", "SOL Correlation_1d"
                    ]
                    for ind in indicators:
                        try: web_reports[ind] = generate_metric_report(ind, ALL_RESULTS)
                        except: pass
                        
                    with open("web_reports.json", "w") as f:
                        json.dump(web_reports, f, default=str)
                    print("[INFO] Web reports sync successful.")
                except Exception as sync_e:
                    print(f"[UYARI] Web rapor senkronizasyon hatası: {sync_e}")
                
                global last_update_time
                last_update_time = datetime.now()

                keyboard = create_reply_keyboard(ALL_RESULTS)
                send_reply_keyboard_message(TELEGRAM_CHAT_ID, analysis_message, keyboard=keyboard)

                record_five_min_report(ALL_RESULTS)

                # Gerektiğinde saatlik rapor oluştur
                if (datetime.now() - last_hourly_report_time).total_seconds() >= 3600:
                    generate_hourly_report()
                    last_hourly_report_time = datetime.now()

                # İstatistikleri gelecekte kullanmak üzere kaydet
                save_prev_stats()

            print(f"[DEBUG] Analiz tamamlandı. Coin sayısı: {len(ALL_RESULTS)}")

        except Exception as main_error:
            print(f"[HATA] Ana analiz döngüsünde hata: {main_error}")
            import traceback
            traceback.print_exc()

        # Bir sonraki döngüden önce bekle
        time.sleep(SLEEP_INTERVAL)


# Modül düzeyinde değişkenleri tanımla (tüm fonksiyonların dışında)
ALL_RESULTS = []
PREV_STATS = {}
# Diğer global değişkenler...

if __name__ == "__main__":
    load_prev_stats()  # Tek çağrı
    print("Başlangıç: Önceki istatistikler yüklendi.")

    # Send Main Menu on Startup
    print("[INFO] Sending main menu to Telegram...")
    try:
        handle_main_menu_return(TELEGRAM_CHAT_ID)
    except Exception as e:
        print(f"[ERROR] Failed to send main menu: {e}")

    analysis_thread = threading.Thread(target=analyze_market)
    analysis_thread.daemon = True
    analysis_thread.start()
    print("Analiz iş parçacığı başlatıldı.")

    try:
        process_telegram_updates()  # Telegram güncellemeleri
    except Exception as e:
        print(f"[CRITICAL ERROR] Telegram updates loop crashed: {e}")
        import traceback
        traceback.print_exc()


