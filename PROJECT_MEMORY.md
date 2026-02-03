# 🧠 RADAR ULTRA - PROJECT MEMORY (CONTEXT FILE)
> **Last Updated:** 2026-01-23
> **Status:** Live & Stable
> **Server:** Oracle Cloud (141.144.251.86)

---

## 🏗️ PROJE MİMARİSİ
Bu proje, Binance üzerinden kripto verilerini analiz eden, yapay zeka destekli sinyaller üreten ve web tabanlı (Flask) bir dashboard sunan bir bottur.

### 📂 Kritik Dosyalar ve Görevleri
*   **`main.py`**: Ana beyin. Veri toplama, analiz döngüsü, sinyal üretimi burada döner.
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
