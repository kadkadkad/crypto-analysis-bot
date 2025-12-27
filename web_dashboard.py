import os
import json
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, send_file, request
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

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
    default_limits=["500 per day", "100 per hour"],
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
@limiter.limit("30 per minute")
@auth.login_required
def get_data():
    results = []
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r") as f:
                results = json.load(f)
            for c in results:
                sym = c.get('Coin', '')
                c['DisplaySymbol'] = f"${sym.replace('USDT', '')}"
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return jsonify({"error": "Data fetch failed"}), 500
    return jsonify(results)

# 📈 API: Rapor çekme (rate limited)
@app.route('/api/report/<report_type>')
@limiter.limit("20 per minute")
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
                "RSI 1H": "RSI", "RSI 4H": "RSI_4h", "RSI 1D": "RSI_1d",
                "MACD 1H": "MACD", "MACD 4H": "MACD_4h", "MACD 1D": "MACD_1d",
                "ADX 1H": "ADX", "ADX 4H": "ADX_4h", "ADX 1D": "ADX_1d",
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
                "BTC Correlation 4H": "BTC Correlation_4h",
                "BTC Correlation 1D": "BTC Correlation_1d",
                "ETH Correlation 4H": "ETH Correlation_4h",
                "ETH Correlation 1D": "ETH Correlation_1d",
                "SOL Correlation 4H": "SOL Correlation_4h",
                "SOL Correlation 1D": "SOL Correlation_1d",
                "Order Block": "Order Block",
                "Liq Heat Map": "Liq Heatmap Summary",
                "Candle Patterns": "Candlestick Patterns",
                "Money Flow": "Money Flow",
                "Market Regime": "Market Regime",
                "Signal Performance": "Signal Performance",
                "Antigravity PA": "Antigravity Strategy"
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
@limiter.limit("60 per minute")
def get_alerts_status():
    """Public endpoint for checking updates"""
    try:
        if os.path.exists(REPORTS_FILE):
            mtime = os.path.getmtime(REPORTS_FILE)
            return jsonify({"last_update": mtime})
        return jsonify({"last_update": 0})
    except Exception as e:
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
            content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
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

        elif export_type == "YouTube Transcripts":
            import youtube_analyzer
            all_content = []
            for name, cid in youtube_analyzer.CHANNELS.items():
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
            
            if not all_content:
                return "No transcripts available", 404
                
            filename = f"youtube_transcripts_{int(time.time())}.txt"
            file_path = f"/tmp/{filename}"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(all_content))
                
            return send_file(file_path, as_attachment=True)

        return "Invalid export type", 400
    except Exception as e:
        return str(e), 500

# 🏥 Health check endpoint (Render için gerekli)
@app.route('/health')
@limiter.exempt
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

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
