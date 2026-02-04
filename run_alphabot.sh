#!/bin/bash

# AlphaBot Autonomous Trader - Continuous Runner
# Her 5 dakikada market tarar, trade yapar ve öğrenir

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                    🤖 ALPHABOT - AUTO RUNNER                          ║"
echo "║                  Autonomous 24/7 Trading Bot                          ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# İlk çalıştırmada learning summary göster
if [ -f "alpha_bot_learning.json" ]; then
    echo "📚 Mevcut öğrenme dosyası bulundu"
    echo "   Analiz edilen coinler: $(python3 -c "import json; print(len(json.load(open('alpha_bot_learning.json'))['coins_analyzed']))" 2>/dev/null || echo "?")"
else
    echo "🆕 İlk çalıştırma - learning başlıyor"
fi

echo ""
echo "⏰ Çalışma programı:"
echo "   • Her 5 dakikada market scan"
echo "   • Otomatik coin seçimi (5 kriter)"
echo "   • Otomatik trade execution"
echo "   • Sürekli learning ve iyileştirme"
echo ""
echo "🛑 Durdurmak için: Ctrl+C"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

cycle=1

while true; do
    echo "┌──────────────────────────────────────────────────────────────────────┐"
    echo "│ CYCLE #$cycle - $(date '+%Y-%m-%d %H:%M:%S')                         │"
    echo "└──────────────────────────────────────────────────────────────────────┘"
    
    # Run bot
    python3 alpha_bot.py
    
    exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "⚠️  Bot error (exit code: $exit_code) - Devam ediliyor..."
    fi
    
    echo ""
    echo "⏳ 5 dakika bekleniyor... (Sonraki cycle: $(date -v+5M '+%H:%M:%S' 2>/dev/null || date -d '+5 minutes' '+%H:%M:%S'))"
    echo ""
    
    ((cycle++))
    sleep 300  # 5 minutes
done
