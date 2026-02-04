# 📊 PAPER TRADING SİSTEMİ - KULLANIM KILAVUZU

## 🎯 Hızlı Başlangıç

### 1. API Endpoint'leri

**BASE URL:** `http://141.144.251.86:5001`

#### **Stats (İstatistikler)**
```bash
GET /api/paper-trading/stats
```

#### **Pozisyon Aç**
```bash
POST /api/paper-trading/open
{
  "symbol": "BTCUSDT",
  "entry": 103000,
  "stop": 102500,
  "target": 104500,
  "risk_percent": 2.0
}
```

#### **Pozisyon Kapat**
```bash
POST /api/paper-trading/close
{
  "symbol": "BTCUSDT",
  "exit_price": 103500,  # Optional - yoksa güncel fiyat
  "reason": "Target Hit"
}
```

#### **Açık Pozisyonlar**
```bash
GET /api/paper-trading/positions
```

#### **Trade Geçmişi**
```bash
GET /api/paper-trading/trades
```

---

## 📝 PAPER TRADING WORKFLOW

### **SABAH RUTINI (09:00-09:30)**

1. **Dashboard'u Aç:** http://141.144.251.86:5001
2. **Stats Kontrol:**
   ```bash
   curl http://141.144.251.86:5001/api/paper-trading/stats
   ```

3. **Shortlist Oluştur:**
   - Smart Score > 70
   - Order Flow > 60
   - Volume Spike > 5x

### **TRADE EXECUTION (09:30-16:00)**

**Bull Flag Pattern Gördüğünde:**

1. **Coin Analysis Report** aç:
   - Entry seviyesini al
   - Support (stop-loss) seviyesini al
   - Resistance (target) seviyesini al

2. **R/R Hesapla:**
   ```
   Risk = Entry - Stop
   Reward = Target - Entry
   R/R = Reward / Risk
   
   Eğer R/R < 2.0 → Trade alma!
   ```

3. **Pozisyon Aç (curl örneği):**
   ```bash
   curl -X POST http://141.144.251.86:5001/api/paper-trading/open \
     -H "Content-Type: application/json" \
     -u admin:your_password \
     -d '{
       "symbol": "SOLUSDT",
       "entry": 145.50,
       "stop": 144.00,
       "target": 148.50,
       "risk_percent": 2.0
     }'
   ```

4. **Sistem Otomatik Hesaplar:**
   - Position size
   - Risk amount ($)
   - Total position value

### **EXIT (Otomatik Stop/Target Check)**

Sistem her coingeçki fiyat kontrolü yapar ve:
- **Stop-loss hit** ise otomatik kapatır
- **Target hit** ise otomatik kapatır

**Manuel Kapat:**
```bash
curl -X POST http://141.144.251.86:5001/api/paper-trading/close \
  -H "Content-Type: application/json" \
  -u admin:your_password \
  -d '{
    "symbol": "SOLUSDT",
    "reason": "Manual Exit"
  }'
```

---

## 📈 STATS AÇIKLAMASI

```json
{
  "current_capital": 5342.50,      # Mevcut sermaye
  "initial_capital": 5000,         # Başlangıç
  "total_pnl": 342.50,            # Toplam kar
  "roi_percent": 6.85,            # % ROI
  "total_trades": 15,             # Toplam trade sayısı
  "winning_trades": 10,           # Kazanan
  "losing_trades": 3,             # Kaybeden
  "scratch_trades": 2,            # Break-even
  "win_rate": 66.67,              # % kazanma oranı
  "avg_win": 145.30,              # Ortalama kazanç
  "avg_loss": -87.20,             # Ortalama kayıp
  "profit_factor": 1.67,          # Avg Win / Avg Loss
  "largest_win": 412.50,          # En büyük kazanç
  "largest_loss": -195.30,        # En büyük kayıp
  "current_streak": 3,            # Aktif streak
  "best_streak": 7,               # En iyi streak
  "daily_loss_count": 0           # Bugün kaç kayıp (max 3)
}
```

---

## ⚠️ GÜVENLİK KURALLARI

### **Otomatik Korumalar:**

1. **Günlük Loss Limit:**
   - 3 kayıp trade sonrası sistem pozisyon açmayı engeller
   - Ertesi gün sıfırlanır

2. **Min R/R Ratio:**
   - R/R < 2.0 pozisyon açılmaz
   - Error döner

3. **Sermaye Kontrolü:**
   - Yetersiz sermaye kontrolü
   - Position value > capital ise error

---

## 🎓 İLK 7 GÜN PLANI

### **Hedef:** Risk almadan stratejiyi öğren

**Gün 1-2:** Setup
- Portföy başlat ($5000)
- Dashboard'a alış
- 5 demo trade yap (gerçek girmek yok)

**Gün 3-5:** Pattern Practice
- Bull flag pattern tanı
- 10+ trade yap
- Sadece >2:1 R/R

**Gün 6-7:** Review
- Stats analiz et
- Win rate %60+ mı?
- Avg win > Avg loss mı?

**7 gün sonrası:**
- **%60+ win rate:** Gerçek paraya geçebilirsin
- **<%60 win rate:** 7 gün daha pratik

---

## 💡 PRO TİPS

1. **Sabah tarama yapmadan trade yapma**
2. **R/R < 2:1 asla alma**
3. **Günlük max 3 trade** (ilk 30 gün)
4. **Her trade'i not al** (neden aldın, neden çıktın)
5. **Haftalık review YAP** (ne doğru/yanlış yaptın)

---

**HAZIR MISIN? İlk paper trade'ini aç ve bana sonucu göster!** 🚀
