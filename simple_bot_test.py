#!/usr/bin/env python3
"""
MINIMAL BOT TEST - Tests ONLY keyboard reception
Run this to verify Telegram connectivity works.
"""
import time
import requests
import config

TOKEN = config.TELEGRAM_BOT_TOKEN
CHAT_ID = config.TELEGRAM_CHAT_ID

print(f"Token: {TOKEN[:10]}...")
print(f"Chat ID: {CHAT_ID}")

# 1. Send test keyboard
def send_keyboard():
    keyboard = [
        [{"text": "✅ TEST 1"}],
        [{"text": "❌ TEST 2"}]
    ]
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": "🧪 <b>MINIMAL TEST</b>\n\nClick a button:",
        "parse_mode": "HTML",
        "reply_markup": {"keyboard": keyboard, "resize_keyboard": True}
    }
    resp = requests.post(url, json=data)
    if resp.ok:
        print("[OK] Keyboard sent!")
    else:
        print(f"[FAIL] {resp.status_code}: {resp.text}")

# 2. Listen for one click
def listen():
    offset = 0
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    
    print("\n[WAITING] Click a button in Telegram...")
    for i in range(30):
        resp = requests.get(url, params={"offset": offset, "timeout": 1})
        if resp.ok:
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    print(f"\n✅ RECEIVED: {text}")
                    if text in ["✅ TEST 1", "❌ TEST 2"]:
                        print("✅✅✅ KEYBOARD WORKS! ✅✅✅")
                        return True
        print(".", end="", flush=True)
        time.sleep(1)
    
    print("\n❌ TIMEOUT - No button click received")
    return False

# Run
send_keyboard()
success = listen()
if not success:
    print("\n⚠️ PROBLEM: Either another bot is running, or network issue.")
