"""
Market Calendar & News Impact Analyzer
Combines economic events from major countries with crypto-specific events and news.
"""

import requests
import datetime
from bs4 import BeautifulSoup
import json
import time
import re

# ==================== CONFIGURATION ====================

# Impact weights for different event types
IMPACT_WEIGHTS = {
    'high': 3,
    'medium': 2,
    'low': 1
}

# Country importance for crypto markets
COUNTRY_CRYPTO_IMPACT = {
    'USD': 1.0,   # US has highest impact
    'CNY': 0.8,   # China - major mining/trading hub
    'JPY': 0.7,   # Japan - major crypto adoption
    'EUR': 0.6,   # Europe - regulatory influence
    'GBP': 0.5,   # UK
    'KRW': 0.6,   # Korea - active trading
}

# Key economic events with crypto impact
KEY_ECONOMIC_EVENTS = {
    'Interest Rate Decision': {'impact': 'high', 'crypto_relevance': 0.9},
    'Fed Interest Rate Decision': {'impact': 'high', 'crypto_relevance': 1.0},
    'FOMC Meeting': {'impact': 'high', 'crypto_relevance': 1.0},
    'CPI': {'impact': 'high', 'crypto_relevance': 0.9},
    'Inflation Rate': {'impact': 'high', 'crypto_relevance': 0.9},
    'GDP': {'impact': 'high', 'crypto_relevance': 0.7},
    'Nonfarm Payrolls': {'impact': 'high', 'crypto_relevance': 0.8},
    'Unemployment Rate': {'impact': 'medium', 'crypto_relevance': 0.6},
    'PMI': {'impact': 'medium', 'crypto_relevance': 0.5},
    'Retail Sales': {'impact': 'medium', 'crypto_relevance': 0.5},
    'Trade Balance': {'impact': 'medium', 'crypto_relevance': 0.4},
    'Consumer Confidence': {'impact': 'medium', 'crypto_relevance': 0.5},
    'BOJ': {'impact': 'high', 'crypto_relevance': 0.8},
    'ECB': {'impact': 'high', 'crypto_relevance': 0.7},
    'PBOC': {'impact': 'high', 'crypto_relevance': 0.8},
}

# ==================== ECONOMIC CALENDAR ====================

class EconomicCalendar:
    """Fetches economic events from multiple sources"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.cache = {}
        self.cache_time = None
        self.cache_duration = 3600  # 1 hour cache
    
    def fetch_investing_calendar(self, days_ahead=7):
        """
        Fetch economic calendar from Investing.com
        Returns list of economic events
        """
        events = []
        
        try:
            # Calculate date range
            today = datetime.date.today()
            end_date = today + datetime.timedelta(days=days_ahead)
            
            # Investing.com economic calendar API endpoint
            url = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
            
            # Countries: US, China, Japan, EU, UK, Germany
            country_ids = "5,37,35,72,4,17"  # US, China, Japan, Eurozone, UK, Germany
            
            payload = {
                'country[]': country_ids.split(','),
                'importance[]': ['1', '2', '3'],  # All importance levels
                'dateFrom': today.strftime('%Y-%m-%d'),
                'dateTo': end_date.strftime('%Y-%m-%d'),
                'timeZone': '8',
                'timeFilter': 'timeRemain',
                'currentTab': 'custom',
                'limit_from': '0'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.investing.com/economic-calendar/'
            }
            
            response = requests.post(url, data=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                html_content = data.get('data', '')
                
                # Parse HTML response
                soup = BeautifulSoup(html_content, 'html.parser')
                rows = soup.find_all('tr', class_='js-event-item')
                
                for row in rows:
                    try:
                        event = self._parse_investing_row(row)
                        if event:
                            events.append(event)
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"[WARN] Investing.com calendar fetch failed: {e}")
            # Fallback to alternative source
            events = self._get_fallback_events(days_ahead)
        
        return events
    
    def _parse_investing_row(self, row):
        """Parse a single row from Investing.com calendar"""
        try:
            # Get event time
            time_cell = row.find('td', class_='time')
            event_time = time_cell.text.strip() if time_cell else "TBA"
            
            # Get country
            flag = row.find('td', class_='flagCur')
            country = flag.find('span')['title'] if flag and flag.find('span') else "Unknown"
            currency = flag.text.strip() if flag else "USD"
            
            # Get importance (bulls count)
            importance_cell = row.find('td', class_='sentiment')
            bulls = len(importance_cell.find_all('i', class_='grayFullBullishIcon')) if importance_cell else 0
            impact = 'high' if bulls >= 3 else 'medium' if bulls >= 2 else 'low'
            
            # Get event name
            event_cell = row.find('td', class_='event')
            event_name = event_cell.text.strip() if event_cell else "Unknown Event"
            
            # Get actual, forecast, previous values
            actual = row.find('td', class_='act')
            forecast = row.find('td', class_='fore')
            previous = row.find('td', class_='prev')
            
            return {
                'time': event_time,
                'country': country,
                'currency': currency,
                'event': event_name,
                'impact': impact,
                'actual': actual.text.strip() if actual else None,
                'forecast': forecast.text.strip() if forecast else None,
                'previous': previous.text.strip() if previous else None,
                'crypto_relevance': self._calculate_crypto_relevance(event_name, currency)
            }
        except:
            return None
    
    def _calculate_crypto_relevance(self, event_name, currency):
        """Calculate how relevant an economic event is to crypto markets"""
        base_relevance = 0.3
        
        # Check if event matches known high-impact events
        for key, info in KEY_ECONOMIC_EVENTS.items():
            if key.lower() in event_name.lower():
                base_relevance = info['crypto_relevance']
                break
        
        # Adjust for country
        country_multiplier = COUNTRY_CRYPTO_IMPACT.get(currency, 0.5)
        
        return round(base_relevance * country_multiplier, 2)
    
    def _get_fallback_events(self, days_ahead=7):
        """Generate known scheduled events as fallback"""
        events = []
        today = datetime.date.today()
        
        # Known recurring events (approximate)
        recurring_events = [
            {'day': 1, 'event': 'US ISM Manufacturing PMI', 'currency': 'USD', 'impact': 'high'},
            {'day': 3, 'event': 'US ISM Services PMI', 'currency': 'USD', 'impact': 'high'},
            {'day': 'first_friday', 'event': 'US Nonfarm Payrolls', 'currency': 'USD', 'impact': 'high'},
            {'day': 10, 'event': 'US CPI (Approx)', 'currency': 'USD', 'impact': 'high'},
            {'day': 15, 'event': 'China GDP/Industrial Production', 'currency': 'CNY', 'impact': 'high'},
        ]
        
        # Add some static important dates for 2026
        static_events = [
            {'date': '2026-01-29', 'event': 'FOMC Meeting', 'currency': 'USD', 'impact': 'high'},
            {'date': '2026-03-19', 'event': 'FOMC Meeting', 'currency': 'USD', 'impact': 'high'},
            {'date': '2026-05-07', 'event': 'FOMC Meeting', 'currency': 'USD', 'impact': 'high'},
        ]
        
        for se in static_events:
            event_date = datetime.datetime.strptime(se['date'], '%Y-%m-%d').date()
            if today <= event_date <= today + datetime.timedelta(days=days_ahead):
                events.append({
                    'date': se['date'],
                    'time': 'TBA',
                    'country': 'United States',
                    'currency': se['currency'],
                    'event': se['event'],
                    'impact': se['impact'],
                    'crypto_relevance': 1.0
                })
        
        return events


# ==================== CRYPTO EVENTS ====================

class CryptoEventTracker:
    """Tracks crypto-specific events like token unlocks, listings, upgrades"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_token_unlocks(self):
        """Fetch upcoming token unlock events"""
        unlocks = []
        
        try:
            # Try TokenUnlocks API or CryptoRank
            url = "https://token.unlocks.app/api/v1/unlocks"
            
            # Alternative: use CoinGecko or manual tracking
            # For now, use known major unlocks
            known_unlocks = self._get_known_unlocks()
            unlocks.extend(known_unlocks)
            
        except Exception as e:
            print(f"[WARN] Token unlocks fetch failed: {e}")
        
        return unlocks
    
    def _get_known_unlocks(self):
        """Return known upcoming token unlocks"""
        today = datetime.date.today()
        
        # Major tokens with regular unlocks (approximate monthly)
        major_tokens = [
            {'symbol': 'ARB', 'name': 'Arbitrum', 'unlock_day': 16, 'typical_pct': 3.0},
            {'symbol': 'OP', 'name': 'Optimism', 'unlock_day': 30, 'typical_pct': 2.5},
            {'symbol': 'APT', 'name': 'Aptos', 'unlock_day': 12, 'typical_pct': 2.0},
            {'symbol': 'SUI', 'name': 'Sui', 'unlock_day': 1, 'typical_pct': 2.5},
            {'symbol': 'SEI', 'name': 'Sei', 'unlock_day': 15, 'typical_pct': 3.0},
            {'symbol': 'TIA', 'name': 'Celestia', 'unlock_day': 18, 'typical_pct': 2.0},
            {'symbol': 'STRK', 'name': 'Starknet', 'unlock_day': 15, 'typical_pct': 4.0},
            {'symbol': 'JUP', 'name': 'Jupiter', 'unlock_day': 1, 'typical_pct': 1.5},
        ]
        
        unlocks = []
        for token in major_tokens:
            # Calculate next unlock date
            this_month = datetime.date(today.year, today.month, token['unlock_day'])
            if this_month < today:
                # Move to next month
                if today.month == 12:
                    next_unlock = datetime.date(today.year + 1, 1, token['unlock_day'])
                else:
                    next_unlock = datetime.date(today.year, today.month + 1, token['unlock_day'])
            else:
                next_unlock = this_month
            
            days_until = (next_unlock - today).days
            
            if days_until <= 30:  # Only show unlocks within 30 days
                unlocks.append({
                    'symbol': token['symbol'],
                    'name': token['name'],
                    'date': next_unlock.strftime('%Y-%m-%d'),
                    'days_until': days_until,
                    'unlock_pct': token['typical_pct'],
                    'impact': 'high' if token['typical_pct'] > 3 else 'medium',
                    'expected_effect': 'bearish'  # Unlocks typically create selling pressure
                })
        
        return sorted(unlocks, key=lambda x: x['days_until'])
    
    def fetch_crypto_news(self, limit=20):
        """Fetch latest crypto news with sentiment from CryptoPanic"""
        news = []
        
        try:
            # CryptoPanic API (free tier)
            url = f"https://cryptopanic.com/api/v1/posts/?auth_token=free&public=true&filter=hot"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('results', [])[:limit]:
                    sentiment = 'neutral'
                    votes = item.get('votes', {})
                    
                    positive = votes.get('positive', 0)
                    negative = votes.get('negative', 0)
                    
                    if positive > negative * 1.5:
                        sentiment = 'bullish'
                    elif negative > positive * 1.5:
                        sentiment = 'bearish'
                    
                    news.append({
                        'title': item.get('title', ''),
                        'source': item.get('source', {}).get('title', 'Unknown'),
                        'url': item.get('url', ''),
                        'published': item.get('published_at', ''),
                        'sentiment': sentiment,
                        'currencies': [c.get('code') for c in item.get('currencies', [])],
                        'votes_positive': positive,
                        'votes_negative': negative
                    })
            
        except Exception as e:
            print(f"[WARN] CryptoPanic news fetch failed: {e}")
        
        return news


# ==================== IMPACT ANALYZER ====================

class MarketImpactAnalyzer:
    """Analyzes the combined impact of economic and crypto events"""
    
    def __init__(self):
        self.economic_calendar = EconomicCalendar()
        self.crypto_tracker = CryptoEventTracker()
    
    def get_daily_impact_report(self):
        """Generate a comprehensive daily impact report"""
        report = {
            'generated_at': datetime.datetime.now().isoformat(),
            'economic_events': [],
            'crypto_events': [],
            'token_unlocks': [],
            'news_sentiment': {},
            'overall_outlook': 'neutral',
            'risk_level': 'medium'
        }
        
        # Fetch economic calendar
        economic_events = self.economic_calendar.fetch_investing_calendar(days_ahead=7)
        report['economic_events'] = economic_events
        
        # Fetch token unlocks
        unlocks = self.crypto_tracker.fetch_token_unlocks()
        report['token_unlocks'] = unlocks
        
        # Fetch news
        news = self.crypto_tracker.fetch_crypto_news(limit=15)
        
        # Analyze news sentiment
        bullish_count = sum(1 for n in news if n['sentiment'] == 'bullish')
        bearish_count = sum(1 for n in news if n['sentiment'] == 'bearish')
        neutral_count = sum(1 for n in news if n['sentiment'] == 'neutral')
        
        report['news_sentiment'] = {
            'bullish': bullish_count,
            'bearish': bearish_count,
            'neutral': neutral_count,
            'overall': 'bullish' if bullish_count > bearish_count * 1.3 else 
                      'bearish' if bearish_count > bullish_count * 1.3 else 'neutral'
        }
        
        # Calculate overall outlook
        report['overall_outlook'] = self._calculate_outlook(economic_events, unlocks, report['news_sentiment'])
        report['risk_level'] = self._calculate_risk_level(economic_events)
        
        return report
    
    def _calculate_outlook(self, economic_events, unlocks, news_sentiment):
        """Calculate overall market outlook"""
        score = 0
        
        # News sentiment factor
        if news_sentiment['overall'] == 'bullish':
            score += 2
        elif news_sentiment['overall'] == 'bearish':
            score -= 2
        
        # Token unlocks factor (bearish pressure)
        near_unlocks = [u for u in unlocks if u['days_until'] <= 3]
        if near_unlocks:
            score -= len(near_unlocks)
        
        # High impact events create uncertainty
        high_impact_today = [e for e in economic_events if e.get('impact') == 'high']
        if len(high_impact_today) >= 2:
            score -= 1  # Uncertainty is slightly bearish
        
        if score >= 2:
            return 'bullish'
        elif score <= -2:
            return 'bearish'
        else:
            return 'neutral'
    
    def _calculate_risk_level(self, economic_events):
        """Calculate market risk level based on upcoming events"""
        high_impact_count = sum(1 for e in economic_events if e.get('impact') == 'high')
        
        if high_impact_count >= 3:
            return 'high'
        elif high_impact_count >= 1:
            return 'medium'
        else:
            return 'low'
    
    def generate_telegram_report(self):
        """Generate a formatted report for Telegram"""
        data = self.get_daily_impact_report()
        
        report = f"📅 <b>MARKET CALENDAR & IMPACT REPORT</b>\n"
        report += f"<i>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Overall Status
        outlook_emoji = "🟢" if data['overall_outlook'] == 'bullish' else "🔴" if data['overall_outlook'] == 'bearish' else "🟡"
        risk_emoji = "🔴" if data['risk_level'] == 'high' else "🟡" if data['risk_level'] == 'medium' else "🟢"
        
        report += f"<b>📊 Overall Status:</b>\n"
        report += f"• Outlook: {outlook_emoji} {data['overall_outlook'].upper()}\n"
        report += f"• Risk Level: {risk_emoji} {data['risk_level'].upper()}\n\n"
        
        # Economic Events - Today & Tomorrow
        report += f"<b>🏛️ Economic Events (7 Days):</b>\n"
        if data['economic_events']:
            for event in data['economic_events'][:8]:
                impact_icon = "🔴" if event.get('impact') == 'high' else "🟡" if event.get('impact') == 'medium' else "⚪"
                report += f"{impact_icon} [{event.get('currency', 'N/A')}] {event.get('event', 'Unknown')}\n"
                report += f"   📍 {event.get('time', 'TBA')} | Crypto Impact: {int(event.get('crypto_relevance', 0)*100)}%\n"
        else:
            report += "• No major events scheduled\n"
        report += "\n"
        
        # Token Unlocks
        report += f"<b>🔓 Token Unlocks (Next 30 Days):</b>\n"
        if data['token_unlocks']:
            for unlock in data['token_unlocks'][:5]:
                days_text = "TODAY" if unlock['days_until'] == 0 else f"in {unlock['days_until']} days"
                report += f"• ${unlock['symbol']}: ~{unlock['unlock_pct']}% unlock {days_text}\n"
        else:
            report += "• No major unlocks detected\n"
        report += "\n"
        
        # News Sentiment
        ns = data['news_sentiment']
        report += f"<b>📰 News Sentiment:</b>\n"
        report += f"• 🟢 Bullish: {ns.get('bullish', 0)} | 🔴 Bearish: {ns.get('bearish', 0)} | ⚪ Neutral: {ns.get('neutral', 0)}\n"
        report += f"• Overall: {ns.get('overall', 'neutral').upper()}\n\n"
        
        # Trading Notes
        report += "<b>⚡ Trading Notes:</b>\n"
        if data['risk_level'] == 'high':
            report += "• ⚠️ High volatility expected - reduce position sizes\n"
        if any(u['days_until'] <= 1 for u in data['token_unlocks']):
            report += "• 🔓 Token unlock imminent - watch for selling pressure\n"
        if data['overall_outlook'] == 'bullish':
            report += "• 📈 Sentiment favors long positions\n"
        elif data['overall_outlook'] == 'bearish':
            report += "• 📉 Sentiment favors caution/shorts\n"
        
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "<i>🤖 Data from multiple sources. Always DYOR.</i>"
        
        return report


# ==================== GLOBAL INSTANCE ====================

MARKET_CALENDAR = None

def init_market_calendar():
    """Initialize the global market calendar instance"""
    global MARKET_CALENDAR
    MARKET_CALENDAR = MarketImpactAnalyzer()
    return MARKET_CALENDAR

def get_market_calendar_report():
    """Get formatted market calendar report for Telegram"""
    global MARKET_CALENDAR
    if not MARKET_CALENDAR:
        init_market_calendar()
    return MARKET_CALENDAR.generate_telegram_report()


# ==================== TEST ====================

if __name__ == "__main__":
    print("Testing Market Calendar...")
    analyzer = MarketImpactAnalyzer()
    report = analyzer.generate_telegram_report()
    # Strip HTML for console
    import re
    clean = re.sub('<[^<]+?>', '', report)
    print(clean)
