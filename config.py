import os
import json
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
BINANCE_API_URL = "https://api.binance.com/api/v3/"
BINANCE_FUTURES_API_URL = "https://fapi.binance.com/fapi/v1/"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# System Configuration
SLEEP_INTERVAL = 120  # 2 minutes - More frequent updates for real-time data
GLOBAL_LOCK = threading.Lock()

# Global State Containers
PREV_STATS = {}
PREV_RANKS = {}
COIN_DETAILS = {}
ALL_RESULTS = []
FIVE_MIN_REPORTS = {}
MODEL_CACHE = {}
PREV_HOURLY_REPORTS = {}
TRADE_RECOMMENDATIONS = {}

# Cache
KLINE_CACHE = {}
last_ticker_data = None

def load_prev_stats():
    """Load previous statistics from file"""
    global PREV_STATS
    try:
        if os.path.exists("prev_stats.json"):
            with open("prev_stats.json", "r") as f:
                PREV_STATS = json.load(f)
            print("Config: Previous statistics loaded.")
        else:
            print("Config: prev_stats.json not found, starting fresh.")
    except Exception as e:
        print(f"Config: Failed to load previous statistics: {e}")

# Initialize
load_prev_stats()
