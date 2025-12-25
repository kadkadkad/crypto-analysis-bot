#!/usr/bin/env python3
import requests
import os
import sys

# Bot token'ı al
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Webhook bilgisini kontrol et
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
response = requests.get(url)

print("=" * 60)
print("WEBHOOK DURUMU:")
print("=" * 60)
print(response.json())
print("=" * 60)

if response.json().get("result", {}).get("url"):
    print("\n⚠️ WEBHOOK AKTİF! Bu yüzden getUpdates çalışmıyor!")
    print("\nWebhook'u silmek için şu komutu çalıştırın:")
    print(f"python3 check_webhook.py delete")
else:
    print("\n✅ Webhook YOK, getUpdates çalışmalı.")
    
# Eğer 'delete' argümanı verildiyse webhook'u sil
import sys
if len(sys.argv) > 1 and sys.argv[1] == "delete":
    delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    delete_response = requests.post(delete_url)
    print("\n🗑️ Webhook silme sonucu:")
    print(delete_response.json())
