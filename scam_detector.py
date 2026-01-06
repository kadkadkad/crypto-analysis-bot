"""
Scam Detector - Token Security Analysis
Analyzes tokens for potential scam/rug pull indicators.
Uses GoPlus Security API and DEXScreener for real data.
"""

import requests
import datetime
import time
from typing import Dict, List, Optional
import json

class ScamDetector:
    """
    Token Security Analyzer
    Checks for: honeypot, mint functions, liquidity locks, holder distribution
    """
    
    def __init__(self):
        # GoPlus Security API (free, no key needed)
        self.goplus_url = "https://api.gopluslabs.io/api/v1"
        
        # DEXScreener API (free)
        self.dexscreener_url = "https://api.dexscreener.com/latest/dex"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Chain IDs for GoPlus
        self.chain_ids = {
            'eth': '1',
            'ethereum': '1',
            'bsc': '56',
            'bnb': '56',
            'polygon': '137',
            'matic': '137',
            'arbitrum': '42161',
            'arb': '42161',
            'base': '8453',
            'solana': 'solana',
            'sol': 'solana',
            'avalanche': '43114',
            'avax': '43114'
        }
    
    def search_token(self, query: str) -> List[Dict]:
        """
        Search for token by name or symbol
        Returns list of matching tokens with their addresses
        """
        results = []
        query = query.strip().upper()
        
        try:
            # Use DEXScreener search API
            url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                
                # Deduplicate by token address
                seen_addresses = set()
                
                for pair in pairs[:20]:  # Check first 20 pairs
                    base_token = pair.get('baseToken', {})
                    address = base_token.get('address', '')
                    symbol = base_token.get('symbol', '').upper()
                    name = base_token.get('name', '')
                    chain = pair.get('chainId', 'ethereum')
                    
                    if address and address not in seen_addresses:
                        # Match by symbol or name
                        if query in symbol or query in name.upper():
                            liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                            
                            results.append({
                                'address': address,
                                'symbol': symbol,
                                'name': name,
                                'chain': chain,
                                'liquidity_usd': liquidity,
                                'price_usd': pair.get('priceUsd', '0'),
                                'dex': pair.get('dexId', 'unknown')
                            })
                            seen_addresses.add(address)
                
                # Sort by liquidity (highest first)
                results.sort(key=lambda x: x['liquidity_usd'], reverse=True)
                
        except Exception as e:
            print(f"[ERROR] Token search failed: {e}")
        
        return results[:10]  # Return top 10 matches
    
    def analyze_by_name(self, query: str, chain: str = None) -> Dict:
        """
        Analyze token by name/symbol (finds address automatically)
        """
        # First search for the token
        matches = self.search_token(query)
        
        if not matches:
            return {
                'error': f"Token '{query}' not found. Try using the contract address.",
                'suggestions': []
            }
        
        # If chain specified, filter
        if chain:
            chain_matches = [m for m in matches if chain.lower() in m['chain'].lower()]
            if chain_matches:
                matches = chain_matches
        
        # Use the best match (highest liquidity)
        best_match = matches[0]
        
        # Map chain name to our format
        chain_map = {
            'ethereum': 'eth',
            'bsc': 'bsc',
            'polygon': 'polygon',
            'arbitrum': 'arbitrum',
            'base': 'base',
            'avalanche': 'avalanche',
            'solana': 'solana'
        }
        detected_chain = chain_map.get(best_match['chain'], 'eth')
        
        # Now analyze the token
        result = self.analyze_token(best_match['address'], detected_chain)
        
        # Add search results for alternative matches
        result['search_query'] = query
        result['alternatives'] = matches[1:5] if len(matches) > 1 else []
        
        return result
    
    def analyze_token(self, token_address: str, chain: str = 'eth') -> Dict:
        """
        Comprehensive token security analysis
        
        Args:
            token_address: Contract address of the token
            chain: Chain name (eth, bsc, polygon, arbitrum, base, solana)
        
        Returns:
            Complete security analysis with risk score
        """
        chain = chain.lower()
        chain_id = self.chain_ids.get(chain, '1')
        
        result = {
            'token_address': token_address,
            'chain': chain,
            'analyzed_at': datetime.datetime.now().isoformat(),
            'risk_score': 0,  # 0-100, higher = more risky
            'risk_level': 'unknown',
            'is_scam': False,
            'warnings': [],
            'security_checks': {},
            'liquidity_info': {},
            'holder_info': {},
            'recommendation': ''
        }
        
        # 1. GoPlus Security Check
        try:
            goplus_data = self._check_goplus_security(token_address, chain_id)
            if goplus_data:
                result['security_checks'] = goplus_data.get('checks', {})
                result['warnings'].extend(goplus_data.get('warnings', []))
                result['risk_score'] += goplus_data.get('risk_score', 0)
        except Exception as e:
            result['warnings'].append(f"Security API check failed: {str(e)}")
        
        # 2. DEXScreener Liquidity Check
        try:
            dex_data = self._check_dexscreener(token_address)
            if dex_data:
                result['liquidity_info'] = dex_data.get('liquidity', {})
                result['token_info'] = dex_data.get('token_info', {})
                result['warnings'].extend(dex_data.get('warnings', []))
                result['risk_score'] += dex_data.get('risk_score', 0)
        except Exception as e:
            result['warnings'].append(f"Liquidity check failed: {str(e)}")
        
        # 3. Calculate final risk level
        result['risk_score'] = min(result['risk_score'], 100)
        result['risk_level'] = self._calculate_risk_level(result['risk_score'])
        result['is_scam'] = result['risk_score'] >= 70
        result['recommendation'] = self._generate_recommendation(result)
        
        return result
    
    def _check_goplus_security(self, token_address: str, chain_id: str) -> Dict:
        """Check token security via GoPlus API"""
        result = {
            'checks': {},
            'warnings': [],
            'risk_score': 0
        }
        
        try:
            url = f"{self.goplus_url}/token_security/{chain_id}"
            params = {'contract_addresses': token_address}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == 1 and data.get('result'):
                    token_data = data['result'].get(token_address.lower(), {})
                    
                    if not token_data:
                        result['warnings'].append("⚠️ Token not found in security database")
                        result['risk_score'] += 20
                        return result
                    
                    # Check critical security flags
                    checks = {}
                    
                    # 🔴 CRITICAL RISKS (high score)
                    if token_data.get('is_honeypot') == '1':
                        checks['honeypot'] = {'status': 'DANGER', 'message': '🚨 HONEYPOT - Cannot sell!'}
                        result['warnings'].append("🚨 HONEYPOT DETECTED - You cannot sell this token!")
                        result['risk_score'] += 50
                    else:
                        checks['honeypot'] = {'status': 'SAFE', 'message': '✅ Not a honeypot'}
                    
                    if token_data.get('is_mintable') == '1':
                        checks['mintable'] = {'status': 'WARNING', 'message': '⚠️ Owner can mint unlimited tokens'}
                        result['warnings'].append("⚠️ Token is MINTABLE - Owner can create unlimited supply")
                        result['risk_score'] += 25
                    else:
                        checks['mintable'] = {'status': 'SAFE', 'message': '✅ Not mintable'}
                    
                    if token_data.get('can_take_back_ownership') == '1':
                        checks['ownership'] = {'status': 'DANGER', 'message': '🚨 Owner can reclaim ownership'}
                        result['warnings'].append("🚨 Owner can reclaim ownership after renouncing")
                        result['risk_score'] += 30
                    
                    if token_data.get('owner_change_balance') == '1':
                        checks['balance_modify'] = {'status': 'DANGER', 'message': '🚨 Owner can modify balances'}
                        result['warnings'].append("🚨 Owner can modify holder balances!")
                        result['risk_score'] += 40
                    
                    if token_data.get('hidden_owner') == '1':
                        checks['hidden_owner'] = {'status': 'WARNING', 'message': '⚠️ Hidden owner detected'}
                        result['warnings'].append("⚠️ Contract has hidden owner")
                        result['risk_score'] += 20
                    
                    if token_data.get('selfdestruct') == '1':
                        checks['selfdestruct'] = {'status': 'DANGER', 'message': '🚨 Contract can self-destruct'}
                        result['warnings'].append("🚨 Contract can self-destruct!")
                        result['risk_score'] += 35
                    
                    if token_data.get('external_call') == '1':
                        checks['external_call'] = {'status': 'WARNING', 'message': '⚠️ External calls in contract'}
                        result['risk_score'] += 10
                    
                    # Trading restrictions
                    if token_data.get('cannot_sell_all') == '1':
                        checks['sell_limit'] = {'status': 'WARNING', 'message': '⚠️ Cannot sell all tokens at once'}
                        result['warnings'].append("⚠️ You cannot sell 100% of your holdings")
                        result['risk_score'] += 15
                    
                    if token_data.get('trading_cooldown') == '1':
                        checks['cooldown'] = {'status': 'WARNING', 'message': '⚠️ Trading cooldown enabled'}
                        result['risk_score'] += 10
                    
                    # Tax analysis
                    buy_tax = float(token_data.get('buy_tax', '0') or '0')
                    sell_tax = float(token_data.get('sell_tax', '0') or '0')
                    
                    if buy_tax > 10 or sell_tax > 10:
                        checks['high_tax'] = {'status': 'WARNING', 'message': f'⚠️ High tax: Buy {buy_tax}%, Sell {sell_tax}%'}
                        result['warnings'].append(f"⚠️ High tax rates: Buy {buy_tax}%, Sell {sell_tax}%")
                        result['risk_score'] += min((buy_tax + sell_tax) / 2, 20)
                    else:
                        checks['tax'] = {'status': 'SAFE', 'message': f'✅ Tax: Buy {buy_tax}%, Sell {sell_tax}%'}
                    
                    # Holder concentration
                    holder_count = int(token_data.get('holder_count', '0') or '0')
                    if holder_count < 100:
                        checks['holders'] = {'status': 'WARNING', 'message': f'⚠️ Only {holder_count} holders'}
                        result['warnings'].append(f"⚠️ Very few holders: {holder_count}")
                        result['risk_score'] += 15
                    elif holder_count < 500:
                        checks['holders'] = {'status': 'CAUTION', 'message': f'⚡ {holder_count} holders'}
                        result['risk_score'] += 5
                    else:
                        checks['holders'] = {'status': 'SAFE', 'message': f'✅ {holder_count} holders'}
                    
                    # Top holder concentration
                    top10_pct = 0
                    holders = token_data.get('holders', [])
                    if holders:
                        for h in holders[:10]:
                            top10_pct += float(h.get('percent', 0))
                    
                    if top10_pct > 80:
                        checks['concentration'] = {'status': 'DANGER', 'message': f'🚨 Top 10 hold {top10_pct:.1f}%'}
                        result['warnings'].append(f"🚨 Extreme concentration: Top 10 wallets hold {top10_pct:.1f}%")
                        result['risk_score'] += 25
                    elif top10_pct > 50:
                        checks['concentration'] = {'status': 'WARNING', 'message': f'⚠️ Top 10 hold {top10_pct:.1f}%'}
                        result['risk_score'] += 10
                    
                    # Contract verification
                    if token_data.get('is_open_source') == '1':
                        checks['verified'] = {'status': 'SAFE', 'message': '✅ Contract verified'}
                    else:
                        checks['verified'] = {'status': 'WARNING', 'message': '⚠️ Contract not verified'}
                        result['warnings'].append("⚠️ Contract source code not verified")
                        result['risk_score'] += 15
                    
                    # Proxy contract
                    if token_data.get('is_proxy') == '1':
                        checks['proxy'] = {'status': 'CAUTION', 'message': '⚡ Proxy contract'}
                        result['risk_score'] += 5
                    
                    result['checks'] = checks
                    
        except Exception as e:
            result['warnings'].append(f"GoPlus API error: {str(e)}")
            result['risk_score'] += 10
        
        return result
    
    def _check_dexscreener(self, token_address: str) -> Dict:
        """Check token on DEXScreener for liquidity and trading data"""
        result = {
            'liquidity': {},
            'token_info': {},
            'warnings': [],
            'risk_score': 0
        }
        
        try:
            url = f"{self.dexscreener_url}/tokens/{token_address}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                
                if not pairs:
                    result['warnings'].append("⚠️ No trading pairs found on DEXScreener")
                    result['risk_score'] += 20
                    return result
                
                # Get the pair with highest liquidity
                main_pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0) or 0))
                
                # Token info
                base_token = main_pair.get('baseToken', {})
                result['token_info'] = {
                    'name': base_token.get('name', 'Unknown'),
                    'symbol': base_token.get('symbol', '???'),
                    'price_usd': main_pair.get('priceUsd', '0'),
                    'price_change_24h': main_pair.get('priceChange', {}).get('h24', 0),
                    'volume_24h': main_pair.get('volume', {}).get('h24', 0),
                    'dex': main_pair.get('dexId', 'unknown'),
                    'pair_created': main_pair.get('pairCreatedAt', 0)
                }
                
                # Liquidity analysis
                liquidity_usd = float(main_pair.get('liquidity', {}).get('usd', 0) or 0)
                result['liquidity'] = {
                    'usd': liquidity_usd,
                    'base': main_pair.get('liquidity', {}).get('base', 0),
                    'quote': main_pair.get('liquidity', {}).get('quote', 0)
                }
                
                if liquidity_usd < 1000:
                    result['warnings'].append(f"🚨 Extremely low liquidity: ${liquidity_usd:,.0f}")
                    result['risk_score'] += 30
                elif liquidity_usd < 10000:
                    result['warnings'].append(f"⚠️ Low liquidity: ${liquidity_usd:,.0f}")
                    result['risk_score'] += 15
                elif liquidity_usd < 50000:
                    result['warnings'].append(f"⚡ Moderate liquidity: ${liquidity_usd:,.0f}")
                    result['risk_score'] += 5
                
                # Age check
                pair_created = main_pair.get('pairCreatedAt', 0)
                if pair_created:
                    age_days = (time.time() * 1000 - pair_created) / (1000 * 60 * 60 * 24)
                    if age_days < 1:
                        result['warnings'].append(f"🚨 Token is less than 1 day old!")
                        result['risk_score'] += 25
                    elif age_days < 7:
                        result['warnings'].append(f"⚠️ Token is only {age_days:.0f} days old")
                        result['risk_score'] += 10
                    result['token_info']['age_days'] = round(age_days, 1)
                
                # Volume to liquidity ratio
                volume_24h = float(main_pair.get('volume', {}).get('h24', 0) or 0)
                if liquidity_usd > 0 and volume_24h > 0:
                    vol_liq_ratio = volume_24h / liquidity_usd
                    if vol_liq_ratio > 10:
                        result['warnings'].append(f"⚠️ Unusual volume/liquidity ratio: {vol_liq_ratio:.1f}x")
                        result['risk_score'] += 10
                    
        except Exception as e:
            result['warnings'].append(f"DEXScreener error: {str(e)}")
        
        return result
    
    def _calculate_risk_level(self, score: int) -> str:
        """Convert risk score to risk level"""
        if score >= 70:
            return 'CRITICAL'
        elif score >= 50:
            return 'HIGH'
        elif score >= 30:
            return 'MEDIUM'
        elif score >= 15:
            return 'LOW'
        else:
            return 'SAFE'
    
    def _generate_recommendation(self, result: Dict) -> str:
        """Generate human-readable recommendation"""
        risk_level = result['risk_level']
        score = result['risk_score']
        
        if risk_level == 'CRITICAL':
            return "🚨 DO NOT BUY - This token shows multiple critical red flags. Very high probability of scam/rug pull."
        elif risk_level == 'HIGH':
            return "⚠️ EXTREME CAUTION - This token has significant security concerns. Only trade with money you can afford to lose completely."
        elif risk_level == 'MEDIUM':
            return "⚡ PROCEED WITH CAUTION - Some warning signs detected. Do additional research before investing."
        elif risk_level == 'LOW':
            return "🟡 MODERATE RISK - Token appears relatively safe but always DYOR (Do Your Own Research)."
        else:
            return "🟢 LOW RISK - No major red flags detected. However, always practice risk management."
    
    def quick_scan(self, token_address: str) -> Dict:
        """Quick scan for basic security checks"""
        return self.analyze_token(token_address, 'eth')


# Global instance
SCAM_DETECTOR = None

def init_scam_detector():
    global SCAM_DETECTOR
    SCAM_DETECTOR = ScamDetector()
    return SCAM_DETECTOR

def get_scam_detector():
    global SCAM_DETECTOR
    if not SCAM_DETECTOR:
        init_scam_detector()
    return SCAM_DETECTOR


if __name__ == "__main__":
    print("Testing Scam Detector...")
    detector = ScamDetector()
    
    # Test with PEPE token on Ethereum
    test_address = "0x6982508145454ce325ddbe47a25d4ec3d2311933"  # PEPE
    
    print(f"\nAnalyzing: {test_address}")
    result = detector.analyze_token(test_address, 'eth')
    
    print(f"\n{'='*50}")
    print(f"Token: {result.get('token_info', {}).get('symbol', 'Unknown')}")
    print(f"Risk Score: {result['risk_score']}/100")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Is Scam: {result['is_scam']}")
    print(f"\nWarnings:")
    for w in result['warnings']:
        print(f"  {w}")
    print(f"\nRecommendation: {result['recommendation']}")
