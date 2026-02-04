"""
Ross Cameron Trading Playbook - 7 Step Scaling Strategy
Crypto versiyonu: Momentum compound sistemi
"""

TRADING_PLAYBOOK = """
╔════════════════════════════════════════════════════════════════════════════════╗
║                    📊 ROSS CAMERON TRADING PLAYBOOK                            ║
║                    7 Adımlı Pozisyon Scaling Stratejisi                       ║
╚════════════════════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 1: COIN BUL (Hisse Seçimi Kriteri)                                       │
├────────────────────────────────────────────────────────────────────────────────┤
│ ✅ 5 KRİTERİ SAĞLAYAN COİN:                                                    │
│                                                                                │
│   1️⃣ HABER KATALİZÖRÜ var (listing, partnership, upgrade)                    │
│   2️⃣ PRE-MARKET %10+ GAP UP (last 4h pump)                                   │
│   3️⃣ VOLUME 5X+ artmış (relative volume spike)                               │
│   4️⃣ FİYAT $0.10-$50 arası (mid-cap altcoin sweet spot)                      │
│   5️⃣ FLOAT <100M (düşük supply → kolay squeeze)                              │
│                                                                                │
│ 🎯 ÖRNEK: SOL haberle $140 → $155 pump yaptı (24h vol 5x+)                    │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 2: PATTERN BEKLE (Bull Flag)                                             │
├────────────────────────────────────────────────────────────────────────────────┤
│ 📈 SQUEEZE → PULLBACK:                                                         │
│                                                                                │
│   Pump:      $140 → $155 → $165 (güçlü yükseliş)                              │
│   Pullback:  $165 → $160 → $157 (hafif geri çekilme %3-5)                     │
│   Flag:      $157-$160 arası konsolidasyon (15-30 dk)                         │
│                                                                                │
│ ⏱️ BEKLEME: İlk 5m yeşil mum flag high'ı ($160) kırmalı                        │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 3: GİRİŞ (Entry Point)                                                   │
├────────────────────────────────────────────────────────────────────────────────┤
│ 🎯 İLK MUM YENİ ZİRVE YAPINCA AL:                                              │
│                                                                                │
│   Entry Price:    $160.50 (flag high breakout)                                │
│   Position Size:  100 SOL (1/4 tam pozisyon - conservative)                   │
│   Entry Value:    $16,050                                                     │
│                                                                                │
│ 📊 POZİSYON BOYUTU:                                                            │
│   Capital: $5,000 → Risk 2% = $100                                            │
│   Stop distance: $2.50 → Size = $100 / $2.50 = 40 SOL                         │
│   İLK GİRİŞ: 40 SOL × 1/4 = 10 SOL (test pozisyonu)                           │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 4: STOP-LOSS (Risk Yönetimi)                                             │
├────────────────────────────────────────────────────────────────────────────────┤
│ 🛑 PULLBACK DÜŞÜK ALTINA:                                                      │
│                                                                                │
│   Stop Price:     $158.00 (pullback low - $157 x 0.99)                        │
│   Risk Per Coin:  $160.50 - $158.00 = $2.50                                   │
│   Total Risk:     10 SOL × $2.50 = $25 (capital'in %0.5'i)                    │
│                                                                                │
│ ⚠️ KURAL: Stop kırılırsa → HEMEN KES (duygusuz)                                │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 5: HEDEF (Initial Target)                                                │
├────────────────────────────────────────────────────────────────────────────────┤
│ 🎯 HIGH OF DAY RETEST:                                                         │
│                                                                                │
│   Target Price:   $165.00 (günün en yükseği)                                  │
│   Profit Per Coin: $165.00 - $160.50 = $4.50                                  │
│   Total Profit:   10 SOL × $4.50 = $45                                        │
│   R/R Ratio:      $4.50 / $2.50 = 1.8:1 (iyi değil ama scalable)             │
│                                                                                │
│ 📈 TARGET HİT: %50 pozisyonu sat ($22.50 kar kilitle)                          │
│              Kalan 50% ile scaling devam et                                   │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 6: KAR DEVAM EDERSE → POZİSYON BÜYÜT! (Scaling In)                       │
├────────────────────────────────────────────────────────────────────────────────┤
│ 💰 KAZANAN TRADE'E EKLE:                                                       │
│                                                                                │
│   Koşul:         Fiyat $165 hedefini vurdu VE kırıyor                         │
│   New Entry:     $165.50 (yeni breakout)                                      │
│   Add Size:      +20 SOL DAHA EKLE                                            │
│   New Total:     30 SOL (10 + 20)                                             │
│   New Avg Price: ($160.50×10 + $165.50×20) / 30 = $163.83                     │
│                                                                                │
│   Yeni Stop:     $163.00 (break-even seviyesi artık)                          │
│   Yeni Target:   $170.00 (sonraki resistance)                                 │
│                                                                                │
│ 🔥 MANTIK: Kazanan trade'e ekle, kaybedene asla!                               │
│   Ross: "Add to winners, cut losers fast"                                     │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ ADIM 7: ÇIKIŞ (Exit Strategy)                                                 │
├────────────────────────────────────────────────────────────────────────────────┤
│ 🚪 HEDEFE ULAŞ veya TERS SİNYAL:                                               │
│                                                                                │
│   SENARYO 1: Target Hit ($170)                                                │
│     → 30 SOL × ($170 - $163.83) = $185 kar                                    │
│     → Tüm pozisyon kapat                                                      │
│                                                                                │
│   SENARYO 2: Ters Sinyal                                                      │
│     → 5m kırmızı mum + volume spike                                           │
│     → Trailing stop devreye girer                                             │
│     → Karı koruma modu (30 SOL @ $168 sat örneğin)                            │
│                                                                                │
│   SENARYO 3: Stop Hit ($163)                                                  │
│     → Küçük kar/break-even exit                                               │
│     → İlk 10 SOL kârlı, son 20 SOL scratch                                    │
│                                                                                │
│ 📊 TOPLAM KAR ÖRNEK:                                                           │
│     İlk 5 SOL @ $165 sat = $22.50                                             │
│     Kalan 25 SOL @ $170 sat = $155                                            │
│     TOTAL: $177.50 (risk $25 idi → 7R kazanç!)                                │
└────────────────────────────────────────────────────────────────────────────────┘

╔════════════════════════════════════════════════════════════════════════════════╗
║                              🎯 SON NOT                                        ║
╠════════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║  Bu strateji çok DİSİPLİN, HIZLI KARAR ve DUYGUSUZLUK gerektirir.             ║
║                                                                                ║
║  Ross'un 51 günde 1 milyon dolar yapması:                                     ║
║    • 10+ yıllık deneyim                                                       ║
║    • Büyük sermaye (100.000$+ alım gücü)                                      ║
║    • Volatil piyasa şartları                                                  ║
║    • Kusursuz uygulama                                                        ║
║                                                                                ║
║  Çoğu insan bu seviyeye yıllar sonra ulaşır veya hiç ulaşamaz.                ║
║                                                                                ║
║  🎓 YENİ BAŞLAYANLAR İÇİN GERÇEKÇI BEKLENTİ:                                   ║
║    • İlk 30 gün: Simülatörde 50+ trade yap                                    ║
║    • Paper trading ile %60+ win rate kanıtla                                  ║
║    • Küçük sermaye ile başla ($500-2000)                                      ║
║    • İlk hedef: Ayda %5-10 ROI (yıllık %60-120)                               ║
║    • Compound ile 1-2 yılda 5-10x gerçekçi                                    ║
║                                                                                ║
║  💡 UNUTMA: "Survive till you thrive" - önce hayatta kal!                     ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝

"""

def get_playbook():
    """Trading playbook'u döndür"""
    return TRADING_PLAYBOOK

if __name__ == "__main__":
    print(get_playbook())
