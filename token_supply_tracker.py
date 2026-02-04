"""
Token Unlock & Supply Pressure Tracker - Inflation risk analysis using free CoinGecko data
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import time

class TokenSupplyTracker:
    """Analyzes token supply dynamics and inflation risk"""
    
    def __init__(self):
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache (supply doesn't change fast)
    
    def get_batch_supply_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get supply data for multiple coins in one batch request"""
        try:
            # Map symbols to CoinGecko IDs
            symbol_map = {
                # Top 20
                "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
                "XRP": "ripple", "ADA": "cardano", "AVAX": "avalanche-2", "DOGE": "dogecoin",
                "TRX": "tron", "LINK": "chainlink", "DOT": "polkadot", "MATIC": "matic-network",
                "SHIB": "shiba-inu", "LTC": "litecoin", "UNI": "uniswap", "ARB": "arbitrum",
                
                # Layer 2s & New Chains
                "OP": "optimism", "SUI": "sui", "APT": "aptos", "SEI": "sei-network",
                "TIA": "celestia", "STRK": "starknet", "IMX": "immutable-x",
                "BLAST": "blast", "MANTA": "manta-network", "ZK": "zksync",
                
                # DeFi Tokens
                "AAVE": "aave", "MKR": "maker", "COMP": "compound-governance-token",
                "CRV": "curve-dao-token", "SNX": "synthetix-network-token",
                "SUSHI": "sushi", "BAL": "balancer", "YFI": "yearn-finance",
                "1INCH": "1inch", "LDO": "lido-dao",
                
                # AI & Data
                "FET": "fetch-ai", "RNDR": "render-token", "WLD": "worldcoin-wld",
                "GRT": "the-graph", "OCEAN": "ocean-protocol",
                
                # Gaming & Metaverse
                "SAND": "the-sandbox", "MANA": "decentraland", "AXS": "axie-infinity",
                "GALA": "gala", "ENJ": "enjincoin", "IMX": "immutable-x",
                
                # Memecoins
                "PEPE": "pepe", "WIF": "dogwifcoin", "BONK": "bonk", 
                "FLOKI": "floki", "BRETT": "brett",
                
                # Solana Ecosystem
                "JUP": "jupiter-exchange-solana", "PYTH": "pyth-network", 
                "JTO": "jito-governance-token", "WEN": "wen-4",
                
                # Storage & Infrastructure
                "FIL": "filecoin", "AR": "arweave", "STORJ": "storj",
                
                # Cosmos Ecosystem
                "ATOM": "cosmos", "INJ": "injective-protocol", "OSMO": "osmosis",
                "TIA": "celestia", "DYM": "dymension",
                
                # Other Notable
                "NEAR": "near", "STX": "blockstack", "RUNE": "thorchain",
                "FTM": "fantom", "ALGO": "algorand", "ETC": "ethereum-classic",
                "XLM": "stellar", "VET": "vechain", "HBAR": "hedera-hashgraph",
                "ICP": "internet-computer", "APE": "apecoin",
                "ENA": "ethena", "PENDLE": "pendle",
                
                # Stablecoins & Wrapped
                "WBTC": "wrapped-bitcoin", "WETH": "weth", "USDT": "tether",
                "USDC": "usd-coin", "DAI": "dai", "BUSD": "binance-usd",
                "TUSD": "true-usd", "PAXG": "pax-gold",
                "SENT": "sentinel-group", "USD1": "usd-coin"  # Fallback mappings
            }
            
            # Map symbols to IDs
            coin_ids = []
            symbol_to_id = {}
            for sym in symbols:
                clean_sym = sym.replace("USDT", "").replace("BUSD", "").upper()
                coin_id = symbol_map.get(clean_sym, clean_sym.lower())
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = clean_sym
            
            # Batch request to CoinGecko markets endpoint
            url = f"{self.coingecko_url}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ",".join(coin_ids[:50]),  # Max 50 per request
                "per_page": 50,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h"
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"[TOKEN-SUPPLY] Batch API error: HTTP {response.status_code}")
                return {}
            
            data = response.json()
            results = {}
            
            for coin in data:
                coin_id = coin.get("id")
                symbol = symbol_to_id.get(coin_id, coin.get("symbol", "").upper())
                
                circulating = coin.get("circulating_supply", 0)
                total = coin.get("total_supply", 0)
                max_supply = coin.get("max_supply", 0)
                
                # Use total if max is missing
                final_total = max_supply if max_supply else total
                if not final_total or final_total == 0:
                    final_total = circulating
                
                unlock_pct = (circulating / final_total) * 100 if final_total > 0 else 100
                locked_pct = 100 - unlock_pct
                
                fdv = coin.get("fully_diluted_valuation", 0)
                mc = coin.get("market_cap", 0)
                
                # Handle None values
                if fdv is None: fdv = mc or 0
                if mc is None: mc = 0
                
                mc_fdv_ratio = mc / fdv if fdv > 0 else 1.0
                
                results[symbol] = {
                    "symbol": symbol,
                    "circulating_supply": circulating,
                    "total_supply": final_total,
                    "locked_percent": locked_pct,
                    "unlocked_percent": unlock_pct,
                    "mc_fdv_ratio": mc_fdv_ratio,
                    "market_cap": mc,
                    "fdv": fdv
                }
            
            return results
            
        except requests.exceptions.Timeout:
            print(f"[TOKEN-SUPPLY] Batch request timeout")
        except requests.exceptions.RequestException as e:
            print(f"[TOKEN-SUPPLY] Batch request error: {e}")
        except Exception as e:
            print(f"[TOKEN-SUPPLY] Unexpected batch error: {e}")
        
        return {}
    
    def get_token_supply_data(self, symbol: str) -> Optional[Dict]:
        """Get supply data from CoinGecko (Free API) - DEPRECATED, use batch instead"""
        print(f"[TOKEN-SUPPLY] Warning: get_token_supply_data is deprecated. Use get_batch_supply_data instead.")
        # This method is now a placeholder. For actual data, the batch method is preferred.
        # If a single call is absolutely needed, one could implement it by calling the batch method
        # with a list containing only 'symbol' and then extracting the result.
        return None

    def analyze_supply_risk(self, coins_data: List[Dict]) -> str:
        """Generate Supply & Unlock Risk Report"""
        report = "🔓 <b>Token Economics & Unlock Risk Report</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "📊 Analyzing MC/FDV ratio to detect inflation pressure\n\n"
        
        high_risk_coins = []
        medium_risk_coins = []
        low_risk_coins = []
        failed_coins = []
        
        # Analyze top 15 coins by volume
        sorted_coins = sorted(
            coins_data, 
            key=lambda x: float(str(x.get("24h Volume", 0)).replace(",", "")), 
            reverse=True
        )[:15]
        
        # Extract symbols for batch request
        symbols = [coin.get("Coin", "") for coin in sorted_coins if coin.get("Coin")]
        
        # Get all supply data in one batch request
        supply_data_map = self.get_batch_supply_data(symbols)
        
        analyzed_count = 0
        for coin in sorted_coins:
            symbol = coin.get("Coin", "")
            if not symbol: continue
            
            clean_symbol = symbol.replace("USDT", "").replace("BUSD", "").upper()
            supply_data = supply_data_map.get(clean_symbol)
            
            if not supply_data:
                failed_coins.append(clean_symbol)
                continue
            
            analyzed_count += 1
            locked = supply_data["locked_percent"]
            ratio = supply_data["mc_fdv_ratio"]
            
            entry = {
                "symbol": supply_data["symbol"],
                "locked": locked,
                "ratio": ratio,
                "fdv": supply_data["fdv"],
                "mc": supply_data["market_cap"]
            }
            
            # Risk Categorization
            if ratio < 0.20 or locked > 80:
                high_risk_coins.append(entry)
            elif ratio < 0.50 or locked > 50:
                medium_risk_coins.append(entry)
            else:
                low_risk_coins.append(entry)
        
        # Sort by risk (lowest ratio first for high risk)
        high_risk_coins.sort(key=lambda x: x["ratio"])
        medium_risk_coins.sort(key=lambda x: x["ratio"])
        low_risk_coins.sort(key=lambda x: x["ratio"], reverse=True)
        
        # Report Header
        report += f"📈 <b>Analyzed {analyzed_count} top coins</b>\n"
        report += f"🚨 High Risk: {len(high_risk_coins)} | 🟠 Medium: {len(medium_risk_coins)} | ✅ Low: {len(low_risk_coins)}\n\n"
        
        # High Risk Section
        if high_risk_coins:
            report += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            report += "🚨 <b>HIGH INFLATION RISK (Low Float)</b>\n"
            report += "⚠️ Massive unlocks expected. Long term dilution risk.\n\n"
            for c in high_risk_coins:
                report += f"<b>${c['symbol']}</b>\n"
                report += f"   🔒 Locked Supply: <b>{c['locked']:.1f}%</b>\n"
                report += f"   📉 MC/FDV Ratio: <b>{c['ratio']:.2f}</b>\n"
                report += f"   💰 MC: ${c['mc']/1e9:.2f}B | FDV: ${c['fdv']/1e9:.2f}B\n\n"
        
        # Medium Risk Section
        if medium_risk_coins:
            report += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            report += "🟠 <b>MEDIUM INFLATION RISK</b>\n"
            report += "⚡ Moderate unlock schedule. Monitor closely.\n\n"
            for c in medium_risk_coins:
                report += f"<b>${c['symbol']}</b>\n"
                report += f"   🔒 Locked: {c['locked']:.1f}% | MC/FDV: {c['ratio']:.2f}\n"
                report += f"   💰 MC: ${c['mc']/1e9:.2f}B | FDV: ${c['fdv']/1e9:.2f}B\n\n"
        
        # Low Risk Section
        if low_risk_coins:
            report += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            report += "✅ <b>LOW INFLATION RISK (Healthy Float)</b>\n"
            report += "🟢 Most tokens already circulating. Low dilution risk.\n\n"
            for c in low_risk_coins[:10]:  # Show top 10 low risk
                report += f"<b>${c['symbol']}</b> - Locked: {c['locked']:.1f}% | MC/FDV: {c['ratio']:.2f}\n"
        
        # Failed Coins
        if failed_coins:
            report += f"\n⚠️ <i>Data unavailable for: {', '.join(failed_coins[:5])}</i>\n"
        
        # Guide Section
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "💡 <b>Guide:</b>\n"
        report += "• <b>MC/FDV < 0.1</b>: Toxic Tokenomics (VC dump risk)\n"
        report += "• <b>High Locked %</b>: Future selling pressure guaranteed\n"
        report += "• <b>MC/FDV > 0.8</b>: Healthy circulation, low dilution\n"
        
        return report

# Global Instance
TOKEN_SUPPLY_TRACKER = TokenSupplyTracker()

def get_token_supply_report(coins_data: List[Dict]) -> str:
    return TOKEN_SUPPLY_TRACKER.analyze_supply_risk(coins_data)
