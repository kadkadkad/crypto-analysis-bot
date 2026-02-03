---
description: Güvenli Geliştirme - Kod Bozulmalarını Önleme
---

# 🛡️ Güvenli Geliştirme İş Akışı

Bu workflow farklı conversation/oturumlarda çalışırken kodların bozulmasını önler.

## Yeni Özellik/Deneme Başlarken

// turbo
1. Mevcut durumu kaydet (commit)
```bash
cd /Users/abdulkadirkarkinli/.gemini/antigravity/scratch/crypto-analysis-bot
git add .
git commit -m "Checkpoint before new feature"
```

// turbo
2. Yeni branch oluştur
```bash
git checkout -b feature/yeni-ozellik-adi
```

## Çalışma Sırasında

// turbo
3. Değişiklikleri düzenli commit et
```bash
git add .
git commit -m "WIP: Açıklama"
```

## Özellik Tamamlandığında

// turbo
4. Main branch'e merge et
```bash
git checkout main
git merge feature/yeni-ozellik-adi
```

// turbo
5. Oracle'a push et
```bash
git push origin main
```

// turbo
6. Oracle sunucuyu güncelle
```bash
ssh -i ../oracle_key ubuntu@141.144.251.86 "cd crypto-analysis-bot && git pull origin main && sudo systemctl restart crypto-bot"
```

## Eğer Kodlar Bozulduysa (Geri Alma)

7. Son çalışan haline dön
```bash
git log --oneline -10  # Son 10 commit'i gör
git checkout <commit-hash>  # Çalışan commit'e dön
git checkout -b fix/revert-broken-code
```

8. Ya da tüm değişiklikleri iptal et
```bash
git reset --hard HEAD  # Dikkat: Kaydedilmemiş tüm değişiklikler silinir!
```

## Deneme/Test İçin

9. Stash kullan (geçici kaydet)
```bash
git stash save "Deneme kodu - conversation XYZ"
git stash list  # Kayıtlı stash'leri gör
git stash pop   # Geri yükle
```

---

**💡 Pro Tip:** Her yeni conversation'da önce `git status` ve `git log -1` çalıştırarak mevcut durumu kontrol edin!
