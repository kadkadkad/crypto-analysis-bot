
import json
import os
import sys

# Add current dir to path to import functions from main if possible
sys.path.append(os.getcwd())

RESULTS_FILE = "web_results.json"
REPORTS_FILE = "web_reports.json"

if not os.path.exists(RESULTS_FILE):
    print("web_results.json not found")
    sys.exit(1)

with open(RESULTS_FILE, "r") as f:
    results = json.load(f)

if not results:
    print("web_results.json is empty")
    sys.exit(1)

# Mocking some basic reports since we can't easily import from main without triggering it
reports = {
    "Summary": "📊 <b>Piyasa Özeti Hazırlanıyor...</b>\nBot şu an ilk analiz döngüsünde. Lütfen 1-2 dakika bekleyin.",
    "Current Analysis": "📈 <b>Analiz Başlatıldı...</b>\nBot verileri Binance'den çekiyor. Kısa süre içinde burada göreceksiniz.",
    "Significant Changes": "📉 Henüz veri değişimi tespit edilmedi.",
    "Cash Flow Report": "💸 Hacim verileri işleniyor...",
    "Hourly Analysis": "🕒 Saatlik tahminler hazırlanıyor...",
    "RSI": "Indikatör verileri yükleniyor...",
    "RSI_4h": "Indikatör verileri yükleniyor...",
    "RSI_1d": "Indikatör verileri yükleniyor..."
}

# Try to save it
with open(REPORTS_FILE, "w") as f:
    json.dump(reports, f, default=str)

print("web_reports.json initialized with placeholders")
