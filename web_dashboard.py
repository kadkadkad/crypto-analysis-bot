import os
import json
import time
from datetime import datetime
import pytz
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
    return render_template('index.html')

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
