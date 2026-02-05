"""
AlphaBot - Autonomous Self-Learning Trading Bot
Ross Cameron stratejisini uygular, kendi trade'lerini yapar ve hatalarından öğrenir
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from paper_trading import PAPER_PORTFOLIO
import os

class AlphaBot:
    """Otonom trading bot - kendisi trade yapar ve öğrenir"""
    
    def __init__(self):
        self.learning_file = "alpha_bot_learning.json"
        self.decisions_file = "alpha_bot_decisions.json"
        self.base_url = "http://localhost:8050"
        self.auth = ("admin", "Admin123!")
        
        # Learning database
        if os.path.exists(self.learning_file):
            with open(self.learning_file, 'r') as f:
                self.learning = json.load(f)
        else:
            self.learning = {
                "total_scans": 0,
                "coins_analyzed": {},  # {symbol: {wins, losses, avg_profit, patterns}}
                "winning_patterns": [],  # Success stories
                "losing_patterns": [],   # Lessons learned
                "strategy_adjustments": [],
                "performance_metrics": {
                    "best_time_of_day": None,
                    "best_volume_range": None,
                    "best_rr_ratio": 2.0,
                    "optimal_risk_percent": 0.5
                }
            }
        
        # Current decisions log
        self.decisions = []
        if os.path.exists(self.decisions_file):
            with open(self.decisions_file, 'r') as f:
                self.decisions = json.load(f)
    
    def save_learning(self):
        """Öğrenilenleri kaydet"""
        with open(self.learning_file, 'w') as f:
            json.dump(self.learning, f, indent=2)
    
    def save_decisions(self):
        """Kararları kaydet"""
        with open(self.decisions_file, 'w') as f:
            json.dump(self.decisions, f, indent=2)
    
    def log_decision(self, decision_type: str, details: Dict):
        """Her kararı logla"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": decision_type,
            "details": details
        }
        self.decisions.append(entry)
        self.save_decisions()
        print(f"📝 [DECISION] {decision_type}: {details.get('message', 'No message')}")
    
    def get_dashboard_data(self) -> Optional[Dict]:
        """Dashboard'dan coin listesi al"""
        try:
            response = requests.get(f"{self.base_url}/api/data", auth=self.auth, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Dashboard data fetch failed: {e}")
        return None
    
    def check_setup(self, coin: Dict) -> Tuple[bool, str, List[str], Dict]:
        """
        Coin için uygun setup (LONG veya SHORT) kontrol et
        Returns: (passed, direction, reasons, scores)
        """
        symbol = coin.get('Coin', '').replace('USDT', '')
        reasons = []
        scores = {}
        
        # Temel verileri al
        try:
            smart_score = float(coin.get('Smart Score', 0))
            change_24h = float(str(coin.get('24h Change', '0')).replace('%', ''))
            price = float(str(coin.get('Price', '0')).replace('$', '').replace(',', ''))
            
            scores['smart_score'] = smart_score
            scores['change_24h'] = change_24h
            scores['price'] = price
        except:
            return False, 'NONE', ["❌ Data parse error"], {}

        # Fiyat filtrelemesi (Penny stock & aşırı pahalıları ele)
        if price < 0.10 or price > 1000:
            return False, 'NONE', [f"❌ Price logic: ${price}"], scores

        # --- STRATEJİ 1: LONG (Momentum / Gap Up) ---
        if change_24h >= 5:  # %5+ Yükseliş
            if smart_score >= 60:
                reasons.append(f"✅ [LONG] Strong Momentum: +{change_24h}%")
                reasons.append(f"✅ [LONG] Smart Score: {smart_score}")
                return True, 'LONG', reasons, scores
            else:
                reasons.append(f"⚠️ [LONG] Düşük Score: {smart_score}")

        # --- STRATEJİ 2: SHORT (Breakdown / Crash) ---
        elif change_24h <= -4:  # %4+ Düşüş (Momentum Breakdown)
            if smart_score <= 45:
                reasons.append(f"✅ [SHORT] Breakdown Detected: {change_24h}%")
                reasons.append(f"✅ [SHORT] Weak Score: {smart_score}")
                return True, 'SHORT', reasons, scores
            else:
                reasons.append(f"⚠️ [SHORT] Score hala yüksek: {smart_score}")
        
        reasons.append(f"❌ No valid setup detected (Change: {change_24h}%)")
        return False, 'NONE', reasons, scores
    
    def calculate_entry_stop_target(self, coin: Dict, direction: str) -> Optional[Dict]:
        """
        Entry/Stop/Target - Yön bazlı hesaplama
        """
        try:
            price = float(str(coin.get('Price', '0')).replace('$', '').replace(',', ''))
            
            if direction == 'LONG':
                # Entry: Current + 0.5%
                entry = price * 1.005
                # Stop: 2.5% below entry
                stop = entry * 0.975
                # Target: 5% above entry (2:1 R/R)
                target = entry * 1.05
            
            else: # SHORT
                # Entry: Current - 0.5% (düşüş onayı)
                entry = price * 0.995 
                # Stop: 2.5% ABOVE entry
                stop = entry * 1.025
                # Target: 5% BELOW entry
                target = entry * 0.95
            
            risk = abs(entry - stop)
            reward = abs(target - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            return {
                "entry": round(entry, 6),
                "stop": round(stop, 6),
                "target": round(target, 6),
                "risk_per_coin": round(risk, 6),
                "reward_per_coin": round(reward, 6),
                "rr_ratio": round(rr_ratio, 2)
            }
        except Exception as e:
            print(f"❌ Price calculation failed: {e}")
            return None
    
    def scan_and_select_coin(self) -> Optional[Dict]:
        """
        Market tara ve en iyi LONG/SHORT fırsatını seç
        """
        print("\n" + "="*80)
        print("🔍 MARKET SCAN BAŞLIYOR (LONG & SHORT)")
        print("="*80)
        
        self.learning['total_scans'] += 1
        self.save_learning()
        
        data = self.get_dashboard_data()
        if not data or 'coins' not in data:
            self.log_decision("SCAN_FAILED", {"message": "Dashboard data unavailable"})
            return None
        
        coins = data['coins']
        print(f"📊 {len(coins)} coin taranıyor...")
        
        candidates = []
        
        for coin in coins:
            symbol = coin.get('Coin', '')
            # Yeni check fonksiyonu
            passed, direction, reasons, scores = self.check_setup(coin)
            
            if passed:
                levels = self.calculate_entry_stop_target(coin, direction)
                if levels and levels['rr_ratio'] >= 1.5:
                    candidates.append({
                        "coin": coin,
                        "symbol": symbol,
                        "type": direction,
                        "scores": scores,
                        "levels": levels,
                        "reasons": reasons
                    })
                    print(f"\n✅ {direction} ADAYI: {symbol}")
                    for reason in reasons:
                        print(f"   {reason}")
                    print(f"   📈 R/R Ratio: {levels['rr_ratio']}")
        
        if not candidates:
            self.log_decision("NO_SETUP", {
                "message": "Uygun LONG/SHORT setup bulunamadı",
                "coins_scanned": len(coins)
            })
            print("\n❌ Setup yok. Bekleme modu...")
            return None
        
        # En iyi adayı seç (Puanlama: Smart score gücü ve R/R)
        # Not: Short için düşük smart score iyidir, o yüzden ters orantı
        def score_candidate(c):
            base_score = c['scores']['smart_score']
            if c['type'] == 'SHORT':
                base_score = 100 - base_score # Short için düşük puan yüksek skor demek
            
            return (base_score * 0.6) + (c['levels']['rr_ratio'] * 40)

        best = max(candidates, key=score_candidate)
        
        print(f"\n🎯 SEÇİLEN ADAY: {best['symbol']} ({best['type']})")
        print(f"   Score: {best['scores']['smart_score']}")
        print(f"   Change: {best['scores']['change_24h']}%")
        
        self.log_decision("COIN_SELECTED", {
            "symbol": best['symbol'],
            "type": best['type'],
            "smart_score": best['scores']['smart_score'],
            "rr_ratio": best['levels']['rr_ratio']
        })
        
        return best
    
    def execute_trade(self, selection: Dict) -> bool:
        """Trade'i aç"""
        symbol = selection['symbol']
        levels = selection['levels']
        
        print(f"\n🚀 TRADE AÇILIYOR: {symbol}")
        print(f"   Entry: ${levels['entry']}")
        print(f"   Stop: ${levels['stop']}")
        print(f"   Target: ${levels['target']}")
        print(f"   R/R: {levels['rr_ratio']}")
        
        # Optimal risk % hesapla (learning'den)
        risk_percent = self.learning['performance_metrics']['optimal_risk_percent']
        
        try:
            # Paper trading API call
            result = PAPER_PORTFOLIO.open_position(
                symbol=symbol,
                entry_price=levels['entry'],
                stop_loss=levels['stop'],
                target=levels['target'],
                risk_percent=risk_percent
            )
            
            if result['success']:
                print(f"✅ TRADE AÇILDI!")
                print(f"   Position size: {result['position_size']}")
                print(f"   Risk amount: ${result['risk_amount']}")
                
                self.log_decision("TRADE_OPENED", {
                    "symbol": symbol,
                    "entry": levels['entry'],
                    "stop": levels['stop'],
                    "target": levels['target'],
                    "position_size": result['position_size'],
                    "risk_amount": result['risk_amount'],
                    "rr_ratio": levels['rr_ratio']
                })
                return True
            else:
                print(f"❌ TRADE BAŞARISIZ: {result['message']}")
                self.log_decision("TRADE_REJECTED", {
                    "symbol": symbol,
                    "reason": result['message']
                })
                return False
                
        except Exception as e:
            print(f"❌ TRADE ERROR: {e}")
            self.log_decision("TRADE_ERROR", {"symbol": symbol, "error": str(e)})
            return False
    
    def analyze_closed_trade(self, trade_result: Dict):
        """Kapatılan trade'i analiz et ve öğren"""
        symbol = trade_result['details']['symbol']
        trade_type = trade_result['trade_type']
        pnl = trade_result['pnl']
        r_value = trade_result['r_value']
        
        print(f"\n📊 TRADE ANALİZ EDİLİYOR: {symbol}")
        print(f"   Sonuç: {trade_type}")
        print(f"   P&L: ${pnl:.2f}")
        print(f"   R Multiple: {r_value:.2f}R")
        
        # Coin istatistiklerini güncelle
        if symbol not in self.learning['coins_analyzed']:
            self.learning['coins_analyzed'][symbol] = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0,
                "avg_r_multiple": 0
            }
        
        coin_stats = self.learning['coins_analyzed'][symbol]
        coin_stats['total_trades'] += 1
        coin_stats['total_pnl'] += pnl
        
        if trade_type == 'WIN':
            coin_stats['wins'] += 1
            
            # Winning pattern kaydet
            pattern = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "r_multiple": r_value,
                "pnl": pnl,
                "lesson": f"{symbol} kazandırdı: {r_value:.2f}R - Bu coin güvenilir"
            }
            self.learning['winning_patterns'].append(pattern)
            self.learning['winning_patterns'] = self.learning['winning_patterns'][-50:]  # Son 50
            
            print(f"✅ KAZANAN PATTERN KAYDEDİLDİ")
            
        elif trade_type == 'LOSS':
            coin_stats['losses'] += 1
            
            # Losing pattern analiz et
            loss_reason = self.diagnose_loss(trade_result)
            pattern = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "r_multiple": r_value,
                "pnl": pnl,
                "reason": loss_reason,
                "lesson": f"{symbol} kaybettirdi: {loss_reason} - Gelecekte dikkat!"
            }
            self.learning['losing_patterns'].append(pattern)
            self.learning['losing_patterns'] = self.learning['losing_patterns'][-50:]
            
            print(f"❌ KAYIP ANALİZ EDİLDİ")
            print(f"   Neden: {loss_reason}")
            print(f"   Ders: {pattern['lesson']}")
        
        # Avg R multiple güncelle
        total_r = sum(
            t.get('r_value', 0) 
            for t in PAPER_PORTFOLIO.trades 
            if t['symbol'] == symbol
        )
        coin_stats['avg_r_multiple'] = total_r / coin_stats['total_trades']
        
        # Strategy adjustment öner
        self.suggest_strategy_adjustment()
        
        self.save_learning()
    
    def diagnose_loss(self, trade_result: Dict) -> str:
        """Kaybın nedenini teşhis et"""
        details = trade_result['details']
        entry = details['entry_price']
        exit_price = details['exit_price']
        stop = details['stop_loss']
        
        # Stop-loss hit mi?
        if abs(exit_price - stop) < (entry * 0.01):  # %1 tolerance
            return "Stop-loss hit - Volatilite fazla veya entry zamanlaması erken"
        
        # Ters yön mü?
        if exit_price < entry:
            return "Ters trend - Pattern bozuldu veya fake breakout"
        
        return "Belirsiz - Daha fazla data gerekli"
    
    def suggest_strategy_adjustment(self):
        """Strateji iyileştirmesi öner"""
        stats = PAPER_PORTFOLIO.get_statistics()
        
        if stats.get('total_trades', 0) < 10:
            return  # Yeterli data yok
        
        win_rate = stats.get('win_rate', 0)
        avg_win = stats.get('avg_win', 0)
        avg_loss = abs(stats.get('avg_loss', 0))
        
        adjustments = []
        
        # Win rate düşükse
        if win_rate < 55:
            adjustments.append({
                "type": "SELECTIVITY",
                "message": "Win rate düşük (%{:.1f}). Daha seçici ol - sadece perfect setup al!".format(win_rate),
                "action": "Min Smart Score'u 70'e çıkar"
            })
            # Min smart score artır
            # (Bu bir örnek - gerçekte kriterleri güncelleyebiliriz)
        
        # Avg loss > avg win ise
        if avg_loss > avg_win * 0.8:
            adjustments.append({
                "type": "RISK_MANAGEMENT",
                "message": "Kayıplar kazançlara yakın. Stop-loss'ları sıkılaştır!",
                "action": "Stop distance'ı %2.5'ten %2'ye düşür"
            })
        
        # R/R ratio iyileştirmesi
        if len(adjustments) == 0 and win_rate > 65:
            current_rr = self.learning['performance_metrics']['best_rr_ratio']
            new_rr = min(current_rr + 0.2, 3.0)
            adjustments.append({
                "type": "OPTIMIZATION",
                "message": f"Win rate iyi ({win_rate:.1f}%)! R/R ratio'yu artırabiliriz",
                "action": f"Min R/R: {current_rr} → {new_rr}"
            })
            self.learning['performance_metrics']['best_rr_ratio'] = new_rr
        
        if adjustments:
            print(f"\n💡 STRATEJİ İYİLEŞTİRME ÖNERİLERİ:")
            for adj in adjustments:
                print(f"   {adj['type']}: {adj['message']}")
                print(f"   → {adj['action']}")
                self.learning['strategy_adjustments'].append({
                    "timestamp": datetime.now().isoformat(),
                    **adj
                })
            self.save_learning()
    
    def monitor_positions(self):
        """Açık pozisyonları izle ve analiz et"""
        alerts = PAPER_PORTFOLIO.check_stop_loss_target()
        
        if alerts:
            print(f"\n🔔 {len(alerts)} ALERT!")
            for alert in alerts:
                print(f"   {alert['message']}")
                
                # Trade kapatıldı, analiz et
                symbol = alert['symbol']
                # Get trade result from portfolio
                last_trade = next(
                    (t for t in reversed(PAPER_PORTFOLIO.trades) if t['symbol'] == symbol),
                    None
                )
                
                if last_trade:
                    # Simulate trade_result format
                    trade_result = {
                        "trade_type": alert['type'].replace('STOP_LOSS', 'LOSS').replace('TARGET', 'WIN'),
                        "pnl": alert['pnl'],
                        "r_value": alert['pnl'] / 25,  # Approximate
                        "details": last_trade
                    }
                    self.analyze_closed_trade(trade_result)
    
    def run_cycle(self):
        """Bir trading döngüsü çalıştır"""
        print(f"\n{'='*80}")
        print(f"🤖 ALPHABOT DÖNGÜSÜ - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*80}")
        
        # 1. Açık poziSyonları kontrol et
        self.monitor_positions()
        
        # 2. Yeni pozisyon açılabilir mi?
        stats = PAPER_PORTFOLIO.get_statistics()
        open_positions = stats.get('open_positions', 0)
        daily_loss_count = PAPER_PORTFOLIO.portfolio.get('daily_loss_count', 0)
        
        if daily_loss_count >= 3:
            print("🛑 Günlük loss limit (3) - Bugün için duruyoruz")
            self.log_decision("DAILY_LIMIT", {"message": "3 loss hit - waiting for next day"})
            return
        
        if open_positions >= 2:
            print("⏸️ 2 açık pozisyon var - yeni trade bekleniyor")
            return
        
        # 3. Market scan ve coin seç
        selection = self.scan_and_select_coin()
        
        # 4. Trade aç
        if selection:
            self.execute_trade(selection)
    
    def print_learning_summary(self):
        """Öğrenilenleri özetle"""
        print(f"\n{'='*80}")
        print("🧠 ALPHABOT ÖĞRENME ÖZETİ")
        print(f"{'='*80}")
        
        print(f"\n📊 GENEL İSTATİSTİKLER:")
        print(f"   Total scans: {self.learning['total_scans']}")
        print(f"   Coins analyzed: {len(self.learning['coins_analyzed'])}")
        print(f"   Winning patterns: {len(self.learning['winning_patterns'])}")
        print(f"   Losing patterns: {len(self.learning['losing_patterns'])}")
        
        print(f"\n🎯 EN İYİ COINLER:")
        sorted_coins = sorted(
            self.learning['coins_analyzed'].items(),
            key=lambda x: x[1].get('avg_r_multiple', 0),
            reverse=True
        )[:5]
        
        for symbol, stats in sorted_coins:
            wr = (stats['wins'] / stats['total_trades'] * 100) if stats['total_trades'] > 0 else 0
            print(f"   {symbol}: {stats['wins']}W/{stats['losses']}L ({wr:.1f}%) - Avg R: {stats['avg_r_multiple']:.2f}")
        
        print(f"\n💡 SON DERSLER:")
        for pattern in self.learning['losing_patterns'][-3:]:
            print(f"   {pattern['timestamp'][:10]}: {pattern['lesson']}")


# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                     🤖 ALPHABOT v1.0                                   ║
    ║              Autonomous Self-Learning Trading Bot                      ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)
    
    bot = AlphaBot()
    
    print("\n🎯 AlphaBot başlatılıyor...")
    print("   ✅ Paper trading entegrasyonu")
    print("   ✅ Ross Cameron 5 kriterleri")
    print("   ✅ Otonom karar mekanizması")
    print("   ✅ Self-learning sistemi")
    
    # Single cycle for testing
    bot.run_cycle()
    
    # Print learning
    bot.print_learning_summary()
    
    print(f"\n{'='*80}")
    print("✅ Döngü tamamlandı!")
    print("💡 Sürekli çalıştırmak için: while true; do python3 alpha_bot.py; sleep 300; done")
    print(f"{'='*80}")
