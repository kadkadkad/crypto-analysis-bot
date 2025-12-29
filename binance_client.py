import asyncio
import aiohttp
import pandas as pd
import config
from ta.trend import MACD, ADXIndicator, EMAIndicator
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volume import MFIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

async def fetch_klines_bybit_async(session, symbol, interval, limit=100):
    bybit_interval_map = {"1h": "60", "4h": "240", "12h": "720", "1d": "D", "1w": "W", "1M": "M"}
    by_interval = bybit_interval_map.get(interval, "60")
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={by_interval}&limit={limit}"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    raw_list = data["result"]["list"]
                    formatted = []
                    for k in reversed(raw_list):
                        formatted.append([int(k[0]), k[1], k[2], k[3], k[4], k[5], 0, k[6], 0, float(k[5])*0.5, float(k[6])*0.5, 0])
                    return formatted
    except: pass
    return None

async def fetch_kline_with_fallback(session, symbol, interval, limit=100):
    try:
        url = f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if len(data) >= min(limit // 2, 5): return data
    except: pass
    return await fetch_klines_bybit_async(session, symbol, interval, limit) or []

async def fetch_funding_rate_async(session, symbol):
    url = f"{config.BINANCE_FUTURES_API_URL}premiumIndex?symbol={symbol}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return float(data.get("lastFundingRate", 0))
    except: pass
    return 0.0

async def fetch_long_short_ratio_async(session, symbol):
    url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                if data and isinstance(data, list):
                    return float(data[0].get("longShortRatio", 1.0))
    except: pass
    return 1.0

async def fetch_order_book_async(session, symbol, limit=100):
    url = f"{config.BINANCE_API_URL}depth?symbol={symbol}&limit={limit}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                bids = [(float(p), float(q)) for p, q in data["bids"]]
                asks = [(float(p), float(q)) for p, q in data["asks"]]
                return bids, asks
    except: pass
    return [], []

def calculate_adx(df, window=14):
    if len(df) < window + 1: return None
    return ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=window).adx().iloc[-1]

def calculate_net_accumulation_detailed(df):
    whale_buy = df["taker_buy_quote"].sum()
    total_quote = df["quote_volume"].sum()
    whale_sell = total_quote - whale_buy
    return {"buy": whale_buy, "sell": whale_sell, "net": whale_buy - whale_sell}

def calculate_ema(df, window):
    if len(df) < window: return None
    return EMAIndicator(close=df["close"], window=window).ema_indicator().iloc[-1]

async def fetch_binance_data_async(session, symbol, ref_returns=None):
    try:
        ticker_url = f"{config.BINANCE_API_URL}ticker/24hr?symbol={symbol}"
        async with session.get(ticker_url, timeout=10) as t_resp:
            if t_resp.status != 200: return None
            t_data = await t_resp.json()

        ticker_data = {
            "price": float(t_data["lastPrice"]),
            "price_change_percent": float(t_data["priceChangePercent"]),
            "volume": float(t_data["volume"]),
            "quote_volume": float(t_data["quoteVolume"]),
            "symbol": symbol
        }

        # Parallel Fetch everything else
        tasks = [
            session.get(f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1h&limit=250", timeout=10),
            session.get(f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1w&limit=2", timeout=5),
            session.get(f"{config.BINANCE_API_URL}klines?symbol={symbol}&interval=1M&limit=2", timeout=5),
            fetch_kline_with_fallback(session, symbol, "4h", 100),
            fetch_kline_with_fallback(session, symbol, "12h", 100),
            fetch_kline_with_fallback(session, symbol, "1d", 100),
            fetch_kline_with_fallback(session, symbol, "15m", 100),
            fetch_funding_rate_async(session, symbol),
            fetch_long_short_ratio_async(session, symbol),
            fetch_order_book_async(session, symbol)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 1. Main 1H Analysis
        resp_1h = results[0]
        klines = []
        if isinstance(resp_1h, aiohttp.ClientResponse) and resp_1h.status == 200:
            klines = await resp_1h.json()
        if len(klines) < 100:
            klines = await fetch_klines_bybit_async(session, symbol, "1h", 250) or []
            
        if not klines: return ticker_data

        df = pd.DataFrame(klines, columns=["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
        for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=["close"])

        def safe_get(val):
            if val is None or pd.isna(val): return 0.0
            return float(val)

        ticker_data["rsi"] = safe_get(RSIIndicator(df["close"]).rsi().iloc[-1])
        ticker_data["macd"] = safe_get(MACD(df["close"]).macd().iloc[-1])
        ticker_data["adx"] = safe_get(calculate_adx(df))
        ticker_data["momentum"] = (ticker_data["rsi"] * 0.3) + (ticker_data["macd"] * 100) + (ticker_data["adx"] * 0.2)
        ticker_data.update(calculate_net_accumulation_detailed(df))
        ticker_data["df"] = df.to_dict('records')
        ticker_data["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"]).average_true_range().iloc[-1]
        ticker_data["mfi"] = MFIIndicator(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"]).money_flow_index().iloc[-1]
        ticker_data["stoch_rsi"] = StochRSIIndicator(close=df["close"]).stochrsi().iloc[-1]

        # 2. History & Other Intervals
        resp_w, resp_m = results[1], results[2]
        try:
            if isinstance(resp_w, aiohttp.ClientResponse) and resp_w.status == 200:
                w_dat = await resp_w.json()
                if len(w_dat) >= 2: ticker_data["weekly_close"] = float(w_dat[-2][4])
        except: ticker_data["weekly_close"] = None
        
        try:
            if isinstance(resp_m, aiohttp.ClientResponse) and resp_m.status == 200:
                m_dat = await resp_m.json()
                if len(m_dat) >= 2: ticker_data["monthly_close"] = float(m_dat[-2][4])
        except: ticker_data["monthly_close"] = None

        def process_sub_df(k_data, interval_name):
            if not k_data or isinstance(k_data, Exception): return None
            sub_df = pd.DataFrame(k_data, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"])
            sub_df = sub_df.apply(pd.to_numeric, errors='coerce').dropna(subset=["close"])
            
            if len(sub_df) >= 14:
                ticker_data[f"rsi_{interval_name}"] = safe_get(RSIIndicator(sub_df["close"]).rsi().iloc[-1])
            
            # Multi-interval Net Accumulation
            net_accum = calculate_net_accumulation_detailed(sub_df)
            ticker_data[f"net_accum_{interval_name}"] = net_accum["net"]
            ticker_data[f"quote_vol_{interval_name}"] = sub_df["quote_volume"].sum()
            
            ticker_data[f"df_{interval_name}"] = sub_df.to_dict('records')
            return sub_df

        df_4h = process_sub_df(results[3], "4h")
        if df_4h is not None and len(df_4h) >= 2: ticker_data["fourh_close"] = float(df_4h["close"].iloc[-2])
        process_sub_df(results[4], "12h")
        df_1d = process_sub_df(results[5], "1d")
        if not isinstance(results[6], Exception): ticker_data["df_15m"] = results[6]

        # 3. Correlation Logic
        if ref_returns:
            try:
                def calc_corr(rets, ref_rets):
                    if len(rets) < 10 or len(ref_rets) < 10: return 0.0
                    # Align lengths
                    min_len = min(len(rets), len(ref_rets))
                    return float(rets.tail(min_len).corr(ref_rets.tail(min_len)))

                # 1H Correlation
                coin_1h_ret = df["close"].pct_change().dropna()
                ticker_data["btc_corr_1h"] = calc_corr(coin_1h_ret, ref_returns.get("btc_1h_ret", pd.Series()))
                
                # 4H Correlation
                if df_4h is not None:
                    coin_4h_ret = df_4h["close"].pct_change().dropna()
                    ticker_data["btc_corr_4h"] = calc_corr(coin_4h_ret, ref_returns.get("btc_4h_ret", pd.Series()))
                
                # 1D Correlation
                if df_1d is not None:
                    coin_1d_ret = df_1d["close"].pct_change().dropna()
                    ticker_data["btc_corr_1d"] = calc_corr(coin_1d_ret, ref_returns.get("btc_1d_ret", pd.Series()))
            except Exception as corr_e:
                print(f"[WARN] Correlation calc failed for {symbol}: {corr_e}")

        # 4. Stats & OrderBook
        ticker_data["funding_rate"] = results[7] if not isinstance(results[7], Exception) else 0.0
        ticker_data["long_short_ratio"] = results[8] if not isinstance(results[8], Exception) else 1.0
        ob = results[9]
        if not isinstance(ob, Exception) and ob:
            ticker_data["bids"], ticker_data["asks"] = ob
        else:
            ticker_data["bids"], ticker_data["asks"] = [], []

        return ticker_data
    except Exception as e:
        print(f"[ERROR] fetch_binance_data_async for {symbol}: {e}")
        return ticker_data if 'ticker_data' in locals() else None

# Legacy Sync wrapper
def fetch_binance_data(symbol):
    async def wrap():
        async with aiohttp.ClientSession() as s: return await fetch_binance_data_async(s, symbol)
    return asyncio.run(wrap())
