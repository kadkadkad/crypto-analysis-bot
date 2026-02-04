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
    
    def get_token_supply_data(self, symbol: str) -> Optional[Dict]:
        """Get supply data from CoinGecko (Free API)"""
        try:
            # Map symbol to CoinGecko ID (simplified mapping)
            symbol_map = {
                "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
                "XRP": "ripple", "ADA": "cardano", "AVAX": "avalanche-2", "DOGE": "dogecoin",
                "TRX": "tron", "LINK": "chainlink", "DOT": "polkadot", "MATIC": "matic-network",
                "SHIB": "shiba-inu", "LTC": "litecoin", "UNI": "uniswap", "ARB": "arbitrum",
                "OP": "optimism", "SUI": "sui", "APT": "aptos", "WLD": "worldcoin-org",
                "TIA": "celestia", "SEI": "sei-network", "INJ": "injective-protocol",
                "RNDR": "render-token", "FIL": "filecoin", "ATOM": "cosmos", "IMX": "immutable-x",
                "NEAR": "near", "STX": "blockstack", "SAND": "the-sandbox", "MANA": "decentraland",
                "AXS": "axie-infinity", "STRK": "starknet", "JUP": "jupiter-exchange-solana",
                "PYTH": "pyth-network", "ENA": "ethena", "WIF": "dogwifcoin"
            }
            
            clean_symbol = symbol.replace("USDT", "").upper()
            coin_id = symbol_map.get(clean_symbol)
            
            if not coin_id:
                # Fallback: try using symbol as id (often works)
                coin_id = clean_symbol.lower()
            
            url = f"{self.coingecko_url}/coins/{coin_id}"
            params = {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false"
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                md = data.get("market_data", {})
                
                circulating = md.get("circulating_supply", 0)
                total = md.get("total_supply", 0)
                max_supply = md.get("max_supply", 0)
                
                # Use total if max is missing (for uncapped coins approx)
                final_total = max_supply if max_supply else total
                
                if not final_total or final_total == 0:
                    final_total = circulating  # Fallback to avoid division by zero
                
                unlock_pct = (circulating / final_total) * 100 if final_total > 0 else 100
                locked_pct = 100 - unlock_pct
                
                fdv = md.get("fully_diluted_valuation", {}).get("usd", 0)
                mc = md.get("market_cap", {}).get("usd", 0)
                
                mc_fdv_ratio = mc / fdv if fdv > 0 else 1.0
                
                return {
                    "symbol": clean_symbol,
                    "circulating_supply": circulating,
                    "total_supply": final_total,
                    "locked_percent": locked_pct,
                    "unlocked_percent": unlock_pct,
                    "mc_fdv_ratio": mc_fdv_ratio,
                    "market_cap": mc,
                    "fdv": fdv
                }
            else:
                print(f"[TOKEN-SUPPLY] CoinGecko API error for {clean_symbol}: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"[TOKEN-SUPPLY] Timeout fetching data for {symbol}")
        except requests.exceptions.RequestException as e:
            print(f"[TOKEN-SUPPLY] Request error for {symbol}: {e}")
        except Exception as e:
            print(f"[TOKEN-SUPPLY] Unexpected error for {symbol}: {e}")
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
        
        analyzed_count = 0
        for coin in sorted_coins:
            symbol = coin.get("Coin", "")
            if not symbol: continue
            
            # Rate limit prevention
            time.sleep(0.25)
            
            supply_data = self.get_token_supply_data(symbol)
            if not supply_data:
                failed_coins.append(symbol.replace("USDT", ""))
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
