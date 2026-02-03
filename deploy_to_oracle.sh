#!/bin/bash

# Configuration
# LÜTFEN AŞAĞIDAKİ BİLGİLERİ KENDİ SUNUCUNA GÖRE DÜZENLE
SERVER_USER="ubuntu"  # Genelde ubuntu veya opc
SERVER_IP="YOUR_SERVER_IP" # Sunucu IP adresini buraya yazmalısın
PROJECT_DIR="~/crypto-analysis-bot" # Sunucudaki proje klasörü

echo "🚀 Deploying updates to remote server..."

ssh $SERVER_USER@$SERVER_IP << EOF
    cd $PROJECT_DIR
    
    echo "⬇️ Pulling latest changes from GitHub..."
    git pull
    
    echo "🔄 Restarting Web Dashboard Service..."
    # Servis adını kontrol et (web-dashboard veya crypto-bot olabilir)
    sudo systemctl restart web-dashboard || sudo systemctl restart crypto-bot
    
    echo "✅ Deployment Complete!"
EOF
