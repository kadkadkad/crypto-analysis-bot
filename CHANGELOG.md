# 🚀 Radar Ultra Dashboard - Changelog

## [2026-01-22] - "Release Ready" Update

### 🛡️ System Validator (New Module)
- **Added:** `system_validator.py` module to audit data integrity continuously.
- **Added:** `/api/system-health` endpoint in Web Dashboard.
- **Auto-Fix:** System now automatically disables signals with <40% win rate.
- **Result:** Price/RSI/MACD accuracy verified at **96.7%**.

### 🔧 Core Fixes
- **Whale Activity:** Fixed "0" value issue by integrating `count` (trades) data from Binance API into `binance_client.py`.
- **Risk Report:** 
  - Fixed "0 coins" in Risk Distribution (Language mismatch bug: TR -> EN).
  - Translated all Macro Risk factors to English (e.g., "Fear & Greed", "Volatility").
  - Fixed Whale Risk calculation error (was static at 70/100).
- **Multi-Timeframe Reports:** Fixed "N/A" bug for RSI 4H, MACD 1D, etc. by improving key normalization logic.
- **Crash Fix:** Fixed pandas column mismatch crash in `calculate_buyer_ratio`.

### 💻 Web UI / Dashboard
- **Sidebar Fix:** Implemented proper scrolling for the long sidebar menu (CSS overflow fix).
- **Menu Cleanup:** Removed broken/inactive reports (Whale Movement, Order Block) from the menu.
- **Visuals:** Order Block analysis now displays "✅ DETECTED" instead of "True/False" or "N/A".

### 🧹 Signal Quality
- **Removed:** `reversal_bullish` signal (0% win rate).
- **Improved:** Bear signals now require 3+ confirmations (SFP logic updated).
- **Optimized:** LS Imbalance score capped at 100 max.

### ✅ Status
- **Ready for Live Broadcast.**
