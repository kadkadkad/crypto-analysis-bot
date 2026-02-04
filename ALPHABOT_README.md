# 🤖 ALPHABOT - Otonom Self-Learning Trading Bot

## 🎯 **NE YAPAR?**

AlphaBot tamamen otonom bir trading botu:

### **1. MARKET TARAMA (Auto)**
- Dashboard'dan tüm coinleri çeker
- Ross Cameron'ın 5 kriterini kontrol eder:
  ```
  ✅ Smart Score > 65
  ✅ 24h Change > 8% (gap up)
  ✅ Volume spike (top volume coins)
  ✅ Price $0.10-$50 arası
  ✅ Healthy float (supply risk low)
  ```

### **2. COİN SEÇİMİ (Auto)**
- 5 kriteri geçen tüm coinleri bulur
- En iyi Smart Score + R/R ratio'ya sahip olanı seçer
- Entry/Stop/Target seviyelerini hesaplar

### **3. TRADE EXECUTION (Auto)**
- Paper trading ile pozisyon açar
- Optimal risk % kullanır (learning'den)
- Stop-loss ve target otomatik set eder

### **4. MONİTORİNG (Auto)**
- Açık pozisyonları sürekli kontrol eder
- Stop hit → Otomatik kapatır
- Target hit → Otomatik kapatır

### **5. LEARNING (Auto - EN ÖNEMLİ!)**
**Her trade sonrası:**
- ✅ Kazanan trade → Pattern kaydedilir
- ❌ Kaybeden trade → Neden analiz edilir:
  - "Stop-loss hit - Volatilite fazla"
  - "Ters trend - Fake breakout"
  - "Entry zamanlaması erken"

**Strateji İyileştirmesi:**
- Win rate < 55% → "Daha seçici ol, min Smart Score artır"
- Avg loss > avg win → "Stop-loss'ları sıkılaştır"
- Win rate > 65% → "R/R ratio yükselt, daha agresif hedef"

---

## 📊 **DOSYA YAPISI**

```
alpha_bot.py              # Ana bot kodu
alpha_bot_learning.json   # Öğrenme database
alpha_bot_decisions.json  # Tüm kararlar log
run_alphabot.sh          # Sürekli çalıştırıcı
```

---

## 🚀 **NASIL ÇALIŞTIRILIR?**

### **Option 1: Tek Cycle (Test)**
```bash
cd /Users/abdulkadirkarkinli/.gemini/antigravity/scratch/crypto-analysis-bot
python3 alpha_bot.py
```

**Yapacakları:**
1. Market scan (tüm coinler)
2. 5 kriter kontrolü
3. En iyi coin seçimi
4. Trade açma (eğer setup varsa)
5. Açık pozisyonları kontrol
6. Learning summary

### **Option 2: Sürekli (24/7 Auto)**
```bash
chmod +x run_alphabot.sh
./run_alphabot.sh
```

**Her 5 dakikada:**
- Market scan
- Yeni coin ara
- Trade aç (gerekirse)
- Pozisyonları kapat (stop/target hit)
- Öğren ve iyileştir

**Durdurmak:** `Ctrl+C`

---

## 🧠 **LEARNING SİSTEMİ**

### **alpha_bot_learning.json İçeriği:**

```json
{
  "total_scans": 42,
  "coins_analyzed": {
    "SOLUSDT": {
      "total_trades": 5,
      "wins": 3,
      "losses": 2,
      "total_pnl": 127.50,
      "avg_r_multiple": 1.8
    },
    "BTCUSDT": {
      "total_trades": 3,
      "wins": 2,
      "losses": 1,
      "total_pnl": 85.20,
      "avg_r_multiple": 2.1
    }
  },
  "winning_patterns": [
    {
      "symbol": "SOLUSDT",
      "r_multiple": 2.3,
      "pnl": 57.50,
      "lesson": "SOLUSDT kazandırdı: 2.30R - Bu coin güvenilir"
    }
  ],
  "losing_patterns": [
    {
      "symbol": "ETHUSDT",
      "r_multiple": -1.0,
      "pnl": -25.00,
      "reason": "Stop-loss hit - Volatilite fazla",
      "lesson": "ETHUSDT kaybettirdi: Gelecekte dikkat!"
    }
  ],
  "strategy_adjustments": [
    {
      "timestamp": "2026-02-05T00:45:00",
      "type": "SELECTIVITY",
      "message": "Win rate düşük (52%). Daha seçici ol!",
      "action": "Min Smart Score'u 70'e çıkar"
    }
  ],
  "performance_metrics": {
    "best_rr_ratio": 2.2,
    "optimal_risk_percent": 0.5
  }
}
```

### **Nasıl Öğreniyor?**

**1. Pattern Recognition:**
- SOLUSDT 3/5 kazandırdı → "Güvenilir coin, prioritize et"
- ETHUSDT 1/3 kazandırdı → "Riskli coin, dikkatli ol"

**2. Loss Diagnosis:**
```python
def diagnose_loss(trade_result):
    if stop_hit:
        return "Volatilite fazla - Entry zamanlaması erken"
    if reverse_trend:
        return "Fake breakout - Pattern bozuldu"
    return "Data yetersiz"
```

**3. Strategy Auto-Tuning:**
- Win rate kötü → Min Smart Score artır (65 → 70)
- Loss büyük → Stop tighten (2.5% → 2%)
- Win rate iyi → R/R artır (2.0 → 2.5)

---

## 📈 **ÖRNEK ÇIKTI**

```
════════════════════════════════════════════════════════════════════════════════
🔍 MARKET SCAN BAŞLIYOR
════════════════════════════════════════════════════════════════════════════════
📊 50 coin taranıyor...

✅ ADAY BULUNDU: SOLUSDT
   ✅ Smart Score OK: 78.5
   ✅ Gap up OK: 12.3%
   ✅ Volume spike assumed (top volume)
   ✅ Price OK: $145.23
   ✅ Float assumed healthy (high smart score)
   📈 R/R Ratio: 2.1

🎯 EN İYİ ADAY: SOLUSDT
   Smart Score: 78.5
   Gap Up: 12.3%
   R/R Ratio: 2.1

🚀 TRADE AÇILIYOR: SOLUSDT
   Entry: $145.96
   Stop: $142.31
   Target: $153.26
   R/R: 2.1

✅ TRADE AÇILDI!
   Position size: 13.7 SOL
   Risk amount: $25.00

════════════════════════════════════════════════════════════════════════════════
🧠 ALPHABOT ÖĞRENME ÖZETİ
════════════════════════════════════════════════════════════════════════════════

📊 GENEL İSTATİSTİKLER:
   Total scans: 15
   Coins analyzed: 7
   Winning patterns: 4
   Losing patterns: 2

🎯 EN İYİ COINLER:
   SOLUSDT: 3W/1L (75.0%) - Avg R: 1.9
   BTCUSDT: 2W/1L (66.7%) - Avg R: 1.5
   ETHUSDT: 1W/2L (33.3%) - Avg R: -0.3

💡 SON DERSLER:
   2026-02-05: ETHUSDT kaybettirdi: Stop-loss hit - Volatilite fazla
   2026-02-04: LINKUSDT kaybettirdi: Fake breakout - Pattern bozuldu
```

---

## ⚙️ **AYARLAR**

### **Risk Management:**
```python
# alpha_bot.py içinde değiştirin:
optimal_risk_percent = 0.5  # Her trade'de max %0.5 risk
daily_loss_limit = 3         # Günde max 3 kayıp
max_open_positions = 2       # Aynı anda max 2 pozisyon
```

### **Selection Criteria:**
```python
# 5 kriterin threshold'larını ayarlayın:
min_smart_score = 65
min_gap_up_percent = 8
min_rr_ratio = 1.5
price_range = (0.10, 50)
```

### **Scan Frequency:**
```bash
# run_alphabot.sh içinde:
sleep 300  # 5 dakika (değiştirebilirsiniz)
```

---

## 🎯 **7 GÜNLÜK TEST PLANI**

### **Gün 1-2: Monitoring**
```bash
# Tek cycle çalıştır, gözlemle
python3 alpha_bot.py

# Log'ları oku
cat alpha_bot_decisions.json | python3 -m json.tool
```

### **Gün 3-5: Auto Mode**
```bash
# 24 saat çalıştır
./run_alphabot.sh

# Her saat kontrol et:
curl http://141.144.251.86:5001/api/paper-trading/stats
```

### **Gün 6-7: Learning Review**
```python
python3 -c "
import json
with open('alpha_bot_learning.json') as f:
    data = json.load(f)
    print('Total scans:', data['total_scans'])
    print('Win patterns:', len(data['winning_patterns']))
    print('Strategy adjustments:', len(data['strategy_adjustments']))
"
```

---

## 🔥 **PRO FEATURES**

### **1. Coin Blacklist (Gelecek)**
Sürekli kaybettiren coinleri otomatik blacklist:
```python
if coin_stats['wins'] / coin_stats['total_trades'] < 0.3:
    # Bu coin'i skip et
```

### **2. Time-of-Day Optimization**
En iyi trade saatlerini öğren:
```python
# Sabah 09:00-11:00 win rate %70
# Akşam 18:00-20:00 win rate %45
# → Sadece sabahları trade yap
```

### **3. Multi-Timeframe Confirmation**
5m + 15m + 1h trend aynı yöndeyse entry:
```python
if trend_5m == trend_15m == trend_1h == "bullish":
    confidence += 50
```

---

## ⚠️ **ÖNEMLİ NOTLAR**

1. **İLK 30 GÜN:** Bot paper trading'de öğreniyor
   - Gerçek para risk YOK
   - Stratejisini geliştiriyor
   - Win rate %60+ olana kadar bekleyin

2. **Data Yetersizse:** İlk 10 trade'de learning kısıtlı
   - Min 20 trade sonrası güvenilir pattern'ler
   - Min 50 trade sonrası strategy tuning

3. **Market Conditions:** Bot trend değişimlerini algılayamayabilir
   - Bear market'te performans düşer
   - High volatility'de stop-loss s ık hit eder

---

## 📚 **İLGİLİ DOSYALAR**

- **`paper_trading.py`** - Backend paper trading
- **`ross_playbook.py`** - 7-step strategy
- **`PLAYBOOK_USAGE.md`** - Manuel kullanım

---

## 🚀 **İLK BAŞLANGIÇ**

```bash
# 1. Bot'u başlat (tek cycle test)
python3 alpha_bot.py

# 2. Learning dosyasını kontrol et
cat alpha_bot_learning.json | python3 -m json.tool

# 3. Sürekli mode'a geç
./run_alphabot.sh
```

---

**AlphaBot sizin için 24/7 çalışacak, öğrenecek ve gelişecek!** 🤖📈🧠
