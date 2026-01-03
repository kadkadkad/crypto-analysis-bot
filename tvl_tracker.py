"""
TVL Protocol Tracker - DeFiLlama Integration
Tracks money flows into/out of DeFi protocols to predict token pumps
"""
import requests
import json
from datetime import datetime
from collections import defaultdict

class TVLTracker:
    def __init__(self):
        self.base_url = "https://api.llama.fi"
        self.protocols_cache = {}
        self.last_fetch = None
        
        # Protocol slug → Binance trading pair (for actionable trades)
        self.protocol_to_binance = {
            # Major DeFi
            "convex-finance": {"token": "CVX", "pair": "CVXUSDT"},
            "curve-dex": {"token": "CRV", "pair": "CRVUSDT"},
            "curve-finance": {"token": "CRV", "pair": "CRVUSDT"},
            "aave-v3": {"token": "AAVE", "pair": "AAVEUSDT"},
            "aave": {"token": "AAVE", "pair": "AAVEUSDT"},
            "compound-v3": {"token": "COMP", "pair": "COMPUSDT"},
            "compound-finance": {"token": "COMP", "pair": "COMPUSDT"},
            "sky-lending": {"token": "MKR", "pair": "MKRUSDT"},
            "makerdao": {"token": "MKR", "pair": "MKRUSDT"},
            "lido": {"token": "LDO", "pair": "LDOUSDT"},
            "rocket-pool": {"token": "RPL", "pair": "RPLUSDT"},
            "pendle": {"token": "PENDLE", "pair": "PENDLEUSDT"},
            
            # DEXs
            "uniswap-v3": {"token": "UNI", "pair": "UNIUSDT"},
            "uniswap-v2": {"token": "UNI", "pair": "UNIUSDT"},
            "sushiswap": {"token": "SUSHI", "pair": "SUSHIUSDT"},
            "pancakeswap-amm": {"token": "CAKE", "pair": "CAKEUSDT"},
            "pancakeswap-amm-v3": {"token": "CAKE", "pair": "CAKEUSDT"},
            
            # Perpetuals
            "gmx": {"token": "GMX", "pair": "GMXUSDT"},
            "dydx": {"token": "DYDX", "pair": "DYDXUSDT"},
            "synthetix": {"token": "SNX", "pair": "SNXUSDT"},
            
            # Solana DeFi
            "jito-liquid-staking": {"token": "JTO", "pair": "JTOUSDT"},
            "raydium-amm": {"token": "RAY", "pair": "RAYUSDT"},
            "orca": {"token": "ORCA", "pair": "ORCAUSDT"},
            "jupiter-perpetual-exchange": {"token": "JUP", "pair": "JUPUSDT"},
            "jupiter-staked-sol": {"token": "JUP", "pair": "JUPUSDT"},
            "kamino-lend": {"token": "KMNO", "pair": "KMNOUSDT"},
            "marinade-finance": {"token": "MNDE", "pair": "MNDEUSDT"},
            
            # Lending
            "morpho-v1": {"token": "MORPHO", "pair": "MORPHOUSDT"},
            "venus-core-pool": {"token": "XVS", "pair": "XVSUSDT"},
            
            # Staking/Restaking
            "ethena-usde": {"token": "ENA", "pair": "ENAUSDT"},
            "eigencloud": {"token": "EIGEN", "pair": "EIGENUSDT"},
            "eigenlayer": {"token": "EIGEN", "pair": "EIGENUSDT"},
            "ether.fi-stake": {"token": "ETHFI", "pair": "ETHFIUSDT"},
            "renzo": {"token": "REZ", "pair": "REZUSDT"},
            "stader": {"token": "SD", "pair": "SDUSDT"},
            "lista-liquid-staking": {"token": "LISTA", "pair": "LISTAUSDT"},
            "kelp": {"token": "RSETH", "pair": None},  # No direct pair
            
            # Layer 2 / Bridges
            "arbitrum-bridge": {"token": "ARB", "pair": "ARBUSDT"},
            "optimism-bridge": {"token": "OP", "pair": "OPUSDT"},
            "starknet-bridge": {"token": "STRK", "pair": "STRKUSDT"},
            "polygon-bridge-&-staking": {"token": "POL", "pair": "POLUSDT"},
            
            # Hot protocols (might not have token)
            "hyperliquid-bridge": {"token": "HYPE", "pair": "HYPEUSDT"},
            "infrared-finance": {"token": "IRED", "pair": None},
            "berachain": {"token": "BERA", "pair": "BERAUSDT"},
            
            # Others
            "threshold-network": {"token": "T", "pair": "TUSDT"},
            "tornado-cash": {"token": "TORN", "pair": "TORNUSDT"},
            "1inch-network": {"token": "1INCH", "pair": "1INCHUSDT"},
            "balancer-v2": {"token": "BAL", "pair": "BALUSDT"},
            "yearn-finance": {"token": "YFI", "pair": "YFIUSDT"},
        }
    
    def fetch_all_protocols(self):
        """Fetch all protocols from DeFiLlama"""
        try:
            url = f"{self.base_url}/protocols"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                protocols = response.json()
                # Create lookup by slug
                self.protocols_cache = {p['slug']: p for p in protocols}
                self.last_fetch = datetime.now()
                print(f"[TVL] Fetched {len(protocols)} protocols")
                return protocols
            return []
        except Exception as e:
            print(f"[TVL ERROR] fetch_all_protocols: {e}")
            return []
    
    def get_top_tvl_changes(self, limit=20):
        """Get protocols with biggest TVL changes (potential pumps)"""
        if not self.protocols_cache:
            self.fetch_all_protocols()
        
        # Filter protocols with valid data
        valid_protocols = []
        for slug, p in self.protocols_cache.items():
            try:
                tvl = p.get('tvl', 0)
                change_1d = p.get('change_1d', 0)
                change_7d = p.get('change_7d', 0)
                
                # Skip if no meaningful data
                if not tvl or not change_1d:
                    continue
                
                # Only consider protocols with >$10M TVL
                if tvl < 10_000_000:
                    continue
                    
                valid_protocols.append({
                    'name': p.get('name', slug),
                    'slug': slug,
                    'symbol': p.get('symbol', '-'),
                    'tvl': tvl,
                    'change_1d': change_1d,
                    'change_7d': change_7d,
                    'category': p.get('category', 'Unknown'),
                    'chains': p.get('chains', [])
                })
            except:
                continue
        
        # Sort by 1d change (biggest inflow first)
        sorted_inflow = sorted(valid_protocols, key=lambda x: x['change_1d'], reverse=True)
        sorted_outflow = sorted(valid_protocols, key=lambda x: x['change_1d'])
        
        return {
            'top_inflow': sorted_inflow[:limit],
            'top_outflow': sorted_outflow[:limit]
        }
    
    def detect_tvl_anomalies(self, threshold_1d=10, threshold_7d=20):
        """
        Detect unusual TVL changes that might predict token pumps
        
        Logic:
        - TVL increase >10% in 1 day = Unusual inflow
        - TVL increase >20% in 7 days = Strong accumulation
        - Combined = High probability pump signal
        """
        if not self.protocols_cache:
            self.fetch_all_protocols()
        
        anomalies = []
        for slug, p in self.protocols_cache.items():
            try:
                tvl = p.get('tvl', 0)
                change_1d = p.get('change_1d', 0) or 0
                change_7d = p.get('change_7d', 0) or 0
                symbol = p.get('symbol', '-')
                
                # Skip non-tradeable or small protocols
                if tvl < 10_000_000:
                    continue
                    
                # Check for anomaly
                is_1d_anomaly = change_1d > threshold_1d
                is_7d_anomaly = change_7d > threshold_7d
                is_extreme_1d = change_1d > 25  # Very extreme
                
                if is_1d_anomaly or is_7d_anomaly or is_extreme_1d:
                    # Calculate signal strength
                    signal_strength = 0
                    if is_1d_anomaly:
                        signal_strength += 30
                    if is_7d_anomaly:
                        signal_strength += 30
                    if is_extreme_1d:
                        signal_strength += 40
                    
                    # Bonus for having tradeable token
                    has_token = symbol != '-' and symbol != None
                    if has_token:
                        signal_strength += 20
                    
                    anomalies.append({
                        'name': p.get('name', slug),
                        'slug': slug,
                        'symbol': symbol,
                        'tvl': tvl,
                        'tvl_display': self._format_number(tvl),
                        'change_1d': change_1d,
                        'change_7d': change_7d,
                        'category': p.get('category', 'Unknown'),
                        'signal_strength': min(signal_strength, 100),
                        'has_tradeable_token': has_token,
                        'anomaly_type': self._get_anomaly_type(change_1d, change_7d)
                    })
            except:
                continue
        
        # Sort by signal strength
        anomalies.sort(key=lambda x: x['signal_strength'], reverse=True)
        return anomalies[:20]
    
    def _get_anomaly_type(self, change_1d, change_7d):
        """Classify the type of TVL anomaly"""
        if change_1d > 25:
            return "🚀 EXTREME INFLOW"
        elif change_1d > 10 and change_7d > 20:
            return "📈 STRONG ACCUMULATION"
        elif change_1d > 10:
            return "⚡ SUDDEN SPIKE"
        elif change_7d > 20:
            return "📊 STEADY GROWTH"
        elif change_1d < -10:
            return "🔴 HEAVY OUTFLOW"
        else:
            return "📍 NOTABLE CHANGE"
    
    def _format_number(self, num):
        """Format large numbers for display"""
        if num >= 1_000_000_000:
            return f"${num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num/1_000:.2f}K"
        else:
            return f"${num:.2f}"
    
    def generate_tvl_report(self, all_results=None):
        """
        Generate a comprehensive TVL analysis report with technical confluence
        """
        anomalies = self.detect_tvl_anomalies()
        changes = self.get_top_tvl_changes(10)
        
        report = f"🛸 <b>RADAR TVL ALPHA REPORT - {datetime.now().strftime('%H:%M')}</b>\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 1. Actionable Binance Alpha (The "Money" section)
        tradeable_anomalies = []
        for a in anomalies:
            binance_info = self.protocol_to_binance.get(a['slug'])
            if binance_info and binance_info.get('pair'):
                a['binance_pair'] = binance_info['pair']
                a['token'] = binance_info['token']
                
                # Cross-reference with technicals if available
                if all_results:
                    coin_data = next((c for c in all_results if c.get('Coin') == a['token']), None)
                    if coin_data:
                        a['rsi'] = float(coin_data.get('RSI', 50))
                        a['change_24h'] = float(coin_data.get('24h Change', 0))
                        a['advice'] = coin_data.get('Advice', '')
                
                tradeable_anomalies.append(a)

        if tradeable_anomalies:
            report += "<b>🎯 BINANCE TRADING SIGNALS:</b>\n"
            report += "<i>(TVL Inflow + Technical Confluence)</i>\n\n"
            
            for i, a in enumerate(tradeable_anomalies[:5], 1):
                # Logic: TVL up + RSI < 60 = Potential Pump Loading
                pump_score = 0
                if a['change_1d'] > 10: pump_score += 40
                if a.get('rsi', 50) < 50: pump_score += 30 # Room to grow
                if a.get('change_24h', 0) < a['change_1d']: pump_score += 30 # TVL leading price
                
                report += f"{i}. <b>{a['binance_pair']}</b> (${a['token']})\n"
                report += f"   🔥 <b>PUMP PROBABILITY: {pump_score}%</b>\n"
                report += f"   💧 TVL 1D: <b>{a['change_1d']:+.1f}%</b> | RSI: {a.get('rsi', 'N/A')}\n"
                report += f"   📊 Trend: {a.get('advice', 'Analyzing...')[:100]}...\n\n"
            
            report += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 2. Watchlist (DeFi Native Alpha)
        non_tradeable = [a for a in anomalies if a['slug'] not in self.protocol_to_binance][:5]
        if non_tradeable:
            report += "<b>👀 ON-CHAIN WATCHLIST (Inflows):</b>\n"
            for a in non_tradeable:
                report += f"• <b>{a['name']}</b>: 1D {a['change_1d']:+.1f}% | TVL {a['tvl_display']}\n"
            report += "\n"

        # 3. Binance Asset Performance (Always show)
        tradeable_protocols = self.get_tradeable_tvl_changes()
        if tradeable_protocols:
            report += "<b>📍 BINANCE DEFI TRACKER:</b>\n"
            gainers = [p for p in tradeable_protocols if p['change_1d'] > 2][:5]
            if gainers:
                report += "💹 <b>Gainers:</b>\n"
                for p in gainers:
                    report += f"📈 {p['pair']}: <b>{p['change_1d']:+.1f}%</b> TVL\n"
            
            losers = [p for p in reversed(tradeable_protocols) if p['change_1d'] < -2][:5]
            if losers:
                report += "\n📉 <b>Outflows:</b>\n"
                for p in losers:
                    report += f"🔻 {p['pair']}: <b>{p['change_1d']:+.1f}%</b> TVL\n"
        
        report += "\n<i>⚡ Data: DeFiLlama | Radar Ultra AI Engine</i>"
        return report
    
    def get_tradeable_tvl_changes(self):
        """Get TVL changes for all Binance-tradeable protocols"""
        if not self.protocols_cache:
            self.fetch_all_protocols()
        
        results = []
        for slug, binance_info in self.protocol_to_binance.items():
            if not binance_info.get('pair'):
                continue
                
            protocol = self.protocols_cache.get(slug)
            if not protocol:
                continue
            
            tvl = protocol.get('tvl', 0) or 0
            change_1d = protocol.get('change_1d', 0) or 0
            change_7d = protocol.get('change_7d', 0) or 0
            
            if tvl < 1_000_000:  # Skip very small
                continue
                
            results.append({
                'name': protocol.get('name', slug),
                'slug': slug,
                'token': binance_info['token'],
                'pair': binance_info['pair'],
                'tvl': tvl,
                'tvl_display': self._format_number(tvl),
                'change_1d': change_1d,
                'change_7d': change_7d
            })
        
        # Sort by 1d change
        results.sort(key=lambda x: x['change_1d'], reverse=True)
        return results
    
    def get_protocol_by_token(self, token_symbol):
        """Get protocol info by its token symbol"""
        # Build reverse mapping
        for slug, info in self.protocol_to_binance.items():
            if info.get('token', '').upper() == token_symbol.upper():
                if not self.protocols_cache:
                    self.fetch_all_protocols()
                return self.protocols_cache.get(slug)
        return None


# Module-level instance for easy import
TVL_TRACKER = TVLTracker()


def get_tvl_alpha_report(all_results=None):
    """Get the TVL alpha report - call this from main.py"""
    return TVL_TRACKER.generate_tvl_report(all_results)


def get_tvl_anomalies():
    """Get list of TVL anomalies - call this from main.py"""
    return TVL_TRACKER.detect_tvl_anomalies()


# Test
if __name__ == "__main__":
    tracker = TVLTracker()
    print(tracker.generate_tvl_report())
