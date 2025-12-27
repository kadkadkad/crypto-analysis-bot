#!/bin/bash
# 🚀 Render.com Deployment Hazırlık Scripti

echo "🚀 Render.com Deployment Hazırlığı Başlıyor..."
echo ""

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Git kontrolü
echo "📝 Git repository kontrol ediliyor..."
if [ ! -d ".git" ]; then
    git init
    echo -e "${GREEN}✅ Git repository oluşturuldu${NC}"
else
    echo -e "${YELLOW}⚠️  Git zaten başlatılmış${NC}"
fi

# 2. .env dosyası kontrolü
echo ""
echo "🔐 Environment variables kontrolü..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env dosyası bulunamadı!${NC}"
    echo "   .env.example dosyasını kopyalayıp düzenleyin:"
    echo "   cp .env.example .env"
else
    echo -e "${GREEN}✅ .env dosyası mevcut${NC}"
fi

# 3. Gereksiz dosyaları temizle
echo ""
echo "🧹 Gereksiz dosyalar temizleniyor..."

# Backup tar dosyalarını temizle
rm -f backup_*.tar.gz 2>/dev/null && echo -e "${GREEN}✅ Backup tar dosyaları temizlendi${NC}"

# Log dosyalarını temizle (isteğe bağlı)
# > bot.log
# > web.log

# 4. Git add
echo ""
echo "📦 Dosyalar Git'e ekleniyor..."
git add .gitignore
git add README.md
git add requirements.txt
git add Dockerfile
git add Procfile
git add .env.example
git add *.py
git add templates/ 2>/dev/null
git add *.md

echo -e "${GREEN}✅ Dosyalar Git'e eklendi${NC}"

# 5. Git status
echo ""
echo "📊 Git Durumu:"
git status --short

# 6. Commit (eğer değişiklik varsa)
echo ""
if git diff --cached --quiet; then
    echo -e "${YELLOW}⚠️  Commit edilecek değişiklik yok${NC}"
else
    echo "💾 Değişiklikler commit ediliyor..."
    git commit -m "Production-ready deployment with security features

- Added authentication (HTTP Basic Auth)
- Added rate limiting (DDoS protection)
- Added CORS configuration
- Added health check endpoint
- Updated web_dashboard.py for production
- Added deployment documentation
- Added security measures"
    
    echo -e "${GREEN}✅ Commit başarılı${NC}"
fi

# 7. GitHub instructions
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 GIT HAZIRLIĞI TAMAMLANDI!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📌 SONRAKİ ADIMLAR:"
echo ""
echo "1️⃣  GitHub'da yeni repository oluştur:"
echo "   https://github.com/new"
echo ""
echo "2️⃣  Remote ekle ve push et:"
echo "   git remote add origin https://github.com/KULLANICI_ADIN/crypto-analysis-bot.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3️⃣  Render.com'a deploy et:"
echo "   → https://render.com"
echo "   → New Web Service"
echo "   → GitHub repo seç"
echo "   → Environment variables ekle (ADMIN_PASSWORD vs.)"
echo "   → Deploy!"
echo ""
echo "📚 Detaylı adımlar: RENDER_DEPLOYMENT.md"
echo ""
echo -e "${GREEN}✅ Başarılı deployment için hazırsın!${NC}"
echo ""
