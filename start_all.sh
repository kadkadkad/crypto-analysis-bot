#!/bin/bash
# Bot ve Web Dashboard Başlatma Scripti

cd "$(dirname "$0")"

echo "🚀 Bot ve Web Dashboard başlatılıyor..."

# Eski processleri temizle
pkill -f "python.*main.py" 2>/dev/null
pkill -f "web_dashboard" 2>/dev/null
sleep 2

# Log dosyalarını temizle (isteğe bağlı)
# > bot.log
# > web.log

# Bot'u başlat
echo "📊 Bot başlatılıyor..."
venv/bin/python main.py >> bot.log 2>&1 &
BOT_PID=$!
echo "   ✅ Bot başlatıldı (PID: $BOT_PID)"

sleep 3

# Web Dashboard'u başlat  
echo "🌐 Web Dashboard başlatılıyor..."
venv/bin/python web_dashboard.py >> web.log 2>&1 &
WEB_PID=$!
echo "   ✅ Web Dashboard başlatıldı (PID: $WEB_PID)"

sleep 2

# Kontrol
echo ""
echo "=== DURUM KONTROLÜ ==="
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot çalışıyor (PID: $(pgrep -f 'python.*main.py' | head -1))"
else
    echo "❌ Bot çalışmıyor!"
fi

if pgrep -f "web_dashboard" > /dev/null; then
    echo "✅ Web Dashboard çalışıyor (PID: $(pgrep -f 'web_dashboard' | head -1))"
    echo "   🌐 URL: http://localhost:5001"
else
    echo "❌ Web Dashboard çalışmıyor!"
fi

echo ""
echo "📝 Log dosyaları:"
echo "   Bot: tail -f bot.log"
echo "   Web: tail -f web.log"
