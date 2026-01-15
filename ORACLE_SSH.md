# Oracle VM SSH Bilgileri

## Bağlantı Detayları

| Bilgi | Değer |
|-------|-------|
| **IP Adresi** | `141.144.251.86` |
| **Kullanıcı** | `ubuntu` |
| **SSH Key** | `id_rsa_oracle` |
| **Port** | `22` (SSH) / `8050` (Dashboard) |

## Dashboard URL

🌐 **http://141.144.251.86:8050/**

## SSH Bağlantı Komutu

```bash
ssh -i id_rsa_oracle ubuntu@141.144.251.86
```

## Sık Kullanılan Komutlar

### Git durumunu kontrol et
```bash
cd ~/crypto-analysis-bot && git status
```

### GitHub'dan güncelle
```bash
cd ~/crypto-analysis-bot && git pull origin main
```

### Bot loglarını görüntüle
```bash
tail -f ~/crypto-analysis-bot/bot.log
```

### Bot servisini yeniden başlat
```bash
sudo systemctl restart crypto-bot
```

### Bot servis durumunu kontrol et
```bash
sudo systemctl status crypto-bot
```

---
*Son güncelleme: 2026-01-13*
