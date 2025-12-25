"""
Signal Win Rate Tracker
Tracks historical performance of trading signals
"""
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

class SignalWinRateTracker:
    def __init__(self, db_file="signal_history.json"):
        self.db_file = db_file
        self.signal_history = self._load_history()
        
    def _load_history(self):
        """Load signal history from file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except:
                return {"signals": [], "stats": {}}
        return {"signals": [], "stats": {}}
    
    def _save_history(self):
        """Save signal history to file"""
        with open(self.db_file, 'w') as f:
            json.dump(self.signal_history, f, default=str)
    
    def record_signal(self, signal_type, symbol, price, indicators):
        """
        Record a new signal
        
        Args:
            signal_type: "ema_bullish_xover", "volume_spike", "cash_flow_high", etc.
            symbol: Coin symbol
            price: Entry price
            indicators: Dict of relevant indicators
        """
        signal = {
            "id": f"{signal_type}_{symbol}_{datetime.now().timestamp()}",
            "type": signal_type,
            "symbol": symbol,
            "entry_price": price,
            "entry_time": datetime.now().isoformat(),
            "indicators": indicators,
            "outcome": None,  # Will be updated later
            "exit_price": None,
            "profit_percent": None,
            "duration_hours": None
        }
        
        self.signal_history["signals"].append(signal)
        self._save_history()
        
        return signal["id"]
    
    def update_signal_outcome(self, current_prices):
        """
        Update outcomes for open signals based on current prices
        
        Check if signal target hit (+5%) or stop loss (-3%)
        """
        updated = 0
        
        for signal in self.signal_history["signals"]:
            if signal["outcome"] is not None:
                continue  # Already closed
            
            symbol = signal["symbol"]
            if symbol not in current_prices:
                continue
            
            current_price = current_prices[symbol]
            entry_price = signal["entry_price"]
            entry_time = datetime.fromisoformat(signal["entry_time"])
            
            # Calculate profit
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            
            # Determine outcome
            signal_type = signal["type"]
            
            # Bullish signals
            if "bullish" in signal_type or "xover" in signal_type and "bullish" in signal_type:
                if profit_pct >= 5.0:  # Target hit
                    signal["outcome"] = "WIN"
                    signal["exit_price"] = current_price
                    signal["profit_percent"] = profit_pct
                elif profit_pct <= -3.0:  # Stop loss
                    signal["outcome"] = "LOSS"
                    signal["exit_price"] = current_price
                    signal["profit_percent"] = profit_pct
            
            # Bearish signals
            elif "bearish" in signal_type:
                if profit_pct <= -5.0:  # Target hit (inverse)
                    signal["outcome"] = "WIN"
                    signal["exit_price"] = current_price
                    signal["profit_percent"] = abs(profit_pct)
                elif profit_pct >= 3.0:  # Stop loss
                    signal["outcome"] = "LOSS"
                    signal["exit_price"] = current_price
                    signal["profit_percent"] = -profit_pct
            
            # Volume/Cash flow signals (neutral, just track)
            else:
                # Auto-close after 24 hours
                if (datetime.now() - entry_time).total_seconds() > 86400:
                    signal["outcome"] = "WIN" if profit_pct > 0 else "LOSS"
                    signal["exit_price"] = current_price
                    signal["profit_percent"] = profit_pct
            
            if signal["outcome"]:
                signal["duration_hours"] = (datetime.now() - entry_time).total_seconds() / 3600
                updated += 1
        
        if updated > 0:
            self._save_history()
            self._recalculate_stats()
        
        return updated
    
    def _recalculate_stats(self):
        """Recalculate win rates and statistics"""
        stats = defaultdict(lambda: {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0
        })
        
        # Calculate for last 30, 60, 90 days
        for period_days in [30, 60, 90]:
            cutoff = datetime.now() - timedelta(days=period_days)
            
            for signal in self.signal_history["signals"]:
                if signal["outcome"] is None:
                    continue
                
                entry_time = datetime.fromisoformat(signal["entry_time"])
                if entry_time < cutoff:
                    continue
                
                signal_type = signal["type"]
                period_key = f"{signal_type}_{period_days}d"
                
                stats[period_key]["total_trades"] += 1
                
                if signal["outcome"] == "WIN":
                    stats[period_key]["wins"] += 1
                    stats[period_key]["avg_profit"] += signal.get("profit_percent", 0)
                else:
                    stats[period_key]["losses"] += 1
                    stats[period_key]["avg_loss"] += abs(signal.get("profit_percent", 0))
        
        # Calculate averages
        for key, data in stats.items():
            if data["total_trades"] > 0:
                data["win_rate"] = (data["wins"] / data["total_trades"]) * 100
                if data["wins"] > 0:
                    data["avg_profit"] /= data["wins"]
                if data["losses"] > 0:
                    data["avg_loss"] /= data["losses"]
        
        self.signal_history["stats"] = dict(stats)
        self._save_history()
    
    def get_signal_badge(self, signal_type, period_days=30):
        """
        Get win rate badge for a signal type
        
        Returns:
            str: HTML badge with win rate
        """
        key = f"{signal_type}_{period_days}d"
        stats = self.signal_history["stats"].get(key)
        
        if not stats or stats["total_trades"] < 5:
            return "🆕 NEW"
        
        win_rate = stats["win_rate"]
        total = stats["total_trades"]
        
        # Color based on win rate
        if win_rate >= 70:
            color = "#10b981"  # green
            emoji = "🔥"
        elif win_rate >= 60:
            color = "#3b82f6"  # blue
            emoji = "✅"
        elif win_rate >= 50:
            color = "#f59e0b"  # yellow
            emoji = "⚖️"
        else:
            color = "#ef4444"  # red
            emoji = "⚠️"
        
        badge = f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">'
        badge += f'{emoji} {win_rate:.0f}% ({total} trades)</span>'
        
        return badge
    
    def get_performance_report(self):
        """Generate performance report for all signals"""
        if not self.signal_history["stats"]:
            return "📊 No signal performance data yet. Keep tracking!"
        
        report = f"📈 <b>Signal Performance Report - {datetime.now().strftime('%Y-%m-%d')}</b>\n\n"
        
        # Group by signal type
        signal_types = set(k.rsplit('_', 1)[0] for k in self.signal_history["stats"].keys())
        
        for sig_type in sorted(signal_types):
            # Get 30-day stats
            key_30d = f"{sig_type}_30d"
            if key_30d in self.signal_history["stats"]:
                stats = self.signal_history["stats"][key_30d]
                
                if stats["total_trades"] >= 3:
                    display_name = sig_type.replace('_', ' ').title()
                    
                    report += f"<b>{display_name}</b>\n"
                    report += f"  Win Rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)\n"
                    report += f"  Avg Profit: +{stats['avg_profit']:.2f}% | Avg Loss: -{stats['avg_loss']:.2f}%\n"
                    report += f"  Total Trades: {stats['total_trades']} (30 days)\n\n"
        
        return report
