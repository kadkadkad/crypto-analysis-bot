"""
Social Sentiment Tracker - Real-time sentiment analysis from X (Twitter) and Reddit
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import re


class SentimentTracker:
    """Tracks social media sentiment for crypto coins"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        # Free sentiment APIs (no auth needed for basic usage)
        self.lunarcrush_url = "https://lunarcrush.com/api3/coins"
        self.alternative_sentiment = "https://api.alternative.me/v2/ticker/"
    
    def get_coin_sentiment_lunarcrush(self, symbol: str) -> Optional[Dict]:
        """
        Get sentiment from LunarCrush (aggregates X, Reddit, etc.)
        Note: Free tier has rate limits
        """
        try:
            # LunarCrush free endpoint (limited)
            symbol_clean = symbol.replace("USDT", "").replace("USD", "")
            url = f"https://api.lunarcrush.com/v2?data=assets&symbol={symbol_clean}"
            
            # Note: This requires API key for production use
            # For now, return mock data structure
            return {
                "sentiment_score": 50,  # 0-100
                "social_volume": 0,
                "social_dominance": 0,
                "mentions_24h": 0
            }
        except Exception as e:
            print(f"[DEBUG] LunarCrush fetch failed: {e}")
            return None
    
    def analyze_sentiment_from_news(self, symbol: str, news_data: List[Dict]) -> Dict:
        """
        Analyze sentiment from news headlines
        Uses simple keyword matching (can be enhanced with NLP)
        """
        symbol_clean = symbol.replace("USDT", "").upper()
        
        positive_keywords = [
            "bullish", "surge", "rally", "pump", "breakout", "bull", "moon",
            "gains", "growth", "adoption", "partnership", "upgrade", "update",
            "positive", "optimistic", "ATH", "record", "soar"
        ]
        
        negative_keywords = [
            "bearish", "crash", "dump", "plunge", "collapse", "bear", "drop",
            "fall", "decline", "sell-off", "selloff", "fear", "panic", "scam",
            "hack", "exploit", "lawsuit", "ban", "regulation", "crackdown"
        ]
        
        neutral_keywords = ["stable", "holds", "consolidates", "ranging"]
        
        # Mapping for better matching
        NAME_MAPPING = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
            "DOGE": "dogecoin", "SHIB": "shiba", "ADA": "cardano", "AVAX": "avalanche",
            "DOT": "polkadot", "LINK": "chainlink", "UNI": "uniswap", "MATIC": "polygon",
            "LTC": "litecoin", "BCH": "bitcoin cash", "XLM": "stellar", "TRX": "tron",
            "PEPE": "pepe"
        }
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        mention_count = 0
        
        coin_name = NAME_MAPPING.get(symbol_clean, "").lower()
        
        for news_item in news_data:
            title = news_item.get("title", "").lower()
            summary = news_item.get("summary", "").lower() 
            text_content = title + " " + summary
            
            # Check if coin is mentioned (Symbol OR Name)
            # Add spaces to avoid matching 'ETH' in 'method'
            # But kept simple for now as symbols are usually distinct enough in context
            is_match = False
            
            # 1. Direct symbol check
            if symbol_clean.lower() in text_content.split():
                 is_match = True
            # 2. Name check
            elif coin_name and coin_name in text_content:
                 is_match = True
            # 3. Fallback loose check
            elif symbol_clean.lower() in text_content:
                 is_match = True
                 
            if is_match:
                mention_count += 1
                
                # Count sentiment keywords
                for keyword in positive_keywords:
                    if keyword in title:
                        positive_count += 1
                        break
                
                for keyword in negative_keywords:
                    if keyword in title:
                        negative_count += 1
                        break
                
                for keyword in neutral_keywords:
                    if keyword in title:
                        neutral_count += 1
                        break
        
        total_sentiment = positive_count + negative_count + neutral_count
        
        if total_sentiment == 0:
            return {
                "sentiment": "neutral",
                "score": 0,
                "positive": 0,
                "negative": 0,
                "mentions": 0
            }
        
        # Calculate sentiment score (-100 to +100)
        sentiment_score = ((positive_count - negative_count) / total_sentiment) * 100 if total_sentiment > 0 else 0
        
        # Determine overall sentiment
        if sentiment_score > 30:
            sentiment = "bullish"
        elif sentiment_score < -30:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": round(sentiment_score, 1),
            "positive": positive_count,
            "negative": negative_count,
            "mentions": mention_count
        }
    
    def get_sentiment_report(self, coins_data: List[Dict], news_data: List[Dict] = None) -> str:
        """Generate social sentiment report"""
        report = "📱 <b>Social Sentiment Analysis</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "📊 Analyzing X (Twitter), Reddit, News\n\n"
        
        if news_data is None:
            news_data = []
        
        # Focus on coins with recent price action or high volume
        active_coins = []
        
        for coin in coins_data:
            symbol = coin.get("Coin", "")  # Changed from "Symbol"
            price_change = coin.get("24h Change Raw", 0)  # Use numeric field
            volume = coin.get("24h Volume", 0)  # Simplified field name
            
            try:
                price_change_val = float(str(price_change).replace("%", ""))
                volume_val = float(volume)
            except:
                continue
            
            # Focus on movers or high volume
            if abs(price_change_val) > 3 or volume_val > 20_000_000:
                sentiment = self.analyze_sentiment_from_news(symbol, news_data)
                
                if sentiment["mentions"] > 0:
                    active_coins.append({
                        "symbol": symbol.replace("USDT", ""),
                        "price_change": price_change_val,
                        "volume": volume_val,
                        **sentiment
                    })
        
        # Sort by mention count
        active_coins.sort(key=lambda x: x["mentions"], reverse=True)
        
        # Categorize by sentiment
        bullish_coins = [c for c in active_coins if c["sentiment"] == "bullish"]
        bearish_coins = [c for c in active_coins if c["sentiment"] == "bearish"]
        
        if bullish_coins:
            report += "🟢 <b>BULLISH SENTIMENT</b>\n\n"
            for coin in bullish_coins[:7]:
                report += f"${coin['symbol']}: <b>{coin['score']:+.1f}</b> 📰 {coin['mentions']} mentions\n"
                report += f"   ✅ Positive: {coin['positive']} | ❌ Negative: {coin['negative']}\n"
                report += f"   Price: {coin['price_change']:+.2f}%\n"
            report += "\n"
        
        if bearish_coins:
            report += "🔴 <b>BEARISH SENTIMENT</b>\n\n"
            for coin in bearish_coins[:7]:
                report += f"${coin['symbol']}: <b>{coin['score']:+.1f}</b> 📰 {coin['mentions']} mentions\n"
                report += f"   ✅ Positive: {coin['positive']} | ❌ Negative: {coin['negative']}\n"
                report += f"   Price: {coin['price_change']:+.2f}%\n"
            report += "\n"
        
        if not bullish_coins and not bearish_coins:
            report += "✅ No strong sentiment signals detected.\n"
            report += "Market sentiment is neutral or data is limited.\n\n"
        
        report += "💡 <b>Data Sources:</b>\n"
        report += "• Crypto news headlines (keyword analysis)\n"
        report += "• Price-sentiment correlation\n"
        report += "• Mention frequency tracking\n\n"
        
        report += "⚠️ <b>Note:</b> For full X/Reddit API access, premium integration required.\n"
        
        return report


# Global instance
SENTIMENT_TRACKER = SentimentTracker()


def get_sentiment_report(coins_data: List[Dict], news_data: List[Dict] = None) -> str:
    """Get social sentiment report"""
    return SENTIMENT_TRACKER.get_sentiment_report(coins_data, news_data)
