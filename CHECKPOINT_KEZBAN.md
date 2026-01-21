# CHECKPOINT: KEZBAN

## Status as of 2026-01-16
- **Feature:** Integrated TradingView Lightweight Charts into Coin Analysis Report.
- **Functionality:** Chart now plots Candles + AI Support/Resistance + Strategy Levels (Entry/TP/SL).
- **Deployment:** 
  - Code pushed to `main`.
  - Server pulled and updated (`web_dashboard.py`, `dashboard_v2.html`).
  - Web service running on Port 5001.
- **Current Issue:** User browser is caching the old `index.html` (V7) despite server serving `dashboard_v2.html` (V2.0).
- **Next Step:** User needs to force clear cache or use Incognito mode to see the changes.

## Commands to Resume
- Check service: `ps aux | grep python`
- Check logs: `cat web.log` or `cat /tmp/web_debug.log`
