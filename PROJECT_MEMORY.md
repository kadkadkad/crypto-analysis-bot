# 🧠 RADAR ULTRA - PROJECT MEMORY (CONTEXT FILE)
> **Last Updated:** 2026-01-22
> **Status:** Release Candidate (Stable)
> **Server:** Oracle Cloud (141.144.251.86)

---

## 🏗️ PROJE MİMARİSİ
Bu proje, Binance üzerinden kripto verilerini analiz eden, yapay zeka destekli sinyaller üreten ve web tabanlı (Flask) bir dashboard sunan bir bottur.

### 📂 Kritik Dosyalar ve Görevleri
*   **`main.py`**: Ana beyin. Veri toplama, analiz döngüsü, sinyal üretimi burada döner.
    *   *Önemli Fonksiyon:* `calculate_asset_risk` (Coin bazlı risk hesabı).
    *   *Önemli Fonksiyon:* `handle_advanced_risk_analysis` (Raporu tetikler ve kaydeder).
*   **`market_analyzer.py`**: Piyasayı genel analiz eden modül. **Risk Raporu buradan çıkar.**
    *   *Önemli Fonksiyon:* `generate_market_risk_report` (Rapor metnini oluşturur).
*   **`web_dashboard.py`**: Flask sunucusu. `dashboard_v2.html` şablonunu sunar ve API isteklerini karşılar.
    *   *Port:* 8050
*   **`binance_client.py`**: Binance API istemcisi. `async` çalışır.
    *   *Önemli:* `trades` verisini (işlem sayısı) buradan çeker.
*   **`system_validator.py`**: Veri doğrulama modülü. Sinyal kalitesini denetler.

---

## ✅ SON YAPILANLAR (STATUS LOG)
**2026-01-22 Tarihli Büyük Güncelleme:**
1.  **Risk Raporu Tamiri:**
    *   Rapor dili tamamen **İngilizce** yapıldı (`market_analyzer.py`).
    *   "0 coins" sorunu çözüldü (Dil uyuşmazlığı giderildi).
    *   Whale Risk eşiği 100M USD'ye çıkarıldı.
    *   LS Imbalance formülü yumuşatıldı (Sürekli 100/100 vermemesi için).
    *   Raporun `web_reports.json` dosyasına kaydedilmemesi sorunu çözüldü.
2.  **Web Arayüzü (Dashboard):**
    *   Sidebar (Menü) kaydırma sorunu CSS ile çözüldü.
    *   Çalışmayan menü öğeleri (Whale Movement, Order Block) gizlendi.
3.  **Sistem Kararlılığı:**
    *   `calculate_buyer_ratio` fonksiyonundaki çökme (crash) sorunu (pandas kolon hatası) giderildi.
    *   `reversal_bullish` gibi verimsiz sinyaller kaldırıldı.
4.  **Veri Doğrulama:**
    *   Whale Activity verisinin (Trades) gelmeme sorunu çözüldü.

---

## 🚀 DEVAM EDİLECEK İŞLER (TODO)
Bu projeye geri dönüldüğünde odaklanılması gerekenler:
1.  **Genel İstekler:** Kullanıcının "genel isteklerini" tamamlamadık. (Detaylandırılmalı).
2.  **Yeni Özellikler:** Whale Movement ve Order Block raporlarının backend tarafını düzeltip menüye geri eklemek.
3.  **Mobil Uyumluluk:** Dashboard mobilde daha iyi görünebilir.

---

## 🛠️ KRİTİK KOMUTLAR (CHEAT SHEET)

### 1. Oracle Sunucusuna Bağlanma & Update
```bash
ssh -i id_rsa_oracle -o StrictHostKeyChecking=no ubuntu@141.144.251.86 "cd ~/crypto-analysis-bot && git pull origin main"
```

### 2. Botu ve Web Dashboard'u Yeniden Başlatma (HARD RESTART)
```bash
ssh -i id_rsa_oracle -o StrictHostKeyChecking=no ubuntu@141.144.251.86 "
pkill -f 'python main.py'
pkill -f 'python -u web_dashboard.py'
cd ~/crypto-analysis-bot
nohup ./venv/bin/python main.py > bot.log 2>&1 &
nohup ./venv/bin/python -u web_dashboard.py > web.log 2>&1 &
echo 'Systems Restarted'
"
```

### 3. Logları İzleme
```bash
ssh -i id_rsa_oracle -o StrictHostKeyChecking=no ubuntu@141.144.251.86 "tail -f ~/crypto-analysis-bot/bot.log"
```

---

## 📝 ÖZEL NOTLAR
*   **Tasarım:** Estetik ve "Premium" hissiyat çok önemli. Basit tasarımlardan kaçın.
*   **Dil:** Raporlar İngilizce olmalı. Kod içindeki Türkçe stringler raporlara sızmamalı.
*   **Altyapı:** Oracle Cloud kullanılıyor. Dosya yolları `/home/ubuntu/crypto-analysis-bot/`.
