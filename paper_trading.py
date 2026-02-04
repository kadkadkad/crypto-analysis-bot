"""
Paper Trading System - Ross Cameron Style Momentum Trading
Sanal portföy ile risk almadan strateji testi
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import requests

class PaperTradingPortfolio:
    """Paper trading portföy yönetimi"""
    
    def __init__(self, initial_capital: float = 5000):
        self.portfolio_file = "paper_portfolio.json"
        self.trades_file = "paper_trades.json"
        
        # İlk kez başlatılıyorsa yeni portföy oluştur
        if not os.path.exists(self.portfolio_file):
            self.portfolio = {
                "initial_capital": initial_capital,
                "current_capital": initial_capital,
                "positions": {},  # {symbol: {quantity, avg_price, entry_time}}
                "daily_pnl": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "scratch_trades": 0,
                "largest_win": 0,
                "largest_loss": 0,
                "current_streak": 0,
                "best_streak": 0,
                "daily_loss_count": 0,
                "created_at": datetime.now().isoformat()
            }
            self.save_portfolio()
        else:
            self.load_portfolio()
        
        # Trades history
        if not os.path.exists(self.trades_file):
            self.trades = []
            self.save_trades()
        else:
            self.load_trades()
    
    def load_portfolio(self):
        """Portföyü yükle"""
        with open(self.portfolio_file, 'r') as f:
            self.portfolio = json.load(f)
    
    def save_portfolio(self):
        """Portföyü kaydet"""
        with open(self.portfolio_file, 'w') as f:
            json.dump(self.portfolio, f, indent=2)
    
    def load_trades(self):
        """Trade geçmişini yükle"""
        with open(self.trades_file, 'r') as f:
            self.trades = json.load(f)
    
    def save_trades(self):
        """Trade geçmişini kaydet"""
        with open(self.trades_file, 'w') as f:
            json.dump(self.trades, f, indent=2)
    
    def get_current_price(self, symbol: str) -> float:
        """Binance'den güncel fiyat çek"""
        try:
            clean_symbol = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={clean_symbol}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return 0
    
    def open_position(self, symbol: str, entry_price: float, stop_loss: float, 
                     target: float, risk_percent: float = 2.0) -> Dict:
        """
        Yeni pozisyon aç (Ross Cameron risk management)
        
        Args:
            symbol: Coin adı (BTCUSDT)
            entry_price: Giriş fiyatı
            stop_loss: Stop-loss seviyesi
            target: Hedef fiyat
            risk_percent: Sermayenin yüzde kaçını risk et (default 2%)
        """
        # Risk kontrolü
        if self.portfolio['daily_loss_count'] >= 3:
            return {
                "success": False,
                "message": "⛔ GÜNLÜK ZARAR LİMİTİ! 3 kayıp trade sonrası bugün için stop."
            }
        
        # Risk/Reward hesapla
        risk_per_coin = abs(entry_price - stop_loss)
        reward_per_coin = abs(target - entry_price)
        rr_ratio = reward_per_coin / risk_per_coin if risk_per_coin > 0 else 0
        
        if rr_ratio < 2.0:
            return {
                "success": False,
                "message": f"❌ Risk/Reward ratio çok düşük: {rr_ratio:.2f} (Min: 2.0)"
            }
        
        # Pozisyon boyutu hesapla
        risk_amount = self.portfolio['current_capital'] * (risk_percent / 100)
        position_size = risk_amount / risk_per_coin
        position_value = position_size * entry_price
        
        # Sermaye yeterli mi?
        if position_value > self.portfolio['current_capital']:
            return {
                "success": False,
                "message": f"❌ Yetersiz sermaye. Gerekli: ${position_value:.2f}"
            }
        
        # Pozisyon aç
        self.portfolio['positions'][symbol] = {
            "quantity": position_size,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "risk_amount": risk_amount,
            "rr_ratio": rr_ratio,
            "entry_time": datetime.now().isoformat()
        }
        
        self.portfolio['current_capital'] -= position_value
        self.save_portfolio()
        
        return {
            "success": True,
            "message": f"✅ Pozisyon açıldı: {symbol}",
            "position_size": position_size,
            "position_value": position_value,
            "risk_amount": risk_amount,
            "rr_ratio": rr_ratio,
            "details": self.portfolio['positions'][symbol]
        }
    
    def close_position(self, symbol: str, exit_price: Optional[float] = None, 
                      reason: str = "Manual") -> Dict:
        """Pozisyon kapat"""
        if symbol not in self.portfolio['positions']:
            return {"success": False, "message": f"❌ Açık pozisyon yok: {symbol}"}
        
        pos = self.portfolio['positions'][symbol]
        
        # Çıkış fiyatını al
        if exit_price is None:
            exit_price = self.get_current_price(symbol)
            if exit_price == 0:
                return {"success": False, "message": "❌ Fiyat alınamadı"}
        
        # P&L hesapla
        quantity = pos['quantity']
        entry_value = quantity * pos['entry_price']
        exit_value = quantity * exit_price
        pnl = exit_value - entry_value
        pnl_percent = (pnl / entry_value) * 100
        
        # R multiple hesapla (kaç R kazandık/kaybettik)
        r_value = pnl / pos['risk_amount']
        
        # Portföyü güncelle
        self.portfolio['current_capital'] += exit_value
        self.portfolio['total_pnl'] += pnl
        self.portfolio['daily_pnl'] += pnl
        self.portfolio['total_trades'] += 1
        
        # Win/Loss kategorize et
        trade_type = "SCRATCH"
        if pnl > pos['risk_amount'] * 0.1:  # %10'dan fazla kazanç
            trade_type = "WIN"
            self.portfolio['winning_trades'] += 1
            self.portfolio['current_streak'] += 1
            self.portfolio['daily_loss_count'] = 0  # Reset loss counter
            if pnl > self.portfolio['largest_win']:
                self.portfolio['largest_win'] = pnl
        elif pnl < -pos['risk_amount'] * 0.1:  # %10'dan fazla kayıp
            trade_type = "LOSS"
            self.portfolio['losing_trades'] += 1
            self.portfolio['current_streak'] = 0
            self.portfolio['daily_loss_count'] += 1
            if abs(pnl) > abs(self.portfolio['largest_loss']):
                self.portfolio['largest_loss'] = pnl
        else:
            trade_type = "SCRATCH"
            self.portfolio['scratch_trades'] += 1
        
        # Best streak update
        if self.portfolio['current_streak'] > self.portfolio['best_streak']:
            self.portfolio['best_streak'] = self.portfolio['current_streak']
        
        # Trade'i kaydet
        trade_record = {
            "id": len(self.trades) + 1,
            "symbol": symbol,
            "type": trade_type,
            "entry_price": pos['entry_price'],
            "exit_price": exit_price,
            "quantity": quantity,
            "entry_time": pos['entry_time'],
            "exit_time": datetime.now().isoformat(),
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "r_value": r_value,
            "reason": reason,
            "stop_loss": pos['stop_loss'],
            "target": pos['target'],
            "rr_ratio": pos['rr_ratio']
        }
        
        self.trades.append(trade_record)
        
        # Pozisyonu sil
        del self.portfolio['positions'][symbol]
        
        self.save_portfolio()
        self.save_trades()
        
        return {
            "success": True,
            "trade_type": trade_type,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "r_value": r_value,
            "current_capital": self.portfolio['current_capital'],
            "total_pnl": self.portfolio['total_pnl'],
            "details": trade_record
        }
    
    def check_stop_loss_target(self) -> List[Dict]:
        """Açık pozisyonlarda stop-loss veya target kontrolü"""
        alerts = []
        
        for symbol, pos in list(self.portfolio['positions'].items()):
            current_price = self.get_current_price(symbol)
            if current_price == 0:
                continue
            
            # Stop-loss hit
            if current_price <= pos['stop_loss']:
                result = self.close_position(symbol, current_price, "Stop-Loss Hit")
                alerts.append({
                    "symbol": symbol,
                    "type": "STOP_LOSS",
                    "message": f"🛑 Stop-loss hit: {symbol} @ ${current_price:.6f}",
                    "pnl": result.get('pnl', 0)
                })
            
            # Target hit
            elif current_price >= pos['target']:
                result = self.close_position(symbol, current_price, "Target Hit")
                alerts.append({
                    "symbol": symbol,
                    "type": "TARGET",
                    "message": f"🎯 Target hit: {symbol} @ ${current_price:.6f}",
                    "pnl": result.get('pnl', 0)
                })
        
        return alerts
    
    def get_statistics(self) -> Dict:
        """Detaylı istatistikler"""
        total_trades = self.portfolio['total_trades']
        
        if total_trades == 0:
            return {
                "message": "Henüz trade yapılmamış",
                "current_capital": self.portfolio['current_capital'],
                "initial_capital": self.portfolio['initial_capital']
            }
        
        win_rate = (self.portfolio['winning_trades'] / total_trades) * 100
        
        # Ortalama kazanç/kayıp hesapla
        winning_trades = [t for t in self.trades if t['type'] == 'WIN']
        losing_trades = [t for t in self.trades if t['type'] == 'LOSS']
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        roi = ((self.portfolio['current_capital'] - self.portfolio['initial_capital']) / 
               self.portfolio['initial_capital']) * 100
        
        return {
            "current_capital": self.portfolio['current_capital'],
            "initial_capital": self.portfolio['initial_capital'],
            "total_pnl": self.portfolio['total_pnl'],
            "roi_percent": roi,
            "total_trades": total_trades,
            "winning_trades": self.portfolio['winning_trades'],
            "losing_trades": self.portfolio['losing_trades'],
            "scratch_trades": self.portfolio['scratch_trades'],
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "largest_win": self.portfolio['largest_win'],
            "largest_loss": self.portfolio['largest_loss'],
            "current_streak": self.portfolio['current_streak'],
            "best_streak": self.portfolio['best_streak'],
            "open_positions": len(self.portfolio['positions']),
            "daily_pnl": self.portfolio['daily_pnl'],
            "daily_loss_count": self.portfolio['daily_loss_count']
        }
    
    def reset_portfolio(self, new_capital: float = 5000):
        """Portföyü sıfırla (yeni başlangıç)"""
        self.portfolio = {
            "initial_capital": new_capital,
            "current_capital": new_capital,
            "positions": {},
            "daily_pnl": 0,
            "total_pnl": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "scratch_trades": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "current_streak": 0,
            "best_streak": 0,
            "daily_loss_count": 0,
            "created_at": datetime.now().isoformat()
        }
        self.trades = []
        self.save_portfolio()
        self.save_trades()
        return {"success": True, "message": f"✅ Portföy sıfırlandı. Yeni sermaye: ${new_capital}"}


# Global instance
PAPER_PORTFOLIO = PaperTradingPortfolio()

def get_paper_trading_stats():
    """Dashboard için stats"""
    return PAPER_PORTFOLIO.get_statistics()

def open_paper_trade(symbol, entry, stop, target, risk_pct=2.0):
    """Yeni paper trade aç"""
    return PAPER_PORTFOLIO.open_position(symbol, entry, stop, target, risk_pct)

def close_paper_trade(symbol, exit_price=None, reason="Manual"):
    """Paper trade kapat"""
    return PAPER_PORTFOLIO.close_position(symbol, exit_price, reason)

def check_paper_alerts():
    """Stop-loss/target kontrolü"""
    return PAPER_PORTFOLIO.check_stop_loss_target()
