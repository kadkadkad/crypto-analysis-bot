#28martcandle
#candle
# This file should be saved as candlestick_patterns.py

import pandas as pd
from datetime import datetime
import requests


# extract_candlestick_patterns function
def extract_candlestick_patterns(klines):
    """
    Extracts patterns from kline data.

    Args:
        klines (list): Kline data

    Returns:
        list: Detected candlestick patterns
    """
    patterns = []

    if not klines or len(klines) < 3:
        return patterns

    # Convert to DataFrame
    df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume",
                                       "close_time", "quote_volume", "trades", "taker_buy_base",
                                       "taker_buy_quote", "ignore"])

    # Convert to numeric
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Check last candles
    for i in range(2, min(len(df), 10)):  # Check up to last 10 candles
        # Candle bodies and wicks
        current_open = df["open"].iloc[-i]
        current_close = df["close"].iloc[-i]
        current_high = df["high"].iloc[-i]
        current_low = df["low"].iloc[-i]

        prev_open = df["open"].iloc[-i - 1]
        prev_close = df["close"].iloc[-i - 1]
        prev_high = df["high"].iloc[-i - 1]
        prev_low = df["low"].iloc[-i - 1]

        pprev_open = df["open"].iloc[-i - 2] if i > 2 else 0
        pprev_close = df["close"].iloc[-i - 2] if i > 2 else 0

        # Body and wick calculations
        current_body = abs(current_close - current_open)
        current_upper_wick = current_high - max(current_open, current_close)
        current_lower_wick = min(current_open, current_close) - current_low

        prev_body = abs(prev_close - prev_open)
        pprev_body = abs(pprev_close - pprev_open)

        # Engulfing patterns
        if i > 1:
            bullish_engulfing = (
                    current_close > current_open and  # Green candle
                    prev_close < prev_open and  # Red candle
                    current_open < prev_close and  # Open below previous close
                    current_close > prev_open  # Close above previous open
            )

            bearish_engulfing = (
                    current_close < current_open and  # Red candle
                    prev_close > prev_open and  # Green candle
                    current_open > prev_close and  # Open above previous close
                    current_close < prev_open  # Close below previous open
            )

            if bullish_engulfing:
                patterns.append({"type": "Bullish Engulfing", "position": -i})
            elif bearish_engulfing:
                patterns.append({"type": "Bearish Engulfing", "position": -i})

        # Hammer/Hanging Man
        body_to_range_ratio = current_body / (current_high - current_low) if (current_high - current_low) > 0 else 0

        is_hammer = (
                body_to_range_ratio < 0.3 and  # Small body
                current_lower_wick > current_body * 2 and  # Long lower wick
                current_upper_wick < current_body * 0.5  # Short upper wick
        )

        if is_hammer:
            if current_close > current_open:  # Green hammer
                patterns.append({"type": "Bullish Hammer", "position": -i})
            else:  # Red hammer/hanging man
                patterns.append({"type": "Hanging Man", "position": -i})

        # Doji
        is_doji = current_body / ((current_high - current_low)) < 0.1 if (current_high - current_low) > 0 else False

        if is_doji:
            patterns.append({"type": "Doji", "position": -i})

        # Evening/Morning Star
        if i > 2:
            first_green = pprev_close > pprev_open
            second_small = prev_body < current_body * 0.5 and prev_body < pprev_body * 0.5
            third_red = current_close < current_open

            evening_star = first_green and second_small and third_red

            first_red = pprev_close < pprev_open
            third_green = current_close > current_open

            morning_star = first_red and second_small and third_green

            if evening_star:
                patterns.append({"type": "Evening Star", "position": -i})
            elif morning_star:
                patterns.append({"type": "Morning Star", "position": -i})

    return patterns


# Function to generate general report for candlestick patterns
def get_candlestick_patterns_report_string(ALL_RESULTS, sync_fetch_kline_data):
    """
    Analyzes candlestick patterns for all coins and returns a general report string.
    """
    if not ALL_RESULTS:
        return "⚠️ No analysis data available yet."

    report = f"🕯️ <b>1 Hourly Candlestick Patterns Report (Last 10 candles) – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

    # Dictionary to group patterns
    pattern_groups = {
        "Bullish Engulfing": [],
        "Bearish Engulfing": [],
        "Bullish Hammer": [],
        "Hanging Man": [],
        "Doji": [],
        "Evening Star": [],
        "Morning Star": []
    }

    # Analyze all coins
    total_coins_with_patterns = 0
    # Process top 50 for efficiency on web
    for coin in ALL_RESULTS[:50]:
        symbol = coin["Coin"]
        klines = sync_fetch_kline_data(symbol, "1h", limit=20)
        patterns = extract_candlestick_patterns(klines)

        if patterns:
            total_coins_with_patterns += 1

            for pattern in patterns:
                pattern_type = pattern["type"]
                if pattern_type in pattern_groups:
                    pattern_groups[pattern_type].append({
                        "symbol": symbol,
                        "position": pattern["position"]
                    })

    # Summary info
    total_patterns = sum(len(coins) for coins in pattern_groups.values())
    report += f"<b>Summary:</b> {total_patterns} candlestick patterns detected in {total_coins_with_patterns} out of {min(50, len(ALL_RESULTS))} coins.\n\n"

    # Report for each pattern type
    for pattern_type, coins in pattern_groups.items():
        if not coins:
            continue

        if "Bullish" in pattern_type or pattern_type == "Morning Star":
            emoji = "🟢"
        elif "Bearish" in pattern_type or pattern_type == "Evening Star" or pattern_type == "Hanging Man":
            emoji = "🔴"
        else:
            emoji = "⚪"

        report += f"<b>{emoji} {pattern_type} Pattern ({len(coins)} coins):</b>\n"

        for coin_data in sorted(coins, key=lambda x: abs(x["position"])):
            position_text = f"{abs(coin_data['position'])} candles ago"
            report += f"   • {coin_data['symbol']}: {position_text}\n"

        report += "\n"

    # General trend commentary
    bullish_count = len(pattern_groups["Bullish Engulfing"]) + len(pattern_groups["Bullish Hammer"]) + len(
        pattern_groups["Morning Star"])
    bearish_count = len(pattern_groups["Bearish Engulfing"]) + len(pattern_groups["Hanging Man"]) + len(
        pattern_groups["Evening Star"])

    report += "<b>📊 General Trend Commentary:</b>\n"
    if bullish_count > bearish_count * 1.5:
        report += f"• Strong bullish signals dominating the market ({bullish_count} bullish, {bearish_count} bearish)\n"
    elif bullish_count > bearish_count:
        report += f"• Slight bullish bias in the market ({bullish_count} bullish, {bearish_count} bearish)\n"
    elif bearish_count > bullish_count * 1.5:
        report += f"• Strong bearish signals dominating the market ({bearish_count} bearish, {bullish_count} bullish)\n"
    elif bearish_count > bullish_count:
        report += f"• Slight bearish bias in the market ({bearish_count} bearish, {bullish_count} bullish)\n"
    else:
        report += f"• Mixed signals in the market ({bullish_count} bullish, {bearish_count} bearish)\n"

    # Info about candlestick patterns
    report += "\n<b>ℹ️ About Candlestick Patterns:</b>\n"
    report += "• <b>Bullish Engulfing:</b> Potential start of an uptrend\n"
    report += "• <b>Bearish Engulfing:</b> Potential start of a downtrend\n"
    report += "• <b>Bullish Hammer:</b> Reversal signal at the bottom\n"
    report += "• <b>Hanging Man:</b> Bearish signal near the top\n"
    report += "• <b>Doji:</b> Indecision, potential trend reversal\n"
    report += "• <b>Evening Star:</b> Strong bearish reversal signal\n"
    report += "• <b>Morning Star:</b> Strong bullish reversal signal\n"

    # Analysis info
    report += "\n<b>📊 Analysis Information:</b>\n"
    report += "• Timeframe: 1 hour (1h)\n"
    report += "• Candles Examined: Last 10 candles\n"
    report += "• Update Interval: Every time analysis refreshes\n"

    return report

def handle_candlestick_patterns_report(ALL_RESULTS, sync_fetch_kline_data, send_telegram_message_long):
    report = get_candlestick_patterns_report_string(ALL_RESULTS, sync_fetch_kline_data)
    if report:
        send_telegram_message_long(report)


# Function to create keyboard for candlestick patterns menu
def create_candlestick_pattern_keyboard():
    """
    Creates buttons for selecting coins by candlestick patterns.

    Returns:
        list: Telegram keyboard structure
    """
    keyboard = []

    pattern_types = [
        "Bullish Engulfing Coins",
        "Bearish Engulfing Coins",
        "Bullish Hammer Coins",
        "Hanging Man Coins",
        "Doji Coins",
        "Evening Star Coins",
        "Morning Star Coins"
    ]

    for i in range(0, len(pattern_types), 2):
        row = []
        row.append({"text": pattern_types[i], "callback_data": f"pattern_{pattern_types[i]}"})
        if i + 1 < len(pattern_types):
            row.append({"text": pattern_types[i + 1], "callback_data": f"pattern_{pattern_types[i + 1]}"})
        keyboard.append(row)

    keyboard.append([{"text": "Candle Patterns Report", "callback_data": "pattern_report"}])
    keyboard.append([{"text": "↩️ Main Menu", "callback_data": "main_menu"}])

    return keyboard


# Function to show candlestick patterns menu
def handle_candlestick_pattern_menu(TELEGRAM_CHAT_ID, send_reply_keyboard_message):
    """
    Shows the candlestick patterns menu.

    Args:
        TELEGRAM_CHAT_ID (str): Telegram chat ID
        send_reply_keyboard_message (function): Keyboard message sender function
    """
    keyboard = [
        [{"text": "Bullish Engulfing Coins"}, {"text": "Bearish Engulfing Coins"}],
        [{"text": "Bullish Hammer Coins"}, {"text": "Hanging Man Coins"}],
        [{"text": "Doji Coins"}, {"text": "Evening Star Coins"}],
        [{"text": "Morning Star Coins"}],
        [{"text": "Candle Patterns Report"}],
        [{"text": "↩️ Main Menu"}]
    ]

    message = "🕯️ <b>Candlestick Patterns Menu</b>\n\n"
    message += "Select an option below to see coins with specific candlestick patterns:"

    send_reply_keyboard_message(TELEGRAM_CHAT_ID, message, keyboard=keyboard)


# Function to list coins with specific pattern
def handle_specific_pattern_coins(pattern_type, ALL_RESULTS, sync_fetch_kline_data, send_telegram_message_long):
    """
    Lists coins with a specific candlestick pattern.

    Args:
        pattern_type (str): Candlestick pattern type
        ALL_RESULTS (list): All analysis results
        sync_fetch_kline_data (function): Kline fetching function
        send_telegram_message_long (function): Long message sender function
    """
    pattern_name = pattern_type.replace(" Coins", "").replace(" Coinleri", "")

    if not ALL_RESULTS:
        send_telegram_message_long(f"⚠️ No analysis data available yet.")
        return

    report = f"🕯️ <b>1 Hourly {pattern_name} Pattern Coins (Last 10 candles) – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"

    matching_coins = []
    for coin in ALL_RESULTS:
        symbol = coin["Coin"]
        klines = sync_fetch_kline_data(symbol, "1h", limit=20)
        patterns = extract_candlestick_patterns(klines)

        for pattern in patterns:
            if pattern["type"] == pattern_name:
                matching_coins.append({
                    "symbol": symbol,
                    "position": pattern["position"],
                    "coin_data": coin
                })
                break

    if not matching_coins:
        report += f"No coins currently detected with {pattern_name} pattern.\n"
    else:
        report += f"<b>Total {len(matching_coins)} coins detected with {pattern_name} pattern:</b>\n\n"

        for i, coin_data in enumerate(matching_coins, 1):
            symbol = coin_data["symbol"]
            position = coin_data["position"]
            coin = coin_data["coin_data"]

            position_text = f"{abs(position)} candles ago"

            report += f"{i}. <b>{symbol}</b> - {position_text}\n"
            report += f"   • Price: {coin.get('Fiyat ($)', 'N/A')}\n"
            report += f"   • RSI: {coin.get('RSI', 'N/A')}\n"
            report += f"   • Volume Ratio: {coin.get('Hacim Oranı', 'N/A')}x\n"
            report += f"   • Net Accum: {coin.get('Net Accum', 'N/A')}\n\n"

    report += f"<b>ℹ️ About {pattern_name} Pattern:</b>\n"
    report += "<pre>" + get_pattern_visualization(pattern_name) + "</pre>\n\n"

    if pattern_name == "Bullish Engulfing":
        report += "Occurs in a downtrend when a green candle completely engulfs the previous red candle.\n"
        report += "Usually considered a strong bullish reversal signal.\n"
    elif pattern_name == "Bearish Engulfing":
        report += "Occurs in an uptrend when a red candle completely engulfs the previous green candle.\n"
        report += "Usually considered a strong bearish reversal signal.\n"
    elif pattern_name == "Bullish Hammer":
        report += "A candle with a long lower wick and small body, usually seen at the end of a downtrend.\n"
        report += "Indicates that buyers are strengthening at lower levels and a potential reversal is coming.\n"
    elif pattern_name == "Hanging Man":
        report += "A candle with a long lower wick and small body, usually seen near the end of an uptrend.\n"
        report += "Indicates that sellers are strengthening at higher levels and a potential drop is coming.\n"
    elif pattern_name == "Doji":
        report += "A candle where opening and closing prices are almost identical, showing indecision.\n"
        report += "May indicate the end of the current trend and a potential reversal.\n"
    elif pattern_name == "Evening Star":
        report += "A three-candle pattern found at the end of an uptrend: green candle, small-bodied candle, and red candle.\n"
        report += "Considered a strong bearish reversal signal.\n"
    elif pattern_name == "Morning Star":
        report += "A three-candle pattern found at the end of a downtrend: red candle, small-bodied candle, and green candle.\n"
        report += "Considered a strong bullish reversal signal.\n"

    # Analysis info
    report += "\n<b>📊 Analysis Information:</b>\n"
    report += "• Timeframe: 1 hour (1h)\n"
    report += "• Candles Examined: Last 10 candles\n"
    report += "• Update Interval: Every time analysis refreshes\n"

    send_telegram_message_long(report)


def get_pattern_text_visualization(pattern_name):
    """
    Returns a text-based visualization of candlestick patterns for Telegram messages
    """
    if pattern_name == "Bullish Engulfing":
        return """
📊 Pattern Visualization:

      ┃
    ┏━┛ ← High
┏━━━┫
┃   ┃ ← Open (Red)
┃   ┃
┗━━━┫
    ┗━┓ ← Low
      ┃
      ┃
      ┃     ┃
    ┏━┛   ┏━┛ ← High
┏━━━┫   ┏━┫
┃   ┃   ┃ ┃ ← Close (Green)
┃   ┃   ┃ ┃
┗━━━┫   ┃ ┃ ← Open (Green)
    ┗━┓ ┗━┫
      ┃   ┗━┓ ← Low
      ┃     ┃

Red Candle  Green Candle
             (Larger)
        """

    elif pattern_name == "Bearish Engulfing":
        return """
📊 Pattern Visualization:

      ┃
    ┏━┛ ← High
┏━━━┫
┃   ┃ ← Close (Green)
┃   ┃
┗━━━┫
    ┗━┓ ← Low
      ┃
      ┃
      ┃     ┃
    ┏━┛   ┏━┛ ← High
┏━━━┫   ┏━┫
┃   ┃   ┃ ┃ ← Open (Red)
┃   ┃   ┃ ┃
┗━━━┫   ┃ ┃ ← Close (Red)
    ┗━┓ ┗━┫
      ┃   ┗━┓ ← Low
      ┃     ┃

Green Candle  Red Candle
              (Larger)
        """

    elif pattern_name == "Bullish Hammer":
        return """
📊 Pattern Visualization:

      ┃
    ┏━┛ ← High
    ┃
┏━━━┫ ← Close (Green)
┗━━━┫ ← Open (Green)
    ┃
    ┃
    ┃
    ┃
    ┃
    ┗━┓ ← Low
      ┃

Small body, long lower wick
        """

    elif pattern_name == "Hanging Man":
        return """
📊 Pattern Visualization:

      ┃
    ┏━┛ ← High
    ┃
┏━━━┫ ← Open (Red)
┗━━━┫ ← Close (Red)
    ┃
    ┃
    ┃
    ┃
    ┃
    ┗━┓ ← Low
      ┃

Small body, long lower wick
        """

    elif pattern_name == "Doji":
        return """
📊 Pattern Visualization:

      ┃
    ┏━┛ ← High
    ┃
    ┃
    ┣━━━┫ ← Open/Close (almost same)
    ┃
    ┃
    ┃
    ┗━┓ ← Low
      ┃

Opening and closing prices are almost identical
        """

    elif pattern_name == "Evening Star":
        return """
📊 Pattern Visualization:

    ┃       ┃       ┃
  ┏━┛     ┏━┛     ┏━┛ ← High
┏━┫     ┏━┫     ┏━┫
┃ ┃     ┃ ┃     ┃ ┃ ← Open (Red)
┃ ┃     ┣━┫     ┃ ┃
┃ ┃     ┃ ┃     ┃ ┃ ← Close (Red)
┗━┫     ┗━┫     ┗━┫
  ┗━┓     ┗━┓     ┗━┓ ← Low
    ┃       ┃       ┃

Green    Small    Red
Candle   Body     Candle
        """

    elif pattern_name == "Morning Star":
        return """
📊 Pattern Visualization:

    ┃       ┃       ┃
  ┏━┛     ┏━┛     ┏━┛ ← High
┏━┫     ┏━┫     ┏━┫
┃ ┃     ┃ ┃     ┃ ┃ ← Close (Green)
┃ ┃     ┣━┫     ┃ ┃
┃ ┃     ┃ ┃     ┃ ┃ ← Open (Green)
┗━┫     ┗━┫     ┗━┫
  ┗━┓     ┗━┓     ┗━┓ ← Low
    ┃       ┃       ┃

Red      Small    Green
Candle   Body     Candle
        """

    else:
        return "No text visualization available for this pattern."


def get_pattern_visualization(pattern_name):
    """
    Returns a text-based visualization for candlestick patterns
    """
    return get_pattern_text_visualization(pattern_name)
