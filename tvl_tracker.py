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
        
        # Token to protocol mapping (protocols with tradeable tokens)
        self.token_protocol_map = {
            "CVX": "convex-finance",
            "CRV": "curve-dex",
            "AAVE": "aave-v3",
            "COMP": "compound-v3",
            "MKR": "sky-lending",
            "LDO": "lido",
            "RPL": "rocket-pool",
            "PENDLE": "pendle",
            "GMX": "gmx",
            "UNI": "uniswap-v3",
            "SUSHI": "sushiswap",
            "SNX": "synthetix",
            "DYDX": "dydx",
            "JTO": "jito-liquid-staking",
            "RAY": "raydium-amm",
            "ORCA": "orca",
            "JUP": "jupiter-perpetual-exchange",
            "KMNO": "kamino-lend",
            "MORPHO": "morpho-v1",
            "ENA": "ethena-usde",
            "EIGEN": "eigencloud",
            "ETHFI": "ether.fi-stake",
            "REZ": "renzo",
            "SD": "stader",
            "LISTA": "lista-liquid-staking",
            "CAKE": "pancakeswap-amm",
            "XVS": "venus-core-pool",
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
    
    def generate_tvl_report(self):
        """Generate a comprehensive TVL analysis report"""
        anomalies = self.detect_tvl_anomalies()
        changes = self.get_top_tvl_changes(10)
        
        report = f"📊 <b>TVL Alpha Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</b>\n\n"
        
        # Anomalies Section
        if anomalies:
            report += "<b>🚨 TVL ANOMALIES DETECTED:</b>\n"
            report += "<i>High TVL change = Money flowing in = Potential pump</i>\n\n"
            
            for i, a in enumerate(anomalies[:10], 1):
                token_info = f" (${a['symbol']})" if a['has_tradeable_token'] else ""
                report += f"{i}. <b>{a['name']}{token_info}</b>\n"
                report += f"   {a['anomaly_type']}\n"
                report += f"   TVL: {a['tvl_display']} | 1D: <b>{a['change_1d']:+.1f}%</b> | 7D: {a['change_7d']:+.1f}%\n"
                report += f"   Signal: {'🟢' * (a['signal_strength'] // 25)}\n\n"
        
        # Top Inflow
        report += "\n<b>💚 TOP TVL INFLOWS (24h):</b>\n"
        for p in changes['top_inflow'][:5]:
            report += f"• {p['name']} ({p['symbol']}): +{p['change_1d']:.1f}%\n"
        
        # Top Outflow
        report += "\n<b>🔴 TOP TVL OUTFLOWS (24h):</b>\n"
        for p in changes['top_outflow'][:5]:
            report += f"• {p['name']} ({p['symbol']}): {p['change_1d']:.1f}%\n"
        
        report += "\n<i>⚡ Data: DeFiLlama | Powered by Radar Ultra AI</i>"
        
        return report
    
    def get_protocol_by_token(self, token_symbol):
        """Get protocol info by its token symbol"""
        token_upper = token_symbol.upper()
        if token_upper in self.token_protocol_map:
            slug = self.token_protocol_map[token_upper]
            if not self.protocols_cache:
                self.fetch_all_protocols()
            return self.protocols_cache.get(slug)
        return None


# Module-level instance for easy import
TVL_TRACKER = TVLTracker()


def get_tvl_alpha_report():
    """Get the TVL alpha report - call this from main.py"""
    return TVL_TRACKER.generate_tvl_report()


def get_tvl_anomalies():
    """Get list of TVL anomalies - call this from main.py"""
    return TVL_TRACKER.detect_tvl_anomalies()


# Test
if __name__ == "__main__":
    tracker = TVLTracker()
    print(tracker.generate_tvl_report())
