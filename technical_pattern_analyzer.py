#28martpattern
#pattern
#tp
# Technical Pattern Analysis Module
# Implements confirmation patterns, breakers, mitigations, and SFP detection

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Arrow
from datetime import datetime


class TechnicalPatternAnalyzer:
    def __init__(self):
        """Initialize the Technical Pattern Analyzer with default settings"""
        self.patterns = {
            "bullish_mitigation": [],
            "bearish_breaker": [],
            "bullish_sfp": [],
            "bearish_sfp": []
        }
        self.levels = {
            "support": [],
            "resistance": []
        }

    def detect_order_blocks(self, df):
        """
        Order Blocks tespit eder - Smart Money Price Action'ın temel bileşeni

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen order blocklar
        """
        # Order block analizini saklamak için veri yapısı
        order_blocks = {
            "bullish_ob": [],  # Alım baskısı olan OB'ler
            "bearish_ob": [],  # Satış baskısı olan OB'ler
            "bul_mitigation_ob": [],  # Mitigation (boşluk doldurma) OB'leri
            "bear_mitigation_ob": []  # Mitigation (boşluk doldurma) OB'leri
        }

        # En az 10 mum olduğunu kontrol et
        if len(df) < 10:
            return order_blocks

        # Bullish Order Block (Düşüş trendi sonrasında görülen ilk yeşil/yükseliş mumu)
        for i in range(3, len(df) - 3):
            # Düşüş trendi kontrolü: önceki 3 mumun en az 2'si kırmızı
            down_trend = sum(1 for j in range(i - 3, i) if df['close'].iloc[j] < df['open'].iloc[j]) >= 2

            # Şimdiki mum yeşil ve sonraki mumlar yükseliyor mu
            current_green = df['close'].iloc[i] > df['open'].iloc[i]
            next_bullish = df['close'].iloc[i + 1] > df['close'].iloc[i] and df['close'].iloc[i + 2] > df['close'].iloc[
                i]

            # Bullish OB koşulları
            if down_trend and current_green and next_bullish:
                # Yüksek hacim kontrol et (ortalama hacmin 1.5 katından büyük)
                avg_volume = df['volume'].iloc[i - 5:i].mean()
                high_volume = df['volume'].iloc[i] > avg_volume * 1.5

                # Order block sınırları
                ob_high = df['high'].iloc[i]
                ob_low = df['low'].iloc[i]
                ob_volume = df['volume'].iloc[i]

                # Confidence score hesapla
                confidence = 0.7
                if high_volume:
                    confidence += 0.1
                if next_bullish and df['close'].iloc[i + 2] > df['high'].iloc[i]:
                    confidence += 0.1

                order_blocks["bullish_ob"].append({
                    "idx": i,
                    "high": ob_high,
                    "low": ob_low,
                    "mid": (ob_high + ob_low) / 2,
                    "volume": ob_volume,
                    "confidence": confidence
                })

        # Bearish Order Block (Yükseliş trendi sonrasında görülen ilk kırmızı/düşüş mumu)
        for i in range(3, len(df) - 3):
            # Yükseliş trendi kontrolü: önceki 3 mumun en az 2'si yeşil
            up_trend = sum(1 for j in range(i - 3, i) if df['close'].iloc[j] > df['open'].iloc[j]) >= 2

            # Şimdiki mum kırmızı ve sonraki mumlar düşüyor mu
            current_red = df['close'].iloc[i] < df['open'].iloc[i]
            next_bearish = df['close'].iloc[i + 1] < df['close'].iloc[i] and df['close'].iloc[i + 2] < df['close'].iloc[
                i]

            # Bearish OB koşulları
            if up_trend and current_red and next_bearish:
                # Yüksek hacim kontrol et (ortalama hacmin 1.5 katından büyük)
                avg_volume = df['volume'].iloc[i - 5:i].mean()
                high_volume = df['volume'].iloc[i] > avg_volume * 1.5

                # Order block sınırları
                ob_high = df['high'].iloc[i]
                ob_low = df['low'].iloc[i]
                ob_volume = df['volume'].iloc[i]

                # Confidence score hesapla
                confidence = 0.7
                if high_volume:
                    confidence += 0.1
                if next_bearish and df['close'].iloc[i + 2] < df['low'].iloc[i]:
                    confidence += 0.1

                order_blocks["bearish_ob"].append({
                    "idx": i,
                    "high": ob_high,
                    "low": ob_low,
                    "mid": (ob_high + ob_low) / 2,
                    "volume": ob_volume,
                    "confidence": confidence
                })

        # Mitigation Order Blocks (Dikkat edilecek boşluk doldurma noktaları)
        # Smart Money teorisine göre, fiyat daha önce belirli bir OB bölgesini test etmek için geri dönebilir

        # Bullish Mitigation OB
        for ob in order_blocks["bullish_ob"]:
            idx = ob["idx"]
            ob_mid = ob["mid"]

            # Fiyat daha sonra bu bölgeye dönüp test etti mi?
            for i in range(idx + 5, min(len(df), idx + 30)):
                if df['low'].iloc[i] <= ob_mid <= df['high'].iloc[i]:
                    # Dönüş sinyali var mı?
                    if i + 1 < len(df) and df['close'].iloc[i + 1] > df['open'].iloc[i + 1]:
                        order_blocks["bul_mitigation_ob"].append({
                            "original_idx": idx,
                            "mitigation_idx": i,
                            "level": ob_mid,
                            "confidence": 0.85
                        })
                        break

        # Bearish Mitigation OB
        for ob in order_blocks["bearish_ob"]:
            idx = ob["idx"]
            ob_mid = ob["mid"]

            # Fiyat daha sonra bu bölgeye dönüp test etti mi?
            for i in range(idx + 5, min(len(df), idx + 30)):
                if df['low'].iloc[i] <= ob_mid <= df['high'].iloc[i]:
                    # Dönüş sinyali var mı?
                    if i + 1 < len(df) and df['close'].iloc[i + 1] < df['open'].iloc[i + 1]:
                        order_blocks["bear_mitigation_ob"].append({
                            "original_idx": idx,
                            "mitigation_idx": i,
                            "level": ob_mid,
                            "confidence": 0.85
                        })
                        break

        return order_blocks

    def detect_fair_value_gaps(self, df):
        """
        Fair Value Gaps (FVG) tespit eder

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen fair value gaps
        """
        fvgs = {
            "bullish_fvg": [],
            "bearish_fvg": []
        }

        # En az 3 mum olduğunu kontrol et
        if len(df) < 3:
            return fvgs

        # Bullish FVG (Mum 1'in high'ı ile Mum 3'ün low'u arasında boşluk)
        for i in range(0, len(df) - 2):
            # Eğer Mum 1'in high'ı Mum 3'ün low'undan küçükse, bir boşluk vardır
            if df['high'].iloc[i] < df['low'].iloc[i + 2]:
                gap_size = df['low'].iloc[i + 2] - df['high'].iloc[i]
                avg_atr = self._calculate_atr(df, i, window=14)

                # Boşluk ATR'nin %30'undan büyükse, önemli bir boşluktur
                if gap_size > avg_atr * 0.3:
                    fvgs["bullish_fvg"].append({
                        "start_idx": i,
                        "end_idx": i + 2,
                        "top": df['low'].iloc[i + 2],
                        "bottom": df['high'].iloc[i],
                        "size": gap_size,
                        "confidence": min(0.7 + (gap_size / avg_atr) * 0.3, 0.95)
                    })

        # Bearish FVG (Mum 1'in low'u ile Mum 3'ün high'ı arasında boşluk)
        for i in range(0, len(df) - 2):
            # Eğer Mum 1'in low'u Mum 3'ün high'ından büyükse, bir boşluk vardır
            if df['low'].iloc[i] > df['high'].iloc[i + 2]:
                gap_size = df['low'].iloc[i] - df['high'].iloc[i + 2]
                avg_atr = self._calculate_atr(df, i, window=14)

                # Boşluk ATR'nin %30'undan büyükse, önemli bir boşluktur
                if gap_size > avg_atr * 0.3:
                    fvgs["bearish_fvg"].append({
                        "start_idx": i,
                        "end_idx": i + 2,
                        "top": df['low'].iloc[i],
                        "bottom": df['high'].iloc[i + 2],
                        "size": gap_size,
                        "confidence": min(0.7 + (gap_size / avg_atr) * 0.3, 0.95)
                    })

        return fvgs

    def detect_liquidity_sweeps(self, df):
        """
        Likidite tarama (sweep) tespiti - Smart Money'nin stop emirlerini hedeflemesi

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen likidite taramaları
        """
        sweeps = {
            "high_sweeps": [],  # Üst seviye likidite taramaları
            "low_sweeps": []  # Alt seviye likidite taramaları
        }

        # Son 30 mumun lokal yüksek ve düşüklerini bul
        if len(df) < 30:
            return sweeps

        # Son 30 mumu incele
        for i in range(30, len(df) - 3):
            recent_highs = [df['high'].iloc[j] for j in range(i - 30, i)]
            recent_lows = [df['low'].iloc[j] for j in range(i - 30, i)]

            max_high = max(recent_highs)
            min_low = min(recent_lows)

            # High Sweep - Fiyat önceki yüksek seviyeyi geçiyor ve sonra dönüyor
            if df['high'].iloc[i] > max_high:
                # Dönüş kontrolü
                if df['close'].iloc[i + 1] < df['open'].iloc[i + 1] and df['close'].iloc[i + 2] < df['close'].iloc[
                    i + 1]:
                    sweeps["high_sweeps"].append({
                        "idx": i,
                        "level": max_high,
                        "exceeded_by": df['high'].iloc[i] - max_high,
                        "confidence": 0.85
                    })

            # Low Sweep - Fiyat önceki düşük seviyeyi geçiyor ve sonra dönüyor
            if df['low'].iloc[i] < min_low:
                # Dönüş kontrolü
                if df['close'].iloc[i + 1] > df['open'].iloc[i + 1] and df['close'].iloc[i + 2] > df['close'].iloc[
                    i + 1]:
                    sweeps["low_sweeps"].append({
                        "idx": i,
                        "level": min_low,
                        "exceeded_by": min_low - df['low'].iloc[i],
                        "confidence": 0.85
                    })

        return sweeps

    def detect_smart_money_cycles(self, df):
        """
        Smart Money döngülerini tespit eder: Akümülasyon, Manipülasyon, Distribüsyon

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen Smart Money döngüleri
        """
        cycles = {
            "accumulation": [],
            "manipulation": [],
            "distribution": []
        }

        # Veri yeterliliğini kontrol et
        if len(df) < 50:
            return cycles

        # Akümülasyon fazı: Düşük volatilite, yatay hareket, hacmin kademeli artması
        for i in range(20, len(df) - 20):
            window = df.iloc[i - 20:i + 1]

            # Volatilite düşük mü?
            price_range = (window['high'].max() - window['low'].min()) / window['low'].min()

            # Hacim artıyor mu?
            volume_trend = np.polyfit(range(len(window)), window['volume'].values, 1)[0]

            # Fiyat yatay mı?
            price_trend = abs(np.polyfit(range(len(window)), window['close'].values, 1)[0])

            if price_range < 0.05 and volume_trend > 0 and price_trend < 0.0005:
                cycles["accumulation"].append({
                    "start_idx": i - 20,
                    "end_idx": i,
                    "confidence": 0.80
                })

        # Manipülasyon fazı: Ani fiyat hareketi, hacmin artması, ardından yükselişin yavaşlaması
        for i in range(15, len(df) - 10):
            # Önceki 15 mumda volatilite düşükse ve sonraki 5 mumda ani hareket varsa
            prev_window = df.iloc[i - 15:i]
            curr_window = df.iloc[i:i + 5]

            prev_range = (prev_window['high'].max() - prev_window['low'].min()) / prev_window['low'].min()
            curr_range = (curr_window['high'].max() - curr_window['low'].min()) / curr_window['low'].min()

            # Hacim artışı
            avg_prev_volume = prev_window['volume'].mean()
            max_curr_volume = curr_window['volume'].max()

            if prev_range < 0.05 and curr_range > 0.05 and max_curr_volume > avg_prev_volume * 1.5:
                cycles["manipulation"].append({
                    "start_idx": i,
                    "end_idx": i + 5,
                    "confidence": 0.85
                })

        # Distribüsyon fazı: Yükseliş yavaşlar, volatilite düşer, hacim düzenli olarak artar
        for i in range(20, len(df) - 15):
            window = df.iloc[i - 15:i + 5]

            # Son 5 mum yatay mı?
            last_5 = window.iloc[-5:]
            price_range = (last_5['high'].max() - last_5['low'].min()) / last_5['low'].min()

            # Önceki 15 mum yükselme eğiliminde mi?
            prev_15 = window.iloc[:-5]
            price_trend = np.polyfit(range(len(prev_15)), prev_15['close'].values, 1)[0]

            # Hacim profili - zirve yapıp düştü mü?
            volume_peak = window['volume'].argmax()

            if price_trend > 0 and price_range < 0.03 and volume_peak > len(window) * 0.6:
                cycles["distribution"].append({
                    "start_idx": i - 5,
                    "end_idx": i + 5,
                    "confidence": 0.75
                })

        return cycles

    def detect_institutional_footprints(self, df):
        """
        Kurumsal izleri (high volume nodes, cluster) tespit eder

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen kurumsal izler
        """
        footprints = {
            "high_volume_nodes": [],
            "volume_clusters": []
        }

        if len(df) < 20:
            return footprints

        # Anormal hacim noktaları
        for i in range(5, len(df) - 5):
            avg_volume = df['volume'].iloc[i - 5:i + 6].mean()
            std_volume = df['volume'].iloc[i - 5:i + 6].std()

            # Hacim ortalamanın 2 standart sapma üzerindeyse
            if df['volume'].iloc[i] > avg_volume + 2 * std_volume:
                # Fiyat hareketi ile hacim tutarlı mı?
                price_change = abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['open'].iloc[i]

                # Eğer hacim artışı, fiyat hareketiyle orantısızsa, potansiyel kurumsal işlem
                if price_change < 0.01 and df['volume'].iloc[i] > avg_volume * 2:
                    footprints["high_volume_nodes"].append({
                        "idx": i,
                        "price": (df['high'].iloc[i] + df['low'].iloc[i]) / 2,
                        "volume": df['volume'].iloc[i],
                        "confidence": 0.85
                    })

        # Hacim kümeleri - fiyatın sıkıştığı ve hacmin arttığı bölgeler
        for i in range(10, len(df) - 10):
            window = df.iloc[i - 10:i + 11]

            price_range = (window['high'].max() - window['low'].min()) / window['low'].min()
            volume_trend = np.polyfit(range(len(window)), window['volume'].values, 1)[0]

            # Fiyat sıkışık, hacim artıyor
            if price_range < 0.03 and volume_trend > 0 and window['volume'].mean() > df['volume'].iloc[
                                                                                     i - 20:i - 10].mean() * 1.3:
                footprints["volume_clusters"].append({
                    "start_idx": i - 10,
                    "end_idx": i + 10,
                    "avg_price": window['close'].mean(),
                    "confidence": 0.80
                })

        return footprints

    def _calculate_atr(self, df, idx, window=14):
        """
        Ortalama True Range (ATR) hesaplar

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe
            idx (int): Hesaplama yapılacak indeks
            window (int): ATR hesaplama penceresi

        Returns:
            float: ATR değeri
        """
        if idx < window:
            window = idx

        true_ranges = []
        for i in range(max(0, idx - window), idx + 1):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            prev_close = df['close'].iloc[i - 1] if i > 0 else df['open'].iloc[i]

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_ranges.append(max(tr1, tr2, tr3))

        return sum(true_ranges) / len(true_ranges)

    def analyze_smart_money_patterns(self, df):
        """
        Tüm Smart Money paternlerini analiz eder

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            dict: Tespit edilen tüm Smart Money paternleri
        """
        # Önce temel analizimizi yapalım
        self.analyze_all_patterns(df)

        # Şimdi Smart Money analizini ekleyelim
        order_blocks = self.detect_order_blocks(df)
        fvgs = self.detect_fair_value_gaps(df)
        sweeps = self.detect_liquidity_sweeps(df)
        cycles = self.detect_smart_money_cycles(df)
        footprints = self.detect_institutional_footprints(df)

        # Tüm analizleri birleştir
        smart_money_analysis = {
            "order_blocks": order_blocks,
            "fair_value_gaps": fvgs,
            "liquidity_sweeps": sweeps,
            "smart_money_cycles": cycles,
            "institutional_footprints": footprints
        }

        return {
            "basic_patterns": {
                "levels": self.levels,
                "patterns": self.patterns
            },
            "smart_money_patterns": smart_money_analysis
        }

    def analyze_all_patterns(self, df):
        """
        Tüm temel paternleri analiz eder

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe
        """
        # Destek ve direnç seviyelerini tespit et
        self.levels["support"] = self._detect_support_levels(df)
        self.levels["resistance"] = self._detect_resistance_levels(df)

        # Diğer paternleri tespit et
        self.patterns["bullish_mitigation"] = self._detect_bullish_mitigation(df)
        self.patterns["bearish_breaker"] = self._detect_bearish_breaker(df)
        self.patterns["bullish_sfp"] = self._detect_bullish_sfp(df)
        self.patterns["bearish_sfp"] = self._detect_bearish_sfp(df)

    def _detect_support_levels(self, df):
        """
        Destek seviyelerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen destek seviyeleri
        """
        # Destek seviyelerini tespit et
        # Basit örnek: Son 20 mum içindeki minimum değerler
        supports = []
        if len(df) < 20:
            return supports

        for i in range(20, len(df) - 5):
            if df['low'].iloc[i] < df['low'].iloc[i - 1] and df['low'].iloc[i] < df['low'].iloc[i + 1]:
                # Minimum 3 mum sonra test edildiyse destek seviyesi
                supports.append({
                    "price": df['low'].iloc[i],
                    "idx": i,
                    "strength": 1
                })

        return supports

    def _detect_resistance_levels(self, df):
        """
        Direnç seviyelerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen direnç seviyeleri
        """
        # Direnç seviyelerini tespit et
        # Basit örnek: Son 20 mum içindeki maksimum değerler
        resistances = []
        if len(df) < 20:
            return resistances

        for i in range(20, len(df) - 5):
            if df['high'].iloc[i] > df['high'].iloc[i - 1] and df['high'].iloc[i] > df['high'].iloc[i + 1]:
                # Maksimum 3 mum sonra test edildiyse direnç seviyesi
                resistances.append({
                    "price": df['high'].iloc[i],
                    "idx": i,
                    "strength": 1
                })

        return resistances

    def _detect_bullish_mitigation(self, df):
        """
        Bullish mitigation (boşluk doldurma) paternlerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen bullish mitigation paternleri
        """
        patterns = []
        if len(df) < 30:
            return patterns

        # Son 30 mumu incele
        for i in range(20, len(df) - 10):
            # Önceki düşük seviyeyi bul (lokal minimum)
            if df['low'].iloc[i] < df['low'].iloc[i - 1] and df['low'].iloc[i] < df['low'].iloc[i + 1]:
                prev_low = df['low'].iloc[i]

                # Bu seviyeye geri dönüş var mı?
                for j in range(i + 5, min(i + 20, len(df) - 1)):
                    # Fiyat düşük seviyeye yaklaştı mı?
                    if abs(df['low'].iloc[j] - prev_low) / prev_low < 0.003:  # %0.3 tolerans
                        # Geri dönüş sonrası yükseliş var mı?
                        if j + 3 < len(df) and df['close'].iloc[j + 3] > df['close'].iloc[j]:
                            patterns.append({
                                "low_idx": i,
                                "mitigation_idx": j,
                                "price": prev_low,
                                "confidence": 0.8
                            })
                            break

        return patterns

    def _detect_bearish_breaker(self, df):
        """
        Bearish breaker paternlerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen bearish breaker paternleri
        """
        patterns = []
        if len(df) < 30:
            return patterns

        # Son 30 mumu incele
        for i in range(20, len(df) - 10):
            # Önceki yüksek seviyeyi bul (lokal maksimum)
            if df['high'].iloc[i] > df['high'].iloc[i - 1] and df['high'].iloc[i] > df['high'].iloc[i + 1]:
                prev_high = df['high'].iloc[i]

                # Bu seviyeyi kıran bir hareket var mı?
                for j in range(i + 5, min(i + 20, len(df) - 1)):
                    # Fiyat yüksek seviyeyi geçti mi?
                    if df['high'].iloc[j] > prev_high * 1.005:  # %0.5 tolerans
                        # Kırılma sonrası düşüş var mı?
                        if j + 3 < len(df) and df['close'].iloc[j + 3] < df['close'].iloc[j]:
                            patterns.append({
                                "high_idx": i,
                                "breaker_idx": j,
                                "price": prev_high,
                                "confidence": 0.8
                            })
                            break

        return patterns

    def _detect_bullish_sfp(self, df):
        """
        Bullish Stop-Hunt / Fakeout / SFP paternlerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen bullish SFP paternleri
        """
        patterns = []
        if len(df) < 20:
            return patterns

        # Son 20 mumu incele
        for i in range(5, len(df) - 5):
            # Son 5 mumdaki en düşük değeri bul
            prev_low = min(df['low'].iloc[i - 5:i].min(), df['low'].iloc[i])

            # Mevcut mum bu değerin altına indi ve sonra geri döndü mü?
            current_low = df['low'].iloc[i]
            current_close = df['close'].iloc[i]

            if current_low < prev_low * 0.997 and current_close > prev_low:  # %0.3 tolerans
                # Sonraki 3 mumda yükseliş var mı?
                if i + 3 < len(df) and df['close'].iloc[i + 3] > current_close:
                    patterns.append({
                        "idx": i,
                        "price": current_low,
                        "prev_low": prev_low,
                        "confidence": 0.85
                    })

        return patterns

    def _detect_bearish_sfp(self, df):
        """
        Bearish Stop-Hunt / Fakeout / SFP paternlerini tespit et

        Args:
            df (pd.DataFrame): OHLC verileri içeren dataframe

        Returns:
            list: Tespit edilen bearish SFP paternleri
        """
        patterns = []
        if len(df) < 20:
            return patterns

        # Son 20 mumu incele
        for i in range(5, len(df) - 5):
            # Son 5 mumdaki en yüksek değeri bul
            prev_high = max(df['high'].iloc[i - 5:i].max(), df['high'].iloc[i])

            # Mevcut mum bu değerin üstüne çıktı ve sonra geri döndü mü?
            current_high = df['high'].iloc[i]
            current_close = df['close'].iloc[i]

            if current_high > prev_high * 1.003 and current_close < prev_high:  # %0.3 tolerans
                # Sonraki 3 mumda düşüş var mı?
                if i + 3 < len(df) and df['close'].iloc[i + 3] < current_close:
                    patterns.append({
                        "idx": i,
                        "price": current_high,
                        "prev_high": prev_high,
                        "confidence": 0.85
                    })

        return patterns

    def generate_smart_money_report(self, symbol, df):
        """
        Creates a comprehensive report for Smart Money patterns

        Args:
            symbol (str): Trading pair symbol
            df (pd.DataFrame): Dataframe containing OHLC data

        Returns:
            str: Smart Money patterns report
        """
        # Run all analyses
        analysis = self.analyze_smart_money_patterns(df)

        report = f"🔍 <b>Smart Money Price Action Analysis - {symbol}</b>\n"
        report += "=" * 50 + "\n\n"

        # Order Blocks
        order_blocks = analysis["smart_money_patterns"]["order_blocks"]
        report += "<b>📊 ORDER BLOCKS:</b>\n"

        if order_blocks["bullish_ob"]:
            report += f"• <b>🟢 Bullish Order Blocks:</b> {len(order_blocks['bullish_ob'])} detected\n"
            for i, ob in enumerate(sorted(order_blocks["bullish_ob"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {ob['mid']:.4f} (Confidence: {ob['confidence'] * 100:.0f}%)\n"

        if order_blocks["bearish_ob"]:
            report += f"• <b>🔴 Bearish Order Blocks:</b> {len(order_blocks['bearish_ob'])} detected\n"
            for i, ob in enumerate(sorted(order_blocks["bearish_ob"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {ob['mid']:.4f} (Confidence: {ob['confidence'] * 100:.0f}%)\n"

        if order_blocks["bul_mitigation_ob"]:
            report += f"• <b>🟢 Bullish Mitigation Order Blocks:</b> {len(order_blocks['bul_mitigation_ob'])} detected\n"
            for i, ob in enumerate(
                    sorted(order_blocks["bul_mitigation_ob"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {ob['level']:.4f} (Confidence: {ob['confidence'] * 100:.0f}%)\n"

        if order_blocks["bear_mitigation_ob"]:
            report += f"• <b>🔴 Bearish Mitigation Order Blocks:</b> {len(order_blocks['bear_mitigation_ob'])} detected\n"
            for i, ob in enumerate(
                    sorted(order_blocks["bear_mitigation_ob"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {ob['level']:.4f} (Confidence: {ob['confidence'] * 100:.0f}%)\n"

        if not any(order_blocks.values()):
            report += "  No Order Blocks detected.\n"

        # Fair Value Gaps
        fvgs = analysis["smart_money_patterns"]["fair_value_gaps"]
        report += "\n<b>📊 FAIR VALUE GAPS (FVG):</b>\n"

        if fvgs["bullish_fvg"]:
            report += f"• <b>🟢 Bullish FVGs:</b> {len(fvgs['bullish_fvg'])} detected\n"
            for i, fvg in enumerate(sorted(fvgs["bullish_fvg"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Range: {fvg['bottom']:.4f} - {fvg['top']:.4f} (Confidence: {fvg['confidence'] * 100:.0f}%)\n"

        if fvgs["bearish_fvg"]:
            report += f"• <b>🔴 Bearish FVGs:</b> {len(fvgs['bearish_fvg'])} detected\n"
            for i, fvg in enumerate(sorted(fvgs["bearish_fvg"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Range: {fvg['bottom']:.4f} - {fvg['top']:.4f} (Confidence: {fvg['confidence'] * 100:.0f}%)\n"

        if not any(fvgs.values()):
            report += "  No Fair Value Gaps detected.\n"

        # Liquidity Sweeps
        sweeps = analysis["smart_money_patterns"]["liquidity_sweeps"]
        report += "\n<b>📊 LIQUIDITY SWEEPS:</b>\n"

        if sweeps["high_sweeps"]:
            report += f"• <b>🔼 High Level Liquidity Sweeps:</b> {len(sweeps['high_sweeps'])} detected\n"
            for i, sweep in enumerate(sorted(sweeps["high_sweeps"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {sweep['level']:.4f} (Exceeded by: {sweep['exceeded_by']:.4f})\n"

        if sweeps["low_sweeps"]:
            report += f"• <b>🔽 Low Level Liquidity Sweeps:</b> {len(sweeps['low_sweeps'])} detected\n"
            for i, sweep in enumerate(sorted(sweeps["low_sweeps"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Level: {sweep['level']:.4f} (Exceeded by: {sweep['exceeded_by']:.4f})\n"

        if not any(sweeps.values()):
            report += "  No Liquidity Sweeps detected.\n"

        # Smart Money Cycles
        cycles = analysis["smart_money_patterns"]["smart_money_cycles"]
        report += "\n<b>📊 SMART MONEY CYCLES:</b>\n"

        cycle_found = False
        for cycle_type, cycle_list in cycles.items():
            if cycle_list:
                cycle_found = True
                cycle_names = {
                    "accumulation": "Accumulation",
                    "manipulation": "Manipulation",
                    "distribution": "Distribution"
                }
                report += f"• <b>{cycle_names[cycle_type]} Phase:</b> {len(cycle_list)} phases detected\n"

        if not cycle_found:
            report += "  No Smart Money Cycles detected.\n"

        # Institutional Footprints
        footprints = analysis["smart_money_patterns"]["institutional_footprints"]
        report += "\n<b>📊 INSTITUTIONAL FOOTPRINTS:</b>\n"

        if footprints["high_volume_nodes"]:
            report += f"• <b>High Volume Nodes:</b> {len(footprints['high_volume_nodes'])} detected\n"
            for i, node in enumerate(
                    sorted(footprints["high_volume_nodes"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Price: {node['price']:.4f} (Confidence: {node['confidence'] * 100:.0f}%)\n"

        if footprints["volume_clusters"]:
            report += f"• <b>Hacim Kümelenmeleri:</b> {len(footprints['volume_clusters'])} adet\n"
            for i, cluster in enumerate(
                    sorted(footprints["volume_clusters"], key=lambda x: x["confidence"], reverse=True)[:3]):
                report += f"  - Ort. Fiyat: {cluster['avg_price']:.4f} (Güven: {cluster['confidence'] * 100:.0f}%)\n"

        if not any(footprints.values()):
            report += "  Tespit edilen Kurumsal İz yok.\n"

        # Smart Money Analysis sonucu ve yorumu
        report += "\n<b>📝 SMART MONEY ANALİZ YORUMU:</b>\n"

        # Bullish ve bearish sinyalleri sayalım
        bullish_signals = (
                len(order_blocks["bullish_ob"]) +
                len(order_blocks["bul_mitigation_ob"]) +
                len(fvgs["bullish_fvg"]) +
                len(sweeps["low_sweeps"])
        )

        bearish_signals = (
                len(order_blocks["bearish_ob"]) +
                len(order_blocks["bear_mitigation_ob"]) +
                len(fvgs["bearish_fvg"]) +
                len(sweeps["high_sweeps"])
        )

        # Akümülasyon varsa bullish, distribüsyon varsa bearish
        if cycles["accumulation"]:
            bullish_signals += len(cycles["accumulation"]) * 2  # Akümülasyona daha fazla ağırlık
        if cycles["distribution"]:
            bearish_signals += len(cycles["distribution"]) * 2  # Distribüsyona daha fazla ağırlık

        # Manipülasyon fazını yorumla
        if cycles["manipulation"]:
            report += "• <b>Manipülasyon Fazı Tespiti:</b> Smart Money muhtemelen piyasayı manipüle ediyor, dikkatli olun.\n"

        # Genel eğilim yorumu
        if bullish_signals > bearish_signals * 1.5:
            report += f"• <b>Genel Eğilim:</b> Güçlü yükseliş eğilimi ({bullish_signals} yükseliş sinyali, {bearish_signals} düşüş sinyali)\n"
            report += "• <b>Smart Money Yorumu:</b> Kurumsal yatırımcılar muhtemelen alım yapıyor.\n"
            report += "• <b>Olası Senaryo:</b> Smart Money likiditesini toplamış ve potansiyel bir yükseliş hareketi hazırlığında olabilir.\n"
        elif bullish_signals > bearish_signals:
            report += f"• <b>Genel Eğilim:</b> Orta seviye yükseliş eğilimi ({bullish_signals} yükseliş sinyali, {bearish_signals} düşüş sinyali)\n"
            report += "• <b>Smart Money Yorumu:</b> Kurumsal yatırımcılar alımlarını yapıyor ancak tamamlanmadı.\n"
            report += "• <b>Olası Senaryo:</b> Daha fazla akümülasyon görebiliriz, ardından yukarı yönlü bir hareket beklenebilir.\n"
        elif bearish_signals > bullish_signals * 1.5:
            report += f"• <b>Genel Eğilim:</b> Güçlü düşüş eğilimi ({bearish_signals} düşüş sinyali, {bullish_signals} yükseliş sinyali)\n"
            report += "• <b>Smart Money Yorumu:</b> Kurumsal yatırımcılar muhtemelen satış yapıyor.\n"
            report += "• <b>Olası Senaryo:</b> Smart Money satışlarını tamamlamış ve potansiyel bir düşüş hareketi başlayabilir.\n"
        elif bearish_signals > bullish_signals:
            report += f"• <b>Genel Eğilim:</b> Orta seviye düşüş eğilimi ({bearish_signals} düşüş sinyali, {bullish_signals} yükseliş sinyali)\n"
            report += "• <b>Smart Money Yorumu:</b> Kurumsal yatırımcılar dağıtım fazında olabilir.\n"
            report += "• <b>Olası Senaryo:</b> Daha fazla satış baskısı görebiliriz, aşağı yönlü hareketlere hazırlıklı olun.\n"
        else:
            report += f"• <b>Genel Eğilim:</b> Nötr ({bullish_signals} yükseliş sinyali, {bearish_signals} düşüş sinyali)\n"
            report += "• <b>Smart Money Yorumu:</b> Net bir kurumsal strateji görünmüyor.\n"
            report += "• <b>Olası Senaryo:</b> Yatay seyir devam edebilir, belirgin bir işaret bekleyin.\n"

        # Kilit izlenecek seviyeleri belirle
        key_levels = []

        # Order Block'lardan önemli seviyeler
        if order_blocks["bullish_ob"]:
            top_bullish_ob = sorted(order_blocks["bullish_ob"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": top_bullish_ob["mid"],
                "type": "Bullish Order Block",
                "confidence": top_bullish_ob["confidence"]
            })

        if order_blocks["bearish_ob"]:
            top_bearish_ob = sorted(order_blocks["bearish_ob"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": top_bearish_ob["mid"],
                "type": "Bearish Order Block",
                "confidence": top_bearish_ob["confidence"]
            })

        # FVG'lerden önemli seviyeler
        if fvgs["bullish_fvg"]:
            top_bullish_fvg = sorted(fvgs["bullish_fvg"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": (top_bullish_fvg["top"] + top_bullish_fvg["bottom"]) / 2,
                "type": "Bullish FVG",
                "confidence": top_bullish_fvg["confidence"]
            })

        if fvgs["bearish_fvg"]:
            top_bearish_fvg = sorted(fvgs["bearish_fvg"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": (top_bearish_fvg["top"] + top_bearish_fvg["bottom"]) / 2,
                "type": "Bearish FVG",
                "confidence": top_bearish_fvg["confidence"]
            })

        # Likidite seviyelerini ekle
        if sweeps["high_sweeps"]:
            top_high_sweep = sorted(sweeps["high_sweeps"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": top_high_sweep["level"],
                "type": "High Sweep",
                "confidence": top_high_sweep["confidence"]
            })

        if sweeps["low_sweeps"]:
            top_low_sweep = sorted(sweeps["low_sweeps"], key=lambda x: x["confidence"], reverse=True)[0]
            key_levels.append({
                "level": top_low_sweep["level"],
                "type": "Low Sweep",
                "confidence": top_low_sweep["confidence"]
            })

        # Kilit seviyeleri ekle
        if key_levels:
            report += "\n<b>🔑 KİLİT İZLENECEK SEVİYELER:</b>\n"
            for i, level in enumerate(sorted(key_levels, key=lambda x: x["confidence"], reverse=True)[:5]):
                report += f"• {level['type']}: {level['level']:.4f} (Güven: {level['confidence'] * 100:.0f}%)\n"

        # Son tavsiye
        report += "\n<b>💡 SMART MONEY TAVSİYESİ:</b>\n"

        if bullish_signals > bearish_signals * 1.5:
            report += "• Güçlü yükseliş potansiyeli mevcut. HODL veya AL pozisyonu düşünülebilir.\n"
            report += "• Order Block'lar stop-loss seviyeleri olarak kullanılabilir.\n"
        elif bullish_signals > bearish_signals:
            report += "• Orta seviye yükseliş potansiyeli mevcut. Kademeli AL düşünülebilir.\n"
            report += "• Stop-loss emirleri için tespit edilen Bullish Order Block seviyelerini kullanın.\n"
        elif bearish_signals > bullish_signals * 1.5:
            report += "• Güçlü düşüş potansiyeli mevcut. SAT veya SHORT pozisyonu düşünülebilir.\n"
            report += "• Tespit edilen Bearish Order Block seviyelerini stop-loss olarak kullanın.\n"
        elif bearish_signals > bullish_signals:
            report += "• Orta seviye düşüş potansiyeli mevcut. Kademeli SAT düşünülebilir.\n"
            report += "• Yukarı yönlü likidite taramalarına dikkat edin, manipülatif hareketler olabilir.\n"
        else:
            report += "• Net bir sinyal yok. Bekle-gör stratejisi uygun olabilir.\n"
            report += "• Order Block ve FVG seviyelerine dikkat edin, bunlar fırsatlar olabilir.\n"

        # Risk uyarısı
        report += "\n⚠️ <b>RİSK UYARISI:</b>\n"
        report += "Bu analiz sadece Smart Money konseptlerine dayanmaktadır ve garanti edilemez. Her zaman kendi analizinizi yapın ve risk yönetimi kurallarınıza uyun."

        return report





