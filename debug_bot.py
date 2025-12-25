import time
import requests
import config
from telegram_bot import send_reply_keyboard_message, MENU_STATE

# 1. Test Configuration
print(f"Token: {config.TELEGRAM_BOT_TOKEN[:5]}...")
print(f"Chat ID: {config.TELEGRAM_CHAT_ID}")

# 2. Test Sending Keyboard
print("\n[TEST] Sending Test Keyboard...")
test_keyboard = [
    [{"text": "TEST BUTTON 1"}],
    [{"text": "TEST BUTTON 2"}]
]
try:
    send_reply_keyboard_message(config.TELEGRAM_CHAT_ID, "🧪 <b>DEBUG TEST</b>\n\nPlease click a button below.", keyboard=test_keyboard)
    print("[SUCCESS] Message sent (check Telegram).")
except Exception as e:
    print(f"[FAIL] Message send failed: {e}")

# 3. Test Polling (Manual)
print("\n[TEST] Polling for 1 update (Please click a button)...")
offset = 0
found = False

for i in range(20): # Try for 20 seconds
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
        resp = requests.get(url, params={"offset": offset, "timeout": 5})
        data = resp.json()
        
        if "result" in data:
            for update in data["result"]:
                offset = update["update_id"] + 1
                if "message" in update:
                    text = update["message"].get("text", "")
                    print(f"\n[RECEIVED] Message: {text}")
                    if text in ["TEST BUTTON 1", "TEST BUTTON 2"]:
                        print("[SUCCESS] Button press received!")
                        found = True
                        break
        
        if found: break
        print(".", end="", flush=True)
        time.sleep(1)
    except Exception as e:
        print(f"[ERROR] Polling failed: {e}")

if not found:
    print("\n[TIMEOUT] No button press detected.")

# 4. Test MENU_STATE
print("\n[TEST] Checking MENU_STATE object...")
try:
    MENU_STATE.set_user_state(config.TELEGRAM_CHAT_ID, "test_mode")
    state = MENU_STATE.get_user_state(config.TELEGRAM_CHAT_ID)
    print(f"State set to: {state}")
    if state == "test_mode":
        print("[SUCCESS] MENU_STATE works.")
    else:
        print(f"[FAIL] MENU_STATE mismatch: {state}")
except Exception as e:
    print(f"[FAIL] MENU_STATE crashed: {e}")
