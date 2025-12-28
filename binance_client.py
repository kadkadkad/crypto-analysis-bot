import asyncio
import aiohttp
import requests
import pandas as pd
import config
from ta.trend import MACD, ADXIndicator, EMAIndicator
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volume import MFIIndicator
from ta.volatility import AverageTrueRange, BollingerBands


def calculate_adx(df, window=14):
    if len(df) < window + 1:
        return None
    indicator = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=window)
    return indicator.adx().iloc[-1]

async def fetch_klines_bybit_async(session, symbol, interval, limit=100):
    """
    Bybit API fallback for Kline data.
    """
    # Bybit interval mapping: 1h=60, 4h=240, 12h=720, 1d=D
    bybit_interval_map = {"1h": "60", "4h": "240", "12h": "720", "1d": "D", "1w": "W", "1M": "M"}
    by_interval = bybit_interval_map.get(interval, "60")
    
    # Bybit symbol normalization (already USDT usually)
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={by_interval}&limit={limit}"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    raw_list = data["result"]["list"]
                    # Bybit returns DESC order: [startTime, open, high, low, close, volume, turnover]
                    formatted = []
                    for k in reversed(raw_list):
                        formatted.append([
                            int(k[0]), # open_time
                            k[1],      # open
                            k[2],      # high
                            k[3],      # low
                            k[4],      # close
                            k[5],      # volume
                            0,         # close_time
                            k[6],      # quote_volume (turnover)
                            0,         # trades
                            float(k[5]) * 0.5, # taker_buy_base (mock 50%)
                            float(k[6]) * 0.5, # taker_buy_quote (mock 50%)
                            0
                        ])
                    return formatted
    except Exception as e:
        print(f"[WARN] Bybit fallback failed for {symbol}: {e}")
    return None


async def fetch_kline_with_fallback(session, symbol, interval, limit=100):
    """
    Fetches Kline data trying Binance first, then Bybit.
    Returns: list of klines or [] on failure.
    """
    # 1. Try Binance
    try:
        url = f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if len(data) >= min(limit // 2, 5): # Basic validation
                    return data
    except Exception as e:
        print(f"[WARN] Binance fetch failed for {symbol} {interval}: {e}")

    # 2. Try Bybit Fallback
    print(f"[INFO] {symbol} {interval} fallback to Bybit...")
    fallback_data = await fetch_klines_bybit_async(session, symbol, interval, limit)
    return fallback_data if fallback_data else []

def calculate_ema(df, window):
    if len(df) < window:
        return None
    indicator = EMAIndicator(close=df["close"], window=window)
    return indicator.ema_indicator().iloc[-1]

def calculate_net_accumulation_detailed(df):
    """
    Returns dict with buy, sell, and net accumulation volumes.
    """
    whale_buy = df["taker_buy_quote"].sum()
    total_quote = df["quote_volume"].sum()
    whale_sell = total_quote - whale_buy
    return {
        "buy": whale_buy,
        "sell": whale_sell,
        "net": whale_buy - whale_sell
    }

def calculate_net_accumulation(df):
    # Binance klines: 7=quote_volume, 10=taker_buy_quote
    # Our df has named columns: "quote_volume", "taker_buy_quote"
    whale_buy = df["taker_buy_quote"].sum()
    total_quote = df["quote_volume"].sum()
    whale_sell = total_quote - whale_buy
    return whale_buy - whale_sell

def calculate_price_roc(df, period=9):
    try:
        current_close = df["close"].iloc[-1]
        prev_close = df["close"].iloc[-period-1]
        return (current_close - prev_close) / prev_close * 100
    except:
        return 0

from ta.volatility import BollingerBands
def calculate_bollinger_bands(df, window=20, window_dev=2):
    indicator = BollingerBands(close=df["close"], window=window, window_dev=window_dev)
    return {
        "upper": indicator.bollinger_hband().iloc[-1],
        "lower": indicator.bollinger_lband().iloc[-1]
    }

def calculate_mfi(df, window=14):
    try:
        indicator = MFIIndicator(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"], window=window)
        return indicator.money_flow_index().iloc[-1]
    except:
        return None

def calculate_stoch_rsi(df, window=14):
    try:
        indicator = StochRSIIndicator(close=df["close"], window=window)
        return indicator.stochrsi().iloc[-1]
    except:
        return None



# ... (synchronous functions kept for backward compatibility if needed, or we leverage async)
# Ideally we replace them, but to respect the "safely refactor" approach, I will ADD async versions first.

def calculate_rsi(df, window=14):
    if len(df) < window + 1:
        return None
    indicator = RSIIndicator(close=df["close"], window=window)
    return indicator.rsi().iloc[-1]

def calculate_macd(df):
    if len(df) < 26:
        return None
    indicator = MACD(close=df["close"])
    return indicator.macd_diff().iloc[-1]

def calculate_atr(df, window=14):
    indicator = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=window)
    return indicator.average_true_range().iloc[-1]

def calculate_volume_ratio(df, window=20):
    if len(df) < window:
        return 1.0
    current_vol = df["volume"].iloc[-1]
    avg_vol = df["volume"].iloc[-window:-1].mean()
    return current_vol / avg_vol if avg_vol > 0 else 1.0

async def fetch_futures_data_async(session, symbol):
    """Fetches futures specific data asynchronously"""
    try:
        futures_info = {}
        url = f"{config.BINANCE_FUTURES_API_URL}premiumIndex?symbol={symbol}"

        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                futures_info = {
                    "funding_rate": float(data.get("lastFundingRate", 0)),
                    "next_funding_time": data.get("nextFundingTime")
                }

        
        # Long/Short Ratio - Try multiple endpoints for robustness
        # 1. Global Long/Short Account Ratio
        ls_endpoints = [
            f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1",
            f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={symbol}&period=5m&limit=1",
            f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=5m&limit=1"
        ]
        
        for url in ls_endpoints:
            try:
                async with session.get(url, timeout=5) as ls_res:
                    if ls_res.status == 200:
                        ls_data = await ls_res.json()
                        if ls_data and isinstance(ls_data, list) and len(ls_data) > 0:
                            ls_val = float(ls_data[0].get("longShortRatio", ls_data[0].get("longShortPositionRatio", 1.0)))
                            if ls_val != 1.0: # If we got a real value, stop searching
                                futures_info["long_short_ratio"] = ls_val
                                break
                            futures_info["long_short_ratio"] = ls_val
            except Exception as e:
                # print(f"[DEBUG] LS fetch failed for {url}: {e}")
                pass
             
        # Open Interest
        oi_url = f"{config.BINANCE_FUTURES_API_URL}openInterest?symbol={symbol}"
        try:
             async with session.get(oi_url, timeout=5) as oi_res:
                if oi_res.status == 200:
                    oi_data = await oi_res.json()
                    futures_info["open_interest"] = float(oi_data.get("openInterest", 0))
        except:
             pass
             
        return futures_info

    except Exception as e:
        # Many coins don't have futures, so this is expected. debug level.
        # print(f"[DEBUG] Futures data not available for {symbol}: {e}")
        pass
    return {}


async def fetch_order_book_async(session, symbol, limit=100):
    """Fetches order book data asynchronously"""
    url = f"{config.BINANCE_API_URL}depth?symbol={symbol}&limit={limit}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                bids = [(float(price), float(qty)) for price, qty in data["bids"]]
                asks = [(float(price), float(qty)) for price, qty in data["asks"]]
                return bids, asks
            else:
                return [], []
    except Exception as e:
        print(f"[ERROR] Async order book fetch failed for {symbol}: {e}")
        return [], []

async def fetch_binance_data_async(session, symbol, ref_returns=None):
    """
    Fetches coin data from Binance asynchronously
    Args:
        session (aiohttp.ClientSession): The async session
        symbol (str): Coin symbol
        ref_returns (dict): Optional dict of returns for BTC/ETH/SOL to calculate correlations
    Returns:
        dict: Dictionary containing price, volume and other data
    """
    try:
        # Ticker data
        url = f"{config.BINANCE_API_URL}ticker/24hr?symbol={symbol}"
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                print(f"[ERROR] Could not fetch ticker for {symbol}: {response.status}")
                return None
            data = await response.json()

        # Initialize DataFrames
        df_4h = None
        df_1d = None

        ticker_data = {
            "z_score_4h": 0,
            "z_score_1d": 0,
            "btc_corr_4h": "N/A", "btc_corr_1d": "N/A",
            "eth_corr_4h": "N/A", "eth_corr_1d": "N/A",
            "sol_corr_4h": "N/A", "sol_corr_1d": "N/A",
            "price": float(data["lastPrice"]),
            "price_change_percent": float(data["priceChangePercent"]),
            "volume": float(data["volume"]),
            "quote_volume": float(data["quoteVolume"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "symbol": symbol
        }

        # Kline data - Fallback to Bybit if Binance fails or has short history
        klines_url = f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1h&limit=250"
        async with session.get(klines_url, timeout=10) as k_response:
            if k_response.status == 200:
                klines = await k_response.json()
            else:
                klines = []
        
        # If binance data is empty or short, try Bybit
        if len(klines) < 100:
            print(f"[INFO] {symbol} klines insufficient on Binance ({len(klines)}), trying Bybit...")
            bybit_klines = await fetch_klines_bybit_async(session, symbol, "1h", 250)
            if bybit_klines:
                klines = bybit_klines

        if not klines:
            return ticker_data

        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        # Convert to numeric
        for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=["close"])

        # Calculate technical indicators (CPU bound, run directly or in executor if massive)
        # For 50 coins, direct calculation is fine.
        ticker_data["rsi"] = calculate_rsi(df)
        ticker_data["macd"] = calculate_macd(df)
        ticker_data["atr"] = calculate_atr(df)
        ticker_data["volume_ratio"] = calculate_volume_ratio(df)
        ticker_data["adx"] = calculate_adx(df)
        ticker_data["mfi"] = calculate_mfi(df)
        ticker_data["stoch_rsi"] = calculate_stoch_rsi(df)
        
        # Capture Net Accumulation Details
        net_accum_data = calculate_net_accumulation_detailed(df)
        ticker_data["net_accumulation"] = net_accum_data["net"]
        ticker_data["whale_buy_vol"] = net_accum_data["buy"]
        ticker_data["whale_sell_vol"] = net_accum_data["sell"]
        
        ticker_data["roc"] = calculate_price_roc(df)
        ticker_data["bb"] = calculate_bollinger_bands(df)
        
        # Calculate EMAs
        ticker_data["ema_20"] = calculate_ema(df, 20)
        ticker_data["ema_50"] = calculate_ema(df, 50)
        ticker_data["ema_100"] = calculate_ema(df, 100)
        ticker_data["ema_200"] = calculate_ema(df, 200)
        
        # Calculate Momentum as per main.py formula: (rsi * 0.3) + (macd * 100) + (adx * 0.2)

        # Z-Score 1h
        m_1h = df["close"].rolling(window=20).mean().iloc[-1]
        s_1h = df["close"].rolling(window=20).std().iloc[-1]
        ticker_data["z_score"] = (df["close"].iloc[-1] - m_1h) / s_1h if s_1h > 0 else 0
        
        # Handle Nones safely although indicators in 'ta' usually return NaN
        def safe_get(val):
            if pd.isna(val): return 0.0
            return float(val)
        
        ticker_data["rsi"] = safe_get(ticker_data["rsi"])
        ticker_data["macd"] = safe_get(ticker_data["macd"])
        ticker_data["adx"] = safe_get(ticker_data["adx"])
        ticker_data["momentum"] = (ticker_data["rsi"] * 0.3) + (ticker_data["macd"] * 100) + (ticker_data["adx"] * 0.2)
        
        # WE KEEP THE DFS BUT main.py MUST CLEAN THEM ASAP
        ticker_data["df"] = df.to_dict('records')

        # Weekly/Monthly Close
        try:
            weekly_url = f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1w&limit=2"
            async with session.get(weekly_url, timeout=5) as w_response:
                if w_response.status == 200:
                    w_data = await w_response.json()
                    if len(w_data) >= 2: ticker_data["weekly_close"] = float(w_data[-2][4])
        except: ticker_data["weekly_close"] = None

        try:
            monthly_url = f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1M&limit=2"
            async with session.get(monthly_url, timeout=5) as m_response:
                if m_response.status == 200:
                    m_data = await m_response.json()
                    if len(m_data) >= 2: ticker_data["monthly_close"] = float(m_data[-2][4])
        except: ticker_data["monthly_close"] = None

        # 4H data
        try:
            k4_data = await fetch_kline_with_fallback(session, symbol, "4h", 100)
            if k4_data:
                df_4h = pd.DataFrame(k4_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
                df_4h = df_4h.apply(pd.to_numeric, errors='coerce').dropna(subset=["close"])
                if len(df_4h) >= 14:
                    ticker_data["rsi_4h"] = RSIIndicator(close=df_4h["close"], window=14).rsi().iloc[-1]
                    ticker_data["macd_4h"] = MACD(close=df_4h["close"]).macd().iloc[-1]
                    ticker_data["adx_4h"] = calculate_adx(df_4h)
                    ticker_data["mfi_4h"] = calculate_mfi(df_4h)
                    ticker_data["stoch_rsi_4h"] = calculate_stoch_rsi(df_4h)
                    ticker_data["mom_4h"] = df_4h["close"].pct_change(periods=min(10, len(df_4h)-1)).iloc[-1] * 100
                    ticker_data["vol_ratio_4h"] = df_4h["volume"].iloc[-1] / df_4h["volume"].iloc[-21:-1].mean() if len(df_4h) > 21 and df_4h["volume"].iloc[-21:-1].mean() > 0 else 1.0
                    na_4h = calculate_net_accumulation_detailed(df_4h)
                    ticker_data["net_accum_4h"] = na_4h["net"]
                    m4 = df_4h["close"].rolling(window=min(20, len(df_4h))).mean().iloc[-1]
                    s4 = df_4h["close"].rolling(window=min(20, len(df_4h))).std().iloc[-1]
                    ticker_data["z_score_4h"] = (df_4h["close"].iloc[-1] - m4) / s4 if s4 > 0 else 0
                    ticker_data["comp_score_4h"] = ((ticker_data.get("rsi_4h", 50) or 50) + (ticker_data.get("mfi_4h", 50) or 50) + (50 + (ticker_data.get("mom_4h", 0) or 0))) / 3
                ticker_data["quote_vol_4h"] = df_4h["quote_volume"].iloc[-1] if not df_4h.empty else 0
                ticker_data["df_4h"] = df_4h.to_dict('records')
        except Exception as e: print(f"[ERROR] 4H calc failed for {symbol}: {e}")

        # 12H data
        try:
            k12_data = await fetch_kline_with_fallback(session, symbol, "12h", 100)
            if k12_data:
                df_12h = pd.DataFrame(k12_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
                df_12h = df_12h.apply(pd.to_numeric, errors='coerce').dropna(subset=["close"])
                if len(df_12h) >= 14:
                    ticker_data["rsi_12h"] = RSIIndicator(close=df_12h["close"], window=14).rsi().iloc[-1]
                    ticker_data["macd_12h"] = MACD(close=df_12h["close"]).macd().iloc[-1]
                    ticker_data["adx_12h"] = calculate_adx(df_12h)
                    ticker_data["mfi_12h"] = calculate_mfi(df_12h)
                    ticker_data["stoch_rsi_12h"] = calculate_stoch_rsi(df_12h)
                    ticker_data["mom_12h"] = df_12h["close"].pct_change(periods=min(10, len(df_12h)-1)).iloc[-1] * 100
                    ticker_data["vol_ratio_12h"] = df_12h["volume"].iloc[-1] / df_12h["volume"].iloc[-21:-1].mean() if len(df_12h) > 21 and df_12h["volume"].iloc[-21:-1].mean() > 0 else 1.0
                    na_12h = calculate_net_accumulation_detailed(df_12h)
                    ticker_data["net_accum_12h"] = na_12h["net"]
                    m12 = df_12h["close"].rolling(window=min(20, len(df_12h))).mean().iloc[-1]
                    s12 = df_12h["close"].rolling(window=min(20, len(df_12h))).std().iloc[-1]
                    ticker_data["z_score_12h"] = (df_12h["close"].iloc[-1] - m12) / s12 if s12 > 0 else 0
                    ticker_data["comp_score_12h"] = ((ticker_data.get("rsi_12h", 50) or 50) + (ticker_data.get("mfi_12h", 50) or 50) + (50 + (ticker_data.get("mom_12h", 0) or 0))) / 3
                ticker_data["df_12h"] = df_12h.to_dict('records')
        except Exception as e: print(f"[ERROR] 12H calc failed for {symbol}: {e}")

        # 1D data
        try:
            k1_data = await fetch_kline_with_fallback(session, symbol, "1d", 100)
            if k1_data:
                df_1d = pd.DataFrame(k1_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
                df_1d = df_1d.apply(pd.to_numeric, errors='coerce').dropna(subset=["close"])
                if len(df_1d) >= 14:
                    ticker_data["rsi_1d"] = RSIIndicator(close=df_1d["close"], window=14).rsi().iloc[-1]
                    ticker_data["macd_1d"] = MACD(close=df_1d["close"]).macd().iloc[-1]
                    ticker_data["adx_1d"] = calculate_adx(df_1d)
                    ticker_data["mfi_1d"] = calculate_mfi(df_1d)
                    ticker_data["stoch_rsi_1d"] = calculate_stoch_rsi(df_1d)
                    ticker_data["mom_1d"] = df_1d["close"].pct_change(periods=min(10, len(df_1d)-1)).iloc[-1] * 100
                    ticker_data["vol_ratio_1d"] = df_1d["volume"].iloc[-1] / df_1d["volume"].iloc[-21:-1].mean() if len(df_1d) > 21 and df_1d["volume"].iloc[-21:-1].mean() > 0 else 1.0
                    na_1d = calculate_net_accumulation_detailed(df_1d)
                    ticker_data["net_accum_1d"] = na_1d["net"]
                    m1 = df_1d["close"].rolling(window=min(20, len(df_1d))).mean().iloc[-1]
                    s1 = df_1d["close"].rolling(window=min(20, len(df_1d))).std().iloc[-1]
                    ticker_data["z_score_1d"] = (df_1d["close"].iloc[-1] - m1) / s1 if s1 > 0 else 0
                    ticker_data["comp_score_1d"] = ((ticker_data.get("rsi_1d", 0) or 0 + ticker_data.get("mfi_1d", 0) or 0 + (50 + ticker_data.get("mom_1d", 0))) / 3)
                ticker_data["quote_vol_1d"] = df_1d["quote_volume"].iloc[-1] if not df_1d.empty else 0
                ticker_data["df_1d"] = df_1d.to_dict('records')
        except Exception as e: print(f"[ERROR] 1D calc failed for {symbol}: {e}")

        # 15M Data for Antigravity PA
        try:
            k15_data = await fetch_kline_with_fallback(session, symbol, "15m", 100)
            if k15_data: ticker_data["df_15m"] = k15_data # We don't need DataFrame conversion here, PA strategy handles it
        except: ticker_data["df_15m"] = []

        # Order Book Fetching
        try:
            bids, asks = await fetch_order_book_async(session, symbol)
            ticker_data["order_book"] = {"bids": bids, "asks": asks}
        except: ticker_data["order_book"] = {"bids": [], "asks": []}

        # Internal Correlations
        if ref_returns:
            try:
                c_ret = df["close"].pct_change().dropna()
                for base in ["btc", "eth", "sol"]:
                    base_ret_1h = ref_returns.get(f"{base}_1h_ret")
                    if base_ret_1h is not None and len(c_ret) > 5:
                        common_len = min(len(c_ret), len(base_ret_1h))
                        correlation = pd.Series(c_ret.iloc[-common_len:].values).corr(pd.Series(base_ret_1h.iloc[-common_len:].values))
                        ticker_data[f"{base}_corr_1h"] = round(correlation, 2) if not pd.isna(correlation) else 0

                if 'df_4h' in locals() and df_4h is not None:
                    c_4h_ret = df_4h["close"].pct_change().dropna()
                    for base in ["btc", "eth", "sol"]:
                        base_ret_4h = ref_returns.get(f"{base}_4h_ret")
                        if base_ret_4h is not None and len(c_4h_ret) > 5:
                            common_len = min(len(c_4h_ret), len(base_ret_4h))
                            correlation = pd.Series(c_4h_ret.iloc[-common_len:].values).corr(pd.Series(base_ret_4h.iloc[-common_len:].values))
                            ticker_data[f"{base}_corr_4h"] = round(correlation, 2) if not pd.isna(correlation) else "N/A"

                if 'df_1d' in locals() and df_1d is not None:
                    c_1d_ret = df_1d["close"].pct_change().dropna()
                    for base in ["btc", "eth", "sol"]:
                        base_ret_1d = ref_returns.get(f"{base}_1d_ret")
                        if base_ret_1d is not None and len(c_1d_ret) > 5:
                            common_len = min(len(c_1d_ret), len(base_ret_1d))
                            correlation = pd.Series(c_1d_ret.iloc[-common_len:].values).corr(pd.Series(base_ret_1d.iloc[-common_len:].values))
                            ticker_data[f"{base}_corr_1d"] = round(correlation, 2) if not pd.isna(correlation) else "N/A"
            except Exception as e: print(f"[WARN] Internal correlation failed for {symbol}: {e}")

        # Add futures data
        ticker_data.update(await fetch_futures_data_async(session, symbol))
        ticker_data.setdefault("long_short_ratio", 1.0)

        return ticker_data

    except Exception as e:
        print(f"[ERROR] Async fetch failed for {symbol}: {e}")
        return None

# Synchronous wrapper for back-compat (if kept)
def fetch_binance_data(symbol):
    # This is the old synchronous version, kept for parts of the code likely not yet migrated
    # or we can remove it if we migrate everything.
    # For now, I'll overwrite the file with imports and BOTH versions.
    return asyncio.run(fetch_binance_data_wrap(symbol))

async def fetch_binance_data_wrap(symbol):
     async with aiohttp.ClientSession() as session:
        return await fetch_binance_data_async(session, symbol)

