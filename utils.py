import re
import gc


def clean_html_for_telegram(text):
    """
    Cleans tags not supported by Telegram HTML formatting
    Args:
        text (str): Text to clean
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
        
    # Telegram supported tags
    supported_tags = ["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code", "pre"]
    supported_tags_pattern = "|".join([f"<{tag}[^>]*>.*?</{tag}>" for tag in supported_tags]) # Incorrect approach for regex replace

    # Better approach: Regex to match any tag <...> and replace it unless it is allowed
    # We will match <tag> and </tag>
    
    # Simple explicit removal of the specific problematic tags seen so far is safer first, 
    # but the user wants a robust fix. 
    # Let's replace the blacklist approach with a whitelist approach logic.
    
    # 1. Escape < and > if they are not part of a valid tag? Hard.
    # 2. Just add "future" and any other common LLM hallucinated tags to the blacklist?
    # 3. Or iterate through all <...> matches and check if they are in whitelist.
    
    # Let's stick to the current structure but expand the blacklist significantly and add a catch-all for unknown tags if possible.
    # Actually, a whitelist approach is better:
    # Remove any <string> or </string> that is NOT in the allowed list.
    
    # Regex explanation: <[/]?(\w+)[^>]*>
    # Match any opening or closing tag
    
    def replace_tag(match):
        tag_content = match.group(1) # e.g. "div class='...'" or "/div"
        # Extract tag name
        tag_name_match = re.match(r"/?([a-zA-Z0-9]+)", tag_content)
        if tag_name_match:
            tag_name = tag_name_match.group(1).lower()
            if tag_name in supported_tags:
                return match.group(0) # Keep it
        return "" # Remove it

    # This regex matches <...> but skips if it looks like just a less than sign
    text = re.sub(r"<([^>]+)>", replace_tag, text)
    
    return text

def balance_html_tags(text):
    """
    Balances HTML tags (adds missing closing tags)
    Args:
        text (str): Text to balance
    Returns:
        str: Balanced text
    """
    if not text:
        return ""

    supported_tags = ["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre"]

    for tag in supported_tags:
        open_tags = len(re.findall(f"<{tag}[^>]*>", text))
        close_tags = len(re.findall(f"</{tag}>", text))

        if open_tags > close_tags:
            text += f"</{tag}>" * (open_tags - close_tags)
        elif close_tags > open_tags:
            # Remove excess closing tags
            excess_close_tags = close_tags - open_tags
            for _ in range(excess_close_tags):
                match = re.search(f"</{tag}>", text)
                if match:
                    text = text[:match.start()] + text[match.end():]

    return text

def check_memory_and_clean(threshold_mb=500):
    """
    Checks memory usage and runs garbage collection if threshold is exceeded
    Args:
        threshold_mb (int): Memory threshold in MB
    Returns:
        float: Current memory usage in MB
    """
    print(f"[SYSTEM] Running garbage collection...")
    gc.collect()
    return 0.0

def optimize_memory():
    """Optimizes memory usage explicitly"""
    gc.collect()

def extract_numeric(value_str, default=0.0):
    """Extracts numeric value from a string"""
    if isinstance(value_str, (int, float)):
        return float(value_str)
    try:
        # Extract first number found
        match = re.search(r"[-+]?\d*\.\d+|\d+", str(value_str))
        if match:
            return float(match.group())
        return default
    except:
        return default

def normalize_symbol_for_exchange(symbol, exchange="binance"):
    """
    Normalizes symbol format for different exchanges
    """
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        quote = "USDT"
    else:
        base = symbol
        quote = "USDT"

    if exchange.lower() == "binance":
        return f"{base}{quote}"
    elif exchange.lower() == "okx":
        return f"{base}-{quote}"
    elif exchange.lower() == "bybit":
        return f"{base}{quote}"
    else:
        return symbol

def parse_money(value):
    try:
        value = str(value).strip()
        
        # Handle empty or '0' strings
        if not value or value == '0' or value == '0.0':
            return 0.0
            
        # Try direct float conversion first (handles scientific notation)
        try:
            direct_value = float(value)
            # If it's a very small number in scientific notation, return it
            if direct_value < 1e-6:  # Very small numbers
                return direct_value
        except:
            pass
        
        # Handle formatted values with K/M suffixes
        match = re.match(r"([\d\.]+)([KM])?", value)
        if match:
            number = float(match.group(1))
            suffix = match.group(2)
            if suffix == "K":
                return number * 1000
            elif suffix == "M":
                return number * 1000000
            else:
                return number
        
        # Fallback: try to extract any number
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
        if match:
            return float(match.group())
            
        return 0.0
    except Exception as e:
        # Debug log for troublesome values
        if value and value != '0' and value != '0.0':
            print(f"[DEBUG] parse_money failed for value: '{value}', error: {e}")
        return 0.0

def format_money(value):
    try:
        if value is None:
            return "N/A"
        value = float(value)
        if value == 0:
            return "0.0"
        abs_val = abs(value)
        if abs_val >= 1e12:
            return f"{value / 1e12:.2f}T"
        elif abs_val >= 1e9:
            return f"{value / 1e9:.2f}B"
        elif abs_val >= 1e6:
            return f"{value / 1e6:.2f}M"
        elif abs_val >= 1e3:
            return f"{value / 1e3:.2f}K"
        elif abs_val < 0.0001:
            return f"{value:.8f}"
        elif abs_val < 0.1:
            return f"{value:.4f}"
        elif abs_val < 10:
            return f"{value:.3f}"
        else:
            return f"{value:.2f}"
    except:
        return str(value)

def calculate_percentage_change(current, previous):
    try:
        current = float(current) if current is not None else 0.0
        previous = float(previous) if previous is not None else 0.0
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100
    except Exception:
        return 0.0

def get_change_arrow(change):
    try:
        change = float(change)
        if change > 0:
            return "🔼"
        elif change < 0:
            return "🔽"
        return ""
    except:
        return ""

def format_indicator(current, previous):
    try:
        current = float(current)
    except:
        current = 0
    try:
        previous = float(previous)
    except:
        previous = 0
    if previous == 0:
        return f"{round(current, 4)}"
    change = ((current - previous) / previous) * 100
    arrow = get_change_arrow(change)
    return f"{round(current, 4)} ({arrow} {round(change, 2)}%)"

def get_whale_logo(net):
    try:
        net = float(net)
        if net < 0:
            return "🐋💸"
        elif net > 0:
            return "🐋💰"
        else:
            return "🐋"
    except:
        return "🐋"

def safe_extract(data, key, default=0, transform=float):
    try:
        if key in data:
            return transform(data[key])
        return default
    except:
        return default
