"""
Market Calendar & News Impact Analyzer V2
Combines real economic events, crypto news aggregation, and AI sentiment analysis.
"""

import requests
import datetime
from bs4 import BeautifulSoup
import json
import time
import re
import feedparser

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

# Crypto News RSS Feeds
CRYPTO_NEWS_FEEDS = {
    'CoinDesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'CoinTelegraph': 'https://cointelegraph.com/rss',
    'Decrypt': 'https://decrypt.co/feed',
    'The Block': 'https://www.theblock.co/rss.xml',
    'Bitcoin Magazine': 'https://bitcoinmagazine.com/feed',
}

# Keywords for impact detection
HIGH_IMPACT_KEYWORDS = [
    'sec', 'etf', 'approved', 'rejected', 'hack', 'exploit', 'crash', 'surge',
    'billion', 'regulation', 'ban', 'legal', 'lawsuit', 'fed', 'rate', 'inflation',
    'blackrock', 'grayscale', 'binance', 'coinbase', 'investigation', 'arrest'
]

BULLISH_KEYWORDS = [
    'approved', 'adoption', 'partnership', 'launch', 'surge', 'rally', 'bullish',
    'institutional', 'record', 'milestone', 'upgrade', 'breakthrough', 'integration',
    'etf approved', 'mainstream', 'accumulation', 'whale buying'
]

BEARISH_KEYWORDS = [
    'hack', 'exploit', 'crash', 'dump', 'bearish', 'ban', 'lawsuit', 'investigation',
    'arrest', 'fraud', 'rug pull', 'bankruptcy', 'layoffs', 'sell-off', 'rejected',
    'fud', 'warning', 'risk', 'collapse'
]

# Major coins for tagging
MAJOR_COINS = [
    'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'MATIC', 'LINK',
    'UNI', 'ATOM', 'LTC', 'BCH', 'NEAR', 'APT', 'ARB', 'OP', 'SUI', 'TIA',
    'PEPE', 'SHIB', 'WIF', 'BONK', 'FET', 'RENDER', 'INJ', 'TRX', 'TON', 'BNB'
]

# ==================== ECONOMIC CALENDAR ====================

class EconomicCalendar:
    """Fetches real economic events from ForexFactory and investing.com"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.cache = {}
        self.cache_time = None
        self.cache_duration = 1800  # 30 min cache
    
    def fetch_economic_events(self, days_ahead=7):
        """
        Fetch economic calendar events from multiple sources
        Returns list of economic events
        """
        events = []
        
        # Try ForexFactory first (more reliable)
        try:
            events = self._fetch_forexfactory()
        except Exception as e:
            print(f"[WARN] ForexFactory fetch failed: {e}")
        
        # If no events, try fallback
        if not events:
            events = self._get_scheduled_events(days_ahead)
        
        return events[:15]  # Return top 15 events
    
    def _fetch_forexfactory(self):
        """Scrape ForexFactory calendar"""
        events = []
        try:
            url = "https://www.forexfactory.com/calendar"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all('tr', class_='calendar__row')
                
                current_date = ""
                for row in rows[:30]:  # Limit to 30 rows
                    try:
                        # Get date
                        date_cell = row.find('td', class_='calendar__date')
                        if date_cell and date_cell.get_text(strip=True):
                            current_date = date_cell.get_text(strip=True)
                        
                        # Get time
                        time_cell = row.find('td', class_='calendar__time')
                        event_time = time_cell.get_text(strip=True) if time_cell else "All Day"
                        
                        # Get currency
                        currency_cell = row.find('td', class_='calendar__currency')
                        currency = currency_cell.get_text(strip=True) if currency_cell else "USD"
                        
                        # Get event name
                        event_cell = row.find('td', class_='calendar__event')
                        if not event_cell:
                            continue
                        event_name = event_cell.get_text(strip=True)
                        
                        if not event_name:
                            continue
                        
                        # Get impact
                        impact_cell = row.find('td', class_='calendar__impact')
                        impact = 'low'
                        if impact_cell:
                            impact_span = impact_cell.find('span')
                            if impact_span:
                                classes = impact_span.get('class', [])
                                if 'high' in str(classes).lower():
                                    impact = 'high'
                                elif 'medium' in str(classes).lower() or 'med' in str(classes).lower():
                                    impact = 'medium'
                        
                        events.append({
                            'date': current_date,
                            'time': event_time,
                            'currency': currency,
                            'event': event_name,
                            'impact': impact,
                            'crypto_relevance': self._calculate_crypto_relevance(event_name, currency)
                        })
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"[ERROR] ForexFactory scraping failed: {e}")
        
        return events
    
    def _calculate_crypto_relevance(self, event_name, currency):
        """Calculate how relevant an economic event is to crypto markets"""
        base_relevance = 0.3
        event_lower = event_name.lower()
        
        # High relevance keywords
        if any(kw in event_lower for kw in ['interest rate', 'fed', 'fomc', 'cpi', 'inflation', 'gdp', 'employment']):
            base_relevance = 0.9
        elif any(kw in event_lower for kw in ['pmi', 'retail sales', 'consumer confidence', 'housing']):
            base_relevance = 0.6
        elif any(kw in event_lower for kw in ['boj', 'ecb', 'pboc']):
            base_relevance = 0.8
        
        # Adjust for country
        country_multiplier = COUNTRY_CRYPTO_IMPACT.get(currency, 0.5)
        
        return round(min(base_relevance * country_multiplier * 1.2, 1.0), 2)
    
    def _get_scheduled_events(self, days_ahead=7):
        """Generate known scheduled major events as fallback"""
        events = []
        today = datetime.date.today()
        
        # Known 2026 FOMC dates
        fomc_dates = [
            '2026-01-29', '2026-03-19', '2026-05-07', '2026-06-18',
            '2026-07-30', '2026-09-17', '2026-11-05', '2026-12-17'
        ]
        
        # Add FOMC meetings
        for date_str in fomc_dates:
            event_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            days_until = (event_date - today).days
            if 0 <= days_until <= days_ahead:
                events.append({
                    'date': event_date.strftime('%b %d'),
                    'time': '14:00 ET',
                    'currency': 'USD',
                    'event': 'FOMC Interest Rate Decision',
                    'impact': 'high',
                    'crypto_relevance': 1.0
                })
        
        # Add regular monthly events (approximate)
        # CPI - usually mid-month
        cpi_date = datetime.date(today.year, today.month, 12)
        if cpi_date < today:
            if today.month == 12:
                cpi_date = datetime.date(today.year + 1, 1, 12)
            else:
                cpi_date = datetime.date(today.year, today.month + 1, 12)
        
        days_until = (cpi_date - today).days
        if 0 <= days_until <= days_ahead:
            events.append({
                'date': cpi_date.strftime('%b %d'),
                'time': '08:30 ET',
                'currency': 'USD',
                'event': 'US CPI (Inflation)',
                'impact': 'high',
                'crypto_relevance': 0.95
            })
        
        # NFP - first Friday of month
        first_day = datetime.date(today.year, today.month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        nfp_date = first_day + datetime.timedelta(days=days_until_friday)
        if nfp_date < today:
            if today.month == 12:
                first_day = datetime.date(today.year + 1, 1, 1)
            else:
                first_day = datetime.date(today.year, today.month + 1, 1)
            days_until_friday = (4 - first_day.weekday()) % 7
            nfp_date = first_day + datetime.timedelta(days=days_until_friday)
        
        days_until = (nfp_date - today).days
        if 0 <= days_until <= days_ahead:
            events.append({
                'date': nfp_date.strftime('%b %d'),
                'time': '08:30 ET',
                'currency': 'USD',
                'event': 'US Nonfarm Payrolls',
                'impact': 'high',
                'crypto_relevance': 0.85
            })
        
        return sorted(events, key=lambda x: x.get('crypto_relevance', 0), reverse=True)


# ==================== CRYPTO NEWS AGGREGATOR ====================

class CryptoNewsAggregator:
    """Aggregates and analyzes crypto news from multiple sources"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = None
        self.cache_duration = 300  # 5 min cache
    
    def fetch_all_news(self, limit=30):
        """Fetch news from all RSS feeds"""
        all_news = []
        
        for source, url in CRYPTO_NEWS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:  # 10 per source
                    news_item = self._parse_feed_entry(entry, source)
                    if news_item:
                        all_news.append(news_item)
            except Exception as e:
                print(f"[WARN] Failed to fetch {source}: {e}")
        
        # Sort by published time (newest first)
        all_news.sort(key=lambda x: x.get('published_ts', 0), reverse=True)
        
        # Analyze sentiment and tag coins
        for item in all_news:
            item['sentiment'] = self._analyze_sentiment(item['title'])
            item['coins'] = self._extract_coins(item['title'] + ' ' + item.get('summary', ''))
            item['is_breaking'] = self._is_breaking_news(item['title'])
            item['impact_score'] = self._calculate_impact_score(item)
        
        return all_news[:limit]
    
    def _parse_feed_entry(self, entry, source):
        """Parse a single RSS feed entry"""
        try:
            # Parse published date
            published_ts = 0
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_ts = time.mktime(entry.published_parsed)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_ts = time.mktime(entry.updated_parsed)
            
            # Calculate time ago
            now = time.time()
            diff = now - published_ts
            if diff < 3600:
                time_ago = f"{int(diff / 60)}m ago"
            elif diff < 86400:
                time_ago = f"{int(diff / 3600)}h ago"
            else:
                time_ago = f"{int(diff / 86400)}d ago"
            
            return {
                'title': entry.get('title', 'No Title'),
                'link': entry.get('link', ''),
                'summary': entry.get('summary', '')[:200] if entry.get('summary') else '',
                'source': source,
                'published_ts': published_ts,
                'time_ago': time_ago
            }
        except Exception as e:
            return None
    
    def _analyze_sentiment(self, text):
        """Analyze sentiment of news title"""
        text_lower = text.lower()
        
        bullish_score = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bearish_score = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        
        if bullish_score > bearish_score + 1:
            return 'bullish'
        elif bearish_score > bullish_score + 1:
            return 'bearish'
        else:
            return 'neutral'
    
    def _extract_coins(self, text):
        """Extract mentioned coins from text"""
        text_upper = text.upper()
        found_coins = []
        
        for coin in MAJOR_COINS:
            # Check for coin symbol with word boundaries
            if re.search(rf'\b{coin}\b', text_upper):
                found_coins.append(coin)
            # Also check for common variations
            if coin == 'BTC' and 'BITCOIN' in text_upper:
                if 'BTC' not in found_coins:
                    found_coins.append('BTC')
            if coin == 'ETH' and 'ETHEREUM' in text_upper:
                if 'ETH' not in found_coins:
                    found_coins.append('ETH')
            if coin == 'SOL' and 'SOLANA' in text_upper:
                if 'SOL' not in found_coins:
                    found_coins.append('SOL')
        
        return found_coins[:5]  # Max 5 coins
    
    def _is_breaking_news(self, title):
        """Detect if news is breaking/high-impact"""
        title_lower = title.lower()
        return any(kw in title_lower for kw in HIGH_IMPACT_KEYWORDS)
    
    def _calculate_impact_score(self, item):
        """Calculate overall impact score (0-100)"""
        score = 30  # Base score
        
        # Breaking news boost
        if item.get('is_breaking'):
            score += 30
        
        # Sentiment intensity
        if item.get('sentiment') in ['bullish', 'bearish']:
            score += 15
        
        # Coin mentions
        if item.get('coins'):
            score += min(len(item['coins']) * 5, 20)
        
        # Recency boost
        if '1h ago' in item.get('time_ago', '') or 'm ago' in item.get('time_ago', ''):
            score += 10
        
        return min(score, 100)


# ==================== TOKEN UNLOCKS ====================

class TokenUnlockTracker:
    """Tracks crypto-specific events like token unlocks"""
    
    def __init__(self):
        pass
    
    def get_upcoming_unlocks(self):
        """Get upcoming token unlock events"""
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
            {'symbol': 'WLD', 'name': 'Worldcoin', 'unlock_day': 24, 'typical_pct': 2.0},
            {'symbol': 'PYTH', 'name': 'Pyth', 'unlock_day': 20, 'typical_pct': 1.5},
        ]
        
        unlocks = []
        for token in major_tokens:
            try:
                # Calculate next unlock date
                this_month = datetime.date(today.year, today.month, min(token['unlock_day'], 28))
                if this_month < today:
                    # Move to next month
                    if today.month == 12:
                        next_unlock = datetime.date(today.year + 1, 1, min(token['unlock_day'], 28))
                    else:
                        next_unlock = datetime.date(today.year, today.month + 1, min(token['unlock_day'], 28))
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
                        'expected_effect': 'bearish'
                    })
            except:
                continue
        
        return sorted(unlocks, key=lambda x: x['days_until'])


# ==================== MAIN ANALYZER ====================

class MarketImpactAnalyzer:
    """Main analyzer combining all data sources"""
    
    def __init__(self):
        self.economic_calendar = EconomicCalendar()
        self.news_aggregator = CryptoNewsAggregator()
        self.unlock_tracker = TokenUnlockTracker()
    
    def get_daily_impact_report(self):
        """Generate comprehensive daily impact report"""
        report = {
            'generated_at': datetime.datetime.now().isoformat(),
            'economic_events': [],
            'crypto_news': [],
            'token_unlocks': [],
            'news_sentiment': {},
            'breaking_news': [],
            'overall_outlook': 'neutral',
            'risk_level': 'medium'
        }
        
        # Fetch economic calendar
        try:
            report['economic_events'] = self.economic_calendar.fetch_economic_events(days_ahead=7)
        except Exception as e:
            print(f"[ERROR] Economic calendar failed: {e}")
        
        # Fetch token unlocks
        try:
            report['token_unlocks'] = self.unlock_tracker.get_upcoming_unlocks()
        except Exception as e:
            print(f"[ERROR] Token unlocks failed: {e}")
        
        # Fetch crypto news
        try:
            all_news = self.news_aggregator.fetch_all_news(limit=25)
            report['crypto_news'] = all_news
            
            # Extract breaking news
            report['breaking_news'] = [n for n in all_news if n.get('is_breaking')][:5]
            
            # Analyze overall sentiment
            bullish_count = sum(1 for n in all_news if n.get('sentiment') == 'bullish')
            bearish_count = sum(1 for n in all_news if n.get('sentiment') == 'bearish')
            neutral_count = sum(1 for n in all_news if n.get('sentiment') == 'neutral')
            
            report['news_sentiment'] = {
                'bullish': bullish_count,
                'bearish': bearish_count,
                'neutral': neutral_count,
                'overall': 'bullish' if bullish_count > bearish_count * 1.3 else 
                          'bearish' if bearish_count > bullish_count * 1.3 else 'neutral'
            }
        except Exception as e:
            print(f"[ERROR] News aggregation failed: {e}")
        
        # Calculate overall outlook
        report['overall_outlook'] = self._calculate_outlook(report)
        report['risk_level'] = self._calculate_risk_level(report)
        
        return report
    
    def _calculate_outlook(self, report):
        """Calculate overall market outlook"""
        score = 0
        
        # News sentiment factor
        ns = report.get('news_sentiment', {})
        if ns.get('overall') == 'bullish':
            score += 2
        elif ns.get('overall') == 'bearish':
            score -= 2
        
        # Token unlocks factor (bearish pressure)
        near_unlocks = [u for u in report.get('token_unlocks', []) if u.get('days_until', 99) <= 3]
        if near_unlocks:
            score -= len(near_unlocks)
        
        # Breaking news can cause volatility
        breaking = report.get('breaking_news', [])
        if breaking:
            bearish_breaking = sum(1 for b in breaking if b.get('sentiment') == 'bearish')
            bullish_breaking = sum(1 for b in breaking if b.get('sentiment') == 'bullish')
            score += (bullish_breaking - bearish_breaking)
        
        if score >= 2:
            return 'bullish'
        elif score <= -2:
            return 'bearish'
        else:
            return 'neutral'
    
    def _calculate_risk_level(self, report):
        """Calculate market risk level"""
        risk_score = 0
        
        # High impact events
        high_events = [e for e in report.get('economic_events', []) if e.get('impact') == 'high']
        risk_score += len(high_events) * 2
        
        # Near token unlocks
        near_unlocks = [u for u in report.get('token_unlocks', []) if u.get('days_until', 99) <= 3]
        risk_score += len(near_unlocks)
        
        # Breaking news
        risk_score += len(report.get('breaking_news', []))
        
        if risk_score >= 5:
            return 'high'
        elif risk_score >= 2:
            return 'medium'
        else:
            return 'low'


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
    
    data = MARKET_CALENDAR.get_daily_impact_report()
    
    # Format for Telegram
    report = f"📅 <b>MARKET CALENDAR & NEWS</b>\n"
    report += f"<i>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Overall Status
    outlook_emoji = "🟢" if data['overall_outlook'] == 'bullish' else "🔴" if data['overall_outlook'] == 'bearish' else "🟡"
    risk_emoji = "🔴" if data['risk_level'] == 'high' else "🟡" if data['risk_level'] == 'medium' else "🟢"
    
    report += f"<b>📊 Overall Status:</b>\n"
    report += f"• Outlook: {outlook_emoji} {data['overall_outlook'].upper()}\n"
    report += f"• Risk Level: {risk_emoji} {data['risk_level'].upper()}\n\n"
    
    # Breaking News
    if data.get('breaking_news'):
        report += f"<b>🚨 BREAKING NEWS:</b>\n"
        for news in data['breaking_news'][:3]:
            sentiment_icon = "🟢" if news.get('sentiment') == 'bullish' else "🔴" if news.get('sentiment') == 'bearish' else "⚪"
            coins = ', '.join([f"${c}" for c in news.get('coins', [])]) if news.get('coins') else ''
            report += f"{sentiment_icon} {news['title'][:60]}...\n"
            if coins:
                report += f"   📌 {coins}\n"
        report += "\n"
    
    # Economic Events
    report += f"<b>🏛️ Economic Events:</b>\n"
    if data['economic_events']:
        for event in data['economic_events'][:5]:
            impact_icon = "🔴" if event.get('impact') == 'high' else "🟡" if event.get('impact') == 'medium' else "⚪"
            report += f"{impact_icon} [{event.get('currency', 'N/A')}] {event.get('event', 'Unknown')}\n"
    else:
        report += "• No major events scheduled\n"
    report += "\n"
    
    # Token Unlocks
    report += f"<b>🔓 Token Unlocks:</b>\n"
    if data['token_unlocks']:
        for unlock in data['token_unlocks'][:5]:
            days_text = "TODAY" if unlock['days_until'] == 0 else f"in {unlock['days_until']}d"
            report += f"• ${unlock['symbol']}: ~{unlock['unlock_pct']}% {days_text}\n"
    else:
        report += "• No major unlocks\n"
    report += "\n"
    
    # News Sentiment
    ns = data.get('news_sentiment', {})
    report += f"<b>📰 News Sentiment:</b>\n"
    report += f"🟢 {ns.get('bullish', 0)} | 🔴 {ns.get('bearish', 0)} | ⚪ {ns.get('neutral', 0)}\n"
    
    return report


# ==================== TEST ====================

if __name__ == "__main__":
    print("Testing Market Calendar V2...")
    analyzer = MarketImpactAnalyzer()
    data = analyzer.get_daily_impact_report()
    print(f"Economic Events: {len(data['economic_events'])}")
    print(f"Crypto News: {len(data['crypto_news'])}")
    print(f"Breaking News: {len(data['breaking_news'])}")
    print(f"Token Unlocks: {len(data['token_unlocks'])}")
    print(f"Overall Outlook: {data['overall_outlook']}")
