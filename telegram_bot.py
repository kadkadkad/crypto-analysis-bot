import requests
import time
import re
import config
import utils

class MenuStateManager:
    def __init__(self):
        self.menu_states = {}

    def get_user_state(self, chat_id):
        return self.menu_states.get(chat_id, "main_menu")

    def set_user_state(self, chat_id, state):
        self.menu_states[chat_id] = state
        print(f"[DEBUG] Chat ID {chat_id} menu state set to '{state}'")

    def clear_user_state(self, chat_id):
        if chat_id in self.menu_states:
            del self.menu_states[chat_id]
            print(f"[DEBUG] Chat ID {chat_id} menu state cleared")

# Global instance
MENU_STATE = MenuStateManager()

def send_telegram_message(chat_id, text, keyboard=None, inline_keyboard=None, parse_mode="HTML"):
    """
    Sends a message to Telegram
    """
    MAX_LENGTH = 4096
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    # Basic cleaning
    text = utils.clean_html_for_telegram(text)
    
    # Balance tags
    text = utils.balance_html_tags(text)

    messages = []
    if len(text) > MAX_LENGTH:
        lines = text.split("\n")
        current_message = ""
        for line in lines:
            if len(current_message) + len(line) + 1 > MAX_LENGTH:
                messages.append(current_message)
                current_message = line
            else:
                current_message += ("\n" + line) if current_message else line
        if current_message:
            messages.append(current_message)
    else:
        messages = [text]

    for msg in messages:
        # Re-balance tags for each chunk if necessary (simple approach here)
        msg_balanced = utils.balance_html_tags(msg)
        
        data = {"chat_id": chat_id, "text": msg_balanced, "parse_mode": parse_mode}
        
        reply_markup = {}
        if inline_keyboard:
            reply_markup["inline_keyboard"] = inline_keyboard
        elif keyboard:
            reply_markup["keyboard"] = keyboard
            reply_markup["resize_keyboard"] = True
            reply_markup["one_time_keyboard"] = False
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        # Retry mechanism for network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, timeout=30)  # Increased from 10s to 30s
                if response.status_code == 200:
                    break  # Success
                elif response.status_code == 429:
                    # Rate limited
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"[WARN] Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"[ERROR] Telegram API error: {response.status_code}, {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
            except requests.exceptions.Timeout:
                print(f"[WARN] Telegram timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"[ERROR] Failed to send message after {max_retries} attempts (timeout)")
            except Exception as e:
                print(f"[ERROR] Failed to send Telegram message: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[ERROR] Failed after {max_retries} attempts")

def send_telegram_document(chat_id, file_path, caption=None):
    """
    Sends a document to Telegram
    """
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    
    try:
        with open(file_path, "rb") as file:
            files = {"document": file}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
                
            response = requests.post(url, data=data, files=files, timeout=30)
            if response.status_code != 200:
                print(f"[ERROR] Failed to send Telegram document: {response.status_code}, {response.text}")
                return False
            return True
    except Exception as e:
        print(f"[ERROR] Exception in send_telegram_document: {e}")
        return False

def send_telegram_message_long(message, chat_id=None, keyboard=None, inline_keyboard=None):
    """
    Sends long messages by splitting them
    """
    if not chat_id:
        chat_id = config.TELEGRAM_CHAT_ID

    message = utils.clean_html_for_telegram(message)
    max_length = 4096
    parts = []
    current_part = ""

    for line in message.split('\n'):
        if len(current_part) + len(line) + 1 > max_length:
            if current_part:
                parts.append(current_part.strip())
            current_part = line + "\n"
        else:
            current_part += line + "\n"

    if current_part:
        parts.append(current_part.strip())

    for i, part in enumerate(parts):
        part = utils.balance_html_tags(part)
        
        # Only attach keyboards to the last part
        current_keyboard = keyboard if i == len(parts) - 1 else None
        current_inline = inline_keyboard if i == len(parts) - 1 else None
        
        send_telegram_message(chat_id, part, keyboard=current_keyboard, inline_keyboard=current_inline)

def send_reply_keyboard_message(chat_id, message, keyboard=None):
    """
    Sends a message with a reply keyboard
    """
    send_telegram_message(chat_id, message, keyboard=keyboard)

def test_keyboard(chat_id):
    """
    Sends a test keyboard to Telegram for verification.
    """
    test_keyboard = [
        [{"text": "📊 View Current Analysis"}],
        [{"text": "🔍 Advanced Risk Analysis"}, {"text": "📈 Trend Status"}],
        [{"text": "Main Menu"}]
    ]
    
    send_telegram_message(
        chat_id, 
        "🧪 <b>Keyboard Test</b>\n\nTesting if the keyboard works correctly...", 
        keyboard=test_keyboard
    )
    
    # Optional: Clean memory if utility is available (keeping consistent with original logic)
    try:
        utils.check_memory_and_clean()
    except:
        pass
