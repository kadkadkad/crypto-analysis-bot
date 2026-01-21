"""
RADAR ULTRA - System Health & Validation Module
================================================
Bu modül tüm verilerin doğruluğunu kontrol eder ve performans takibi yapar.

Amaç:
1. Veri doğruluğunu sürekli kontrol et
2. Sinyal performansını ölç
3. Sorunları otomatik tespit et
4. Yatırımcıyı koru

Kullanım:
    from system_validator import SystemValidator
    validator = SystemValidator()
    health_report = validator.full_audit()
"""

import json
import time
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class MetricValidation:
    """Tek bir metrik için doğrulama sonucu"""
    name: str
    our_value: float
    reference_value: float
    deviation_percent: float
    status: HealthStatus
    details: str = ""
    
@dataclass
class SignalPerformance:
    """Sinyal tipi performans özeti"""
    signal_type: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    expected_value: float
    risk_reward: float
    status: HealthStatus
    recommendation: str

@dataclass
class SystemHealthReport:
    """Tam sistem sağlık raporu"""
    timestamp: str
    overall_status: HealthStatus
    overall_score: float  # 0-100
    
    # Alt bölümler
    data_accuracy: Dict
    signal_performance: Dict
    api_health: Dict
    anomalies: List[str]
    recommendations: List[str]
    
    def to_dict(self):
        return asdict(self)

class SystemValidator:
    """
    Sistem doğrulama ve sağlık kontrolü ana sınıfı.
    """
    
    def __init__(self, signal_history_path: str = "signal_history.json"):
        self.signal_history_path = signal_history_path
        self.binance_base_url = "https://api.binance.com/api/v3"
        self.validation_results = []
        self.last_audit_time = None
        
    # ====================
    # 1. VERİ DOĞRULAMA
    # ====================
    
    def validate_price(self, symbol: str, our_price: float) -> MetricValidation:
        """Fiyat doğruluğunu Binance API ile karşılaştır"""
        try:
            url = f"{self.binance_base_url}/ticker/price?symbol={symbol}"
            response = requests.get(url, timeout=5)
            data = response.json()
            ref_price = float(data['price'])
            
            deviation = abs((our_price - ref_price) / ref_price * 100) if ref_price > 0 else 0
            
            if deviation < 0.5:
                status = HealthStatus.HEALTHY
            elif deviation < 2:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.CRITICAL
                
            return MetricValidation(
                name=f"{symbol} Price",
                our_value=our_price,
                reference_value=ref_price,
                deviation_percent=deviation,
                status=status,
                details=f"Fark: {deviation:.2f}%"
            )
        except Exception as e:
            return MetricValidation(
                name=f"{symbol} Price",
                our_value=our_price,
                reference_value=0,
                deviation_percent=0,
                status=HealthStatus.UNKNOWN,
                details=f"API hatası: {str(e)}"
            )
    
    def validate_rsi(self, symbol: str, our_rsi: float, interval: str = "1h", period: int = 14) -> MetricValidation:
        """RSI hesaplamasını bağımsız olarak doğrula"""
        try:
            # Kline verisi al
            url = f"{self.binance_base_url}/klines"
            params = {"symbol": symbol, "interval": interval, "limit": period + 50}
            response = requests.get(url, params=params, timeout=10)
            klines = response.json()
            
            closes = [float(k[4]) for k in klines]
            
            # RSI hesapla (Wilder's smoothing)
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[:period])
            avg_loss = np.mean(losses[:period])
            
            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                ref_rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                ref_rsi = 100 - (100 / (1 + rs))
            
            deviation = abs(our_rsi - ref_rsi)
            
            if deviation < 2:
                status = HealthStatus.HEALTHY
            elif deviation < 5:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.CRITICAL
                
            return MetricValidation(
                name=f"{symbol} RSI ({interval})",
                our_value=our_rsi,
                reference_value=ref_rsi,
                deviation_percent=deviation,
                status=status,
                details=f"Fark: {deviation:.1f} puan"
            )
        except Exception as e:
            return MetricValidation(
                name=f"{symbol} RSI ({interval})",
                our_value=our_rsi,
                reference_value=0,
                deviation_percent=0,
                status=HealthStatus.UNKNOWN,
                details=f"Hesaplama hatası: {str(e)}"
            )
    
    def validate_24h_change(self, symbol: str, our_change: float) -> MetricValidation:
        """24 saatlik değişim doğrulaması"""
        try:
            url = f"{self.binance_base_url}/ticker/24hr?symbol={symbol}"
            response = requests.get(url, timeout=5)
            data = response.json()
            ref_change = float(data['priceChangePercent'])
            
            deviation = abs(our_change - ref_change)
            
            if deviation < 0.5:
                status = HealthStatus.HEALTHY
            elif deviation < 2:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.CRITICAL
                
            return MetricValidation(
                name=f"{symbol} 24h Change",
                our_value=our_change,
                reference_value=ref_change,
                deviation_percent=deviation,
                status=status,
                details=f"Fark: {deviation:.2f}%"
            )
        except Exception as e:
            return MetricValidation(
                name=f"{symbol} 24h Change",
                our_value=our_change,
                reference_value=0,
                deviation_percent=0,
                status=HealthStatus.UNKNOWN,
                details=f"API hatası: {str(e)}"
            )
    
    def validate_volume_ratio(self, symbol: str, our_vol_ratio: float) -> MetricValidation:
        """Volume ratio mantıklılık kontrolü"""
        # Volume ratio genelde 0.1 - 10 arasında olmalı
        if our_vol_ratio <= 0:
            status = HealthStatus.CRITICAL
            details = "Volume ratio sıfır veya negatif!"
        elif our_vol_ratio > 20:
            status = HealthStatus.WARNING
            details = "Aşırı yüksek volume ratio - kontrol et"
        elif our_vol_ratio < 0.1:
            status = HealthStatus.WARNING
            details = "Çok düşük volume ratio"
        else:
            status = HealthStatus.HEALTHY
            details = "Normal aralıkta"
            
        return MetricValidation(
            name=f"{symbol} Volume Ratio",
            our_value=our_vol_ratio,
            reference_value=1.0,  # Beklenen ortalama
            deviation_percent=abs(our_vol_ratio - 1.0) * 100,
            status=status,
            details=details
        )
    
    # ====================
    # 2. SİNYAL PERFORMANSI
    # ====================
    
    def analyze_signal_performance(self) -> List[SignalPerformance]:
        """Tüm sinyal tiplerinin performansını analiz et"""
        try:
            with open(self.signal_history_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        
        stats = data.get('stats', {})
        performances = []
        
        # 30 günlük metrikleri analiz et
        for key, value in stats.items():
            if not key.endswith('_30d'):
                continue
                
            signal_type = key.replace('_30d', '')
            total = value.get('total_trades', 0)
            
            if total == 0:
                continue
            
            wins = value.get('wins', 0)
            losses = value.get('losses', 0)
            win_rate = value.get('win_rate', 0)
            avg_profit = value.get('avg_profit', 0)
            avg_loss = value.get('avg_loss', 0)
            
            # Beklenen değer hesapla
            expected_value = (win_rate/100 * avg_profit) - ((100-win_rate)/100 * avg_loss)
            
            # Risk/Reward
            risk_reward = avg_profit / avg_loss if avg_loss > 0 else 0
            
            # Status belirle
            if win_rate >= 55 and expected_value > 0.5:
                status = HealthStatus.HEALTHY
                recommendation = "✅ İyi performans - Kullanmaya devam"
            elif win_rate >= 45 and expected_value > 0:
                status = HealthStatus.WARNING
                recommendation = "⚠️ Orta performans - İzle ve optimize et"
            else:
                status = HealthStatus.CRITICAL
                recommendation = "❌ Düşük performans - Devre dışı bırak veya düzelt"
            
            performances.append(SignalPerformance(
                signal_type=signal_type,
                total_trades=total,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                avg_profit=avg_profit,
                avg_loss=avg_loss,
                expected_value=expected_value,
                risk_reward=risk_reward,
                status=status,
                recommendation=recommendation
            ))
        
        # Beklenen değere göre sırala
        performances.sort(key=lambda x: x.expected_value, reverse=True)
        return performances
    
    def get_problem_signals(self) -> List[str]:
        """Sorunlu sinyalleri listele"""
        performances = self.analyze_signal_performance()
        problems = []
        
        for p in performances:
            if p.status == HealthStatus.CRITICAL:
                problems.append(
                    f"🔴 {p.signal_type}: Win Rate {p.win_rate:.1f}%, "
                    f"EV: {p.expected_value:+.2f}%, {p.total_trades} işlem"
                )
        
        return problems
    
    def get_healthy_signals(self) -> List[str]:
        """Sağlıklı sinyalleri listele"""
        performances = self.analyze_signal_performance()
        healthy = []
        
        for p in performances:
            if p.status == HealthStatus.HEALTHY:
                healthy.append(
                    f"✅ {p.signal_type}: Win Rate {p.win_rate:.1f}%, "
                    f"EV: {p.expected_value:+.2f}%, R/R: {p.risk_reward:.2f}"
                )
        
        return healthy
    
    # ====================
    # 3. API SAĞLIK KONTROLÜ
    # ====================
    
    def check_binance_api(self) -> Dict:
        """Binance API sağlık kontrolü"""
        tests = {}
        
        # 1. Ping testi
        try:
            start = time.time()
            response = requests.get(f"{self.binance_base_url}/ping", timeout=5)
            latency = (time.time() - start) * 1000
            tests['ping'] = {
                'status': 'ok' if response.status_code == 200 else 'error',
                'latency_ms': round(latency, 2)
            }
        except Exception as e:
            tests['ping'] = {'status': 'error', 'error': str(e)}
        
        # 2. Server time testi
        try:
            response = requests.get(f"{self.binance_base_url}/time", timeout=5)
            server_time = response.json().get('serverTime', 0)
            local_time = int(time.time() * 1000)
            drift = abs(server_time - local_time)
            tests['time_sync'] = {
                'status': 'ok' if drift < 5000 else 'warning',
                'drift_ms': drift
            }
        except Exception as e:
            tests['time_sync'] = {'status': 'error', 'error': str(e)}
        
        # 3. Rate limit kontrolü
        try:
            response = requests.get(f"{self.binance_base_url}/exchangeInfo", timeout=10)
            tests['exchange_info'] = {
                'status': 'ok' if response.status_code == 200 else 'error',
                'symbols_count': len(response.json().get('symbols', []))
            }
        except Exception as e:
            tests['exchange_info'] = {'status': 'error', 'error': str(e)}
        
        return tests
    
    # ====================
    # 4. ANOMALİ TESPİTİ
    # ====================
    
    def detect_anomalies(self, results: List[Dict]) -> List[str]:
        """Veri anomalilerini tespit et"""
        anomalies = []
        
        if not results:
            anomalies.append("⚠️ Analiz sonucu yok!")
            return anomalies
        
        # 1. N/A değer kontrolü
        na_count = 0
        for coin in results:
            for key, value in coin.items():
                if value in ['N/A', None, '', 'nan']:
                    na_count += 1
        
        if na_count > 50:
            anomalies.append(f"🔴 Çok fazla N/A değer: {na_count} adet")
        elif na_count > 10:
            anomalies.append(f"⚠️ N/A değerler mevcut: {na_count} adet")
        
        # 2. Sıfır değer kontrolü
        zero_rsi = sum(1 for c in results if c.get('RSI', 50) == 0)
        if zero_rsi > 5:
            anomalies.append(f"🔴 {zero_rsi} coin için RSI = 0")
        
        # 3. Aşırı değer kontrolü
        extreme_rsi = sum(1 for c in results if c.get('RSI', 50) > 95 or c.get('RSI', 50) < 5)
        if extreme_rsi > 10:
            anomalies.append(f"⚠️ {extreme_rsi} coin için aşırı RSI değeri")
        
        # 4. Korelasyon kontrolü
        btc_corr_zero = sum(1 for c in results if c.get('BTC_Corr', 0) == 0)
        if btc_corr_zero > len(results) / 2:
            anomalies.append("🔴 Çoğu coin için BTC korelasyonu hesaplanamamış")
        
        # 5. Volume ratio kontrolü
        vol_zero = sum(1 for c in results if c.get('Volume Ratio', 1) == 0)
        if vol_zero > 5:
            anomalies.append(f"⚠️ {vol_zero} coin için Volume Ratio = 0")
        
        return anomalies
    
    # ====================
    # 5. TAM AUDIT
    # ====================
    
    def full_audit(self, results: List[Dict] = None, sample_coins: List[str] = None) -> SystemHealthReport:
        """
        Tam sistem denetimi yap.
        
        Args:
            results: Mevcut analiz sonuçları (opsiyonel)
            sample_coins: Test edilecek coin listesi (opsiyonel)
        """
        if sample_coins is None:
            sample_coins = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 1. Veri doğrulama
        data_validations = []
        for symbol in sample_coins:
            # Fiyat testi (örnek değerlerle, gerçek değerler results'tan alınmalı)
            if results:
                coin_data = next((c for c in results if c.get('Coin') == symbol), None)
                if coin_data:
                    our_price = float(str(coin_data.get('Price', 0)).replace('$', '').replace(',', ''))
                    data_validations.append(self.validate_price(symbol, our_price))
                    
                    our_rsi = float(coin_data.get('RSI', 50))
                    data_validations.append(self.validate_rsi(symbol, our_rsi))
        
        # 2. Sinyal performansı
        signal_perfs = self.analyze_signal_performance()
        problem_signals = self.get_problem_signals()
        healthy_signals = self.get_healthy_signals()
        
        # 3. API sağlığı
        api_health = self.check_binance_api()
        
        # 4. Anomali tespiti
        anomalies = self.detect_anomalies(results) if results else []
        
        # 5. Genel skor hesapla
        scores = []
        
        # Veri doğruluğu skoru
        if data_validations:
            healthy_count = sum(1 for v in data_validations if v.status == HealthStatus.HEALTHY)
            scores.append(healthy_count / len(data_validations) * 100)
        
        # Sinyal performans skoru
        if signal_perfs:
            healthy_signals_count = sum(1 for p in signal_perfs if p.status == HealthStatus.HEALTHY)
            scores.append(healthy_signals_count / len(signal_perfs) * 100)
        
        # API sağlık skoru
        api_ok = sum(1 for v in api_health.values() if v.get('status') == 'ok')
        scores.append(api_ok / len(api_health) * 100)
        
        # Anomali skoru (az anomali = yüksek skor)
        anomaly_score = max(0, 100 - len(anomalies) * 10)
        scores.append(anomaly_score)
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Genel durum
        if overall_score >= 80:
            overall_status = HealthStatus.HEALTHY
        elif overall_score >= 50:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.CRITICAL
        
        # Öneriler oluştur
        recommendations = []
        
        if problem_signals:
            recommendations.append("🔴 Düşük performanslı sinyalleri devre dışı bırak veya filtre ekle")
        
        if len(anomalies) > 0:
            recommendations.append("⚠️ Veri anomalilerini incele ve düzelt")
        
        if api_health.get('ping', {}).get('latency_ms', 0) > 500:
            recommendations.append("🌐 API latency yüksek - ağ bağlantısını kontrol et")
        
        if not healthy_signals:
            recommendations.append("📊 Hiç sağlıklı sinyal yok - stratejiyi gözden geçir")
        
        # Rapor oluştur
        # Convert validations to dict with status as string
        validations_dict = []
        for v in data_validations:
            d = asdict(v)
            d['status'] = v.status.value  # Convert enum to string
            validations_dict.append(d)
        
        # Convert performances to dict with status as string
        performances_dict = []
        for p in signal_perfs:
            d = asdict(p)
            d['status'] = p.status.value  # Convert enum to string
            performances_dict.append(d)
        
        report = SystemHealthReport(
            timestamp=timestamp,
            overall_status=overall_status,
            overall_score=overall_score,
            data_accuracy={
                'validations': validations_dict,
                'healthy_count': sum(1 for v in data_validations if v.status == HealthStatus.HEALTHY),
                'total_count': len(data_validations)
            },
            signal_performance={
                'performances': performances_dict,
                'healthy_signals': healthy_signals,
                'problem_signals': problem_signals,
                'total_signal_types': len(signal_perfs)
            },
            api_health=api_health,
            anomalies=anomalies,
            recommendations=recommendations
        )
        
        self.last_audit_time = timestamp
        return report
    
    def print_report(self, report: SystemHealthReport):
        """Raporu okunabilir formatta yazdır"""
        print("=" * 70)
        print("📊 SİSTEM SAĞLIK RAPORU")
        print("=" * 70)
        print(f"📅 Zaman: {report.timestamp}")
        print(f"📈 Genel Skor: {report.overall_score:.1f}/100")
        print(f"🚦 Durum: {report.overall_status.value.upper()}")
        print()
        
        # Veri Doğrulama
        print("-" * 70)
        print("1️⃣ VERİ DOĞRULUĞU")
        print("-" * 70)
        da = report.data_accuracy
        print(f"   Sağlıklı: {da['healthy_count']}/{da['total_count']}")
        for v in da.get('validations', []):
            status_icon = "✅" if v['status'] == 'healthy' else "⚠️" if v['status'] == 'warning' else "❌"
            print(f"   {status_icon} {v['name']}: {v['our_value']:.4f} vs {v['reference_value']:.4f} ({v['details']})")
        print()
        
        # Sinyal Performansı
        print("-" * 70)
        print("2️⃣ SİNYAL PERFORMANSI")
        print("-" * 70)
        sp = report.signal_performance
        print(f"   Toplam sinyal tipi: {sp['total_signal_types']}")
        print()
        
        if sp['healthy_signals']:
            print("   ✅ SAĞLIKLI SİNYALLER:")
            for s in sp['healthy_signals']:
                print(f"      {s}")
        print()
        
        if sp['problem_signals']:
            print("   ❌ SORUNLU SİNYALLER:")
            for s in sp['problem_signals']:
                print(f"      {s}")
        print()
        
        # API Sağlığı
        print("-" * 70)
        print("3️⃣ API SAĞLIĞI")
        print("-" * 70)
        for test, result in report.api_health.items():
            status_icon = "✅" if result.get('status') == 'ok' else "❌"
            print(f"   {status_icon} {test}: {result}")
        print()
        
        # Anomaliler
        if report.anomalies:
            print("-" * 70)
            print("4️⃣ ANOMALİLER")
            print("-" * 70)
            for a in report.anomalies:
                print(f"   {a}")
            print()
        
        # Öneriler
        if report.recommendations:
            print("-" * 70)
            print("5️⃣ ÖNERİLER")
            print("-" * 70)
            for r in report.recommendations:
                print(f"   {r}")
        
        print()
        print("=" * 70)


# ====================
# AUTO-PROTECTION SİSTEMİ
# ====================

class SignalProtector:
    """
    Düşük performanslı sinyalleri otomatik devre dışı bırakan koruma sistemi.
    """
    
    def __init__(self, validator: SystemValidator):
        self.validator = validator
        self.disabled_signals = set()
        self.signal_weights = {}
        
    def update_weights(self):
        """Sinyal ağırlıklarını performansa göre güncelle"""
        performances = self.validator.analyze_signal_performance()
        
        for p in performances:
            # Beklenen değere göre ağırlık
            if p.expected_value > 1.0:
                weight = 1.5  # Boost
            elif p.expected_value > 0:
                weight = 1.0  # Normal
            elif p.expected_value > -1.0:
                weight = 0.5  # Düşür
            else:
                weight = 0.0  # Devre dışı
                self.disabled_signals.add(p.signal_type)
            
            self.signal_weights[p.signal_type] = weight
        
        return self.signal_weights
    
    def should_allow_signal(self, signal_type: str, confidence: float = 50, market_regime: str = "neutral") -> Tuple[bool, float]:
        """
        Sinyal verilmeli mi kontrol et.
        
        Returns:
            (izin_ver, adjusted_confidence)
        """
        # Devre dışı sinyaller
        if signal_type in self.disabled_signals:
            return False, 0
        
        # Ağırlık uygula
        weight = self.signal_weights.get(signal_type, 1.0)
        adjusted_confidence = confidence * weight
        
        # Minimum eşik
        if adjusted_confidence < 30:
            return False, adjusted_confidence
        
        return True, adjusted_confidence
    
    def get_protection_status(self) -> Dict:
        """Koruma sisteminin durumunu döndür"""
        return {
            'disabled_signals': list(self.disabled_signals),
            'signal_weights': self.signal_weights,
            'protection_active': len(self.disabled_signals) > 0
        }


# ====================
# TEST
# ====================

if __name__ == "__main__":
    print("🔍 Sistem Doğrulama Modülü Test Ediliyor...\n")
    
    validator = SystemValidator()
    
    # Basit test
    report = validator.full_audit()
    validator.print_report(report)
    
    # Protection sistemi
    protector = SignalProtector(validator)
    weights = protector.update_weights()
    
    print("\n📊 SİNYAL AĞIRLIKLARI:")
    for sig, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        status = "✅" if weight > 0 else "❌"
        print(f"   {status} {sig}: {weight:.2f}")
    
    print("\n⛔ DEVRE DIŞI SİNYALLER:")
    for sig in protector.disabled_signals:
        print(f"   🚫 {sig}")
