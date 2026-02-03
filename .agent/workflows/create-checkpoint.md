---
description: Hızlı Checkpoint Oluştur
---

# 📸 Hızlı Checkpoint Sistemi

Her conversation başında kullanın!

// turbo-all

1. Tarihli checkpoint oluştur
```bash
cd /Users/abdulkadirkarkinli/.gemini/antigravity/scratch/crypto-analysis-bot
git add .
git commit -m "Checkpoint: $(date '+%Y-%m-%d %H:%M')"
git tag -a checkpoint-$(date '+%Y%m%d-%H%M') -m "Auto checkpoint"
```

2. Tüm checkpoint'leri listele
```bash
git tag -l "checkpoint-*"
```

3. Checkpoint'e geri dön (gerekirse)
```bash
git checkout checkpoint-YYYYMMDD-HHMM
```
