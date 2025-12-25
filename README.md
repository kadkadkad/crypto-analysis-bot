# 🚀 Crypto Analysis Bot

Gerçek zamanlı kripto para piyasası analiz platformu. 50+ teknik gösterge, whale tracking, market risk analizi ve daha fazlası!

## ✨ Özellikler

- 📊 **50+ Teknik Gösterge:** RSI, MACD, EMA, ADX, MFI, Bollinger Bands
- 🐋 **Whale Tracking:** Net accumulation, money flow analizi
- ⚠️ **Risk Analizi:** Market maker detection, liquidation heatmaps
- 🕯️ **Candlestick Patterns:** 7+ mum formasyonu tespiti
- 📺 **YouTube Alpha:** Video transkript analizi (LLM ile)
- 🌐 **Web Dashboard:** Güvenli, authentication'lı arayüz
- 🔔 **Telegram Bot:** Interaktif menüler ve raporlar

## 🔐 Güvenlik

- ✅ HTTP Basic Authentication
- ✅ Rate Limiting (DDoS koruması)
- ✅ CORS kontrollü
- ✅ Otomatik HTTPS (Render.com)

## 🚀 Hızlı Başlangıç

### Local Çalıştırma:

```bash
# 1. Repository'yi clone'la
git clone https://github.com/KULLANICI_ADIN/crypto-analysis-bot.git
cd crypto-analysis-bot

# 2. Virtual environment oluştur
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencies kur
pip install -r requirements.txt

# 4. Environment variables ayarla
cp .env.example .env
# .env dosyasını düzenle (API keys, passwords vs.)

# 5. Bot ve Web Dashboard'u başlat
./start_all.sh
```

### Render.com Deployment:

Detaylı adımlar için → [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)

1. GitHub'a push et
2. Render.com'da yeni Web Service oluştur
3. Environment variables ekle
4. Deploy et!

## 📊 Kullanım

### Web Dashboard:
```
http://localhost:5001
Username: admin
Password: (senin belirlediğin)
```

### Telegram Bot:
Bot'u Telegram'da başlat → `/start`

## 📁 Proje Yapısı

```
crypto-analysis-bot/
├── main.py                    # Ana bot mantığı
├── web_dashboard.py           # Web arayüzü (güvenli)
├── binance_client.py          # Binance/Bybit API
├── market_analyzer.py         # Risk analizi
├── youtube_analyzer.py        # YouTube LLM analizi
├── candlestick_patterns.py    # Mum formasyonları
├── telegram_bot.py             # Telegram integration
├── utils.py                   # Yardımcı fonksiyonlar
├── requirements.txt           # Dependencies
├── Dockerfile                 # Container deployment
├── Procfile                   # Render/Heroku config
└── templates/                 # Web UI templates

```

## 🔧 Ayarlar

`.env` dosyası:

```env
# Bot
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id

# LLM APIs
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key

# Web Security
ADMIN_USERNAME=admin
ADMIN_PASSWORD=güçlü_şifre_buraya!
```

## 📚 Dökümanlar

- [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) - Render deployment rehberi
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Genel deployment rehberi
- [QUICK_START.md](QUICK_START.md) - Hızlı başlangıç
- [CODE_ANALYSIS_TR.md](CODE_ANALYSIS_TR.md) - Kod analizi

## 🛠️ Teknolojiler

- **Backend:** Python 3.9+, Flask, AsyncIO
- **APIs:** Binance, Bybit, YouTube Transcript, Groq/Gemini LLM
- **Güvenlik:** Flask-HTTPAuth, Flask-Limiter, CORS
- **Deployment:** Docker, Gunicorn, Render.com
- **Analiz:** Pandas, NumPy, TA-Lib, Scikit-learn

## 📈 Roadmap

- [ ] PostgreSQL database entegrasyonu
- [ ] Real-time WebSocket feeds
- [ ] Custom domain support
- [ ] Multi-language support
- [ ] Mobile app (React Native)
- [ ] Email/SMS alertleri

## 🤝 Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır!

## 📄 Lisans

MIT License

## 📞 İletişim

Sorular için Issue açabilirsiniz.

---

**⚠️ Disclaimer:** Bu bot sadece bilgilendirme amaçlıdır. Yatırım tavsiyesi değildir. Kripto para yatırımları risklidir.
