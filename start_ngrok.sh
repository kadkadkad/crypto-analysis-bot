#!/bin/bash
# Ngrok ile Web Dashboard'u İnternete Açma

echo "🌐 Ngrok başlatılıyor..."
echo ""
echo "⚠️  İlk kullanımda auth token gerekir:"
echo "   1. https://dashboard.ngrok.com/get-started/your-authtoken"
echo "   2. Ücretsiz hesap aç"
echo "   3. Token'ı kopyala"
echo "   4. Çalıştır: ngrok config add-authtoken YOUR_TOKEN_HERE"
echo ""
echo "🚀 Web Dashboard internete açılıyor..."
echo ""

# Ngrok başlat
ngrok http 5001

# URL görünecek:
# Forwarding  https://abc123.ngrok-free.app -> http://localhost:5001
