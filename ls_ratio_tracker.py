"""
Long/Short Ratio & OI Breakdown - Multi-exchange comprehensive analysis
Uses FREE endpoints from Binance, Bybit, OKX
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import aiohttp


class LongShortRatioTracker:
    """Tracks Long/Short ratios and OI breakdown across exchanges"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60
    
    async def fetch_binance_ls_ratio(self, session, symbol: str) -> Dict:
        """Fetch Binance Long/Short ratio - FREE API"""
        try:
            # Global Long/Short Account Ratio
            url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
            params = {"symbol": symbol, "period": "5m", "limit": 1}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return {
                            "long_account": float(data[0].get("longAccount", 0.5)),
                            "short_account": float(data[0].get("shortAccount", 0.5)),
                            "long_short_ratio": float(data[0].get("longShortRatio", 1.0)),
                            "timestamp": int(data[0].get("timestamp", 0))
                        }
        except Exception as e:
            print(f"[DEBUG] Binance L/S ratio failed for {symbol}: {e}")
        return None
    
    async def fetch_binance_oi(self, session, symbol: str) -> Optional[float]:
        """Fetch Binance Open Interest - FREE API"""
        try:
            url = "https://fapi.binance.com/fapi/v1/openInterest"
            params = {"symbol": symbol}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("openInterest", 0))
        except:
            pass
        return None
    
    async def fetch_bybit_ls_ratio(self, session, symbol: str) -> Dict:
        """Fetch Bybit Long/Short ratio - FREE API"""
        try:
            normalized = symbol.replace("USDT", "")
            url = "https://api.bybit.com/v5/market/account-ratio"
            params = {"category": "linear", "symbol": f"{normalized}USDT", "period": "5min", "limit": 1}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("result") and data["result"].get("list"):
                        item = data["result"]["list"][0]
                        buy_ratio = float(item.get("buyRatio", 0.5))
                        sell_ratio = float(item.get("sellRatio", 0.5))
                        
                        return {
                            "long_account": buy_ratio,
                            "short_account": sell_ratio,
                            "long_short_ratio": buy_ratio / sell_ratio if sell_ratio > 0 else 1.0,
                            "timestamp": int(item.get("timestamp", 0))
                        }
        except Exception as e:
            print(f"[DEBUG] Bybit L/S ratio failed for {symbol}: {e}")
        return None
    
    async def fetch_bybit_oi(self, session, symbol: str) -> Optional[float]:
        """Fetch Bybit Open Interest - FREE API"""
        try:
            normalized = symbol.replace("USDT", "")
            url = "https://api.bybit.com/v5/market/open-interest"
            params = {"category": "linear", "symbol": f"{normalized}USDT", "intervalTime": "5min", "limit": 1}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("result") and data["result"].get("list"):
                        return float(data["result"]["list"][0].get("openInterest", 0))
        except:
            pass
        return None
    
    async def fetch_okx_ls_ratio(self, session, symbol: str) -> Dict:
        """Fetch OKX Long/Short ratio - FREE API"""
        try:
            normalized = symbol.replace("USDT", "")
            url = "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio"
            params = {"instId": f"{normalized}-USDT-SWAP", "period": "5m"}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        item = data["data"][0]
                        long_pct = float(item.get("longAccount", 0.5))
                        short_pct = float(item.get("shortAccount", 0.5))
                        
                        return {
                            "long_account": long_pct,
                            "short_account": short_pct,
                            "long_short_ratio": long_pct / short_pct if short_pct > 0 else 1.0,
                            "timestamp": int(item.get("ts", 0))
                        }
        except Exception as e:
            print(f"[DEBUG] OKX L/S ratio failed for {symbol}: {e}")
        return None
    
    async def fetch_okx_oi(self, session, symbol: str) -> Optional[float]:
        """Fetch OKX Open Interest - FREE API"""
        try:
            normalized = symbol.replace("USDT", "")
            url = "https://www.okx.com/api/v5/public/open-interest"
            params = {"instId": f"{normalized}-USDT-SWAP"}
            
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        return float(data["data"][0].get("oi", 0))
        except:
            pass
        return None
    
    async def get_multi_exchange_data(self, symbol: str) -> Dict:
        """Fetch L/S ratio and OI from all exchanges"""
        async with aiohttp.ClientSession() as session:
            tasks = {
                "binance_ls": self.fetch_binance_ls_ratio(session, symbol),
                "binance_oi": self.fetch_binance_oi(session, symbol),
                "bybit_ls": self.fetch_bybit_ls_ratio(session, symbol),
                "bybit_oi": self.fetch_bybit_oi(session, symbol),
                "okx_ls": self.fetch_okx_ls_ratio(session, symbol),
                "okx_oi": self.fetch_okx_oi(session, symbol),
            }
            
            results = {}
            for key, task in tasks.items():
                try:
                    results[key] = await task
                except:
                    results[key] = None
            
            return results
    
    def calculate_aggregate_metrics(self, multi_data: Dict) -> Dict:
        """Calculate aggregated L/S ratio and OI"""
        ls_ratios = []
        total_oi = 0
        exchange_details = {}
        
        # Binance
        if multi_data.get("binance_ls"):
            ls_ratios.append(multi_data["binance_ls"]["long_short_ratio"])
            oi_binance = multi_data.get("binance_oi", 0) or 0
            total_oi += oi_binance
            exchange_details["binance"] = {
                "ls_ratio": multi_data["binance_ls"]["long_short_ratio"],
                "long_pct": multi_data["binance_ls"]["long_account"] * 100,
                "short_pct": multi_data["binance_ls"]["short_account"] * 100,
                "oi": oi_binance
            }
        
        # Bybit
        if multi_data.get("bybit_ls"):
            ls_ratios.append(multi_data["bybit_ls"]["long_short_ratio"])
            oi_bybit = multi_data.get("bybit_oi", 0) or 0
            total_oi += oi_bybit
            exchange_details["bybit"] = {
                "ls_ratio": multi_data["bybit_ls"]["long_short_ratio"],
                "long_pct": multi_data["bybit_ls"]["long_account"] * 100,
                "short_pct": multi_data["bybit_ls"]["short_account"] * 100,
                "oi": oi_bybit
            }
        
        # OKX
        if multi_data.get("okx_ls"):
            ls_ratios.append(multi_data["okx_ls"]["long_short_ratio"])
            oi_okx = multi_data.get("okx_oi", 0) or 0
            total_oi += oi_okx
            exchange_details["okx"] = {
                "ls_ratio": multi_data["okx_ls"]["long_short_ratio"],
                "long_pct": multi_data["okx_ls"]["long_account"] * 100,
                "short_pct": multi_data["okx_ls"]["short_account"] * 100,
                "oi": oi_okx
            }
        
        # Calculate weighted average L/S ratio
        if ls_ratios:
            avg_ls_ratio = sum(ls_ratios) / len(ls_ratios)
        else:
            avg_ls_ratio = 1.0
        
        # Determine bias
        if avg_ls_ratio > 1.5:
            bias = "bullish"
        elif avg_ls_ratio < 0.67:
            bias = "bearish"
        else:
            bias = "neutral"
        
        return {
            "avg_ls_ratio": avg_ls_ratio,
            "total_oi": total_oi,
            "bias": bias,
            "exchange_details": exchange_details,
            "exchange_count": len(exchange_details)
        }
    
    def get_ls_ratio_report(self, coins_data: List[Dict]) -> str:
        """Generate comprehensive Long/Short ratio report"""
        report = "📊 <b>Long/Short Ratio & OI Breakdown</b>\n"
        report += f"🕐 Updated: {datetime.now().strftime('%H:%M:%S')}\n"
        report += "🔄 Multi-Exchange Analysis (Binance, Bybit, OKX)\n\n"
        
        # Focus on high OI coins
        high_oi_coins = []
        
        for coin in coins_data[:30]:  # Top 30 by volume
            symbol = coin.get("Coin", "")  # Changed from "Symbol"
            if not symbol:
                continue
            
            try:
                # Get multi-exchange data
                multi_data = asyncio.run(self.get_multi_exchange_data(symbol))
                metrics = self.calculate_aggregate_metrics(multi_data)
                
                if metrics["exchange_count"] > 0:
                    high_oi_coins.append({
                        "symbol": symbol.replace("USDT", ""),
                        **metrics
                    })
            except Exception as e:
                print(f"[DEBUG] L/S tracking failed for {symbol}: {e}")
                continue
        
        # Sort by total OI
        high_oi_coins.sort(key=lambda x: x["total_oi"], reverse=True)
        
        # Categorize by bias
        bullish = [c for c in high_oi_coins if c["bias"] == "bullish"]
        bearish = [c for c in high_oi_coins if c["bias"] == "bearish"]
        neutral = [c for c in high_oi_coins if c["bias"] == "neutral"]
        
        # Report bullish bias
        if bullish:
            report += "🟢 <b>BULLISH BIAS (L/S > 1.5)</b>\n\n"
            for coin in bullish[:7]:
                report += f"<b>${coin['symbol']}</b> - L/S: {coin['avg_ls_ratio']:.2f}\n"
                report += f"   Total OI: ${coin['total_oi']/1e6:.2f}M\n"
                
                if "binance" in coin["exchange_details"]:
                    ex = coin["exchange_details"]["binance"]
                    report += f"   📍 Binance: {ex['long_pct']:.1f}% Long / {ex['short_pct']:.1f}% Short\n"
                
                if "bybit" in coin["exchange_details"]:
                    ex = coin["exchange_details"]["bybit"]
                    report += f"   📍 Bybit: {ex['long_pct']:.1f}% Long / {ex['short_pct']:.1f}% Short\n"
                
                if "okx" in coin["exchange_details"]:
                    ex = coin["exchange_details"]["okx"]
                    report += f"   📍 OKX: {ex['long_pct']:.1f}% Long / {ex['short_pct']:.1f}% Short\n"
                
                report += "\n"
        
        # Report bearish bias
        if bearish:
            report += "🔴 <b>BEARISH BIAS (L/S < 0.67)</b>\n\n"
            for coin in bearish[:7]:
                report += f"<b>${coin['symbol']}</b> - L/S: {coin['avg_ls_ratio']:.2f}\n"
                report += f"   Total OI: ${coin['total_oi']/1e6:.2f}M\n"
                
                for exchange in ["binance", "bybit", "okx"]:
                    if exchange in coin["exchange_details"]:
                        ex = coin["exchange_details"][exchange]
                        report += f"   📍 {exchange.title()}: {ex['long_pct']:.1f}% L / {ex['short_pct']:.1f}% S\n"
                
                report += "\n"
        
        # Summary
        report += "📈 <b>Market Summary</b>\n"
        report += f"• Bullish Bias: {len(bullish)} coins\n"
        report += f"• Bearish Bias: {len(bearish)} coins\n"
        report += f"• Neutral: {len(neutral)} coins\n\n"
        
        report += "💡 <b>Interpretation:</b>\n"
        report += "• L/S > 2.0: Extreme long positions (short squeeze risk)\n"
        report += "• L/S < 0.5: Extreme short positions (long squeeze risk)\n"
        report += "• Multi-exchange confirmation = stronger signal\n"
        
        return report


# Global instance
LS_RATIO_TRACKER = LongShortRatioTracker()


def get_ls_ratio_report(coins_data: List[Dict]) -> str:
    """Get Long/Short ratio report"""
    return LS_RATIO_TRACKER.get_ls_ratio_report(coins_data)
