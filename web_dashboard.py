import os
import json
import time
from datetime import datetime
import pytz
import ccxt
from flask import Flask, render_template, jsonify, send_file, request
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# Turkey timezone (GMT+3)
TURKEY_TZ = pytz.timezone('Europe/Istanbul')

def get_turkey_time():
    """Get current time in Turkey timezone (GMT+3)"""
    return datetime.now(TURKEY_TZ)


app = Flask(__name__)

# 🔐 GÜVENLIK AYARLARI
auth = HTTPBasicAuth()

# Şifre koruması (environment variable'dan al)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'changeme123')  # Render'da değiştir!

@auth.verify_password
def verify_password(username, password):
    """Simple password verification (production'da daha güvenli hash kullan)"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return username
    return None

# Rate Limiting (DDoS koruması)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://"
)

# CORS - Sadece güvenli originlere izin (production'da domain ekle)
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

# Dosya yolları
RESULTS_FILE = "web_results.json"
REPORTS_FILE = "web_reports.json"

# 🏠 Ana sayfa (şifre korumalı)
@app.route('/')
@auth.login_required
def index():
    # Cache Buster
    return render_template('index.html', v=int(time.time()))

# 📊 API: Veri çekme (rate limited)
@app.route('/api/data')
@limiter.limit("120 per minute")
@auth.login_required
def get_data():
    results = []
    print(f"[API] /api/data requested at {get_turkey_time().strftime('%H:%M:%S')}")
    print(f"[API] Checking for {RESULTS_FILE}...")
    
    if os.path.exists(RESULTS_FILE):
        try:
            file_size = os.path.getsize(RESULTS_FILE)
            print(f"[API] ✅ {RESULTS_FILE} found ({file_size} bytes)")
            with open(RESULTS_FILE, "r") as f:
                results = json.load(f)
            print(f"[API] ✅ Loaded {len(results)} coins from {RESULTS_FILE}")
            for c in results:
                sym = c.get('Coin', '')
                c['DisplaySymbol'] = f"${sym.replace('USDT', '')}"
        except Exception as e:
            print(f"[API] ❌ Error reading {RESULTS_FILE}: {e}")
            return jsonify({"error": "Data fetch failed"}), 500
    else:
        print(f"[API] ⚠️ {RESULTS_FILE} does NOT exist yet - analyzer may not have run")
    
    return jsonify(results)

# 📈 API: Rapor çekme (rate limited)
@app.route('/api/report/<path:report_type>')
@limiter.limit("100 per minute")
@auth.login_required
def get_report(report_type):
    try:
        if os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "r") as f:
                reports = json.load(f)
            
            # Mapping from Sidebar Button types to Telegram keys
            mapping = {
                "Current Analysis": "Current Analysis",
                "Summary": "Summary",
                "Market Alerts": "Market Alerts",
                "Live Ticker": "Live Ticker",
                "Significant Changes": "Significant Changes",
                "Cash Flow Report": "Cash Flow Report",
                "Hourly Analysis": "Hourly Analysis",
                "Flow Migrations": "Flow Migrations",
                "Whale Movement": "Whale Movement",
                "Net Accum": "Net Accum",
                "Smart Money": "Smart Money",
                "Whale Ranking": "Whale Ranking",
                "MM Analysis": "MM Analysis",
                "Manipulation Detector": "Manipulation Detector",
                "Taker Rate": "Taker Rate",
                "RSI 1H": "RSI", "RSI 4H": "RSI 4h", "RSI 1D": "RSI 1d",
                "MACD 1H": "MACD", "MACD 4H": "MACD 4h", "MACD 1D": "MACD 1d",
                "ADX 1H": "ADX", "ADX 4H": "ADX 4h", "ADX 1D": "ADX 1d",
                "EMA Report": "EMA",
                "EMA Crossings": "EMA Crossings",
                "MFI": "MFI",
                "Momentum": "Momentum",
                "Bollinger Squeeze": "Bollinger Squeeze",
                "Risk Analysis": "Risk Analysis",
                "Smart Score": "Smart Score",
                "Composite Score": "Composite Score",
                "Outlier Score": "Outlier Score",
                "BTC Correlation": "BTC Correlation",
                "ETH Correlation": "ETH Correlation",
                "SOL Correlation": "SOL Correlation",
                "BTC Correlation 4H": "BTC Correlation 4h",
                "BTC Correlation 1D": "BTC Correlation 1d",
                "ETH Correlation 4H": "ETH Correlation 4h",
                "ETH Correlation 1D": "ETH Correlation 1d",
                "SOL Correlation 4H": "SOL Correlation 4h",
                "SOL Correlation 1D": "SOL Correlation 1d",
                "Order Block": "Order Block",
                "Liq Heat Map": "Liq Heatmap Summary",
                "Candle Patterns": "Candlestick Patterns",
                "Money Flow": "Money Flow",
                "Market Regime": "Market Regime",
                "Signal Performance": "Signal Performance",
                "Antigravity PA": "Antigravity Strategy",
                "Smart Money Indicators": "Smart Money Indicators",
                "Arbitrage Report": "Arbitrage Report",
                "OI Change": "OI Change",
                "Open Interest": "Open Interest",
                "Global Analysis": "Global Analysis",
                "15m Change": "15m Change",
                "1H Change": "1H Change",
                "4H Change": "4H Change",
                "Weekly Change": "Weekly Change",
                "Monthly Change": "Monthly Change",
                "24h Volume": "24h Volume",
                "S/R Levels": "Support/Resistance",
                "Support/Resistance": "Support/Resistance",
                "Market Cash Flow Data": "Market Cash Flow Data",
                "YouTube Alpha": "YouTube Alpha",
                "TVL Alpha": "TVL Alpha",
                "Pump Predictions": "Pump Predictions",
                "Deep Analysis": "Deep Analysis",
                "ADX": "ADX",
                "Liq Heatmap Summary": "Liq Heatmap Summary",
                "Volume Ratio": "Volume Ratio"
            }
            
            key = mapping.get(report_type, report_type)
            if key in reports:
                return jsonify({"content": reports[key]})

        return jsonify({
            "content": f"⚠️ Report '{report_type}' is not yet available. Please wait for the next analysis cycle."
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔔 API: Alert durumu (public - rate limited)
@app.route('/api/alerts/status')
@limiter.limit("120 per minute")
def get_alerts_status():
    """Public endpoint for checking updates based on actual signal time"""
    try:
        if os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "r") as f:
                data = json.load(f)
                latest = data.get("Latest Signal Time", 0)
                if latest:
                    return jsonify({"last_update": latest})
            # Fallback to mtime only if JSON is empty or missing key
            return jsonify({"last_update": os.path.getmtime(REPORTS_FILE)})
        return jsonify({"last_update": 0})
    except Exception as e:
        return jsonify({"last_update": 0})

# 📅 API: Market Calendar (economic events, token unlocks, news)
@app.route('/api/calendar')
@limiter.limit("30 per minute")
@auth.login_required
def get_market_calendar():
    """Returns economic calendar, token unlocks, and news sentiment"""
    try:
        from market_calendar import MarketImpactAnalyzer
        
        analyzer = MarketImpactAnalyzer()
        data = analyzer.get_daily_impact_report()
        
        return jsonify(data)
    except Exception as e:
        print(f"[API] Market Calendar error: {e}")
        return jsonify({"error": str(e)}), 500

# 🩺 API: Trade Doctor (position analysis)
@app.route('/api/trade-doctor', methods=['POST'])
@limiter.limit("20 per minute")
@auth.login_required
def analyze_position():
    """Analyze a trading position and get AI recommendation"""
    try:
        from trade_doctor import TradeDoctor
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        symbol = data.get('symbol', 'BTC')
        entry_price = float(data.get('entry_price', 0))
        quantity = float(data.get('quantity', 0))
        position_type = data.get('position_type', 'long')
        
        if entry_price <= 0 or quantity <= 0:
            return jsonify({"error": "Invalid entry_price or quantity"}), 400
        
        doctor = TradeDoctor()
        analysis = doctor.analyze_position(symbol, entry_price, quantity, position_type)
        
        return jsonify(analysis)
    except Exception as e:
        print(f"[API] Trade Doctor error: {e}")
        return jsonify({"error": str(e)}), 500

# 🩺 API: Trade Doctor Quick Check
@app.route('/api/trade-doctor/quick/<symbol>')
@limiter.limit("30 per minute")
@auth.login_required
def quick_check(symbol):
    """Quick health check for a coin"""
    try:
        from trade_doctor import TradeDoctor
        
        doctor = TradeDoctor()
        result = doctor.quick_check(symbol)
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] Quick Check error: {e}")
        return jsonify({"error": str(e)}), 500

# 🐋 API: Whale Watcher
@app.route('/api/whales')
@limiter.limit("20 per minute")
@auth.login_required
def get_whale_transactions():
    """Get recent whale transactions"""
    try:
        from whale_watcher import WhaleWatcher
        
        watcher = WhaleWatcher()
        transactions = watcher.get_whale_transactions(20)
        summary = watcher.get_whale_summary()
        alerts = watcher.get_alerts(1_000_000)  # $1M+ alerts
        
        return jsonify({
            "transactions": transactions,
            "summary": summary,
            "alerts": alerts
        })
    except Exception as e:
        print(f"[API] Whale Watcher error: {e}")
        return jsonify({"error": str(e)}), 500

# 🛡️ API: Scam Detector
@app.route('/api/scam-check', methods=['POST'])
@limiter.limit("10 per minute")
@auth.login_required
def check_token_security():
    """Analyze token for scam/rug pull indicators"""
    try:
        from scam_detector import ScamDetector
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        query = data.get('query', '') or data.get('address', '')
        chain = data.get('chain', '')
        
        if not query:
            return jsonify({"error": "Token name or address required"}), 400
        
        detector = ScamDetector()
        
        # Check if query looks like an address (starts with 0x and is long)
        if query.startswith('0x') and len(query) >= 40:
            result = detector.analyze_token(query, chain or 'eth')
        else:
            # Search by name/symbol
            result = detector.analyze_by_name(query, chain if chain else None)
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] Scam Detector error: {e}")
        return jsonify({"error": str(e)}), 500

# 🌊 API: Elliott Wave Analysis
@app.route('/api/elliott-wave', methods=['POST'])
@limiter.limit("15 per minute")
@auth.login_required
def elliott_wave_analysis():
    """Perform Elliott Wave analysis on a symbol"""
    try:
        from elliott_wave import ElliottWaveAnalyzer
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        symbol = data.get('symbol', 'BTC')
        timeframe = data.get('timeframe', '4h')
        
        analyzer = ElliottWaveAnalyzer()
        result = analyzer.analyze(symbol, timeframe)
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] Elliott Wave error: {e}")
        return jsonify({"error": str(e)}), 500

# 📊 API: Coin Analysis Report (Comprehensive Single Coin Report)
@app.route('/api/coin-analysis/<symbol>')
@limiter.limit("30 per minute")
@auth.login_required
def get_coin_analysis(symbol):
    """
    Generate comprehensive analysis report for a single coin.
    Returns bullish/bearish factors, support/resistance, and strategy recommendation.
    """
    try:
        # Normalize symbol
        symbol = symbol.upper()
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        
        # Load current data
        if not os.path.exists(RESULTS_FILE):
            return jsonify({"error": "No data available yet"}), 404
        
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
        
        # Find coin data
        coin_data = None
        for coin in results:
            if coin.get('Coin') == symbol:
                coin_data = coin
                break
        
        if not coin_data:
            return jsonify({"error": f"Coin {symbol} not found in top 50"}), 404
        
        # Generate comprehensive report
        report = generate_coin_analysis_report(coin_data, results)
        
        return jsonify(report)
    except Exception as e:
        print(f"[API] Coin Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def generate_coin_analysis_report(coin, all_results):
    """
    Generate a comprehensive analysis report for a single coin.
    Includes ALL available metrics for thorough analysis.
    
    Returns:
        dict: Structured report with bullish/bearish factors, levels, and strategy
    """
    def safe_float(val, default=0):
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        try:
            # Remove any non-numeric characters except . and -
            cleaned = ''.join(c for c in str(val) if c.isdigit() or c in '.-')
            return float(cleaned) if cleaned else default
        except:
            return default
    
    def parse_support_resistance(val, price, is_support=True):
        """Parse support/resistance values that might be in K format"""
        if val is None:
            return price * (0.97 if is_support else 1.03)
        if isinstance(val, (int, float)):
            return float(val)
        try:
            val_str = str(val).strip()
            if 'K' in val_str.upper():
                return float(val_str.upper().replace('K', '')) * 1000
            return float(val_str)
        except:
            return price * (0.97 if is_support else 1.03)
    
    symbol = coin.get('Coin', 'UNKNOWN')
    display_symbol = f"${symbol.replace('USDT', '')}"
    
    # ============= EXTRACT ALL METRICS =============
    # Basic Price Info
    price = safe_float(coin.get('Price', coin.get('price', 0)))
    price_24h_change = safe_float(coin.get('24h Change Raw', 0))
    
    # Support/Resistance
    support = parse_support_resistance(coin.get('Support'), price, is_support=True)
    resistance = parse_support_resistance(coin.get('Resistance'), price, is_support=False)
    
    # Multi-timeframe RSI
    rsi_1h = safe_float(coin.get('RSI', 50))
    rsi_4h = safe_float(coin.get('RSI_4h', 50))
    rsi_12h = safe_float(coin.get('rsi_12h', 50))
    rsi_1d = safe_float(coin.get('RSI_1d', 50))
    
    # Multi-timeframe MACD
    macd_1h = safe_float(coin.get('MACD', 0))
    macd_4h = safe_float(coin.get('MACD_4h', 0))
    macd_12h = safe_float(coin.get('macd_12h', 0))
    macd_1d = safe_float(coin.get('MACD_1d', 0))
    
    # Multi-timeframe ADX
    adx_1h = safe_float(coin.get('ADX', 0))
    adx_4h = safe_float(coin.get('ADX_4h', 0))
    adx_12h = safe_float(coin.get('adx_12h', 0))
    adx_1d = safe_float(coin.get('ADX_1d', 0))
    
    # Multi-timeframe MFI
    mfi_1h = safe_float(coin.get('MFI', 50))
    mfi_4h = safe_float(coin.get('mfi_4h', 50))
    mfi_12h = safe_float(coin.get('mfi_12h', 50))
    mfi_1d = safe_float(coin.get('mfi_1d', 50))
    
    # Multi-timeframe Z-Score
    z_score_1h = safe_float(coin.get('Z-Score', 0))
    z_score_4h = safe_float(coin.get('z_score_4h', 0))
    z_score_12h = safe_float(coin.get('z_score_12h', 0))
    z_score_1d = safe_float(coin.get('z_score_1d', 0))
    
    # Multi-timeframe Net Accumulation
    net_accum_1h = safe_float(coin.get('NetAccum_raw', 0))
    net_accum_4h = safe_float(coin.get('net_accum_4h', 0))
    net_accum_12h = safe_float(coin.get('net_accum_12h', 0))
    net_accum_1d = safe_float(coin.get('net_accum_1d', 0))
    
    # Momentum & Trend
    momentum = safe_float(coin.get('Momentum', 0))
    ema_trend = coin.get('EMA Trend', coin.get('EMA_Trend', 'Neutral'))
    sma_trend = coin.get('SMA Trend', 'Neutral')
    ema_crossover = coin.get('EMA Crossover', 'No significant crossover')
    ema20_cross = coin.get('EMA20 Cross', 'No Crossover')
    
    # Volume & Liquidity
    volume_ratio = safe_float(coin.get('Volume Ratio', 1))
    volume_24h = safe_float(coin.get('24h Volume', 0))
    quote_vol_4h = safe_float(coin.get('quote_vol_4h', 0))
    quote_vol_1d = safe_float(coin.get('quote_vol_1d', 0))
    price_spread = safe_float(coin.get('Price Spread', 0.1))
    
    # Derivatives Data
    funding_rate = coin.get('Funding Rate', '0%')
    long_short_ratio = safe_float(coin.get('Long/Short Ratio', 1))
    oi_change = safe_float(coin.get('OI Change %', 0))
    open_interest = safe_float(coin.get('Open Interest', 0))
    
    # Taker Ratio from Manipulation Results
    manipulation_data = coin.get('Manipulation_Results', {})
    manipulation_metrics = manipulation_data.get('metrics', {})
    taker_ratio_15m = safe_float(manipulation_metrics.get('taker_ratio_15m', 50)) / 100
    taker_ratio_1h = safe_float(manipulation_metrics.get('taker_ratio_1h', 50)) / 100
    order_book_imbalance = safe_float(manipulation_metrics.get('order_book_imbalance', 0))
    
    # Scores
    smart_score = safe_float(coin.get('Composite Score', coin.get('Smart Score', 0)))
    outlier_score = safe_float(coin.get('Outlier Score', 0))
    
    # Order Flow (derive from multiple signals)
    order_flow = 0
    if macd_1h > 0: order_flow += 15
    if macd_4h > 0: order_flow += 15
    if net_accum_1h > 0: order_flow += 20
    if taker_ratio_1h > 0.52: order_flow += 15
    if volume_ratio > 1.3: order_flow += 10
    if order_book_imbalance > 20: order_flow += 10
    elif order_book_imbalance < -20: order_flow -= 10
    if net_accum_1h < 0: order_flow -= 20
    if taker_ratio_1h < 0.48: order_flow -= 15
    
    # Correlations
    btc_corr_1h = safe_float(coin.get('btc_corr_1h', 0))
    btc_corr_4h = safe_float(coin.get('btc_corr_4h', 0))
    btc_corr_1d = safe_float(coin.get('btc_corr_1d', 0))
    eth_corr_1h = safe_float(coin.get('eth_corr_1h', 0))
    eth_corr_4h = safe_float(coin.get('eth_corr_4h', 0))
    eth_corr_1d = safe_float(coin.get('eth_corr_1d', 0))
    sol_corr_1h = safe_float(coin.get('sol_corr_1h', 0))
    sol_corr_4h = safe_float(coin.get('sol_corr_4h', 0))
    sol_corr_1d = safe_float(coin.get('sol_corr_1d', 0))
    
    # Technical Patterns
    bb_squeeze = coin.get('BB Squeeze', 'Normal')
    bullish_ob = coin.get('bullish_ob', False)
    bearish_ob = coin.get('bearish_ob', False)
    pa_structure = coin.get('pa_structure', 'Sideways')
    rsi_div = coin.get('RSI_Div', 'Neutral')
    vol_climax = coin.get('Vol_Climax', 'Neutral')
    sfp_pattern = coin.get('SFP_Pattern', 'Neutral')
    trap_status = coin.get('Trap Status', 'None')
    
    # Manipulation Detection
    detected_strategies = manipulation_data.get('detected_strategies', [])
    
    # Calculate Smart Score rank
    smart_score_rank = 1
    for c in all_results:
        if safe_float(c.get('Composite Score', c.get('Smart Score', 0))) > smart_score:
            smart_score_rank += 1
    
    # ============= BUILD BULLISH FACTORS (Bullish Confluence) =============
    bullish_factors = []
    
    # EMA Trend
    if 'bullish' in str(ema_trend).lower():
        strength = "Strong" if 'strong' in str(ema_trend).lower() else "Moderate"
        bullish_factors.append({
            "name": "EMA Trend",
            "value": ema_trend,
            "emoji": "🟢",
            "description": f"{strength} bullish alignment across timeframes"
        })
    
    # EMA Crossover
    if 'bullish' in str(ema_crossover).lower():
        bullish_factors.append({
            "name": "EMA Crossover",
            "value": ema_crossover,
            "emoji": "✨",
            "description": "Recent bullish EMA cross detected"
        })
    
    # Multi-TF MACD
    macd_bullish_count = sum([1 for m in [macd_1h, macd_4h, macd_1d] if m > 0])
    if macd_1h > 0:
        bullish_factors.append({
            "name": "MACD (1H)",
            "value": f"{macd_1h:.4f}",
            "emoji": "📈",
            "description": f"Positive momentum ({macd_bullish_count}/3 TFs bullish)"
        })
    
    # Momentum
    if momentum > 0:
        strength = "Strong" if momentum > 50 else "Moderate" if momentum > 20 else "Weak"
        bullish_factors.append({
            "name": "Momentum (1H)",
            "value": f"{momentum:.2f}",
            "emoji": "🚀",
            "description": f"{strength} upward momentum"
        })
    
    # Order Flow
    if order_flow > 20:
        flow_desc = "Very strong" if order_flow > 50 else "Strong" if order_flow > 35 else "Moderate"
        bullish_factors.append({
            "name": "Order Flow",
            "value": f"+{order_flow:.0f}",
            "emoji": "💹",
            "description": f"{flow_desc} bullish flow (multi-TF aligned)"
        })
    
    # Volume Ratio
    if volume_ratio > 1.2:
        vol_desc = "Very high" if volume_ratio > 2 else "High" if volume_ratio > 1.5 else "Above average"
        bullish_factors.append({
            "name": "Volume Ratio",
            "value": f"{volume_ratio:.2f}x",
            "emoji": "📊",
            "description": f"{vol_desc} volume, healthy interest"
        })
    
    # Taker Ratio (buyers dominant)
    if taker_ratio_1h > 0.52:
        bullish_factors.append({
            "name": "Taker Ratio (1H)",
            "value": f"{taker_ratio_1h*100:.1f}%",
            "emoji": "🛒",
            "description": "Buyer pressure dominant"
        })
    
    # Price Spread (low = good liquidity)
    if price_spread < 0.1:
        bullish_factors.append({
            "name": "Price Spread",
            "value": f"{price_spread:.4f}%",
            "emoji": "💧",
            "description": "Low spread, good liquidity (low slippage risk)"
        })
    
    # Positive Net Accumulation
    if net_accum_1h > 5000000:  # +5M threshold
        bullish_factors.append({
            "name": "Net Accumulation (1H)",
            "value": f"+{net_accum_1h/1e6:.2f}M",
            "emoji": "🐋",
            "description": "Whale accumulation detected"
        })
    
    # Order Book Imbalance (buy side)
    if order_book_imbalance > 20:
        bullish_factors.append({
            "name": "Order Book",
            "value": f"+{order_book_imbalance:.1f}%",
            "emoji": "📗",
            "description": "Buy-side order book dominance"
        })
    
    # Long/Short Ratio
    if long_short_ratio > 1.5:
        bullish_factors.append({
            "name": "L/S Ratio",
            "value": f"{long_short_ratio:.2f}",
            "emoji": "📈",
            "description": "Longs dominant in derivatives"
        })
    
    # Bullish Order Block
    if bullish_ob:
        bullish_factors.append({
            "name": "Bullish OB",
            "value": "Detected",
            "emoji": "🟩",
            "description": "Bullish order block nearby"
        })
    
    # Low Correlations (independent mover)
    avg_btc_corr = (btc_corr_1h + btc_corr_4h + btc_corr_1d) / 3
    if avg_btc_corr < 0.4:
        bullish_factors.append({
            "name": "BTC Independence",
            "value": f"{avg_btc_corr:.2f}",
            "emoji": "🔓",
            "description": "Low BTC correlation - independent mover"
        })
    
    # ============= BUILD BEARISH FACTORS (Bearish Risks) =============
    bearish_factors = []
    
    # RSI Overbought (multi-TF)
    rsi_overbought = []
    if rsi_1h > 70: rsi_overbought.append(f"1H:{rsi_1h:.0f}")
    if rsi_4h > 70: rsi_overbought.append(f"4H:{rsi_4h:.0f}")
    if rsi_1d > 70: rsi_overbought.append(f"1D:{rsi_1d:.0f}")
    if rsi_overbought:
        severity = "Critical" if len(rsi_overbought) >= 2 else "Warning"
        bearish_factors.append({
            "name": "RSI Overbought",
            "value": "/".join(rsi_overbought),
            "emoji": "⚠️" if len(rsi_overbought) >= 2 else "⚡",
            "description": f"{severity}: Approaching or in overbought territory"
        })
    
    # RSI Oversold (multi-TF) - Potential reversal risk
    rsi_oversold = []
    if rsi_1h < 30: rsi_oversold.append(f"1H:{rsi_1h:.0f}")
    if rsi_4h < 30: rsi_oversold.append(f"4H:{rsi_4h:.0f}")
    if rsi_1d < 30: rsi_oversold.append(f"1D:{rsi_1d:.0f}")
    if rsi_oversold:
        bearish_factors.append({
            "name": "RSI Oversold",
            "value": "/".join(rsi_oversold),
            "emoji": "📉",
            "description": "Oversold - weak momentum, potential capitulation"
        })
    
    # MFI High (potential exhaustion)
    if mfi_1h > 65:
        bearish_factors.append({
            "name": "MFI (1H)",
            "value": f"{mfi_1h:.2f}",
            "emoji": "💦",
            "description": "High MFI, potential buying exhaustion signal"
        })
    
    # ADX Peaking
    if adx_1h > 40:
        bearish_factors.append({
            "name": "ADX (1H)",
            "value": f"{adx_1h:.2f}",
            "emoji": "📉",
            "description": "Strong trend but may be peaking/exhausting"
        })
    
    # Whale Selling (Negative Net Accum)
    if net_accum_1h < -5000000:  # -5M threshold
        severity = "Heavy" if net_accum_1h < -20000000 else "Moderate"
        bearish_factors.append({
            "name": "Whale Net Accum (1H)",
            "value": f"{net_accum_1h/1e6:.2f}M",
            "emoji": "🐋",
            "description": f"{severity} whale selling pressure detected"
        })
    
    # Multi-TF Whale Selling Confirmation
    if net_accum_4h < -10000000 and net_accum_1h < 0:
        bearish_factors.append({
            "name": "Whale Net Accum (4H)",
            "value": f"{net_accum_4h/1e6:.2f}M",
            "emoji": "🐋",
            "description": "Sustained whale distribution on 4H"
        })
    
    # OI Divergence (OI up but whales selling = potential trap)
    if oi_change > 0.5 and net_accum_1h < -1000000:
        bearish_factors.append({
            "name": "OI Divergence",
            "value": f"+{oi_change:.2f}% OI",
            "emoji": "🔀",
            "description": "OI increasing but whales selling - potential long trap"
        })
    
    # Low Smart Score
    if smart_score < 40:
        bearish_factors.append({
            "name": "Smart Score",
            "value": f"{smart_score:.2f}",
            "emoji": "🧠",
            "description": f"Low score (Rank #{smart_score_rank}/{len(all_results)})"
        })
    
    # Bearish EMA
    if 'bearish' in str(ema_trend).lower():
        strength = "Strong" if 'strong' in str(ema_trend).lower() else "Moderate"
        bearish_factors.append({
            "name": "EMA Trend",
            "value": ema_trend,
            "emoji": "🔴",
            "description": f"{strength} bearish EMA alignment"
        })
    
    # Death Cross
    if 'death' in str(sma_trend).lower() or 'death' in str(ema_crossover).lower():
        bearish_factors.append({
            "name": "Death Cross",
            "value": sma_trend,
            "emoji": "💀",
            "description": "Death cross detected - bearish signal"
        })
    
    # BB Squeeze (volatility warning)
    if 'squeeze' in str(bb_squeeze).lower():
        bearish_factors.append({
            "name": "BB Squeeze",
            "value": bb_squeeze,
            "emoji": "🔥",
            "description": "Volatility squeeze - big move incoming (direction unclear)"
        })
    
    # Bearish Order Block
    if bearish_ob:
        bearish_factors.append({
            "name": "Bearish OB",
            "value": "Detected",
            "emoji": "🟥",
            "description": "Bearish order block overhead"
        })
    
    # Order Book Imbalance (sell side)
    if order_book_imbalance < -20:
        bearish_factors.append({
            "name": "Order Book",
            "value": f"{order_book_imbalance:.1f}%",
            "emoji": "📕",
            "description": "Sell-side order book pressure"
        })
    
    # Manipulation Detected
    for strategy in detected_strategies:
        if strategy.get('score', 0) >= 50:
            bearish_factors.append({
                "name": f"⚠️ {strategy.get('type', 'Manipulation')}",
                "value": f"Score: {strategy.get('score', 0)}",
                "emoji": strategy.get('danger_level', '⚠️'),
                "description": strategy.get('recommendation', 'Caution advised')
            })
    
    # Negative Funding Rate (shorts paying longs = bearish pressure)
    try:
        funding_val = float(str(funding_rate).replace('%', ''))
        if funding_val < -0.02:
            bearish_factors.append({
                "name": "Negative Funding",
                "value": funding_rate,
                "emoji": "📊",
                "description": "Shorts paying - bearish pressure in derivatives"
            })
    except:
        pass
    
    # High Z-Score (overextended)
    if z_score_1h > 2.5:
        bearish_factors.append({
            "name": "Z-Score (1H)",
            "value": f"{z_score_1h:.2f}",
            "emoji": "📏",
            "description": "Price overextended from mean - reversion risk"
        })
    
    # ============= CALCULATE SENTIMENT =============
    bull_score = len(bullish_factors) * 10 + (order_flow if order_flow > 0 else 0)
    bear_score = len(bearish_factors) * 12 + (abs(order_flow) if order_flow < 0 else 0)
    
    # Add weight for critical signals
    for bf in bearish_factors:
        if 'Whale' in bf['name'] or 'Manipulation' in bf['name']:
            bear_score += 15
    
    if bull_score > bear_score + 20:
        sentiment = "BULLISH"
        sentiment_emoji = "🟢"
    elif bear_score > bull_score + 15:
        sentiment = "BEARISH"
        sentiment_emoji = "🔴"
    else:
        sentiment = "NEUTRAL"
        sentiment_emoji = "🟡"
    
    # ============= GENERATE STRATEGY =============
    # Format support/resistance for display
    if support >= 1000:
        support_display = f"${support/1000:.2f}K"
    else:
        support_display = f"${support:.4f}"
    
    if resistance >= 1000:
        resistance_display = f"${resistance/1000:.2f}K"
    else:
        resistance_display = f"${resistance:.4f}"
    
    if price >= 1000:
        price_display = f"${price/1000:.2f}K"
    else:
        price_display = f"${price:.4f}"
    
    # Calculate pullback probability
    pullback_risk = len([f for f in bearish_factors if 'Whale' in f['name'] or 'RSI' in f['name'] or 'MFI' in f['name']])
    pullback_pct = min(8, 3 + pullback_risk * 2)
    
    if sentiment == "BULLISH":
        entry_low = support
        entry_high = price * 0.99
        if entry_low >= 1000:
            entry_zone = f"${entry_low/1000:.2f}K - ${entry_high/1000:.2f}K"
        else:
            entry_zone = f"${entry_low:.4f} - ${entry_high:.4f}"
        
        target_low = resistance
        target_high = resistance * 1.05
        if target_low >= 1000:
            target = f"${target_low/1000:.2f}K - ${target_high/1000:.2f}K"
        else:
            target = f"${target_low:.4f} - ${target_high:.4f}"
        
        stop = support * 0.97
        if stop >= 1000:
            stop_loss = f"${stop/1000:.2f}K"
        else:
            stop_loss = f"${stop:.4f}"
        
        risk_level = "Medium" if len(bearish_factors) > 3 else "Low-Medium"
        strategy = f"Wait for dip to {entry_zone} or breakout confirmation above {resistance_display}"
        
    elif sentiment == "BEARISH":
        entry_zone = "Wait for reversal confirmation"
        target = support_display
        stop = resistance * 1.02
        if stop >= 1000:
            stop_loss = f"${stop/1000:.2f}K"
        else:
            stop_loss = f"${stop:.4f}"
        risk_level = "High"
        strategy = f"Avoid new longs, consider short on rejection at {resistance_display}"
        
    else:  # NEUTRAL
        if support >= 1000:
            entry_zone = f"${support/1000:.2f}K - {price_display}"
        else:
            entry_zone = f"${support:.4f} - {price_display}"
        target = resistance_display
        stop = support * 0.97
        if stop >= 1000:
            stop_loss = f"${stop/1000:.2f}K"
        else:
            stop_loss = f"${stop:.4f}"
        risk_level = "Medium-High" if len(bearish_factors) > len(bullish_factors) else "Medium"
        strategy = f"Wait for clearer direction, watch S/R levels ({pullback_pct}% pullback likely)"
    
    # ============= BUILD ASSESSMENT =============
    bull_highlights = ", ".join([f.get('name') for f in bullish_factors[:3]]) if bullish_factors else "None"
    bear_highlights = ", ".join([f.get('name') for f in bearish_factors[:3]]) if bearish_factors else "None"
    
    assessment = f"{display_symbol} is showing **{sentiment.lower()}** signals. "
    if bullish_factors:
        assessment += f"**Strengths:** {bull_highlights}. "
    if bearish_factors:
        assessment += f"**Risks:** {bear_highlights}. "
    
    if sentiment == "BULLISH":
        assessment += f"If {resistance_display} resistance breaks, expect acceleration to higher targets. "
        assessment += f"Failure to break may lead to pullback towards {support_display} ({pullback_pct}% pullback possible)."
    elif sentiment == "BEARISH":
        assessment += f"Watch for support at {support_display}. Break below could accelerate selling."
    else:
        assessment += "Mixed signals suggest caution. Wait for clearer directional move."
    
    # ============= BUILD RESPONSE =============
    return {
        "symbol": symbol,
        "display_symbol": display_symbol,
        "timestamp": get_turkey_time().isoformat(),
        "price": {
            "current": price,
            "current_display": price_display,
            "support": support,
            "support_display": support_display,
            "resistance": resistance,
            "resistance_display": resistance_display,
            "range": f"{support_display} - {resistance_display}",
            "change_24h": f"{price_24h_change:+.2f}%"
        },
        "scores": {
            "smart_score": round(smart_score, 2),
            "smart_score_rank": smart_score_rank,
            "total_coins": len(all_results),
            "order_flow": order_flow,
            "outlier_score": outlier_score
        },
        "sentiment": {
            "overall": sentiment,
            "emoji": sentiment_emoji,
            "bull_count": len(bullish_factors),
            "bear_count": len(bearish_factors),
            "pullback_risk_pct": pullback_pct
        },
        "bullish_factors": bullish_factors,
        "bearish_factors": bearish_factors,
        "assessment": assessment,
        "strategy": {
            "recommendation": strategy,
            "entry_zone": entry_zone,
            "target": target,
            "stop_loss": stop_loss,
            "risk_level": risk_level
        },
        "raw_metrics": {
            "rsi": {
                "1h": round(rsi_1h, 2),
                "4h": round(rsi_4h, 2),
                "12h": round(rsi_12h, 2),
                "1d": round(rsi_1d, 2)
            },
            "macd": {
                "1h": round(macd_1h, 4),
                "4h": round(macd_4h, 4),
                "12h": round(macd_12h, 4),
                "1d": round(macd_1d, 4)
            },
            "adx": {
                "1h": round(adx_1h, 2),
                "4h": round(adx_4h, 2),
                "12h": round(adx_12h, 2),
                "1d": round(adx_1d, 2)
            },
            "mfi": {
                "1h": round(mfi_1h, 2),
                "4h": round(mfi_4h, 2),
                "12h": round(mfi_12h, 2),
                "1d": round(mfi_1d, 2)
            },
            "z_score": {
                "1h": round(z_score_1h, 2),
                "4h": round(z_score_4h, 2),
                "12h": round(z_score_12h, 2),
                "1d": round(z_score_1d, 2)
            },
            "net_accumulation": {
                "1h": round(net_accum_1h / 1e6, 2),
                "4h": round(net_accum_4h / 1e6, 2),
                "12h": round(net_accum_12h / 1e6, 2),
                "1d": round(net_accum_1d / 1e6, 2),
                "unit": "M"
            },
            "volume": {
                "ratio": round(volume_ratio, 2),
                "24h": round(volume_24h / 1e6, 2),
                "unit": "M"
            },
            "taker_ratio": {
                "15m": round(taker_ratio_15m * 100, 1),
                "1h": round(taker_ratio_1h * 100, 1)
            },
            "derivatives": {
                "funding_rate": funding_rate,
                "long_short_ratio": round(long_short_ratio, 2),
                "oi_change_pct": round(oi_change, 2),
                "open_interest": round(open_interest, 2)
            },
            "correlations": {
                "btc": {"1h": btc_corr_1h, "4h": btc_corr_4h, "1d": btc_corr_1d},
                "eth": {"1h": eth_corr_1h, "4h": eth_corr_4h, "1d": eth_corr_1d},
                "sol": {"1h": sol_corr_1h, "4h": sol_corr_4h, "1d": sol_corr_1d}
            },
            "trends": {
                "ema_trend": ema_trend,
                "sma_trend": sma_trend,
                "ema_crossover": ema_crossover,
                "momentum": round(momentum, 2)
            },
            "patterns": {
                "bb_squeeze": bb_squeeze,
                "bullish_ob": bullish_ob,
                "bearish_ob": bearish_ob,
                "pa_structure": pa_structure,
                "rsi_div": rsi_div,
                "trap_status": trap_status
            },
            "manipulation": {
                "detected": len(detected_strategies) > 0,
                "strategies": [s.get('type') for s in detected_strategies if s.get('score', 0) >= 40],
                "order_book_imbalance": round(order_book_imbalance, 2)
            }
        }
    }

# 📥 API: Export (şifre korumalı, rate limited)
@app.route('/api/export/<export_type>')
@limiter.limit("5 per minute")
@auth.login_required
def export_data(export_type):
    try:
        if export_type == "NotebookLM Export":
            if not os.path.exists(RESULTS_FILE):
                return "Results file not found", 404
            
            with open(RESULTS_FILE, "r") as f:
                results = json.load(f)
            
            filename = f"Market_Analysis_Export_{int(time.time())}.md"
            content = "# Market Analysis Consolidated Report\n"
            content += f"Generated on: {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"Total Coins Analyzed: {len(results)}\n\n"
            
            for coin in results:
                symbol = coin.get("Coin", "Unknown")
                content += f"## {symbol} Analysis\n"
                content += f"- **Price**: {coin.get('Price_Display', 'N/A')}\n"
                content += f"- **24h Change**: {coin.get('24h Change', 'N/A')}%\n"
                content += f"- **RSI**: {coin.get('RSI', 'N/A')}\n"
                content += f"- **MACD**: {coin.get('MACD', 'N/A')}\n"
                content += f"- **Net Accum**: {coin.get('Net Accum', 'N/A')}\n"
                content += "\n---\n\n"
            
            file_path = f"/tmp/{filename}"
            with open(file_path, "w") as f:
                f.write(content)
            
            return send_file(file_path, as_attachment=True)

        elif export_type == "YouTube Alpha":
            import youtube_analyzer
            
            # Use data from main report file for context if available
            market_summary = "General Crypto Market Context"
            if os.path.exists(RESULTS_FILE):
                try:
                    with open(RESULTS_FILE, "r") as f:
                        data = json.load(f)
                        # Create a mini summary of top 5 coins
                        top_coins = sorted(data, key=lambda x: str(x.get("Composite Score", 0)), reverse=True)[:5]
                        market_summary = "\\n".join([f"{c.get('Coin')}: {c.get('Price_Display')} (Score: {c.get('Composite Score')})" for c in top_coins])
                except: pass

            report_content = youtube_analyzer.analyze_youtube_alpha(market_summary)
            
            filename = f"YouTube_Alpha_Analysis_{int(time.time())}.md"
            file_path = f"/tmp/{filename}"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_content)
                
            return send_file(file_path, as_attachment=True)

        elif export_type == "YouTube Transcripts":
            import youtube_analyzer
            all_content = []
            errors = []
            
            for name, cid in youtube_analyzer.CHANNELS.items():
                try:
                    vid, title = youtube_analyzer.get_latest_video_id(cid)
                    if vid:
                        text = youtube_analyzer.get_transcript(vid)
                        if text:
                            all_content.append(
                                f"=== CHANNEL: {name} ===\n"
                                f"TITLE: {title}\n"
                                f"URL: https://www.youtube.com/watch?v={vid}\n\n"
                                f"TRANSCRIPT:\n{text}\n\n"
                            )
                        else:
                            errors.append(f"{name}: No subtitles available")
                    else:
                        errors.append(f"{name}: Could not get video")
                except Exception as e:
                    errors.append(f"{name}: {str(e)[:50]}")
            
            if not all_content:
                # Return detailed error
                error_msg = "No transcripts available.\n\nErrors:\n" + "\n".join(errors)
                return error_msg, 404
                
            filename = f"youtube_transcripts_{int(time.time())}.txt"
            file_path = f"/tmp/{filename}"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(all_content))
                if errors:
                    f.write("\n\n=== CHANNELS WITHOUT SUBTITLES ===\n")
                    f.write("\n".join(errors))
                
            return send_file(file_path, as_attachment=True)

        return "Invalid export type", 400
    except Exception as e:
        return str(e), 500

# 🏥 Health check endpoint (Render için gerekli)
@app.route('/health')
@limiter.exempt
def health():
    return jsonify({"status": "healthy", "timestamp": get_turkey_time().isoformat()}), 200

# 📊 Kline Data Endpoint (Frontend Chart için)
@app.route('/api/klines/<symbol>')
@auth.login_required
def get_klines(symbol):
    try:
        limit = request.args.get('limit', 200, type=int)
        interval = request.args.get('interval', '1h')
        
        # Initialize Exchange (Create new or use existing if safe)
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # Use futures data generally
        })
        
        clean_symbol = symbol.replace('USDT', '').upper()
        
        # Fetch OHLCV
        ohlcv = exchange.fetch_ohlcv(f"{clean_symbol}/USDT", interval, limit=limit)
        
        # Format for Lightweight Charts
        data = []
        for candle in ohlcv:
            data.append({
                'time': int(candle[0] / 1000), # Unix Timestamp (Seconds)
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4]
            })
            
        return jsonify(data)
    except Exception as e:
        print(f"Kline Error: {e}")
        return jsonify({"error": str(e)}), 500

# ⚠️ Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please try again later."
    }), 429

@app.errorhandler(401)
def unauthorized_handler(e):
    return jsonify({
        "error": "Unauthorized",
        "message": "Invalid credentials"
    }), 401

@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong"
    }), 500

if __name__ == '__main__':
    # Development
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)
