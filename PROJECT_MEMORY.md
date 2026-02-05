# 🧠 RADAR ULTRA - PROJECT MEMORY (CONTEXT FILE)
> **Last Updated:** 2026-02-05
> **Status:** Live & Stable + Paper Trading + AlphaBot
> **Server:** Oracle Cloud (141.144.251.86)

---

## 🏗️ PROJE MİMARİSİ
Bu proje, Binance üzerinden kripto verilerini analiz eden, yapay zeka destekli sinyaller üreten, **paper trading sistemi** ve **otonom AI trading botu (AlphaBot)** içeren web tabanlı (Flask) bir platform.

### 📂 Kritik Dosyalar ve Görevleri

#### **Core System:**
*   **`main.py`**: Ana beyin. Veri toplama, analiz döngüsü, sinyal üretimi burada döner.
*   **`web_dashboard.py`**: Flask sunucusu. API endpoints, web raporları, dashboard UI.
*   **`binance_client.py`**: Binance API istemcisi (veri çekimi).
*   **Templates klasörü**: HTML template'leri (dashboard UI).
*   **`web_reports.json`**: Web dashboard'da görüntülenen tüm raporlar.

#### **Trading Systems (YENİ! 2026-02-05):**
*   **`paper_trading.py`** (358 satır): Paper trading backend - Ross Cameron risk yönetimi
    - Position sizing, stop-loss/target tracking
    - Performance analytics (win rate, profit factor, R multiples)
    - Günlük loss limit (3 kayıp = stop)
    - API endpoints: `/api/paper-trading/*`

*   **`alpha_bot.py`** (551 satır): Otonom self-learning AI trader
    - Market scanning (5 kriter: Smart Score, Gap Up, Volume, Price, Float)
    - Otomatik coin seçimi ve trade execution
    - Loss diagnosis ve strategy optimization
    - Learning database (`alpha_bot_learning.json`)
    - Decision log (`alpha_bot_decisions.json`)

*   **`ross_playbook.py`** (153 satır): Ross Cameron 7-step scaling strategy
    - Bull flag pattern detection
    - Position scaling logic
    - Risk/Reward hesaplamaları

*   **`run_alphabot.sh`**: 24/7 AlphaBot runner (her 5 dakikada market scan)

#### **Documentation:**
*   **`ALPHABOT_README.md`**: Kapsamlı AlphaBot kullanım kılavuzu
*   **`PLAYBOOK_USAGE.md`**: Ross playbook pratik kılavuzu
*   **`PAPER_TRADING_GUIDE.md`**: Paper trading API dökümanı
*   **`test_paper_trading.sh`**: Hızlı test scripti

---

## 📝 SON YAPILANLAR

### ✅ PAPER TRADING & ALPHABOT SİSTEMİ - BAŞARILI! (2026-02-05)

#### **🎯 Hedef:**
Ross Cameron'ın momentum trading stratejisini kullanarak:
- Paper trading ile risk almadan strateji testi
- Otonom AI bot ile 24/7 market tarama
- Self-learning sistem ile sürekli iyileştirme
- 90 günde 5-10x hedef (compound strategy)

#### **🚀 Eklenen Özellikler:**

**1. Paper Trading Backend (`paper_trading.py`):**
- ✅ Pozisyon açma/kapama (entry/stop/target)
- ✅ Otomatik position sizing (2% risk rule)
- ✅ R/R ratio kontrolü (minimum 2:1)
- ✅ Stop-loss ve target otomatik tracking
- ✅ Win rate, profit factor, streak tracking
- ✅ Günlük loss limit (3 kayıp sonrası durur)
- ✅ Trade history ve portfolio stats

**2. AlphaBot - Otonom AI Trader (`alpha_bot.py`):**
- ✅ **Market Scanning:** Dashboard'dan 50 coin tarar
- ✅ **5 Kriter Kontrolü:**
    1. Smart Score > 65
    2. 24h Change > 8% (gap up)
    3. Volume spike (top volume)
    4. Price $0.10-$50 arası
    5. Healthy float (low supply risk)
- ✅ **Coin Selection:** En iyi Smart Score + R/R ratio
- ✅ **Auto Trade Execution:** Paper trading ile pozisyon açar
- ✅ **Position Monitoring:** Stop/target auto-close
- ✅ **Loss Diagnosis:** 
    - "Stop-loss hit - Volatilite fazla"
    - "Fake breakout - Pattern bozuldu"
    - "Ters trend - Entry erken"
- ✅ **Strategy Optimization:**
    - Win rate < 55% → "Daha seçici ol (min Smart Score artır)"
    - Avg loss > avg win → "Stop-loss sıkılaştır"
    - Win rate > 65% → "R/R ratio yükselt"
- ✅ **Learning Database:** Coin performansları, winning/losing patterns

**3. Dashboard UI Entegrasyonu:**
- ✅ **💰 PAPER TRADING** kategorisi eklendi:
    - Portfolio Stats
    - Open Positions
    - Trade History
    - New Trade
- ✅ **🤖 ALPHABOT** kategorisi eklendi:
    - Bot Status
    - Learning Stats
    - Recent Decisions
    - Ross Playbook

**4. API Endpoints (`web_dashboard.py`):**
```
GET  /api/paper-trading/stats       # Portfolio istatistikleri
POST /api/paper-trading/open        # Yeni pozisyon aç
POST /api/paper-trading/close       # Pozisyon kapat
GET  /api/paper-trading/positions   # Açık pozisyonlar
GET  /api/paper-trading/trades      # Trade geçmişi
POST /api/paper-trading/reset       # Portföyü sıfırla
```

#### **📊 Dosya Yapısı:**
```
+ paper_trading.py              (358 satır)
+ alpha_bot.py                  (551 satır)
+ ross_playbook.py              (153 satır)
+ run_alphabot.sh               ( 56 satır)
+ ALPHABOT_README.md            (350 satır)
+ PLAYBOOK_USAGE.md             (206 satır)
+ PAPER_TRADING_GUIDE.md        (198 satır)
+ test_paper_trading.sh         ( 30 satır)
~ templates/dashboard_v2.html   (+44 satır - butonlar)
~ web_dashboard.py              (+110 satır - API endpoints)
─────────────────────────────────────────
TOPLAM: 1,360+ satır yeni kod!
```

#### **🎓 Ross Cameron 7-Step Playbook:**
1. **Coin Bul:** 5 kriteri sağlayan (haber, gap up, volume, price, float)
2. **Pattern Bekle:** Bull flag (squeeze → pullback)
3. **Giriş:** İlk mum yeni zirve yapınca (1/4 pozisyon)
4. **Stop:** Pullback düşük altına (%2-2.5)
5. **Hedef:** High of day retest (min 2:1 R/R)
6. **Scaling:** Kazanan trade'e ekle (kaybedene asla!)
7. **Çıkış:** Target hit veya ters sinyal

---

### ✅ MM Analysis Report - BAŞARILI! (2026-02-04)
- **Sorun:** "MM Analysis" raporu web_reports.json'da yoktu
- **Çözümler:** 
  1. `handle_market_maker_analysis()` fonksiyonu modifiye edildi - artık raporu return ediyor
  2. `market_analyzer.` prefix'i eklendi
  3. Stop Hunt ve Compression çıktıları human-readable formata çevrildi
  4. Web reports sync kısmına eklendi
- **Sonuç:** MM Analysis düzgün çalışıyor ve dashboard'da görünüyor! 🎉

### 🎯 Whale Heatmap Revizyonu (Önceki)
*   Whale Movement raporu RSI Heatmap stiline dönüştürüldü.
*   HTML encoding bozulması giderildi.
*   Tasarım: Koyu kartlar, renkli border, büyük rakamlar.

---

## ⏭️ DEVAM EDİLECEK İŞLER

### **Paper Trading & AlphaBot:**
1. ✅ **Test Phase (7 gün):** Paper trading ile 10+ trade
2. ✅ **AlphaBot Monitoring:** Learning database kontrol
3. ⏳ **Strategy Optimization:** Win rate > 60% sağlanana kadar
4. ⏳ **Production Ready:** 30 gün sonrası gerçek para (küçük sermaye)

### **Genel:**
1. Dashboard butonlarına JavaScript fonksiyonları tam entegre et
2. AlphaBot API endpoints ekle (status, learning, decisions)
3. Ross Playbook report endpoint oluştur
4. Mobil responsive optimizasyon

---

## 💡 ÖNEMLİ HATIRLATMALAR

### **Paper Trading Kullanımı:**
```bash
# Stats kontrol
curl -u admin:Admin123! http://141.144.251.86:5001/api/paper-trading/stats

# Trade aç (örnek)
curl -X POST -u admin:Admin123! \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "entry": 103000,
    "stop": 102500,
    "target": 104500,
    "risk_percent": 2.0
  }' \
  http://141.144.251.86:5001/api/paper-trading/open

# Pozisyon kapat
curl -X POST -u admin:Admin123! \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "reason": "Manual"}' \
  http://141.144.251.86:5001/api/paper-trading/close
```

### **AlphaBot Çalıştırma:**
```bash
# Oracle'a SSH
ssh -i id_rsa_oracle ubuntu@141.144.251.86

# Tek cycle test
cd ~/crypto-analysis-bot
python3 alpha_bot.py

# 24/7 sürekli mod
nohup ./run_alphabot.sh > alphabot.log 2>&1 &

# Log takip
tail -f alphabot.log
```

### **Deployment Süreci (Oracle VM):**
1. **Lokal Geliştirme** → GitHub'a push
2. **Oracle SSH**: `ssh -i id_rsa_oracle ubuntu@141.144.251.86`
3. **Kodları Güncelle**:
    ```bash
    cd ~/crypto-analysis-bot
    git pull origin main
    ```
4. **Servisleri Yeniden Başlat**:
    ```bash
    sudo systemctl restart crypto-bot
    ```
5. **Log Kontrol**: `sudo journalctl -u crypto-bot -f`

### **Kritik Özel Notlar:**
- ⚠️ **PROFESYONEL dil kullan** (resmi ve teknik)
- 🎨 **Estetik ve Premium** hissiyat önemli
- 🌐 **Raporlar İngilizce** olmalı
- 💰 **Paper Trading:** İlk 30 gün risk alma, sadece öğren
- 🤖 **AlphaBot:** Self-learning, 50+ trade sonrası stratejiler optimize olur

---

## 🛠️ KRİTİK KOMUTLAR (CHEAT SHEET)

### 1. Oracle Sunucusuna Bağlanma & Update
```bash
ssh -i id_rsa_oracle -o StrictHostKeyChecking=no ubuntu@141.144.251.86 "cd ~/crypto-analysis-bot && git pull origin main"
```

### 2. Bot Yeniden Başlatma
```bash
ssh -i id_rsa_oracle ubuntu@141.144.251.86 "sudo systemctl restart crypto-bot"
```

### 3. Logları İzleme
```bash
ssh -i id_rsa_oracle ubuntu@141.144.251.86 "sudo journalctl -u crypto-bot -f"
```

### 4. Paper Trading Test
```bash
cd /path/to/crypto-analysis-bot
./test_paper_trading.sh
```

### 5. AlphaBot Status
```bash
ssh -i id_rsa_oracle ubuntu@141.144.251.86 "ps aux | grep alpha_bot"
```

---

## � BEKLENEN SONUÇLAR (30 GÜN)

### **Paper Trading:**
- **Başlangıç:** $5,000
- **Hedef:** $6,000-7,500 (1.2-1.5x)
- **Trades:** 30-50
- **Win Rate:** 60-70%
- **Profit Factor:** 2.0+

### **AlphaBot:**
- **Total Scans:** 8,000+
- **Trades Executed:** 40-60
- **Learning Patterns:** 50+
- **Strategy Adjustments:** 5-10
- **Best Coins Identified:** 10-15 (>70% win rate)

---

## 📝 ÖZEL NOTLAR
*   **İletişim:** PROFESYONEL ve teknik dil.
*   **Tasarım:** Premium estetik.
*   **Dil:** İngilizce raporlar.
*   **Trading:** Ross Cameron momentum stratejisi.
*   **Risk:** 2% per trade, 3 loss daily limit.
*   **Compound:** 90 günde 5-10x hedef (realistic: 3-5x).
