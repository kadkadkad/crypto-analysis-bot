# 🧠 RADAR ULTRA - PROJECT MEMORY (CONTEXT FILE)
> **Last Updated:** 2026-02-04
> **Status:** Live & Stable
> **Server:** Oracle Cloud (141.144.251.86)

---

## 🏗️ PROJE MİMARİSİ
Bu proje, Binance üzerinden kripto verilerini analiz eden, yapay zeka destekli sinyaller üreten ve web tabanlı (Flask) bir dashboard sunan bir bottur.

### 📂 Kritik Dosyalar ve Görevleri
*   **`main.py`**: Ana beyin. Veri toplama, analiz döngüsü, sinyal üretimi burada döner.
*   **`web_dashboard.py`**: Flask sunucusu. API endpoints, web raporları, dashboard UI.
*   **`telegram_bot.py`**: Telegram entegrasyonu (ŞU AN KAPALI).
*   **`binance_client.py`**: Binance API istemcisi (veri çekimi).
*   **Templates klasörü**: HTML template'leri (dashboard UI).
*   **`web_reports.json`**: Web dashboard'da görüntülenen tüm raporlar.

---

##📝 SON YAPILANLAR

### ✅ MM Analysis Report - BAŞARILI! (2026-02-04 17:49)
- **Sorun:** "MM Analysis" raporu web_reports.json'da yoktu
- **Çözümler:** 
  1. `handle_market_maker_analysis()` fonksiyonu modifiye edildi - artık raporu return ediyor
  2. `market_analyzer.` prefix'i eklendi (detect_stophunt_pattern, detect_price_compression)
  3. Stop Hunt ve Compression çıktıları human-readable formata çevrildi
     - **Önce:** `Stop Hunt: {'detected': False}` ❌
     - **Sonra:** `Stop Hunt: ✅ None detected` ✅
  4. Web reports sync kısmına `web_reports["MM Analysis"] = handle_market_maker_analysis()` eklendi
- **Sonuç:** MM Analysis artık düzgün çalışıyor ve dashboard'da görünüyor! 🎉

### 🎯 Whale Heatmap Revizyonu (Önceki)
*   Whale Movement raporu RSI Heatmap stiline dönüştürüldü.
*   HTML encoding bozulması giderildi.
*   Tasarım: Koyu kartlar, renkli border, büyük rakamlar.
*   GitHub'a push edildi, Oracle VM'e deploy edildi.

---

## ⏭️ DEVAM EDİLECEK İŞLER
1.  Genel performans kontrolü (yeni heatmap + MM Analysis)
2.  Order Block Raporu backend entegrasyonu
3.  Mobil responsive optimizasyon

---

## 💡 ÖNEMLİ HATIRLATMALAR

### Deployment Süreci (Oracle VM)
1.  **Lokal Geliştirme** → GitHub'a push
2.  **Oracle SSH**: `ssh -i id_rsa_oracle ubuntu@141.144.251.86`
3.  **Kodları Güncelle**:
    ```bash
    cd ~/crypto-analysis-bot
    git pull origin main
    ```
4.  **Servisleri Yeniden Başlat**:
    ```bash
    sudo systemctl restart crypto-bot
    sudo systemctl restart web-dashboard
    ```
5.  **Log Kontrol**: `sudo journalctl -u crypto-bot -f`

### Kritik Özel Notlar
- ⚠️ **PROFESYONEL dil kullan** ("Abim" gibi hitaplar yasak)
- 🎨 **Estetik ve Premium** hissiyat önemli
- 🌐 **Raporlar İngilizce** olmalı
*   **`market_analyzer.py`**: Piyasayı genel analiz eden modül. **Risk Raporu buradan çıkar.**
*   **`web_dashboard.py`**: Flask sunucusu (Port 8050).
*   **`binance_client.py`**: Binance API istemcisi.
*   **`system_validator.py`**: Veri doğrulama modülü.

---

## ✅ SON YAPILANLAR (STATUS LOG)
**2026-02-04 Tarihli Güncelleme:**
1.  **Whale Heatmap Revizyonu:**
    *   "Whale Movement" raporu, görsel olarak **RSI Heatmap** stiline (kartlı yapı) dönüştürüldü.
    *   HTML bozulmasına neden olan satır atlaması hatası giderildi.
    *   Tasarım: Koyu kartlar, renkli border-top (Yeşil/Kırmızı), büyük renkli rakamlar ve net coin sembolleri.
    *   "Accumulation" ve "Distribution" durumları renk kodlu olarak netleştirildi.
2.  **Deployment:**
    *   Yerel değişiklikler GitHub'a pushlandı.
    *   Oracle VM üzerinde `git pull` ve `systemctl restart crypto-bot` komutları ile canlıya alındı.

---

## 🚀 DEVAM EDİLECEK İŞLER (TODO)
Bu projeye geri dönüldüğünde odaklanılması gerekenler:
1.  **Genel Performans Kontrolü:** Yeni eklenen heatmap'in veri akış hızının takibi.
2.  **Order Block Raporu:** Backend entegrasyonunun tamamlanması.
3.  **Mobil Responsive:** Dashboard'un mobil cihazlarda görünüm optimizasyonu.

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
echo 'Main Bot Restarted'
"
# Not: Dashboard artık main.py içinden ayrı bir thread olarak 8050 portunda çalışıyor.
```

### 3. Logları İzleme
```bash
ssh -i id_rsa_oracle -o StrictHostKeyChecking=no ubuntu@141.144.251.86 "tail -f ~/crypto-analysis-bot/bot.log"
```

---

## 📝 ÖZEL NOTLAR
*   **İletişim:** Kullanıcı kesinlikle **PROFESYONEL** bir dil istiyor. "Abim" gibi hitaplar YASAK. Resmi ve teknik konuş.
*   **Tasarım:** Estetik ve "Premium" hissiyat çok önemli.
*   **Dil:** Raporlar İngilizce.
