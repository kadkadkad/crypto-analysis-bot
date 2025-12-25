import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("HATA: Token bulunamadı!")
    exit(1)

URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

# Tüm update türlerini kabul etmesi için allowed_updates'i boş liste olarak JSON string formatında gönderiyoruz
params = {
    "offset": 0,
    "timeout": 10,
    "allowed_updates": json.dumps(["message", "edited_message", "channel_post", "edited_channel_post", "inline_query", "chosen_inline_result", "callback_query"])
}

print(f"Token: {TOKEN[:5]}...{TOKEN[-5:]}")
print("Ayarlar sıfırlanıyor...")

try:
    response = requests.get(URL, params=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.ok:
        print("\n✅ BAŞARILI! Bot ayarları sıfırlandı.")
        print("Artık private mesajları ve butonları algılamalı.")
    else:
        print("\n❌ HATA! Ayarlar sıfırlanamadı.")
except Exception as e:
    print(f"\n❌ Beklenmeyen hata: {e}")
