"""
Whale Watcher V2 - Real-time Large Transaction Tracker
Monitors large crypto transactions from multiple sources.
"""

import requests
import datetime
import time
from typing import Dict, List, Optional
import json

class WhaleWatcher:
    """Real-time whale transaction tracker using multiple APIs"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Minimum transaction size to track (in USD)
        self.min_transaction_usd = 1_000_000  # $1M+
        self.cache = {}
        self.cache_time = None
        self.cache_duration = 60  # 1 minute cache
    
    def get_whale_transactions(self, limit: int = 20) -> List[Dict]:
        """
        Get recent whale transactions from multiple sources
        Returns list of large transactions
        """
        # Check cache
        now = time.time()
        if self.cache_time and (now - self.cache_time) < self.cache_duration:
            return self.cache.get('transactions', [])[:limit]
        
        all_transactions = []
        
        # Try multiple sources
        try:
            # Source 1: Blockchain.com large transactions
            btc_whales = self._get_btc_large_transactions()
            all_transactions.extend(btc_whales)
        except Exception as e:
            print(f"[WARN] BTC whale fetch failed: {e}")
        
        try:
            # Source 2: Etherscan large transactions (ETH)
            eth_whales = self._get_eth_large_transactions()
            all_transactions.extend(eth_whales)
        except Exception as e:
            print(f"[WARN] ETH whale fetch failed: {e}")
        
        try:
            # Source 3: Whale Alert style public data
            whale_alert_data = self._get_whale_alert_public()
            all_transactions.extend(whale_alert_data)
        except Exception as e:
            print(f"[WARN] Whale Alert fetch failed: {e}")
        
        # Sort by timestamp (newest first)
        all_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Cache results
        self.cache['transactions'] = all_transactions
        self.cache_time = now
        
        return all_transactions[:limit]
    
    def _get_btc_large_transactions(self) -> List[Dict]:
        """Get large BTC transactions from blockchain.info"""
        transactions = []
        try:
            # Get unconfirmed transactions (recent ones)
            url = "https://blockchain.info/unconfirmed-transactions?format=json"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                txs = data.get('txs', [])
                
                # Get current BTC price
                btc_price = self._get_btc_price()
                
                for tx in txs[:50]:  # Check first 50
                    try:
                        # Calculate total output value
                        total_btc = sum(out.get('value', 0) for out in tx.get('out', [])) / 100_000_000
                        total_usd = total_btc * btc_price
                        
                        if total_usd >= self.min_transaction_usd:
                            transactions.append({
                                'coin': 'BTC',
                                'amount': round(total_btc, 4),
                                'amount_usd': round(total_usd, 0),
                                'type': self._determine_tx_type(tx),
                                'hash': tx.get('hash', '')[:16] + '...',
                                'timestamp': tx.get('time', int(time.time())),
                                'time_ago': self._time_ago(tx.get('time', int(time.time()))),
                                'source': 'Blockchain.info'
                            })
                    except:
                        continue
        except Exception as e:
            print(f"[ERROR] BTC large tx fetch: {e}")
        
        return transactions[:10]  # Return max 10
    
    def _get_eth_large_transactions(self) -> List[Dict]:
        """Get large ETH transactions - using public endpoints"""
        transactions = []
        try:
            # Get ETH price first
            eth_price = self._get_eth_price()
            
            # Etherscan public API (no key needed for basic queries)
            # Get latest blocks and check large transactions
            url = "https://api.etherscan.io/api"
            params = {
                'module': 'proxy',
                'action': 'eth_blockNumber'
            }
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result'):
                    # For now, we'll simulate with known whale addresses monitoring
                    # Real implementation would need Etherscan API key
                    pass
        except:
            pass
        
        return transactions
    
    def _get_whale_alert_public(self) -> List[Dict]:
        """
        Get whale transaction data from public sources
        Note: Real Whale Alert API requires paid key, this uses alternatives
        """
        transactions = []
        
        # Use Binance large trades as whale indicator
        try:
            # Get large trades from Binance
            for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']:
                trades = self._get_binance_large_trades(symbol)
                transactions.extend(trades)
        except Exception as e:
            print(f"[WARN] Binance trades fetch failed: {e}")
        
        return transactions
    
    def _get_binance_large_trades(self, symbol: str) -> List[Dict]:
        """Get recent large trades from Binance"""
        transactions = []
        try:
            url = f"https://api.binance.com/api/v3/trades"
            params = {'symbol': symbol, 'limit': 100}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                trades = response.json()
                coin = symbol.replace('USDT', '')
                
                for trade in trades:
                    try:
                        price = float(trade.get('price', 0))
                        qty = float(trade.get('qty', 0))
                        total_usd = price * qty
                        
                        # Only track trades > $100k for Binance
                        if total_usd >= 100_000:
                            is_buyer_maker = trade.get('isBuyerMaker', False)
                            
                            transactions.append({
                                'coin': coin,
                                'amount': round(qty, 4),
                                'amount_usd': round(total_usd, 0),
                                'type': 'SELL' if is_buyer_maker else 'BUY',
                                'hash': f"binance_{trade.get('id', '')}",
                                'timestamp': trade.get('time', 0) // 1000,
                                'time_ago': self._time_ago(trade.get('time', 0) // 1000),
                                'source': 'Binance',
                                'price': round(price, 4)
                            })
                    except:
                        continue
        except Exception as e:
            print(f"[ERROR] Binance trades fetch: {e}")
        
        return transactions[:5]  # Max 5 per coin
    
    def _get_btc_price(self) -> float:
        """Get current BTC price"""
        try:
            response = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={'symbol': 'BTCUSDT'},
                timeout=5
            )
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return 95000  # Fallback
    
    def _get_eth_price(self) -> float:
        """Get current ETH price"""
        try:
            response = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={'symbol': 'ETHUSDT'},
                timeout=5
            )
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return 3500  # Fallback
    
    def _determine_tx_type(self, tx: Dict) -> str:
        """Determine if transaction is likely exchange deposit/withdrawal"""
        # Simplified logic - in reality would check known exchange addresses
        inputs = len(tx.get('inputs', []))
        outputs = len(tx.get('out', []))
        
        if inputs == 1 and outputs > 5:
            return 'DISTRIBUTION'
        elif inputs > 5 and outputs == 1:
            return 'CONSOLIDATION'
        elif outputs == 2:
            return 'TRANSFER'
        else:
            return 'UNKNOWN'
    
    def _time_ago(self, timestamp: int) -> str:
        """Convert timestamp to human-readable time ago"""
        if not timestamp:
            return 'just now'
        
        now = int(time.time())
        diff = now - timestamp
        
        if diff < 60:
            return f"{diff}s ago"
        elif diff < 3600:
            return f"{diff // 60}m ago"
        elif diff < 86400:
            return f"{diff // 3600}h ago"
        else:
            return f"{diff // 86400}d ago"
    
    def get_whale_summary(self) -> Dict:
        """Get summary of recent whale activity"""
        transactions = self.get_whale_transactions(50)
        
        if not transactions:
            return {
                'total_transactions': 0,
                'total_volume_usd': 0,
                'buy_volume': 0,
                'sell_volume': 0,
                'sentiment': 'neutral',
                'top_coins': []
            }
        
        total_volume = sum(t.get('amount_usd', 0) for t in transactions)
        buy_volume = sum(t.get('amount_usd', 0) for t in transactions if t.get('type') == 'BUY')
        sell_volume = sum(t.get('amount_usd', 0) for t in transactions if t.get('type') == 'SELL')
        
        # Count by coin
        coin_counts = {}
        for t in transactions:
            coin = t.get('coin', 'UNKNOWN')
            if coin not in coin_counts:
                coin_counts[coin] = {'count': 0, 'volume': 0}
            coin_counts[coin]['count'] += 1
            coin_counts[coin]['volume'] += t.get('amount_usd', 0)
        
        top_coins = sorted(coin_counts.items(), key=lambda x: x[1]['volume'], reverse=True)[:5]
        
        # Determine sentiment
        if buy_volume > sell_volume * 1.5:
            sentiment = 'bullish'
        elif sell_volume > buy_volume * 1.5:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'
        
        return {
            'total_transactions': len(transactions),
            'total_volume_usd': round(total_volume, 0),
            'buy_volume': round(buy_volume, 0),
            'sell_volume': round(sell_volume, 0),
            'buy_sell_ratio': round(buy_volume / sell_volume, 2) if sell_volume > 0 else 999,
            'sentiment': sentiment,
            'top_coins': [{'coin': c[0], 'count': c[1]['count'], 'volume': round(c[1]['volume'], 0)} for c in top_coins],
            'last_updated': datetime.datetime.now().isoformat()
        }
    
    def get_alerts(self, min_usd: int = 5_000_000) -> List[Dict]:
        """Get high-value whale alerts (>$5M by default)"""
        transactions = self.get_whale_transactions(50)
        
        alerts = []
        for t in transactions:
            if t.get('amount_usd', 0) >= min_usd:
                emoji = '🐳' if t['amount_usd'] >= 10_000_000 else '🐋'
                direction = '🟢' if t.get('type') == 'BUY' else '🔴' if t.get('type') == 'SELL' else '⚪'
                
                alerts.append({
                    'emoji': emoji,
                    'direction': direction,
                    'message': f"{emoji} {direction} ${t['coin']}: ${t['amount_usd']:,.0f} ({t['amount']} {t['coin']})",
                    'time_ago': t.get('time_ago', 'recently'),
                    'details': t
                })
        
        return alerts[:10]


# Global instance
WHALE_WATCHER = None

def init_whale_watcher():
    global WHALE_WATCHER
    WHALE_WATCHER = WhaleWatcher()
    return WHALE_WATCHER

def get_whale_watcher():
    global WHALE_WATCHER
    if not WHALE_WATCHER:
        init_whale_watcher()
    return WHALE_WATCHER


if __name__ == "__main__":
    print("Testing Whale Watcher V2...")
    watcher = WhaleWatcher()
    
    # Test get transactions
    txs = watcher.get_whale_transactions(10)
    print(f"Found {len(txs)} whale transactions")
    for tx in txs[:5]:
        print(f"  {tx['coin']}: ${tx['amount_usd']:,.0f} - {tx['type']} ({tx['time_ago']})")
    
    # Test summary
    summary = watcher.get_whale_summary()
    print(f"\nSummary: {json.dumps(summary, indent=2)}")
    
    # Test alerts
    alerts = watcher.get_alerts(500_000)  # Lower threshold for testing
    print(f"\nAlerts: {len(alerts)}")
    for a in alerts[:3]:
        print(f"  {a['message']}")
