
def get_whale_heatmap_report(coins_data):
    if not coins_data:
        return "<div class='alert alert-warning'>⚠️ No data available yet.</div>"

    try:
        # Sort by Net Accumulation (NetAccum_raw)
        # We assume NetAccum_raw is present in web_results.json
        def get_accum(c):
             try: return float(str(c.get("NetAccum_raw", 0)).replace(",",""))
             except: return 0
        
        sorted_results = sorted(coins_data, key=get_accum, reverse=True)
        
        html = """
        <style>
            .whale-map { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-top: 15px; }
            .whale-card { padding: 15px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.1); }
            .w-bull-Strong { background: rgba(0, 255, 0, 0.25); border-color: #0f0; box-shadow: 0 0 10px rgba(0,255,0,0.2); }
            .w-bull-Weak { background: rgba(0, 255, 0, 0.1); border-color: #0c0; }
            .w-bear-Strong { background: rgba(255, 0, 0, 0.25); border-color: #f00; box-shadow: 0 0 10px rgba(255,0,0,0.2); }
            .w-bear-Weak { background: rgba(255, 0, 0, 0.1); border-color: #c00; }
            .w-neutral { background: rgba(255, 255, 255, 0.05); }
            .w-sym { font-size: 1.2em; font-weight: bold; margin-bottom: 5px; }
            .w-val { font-size: 1.1em; font-family: monospace; }
            .w-lbl { font-size: 0.8em; opacity: 0.7; margin-top: 5px; }
        </style>
        <h4>🐋 Whale Net Accumulation Heatmap (Live)</h4>
        <div class="whale-map">
        """
        
        for coin in sorted_results[:50]:
            try:
                net_accum = get_accum(coin)
                price_change = coin.get("24h Change", "0%")
                symbol = coin.get("Coin", "UNKNOWN").replace("USDT", "")
                
                # Determine Class
                card_class = "w-neutral"
                score = "Neutral"
                
                # Thresholds (adjust if NetAccum is not in raw $)
                # Assuming NetAccum is in raw USD
                if net_accum > 10_000_000: card_class = "w-bull-Strong"; score = "Strong BUY"
                elif net_accum > 0: card_class = "w-bull-Weak"; score = "Accumulation"
                elif net_accum < -10_000_000: card_class = "w-bear-Strong"; score = "Strong SELL"
                elif net_accum < 0: card_class = "w-bear-Weak"; score = "Distribution"
                
                icon = "🟢" if net_accum > 0 else "🔴"
                
                # Display in Millions
                accum_display = f"{net_accum / 1_000_000:.2f}M"
                
                html += f"""
                <div class="whale-card {card_class}">
                    <div class="w-sym">{icon} ${symbol}</div>
                    <div class="w-val">{accum_display}</div>
                    <div class="w-lbl">Change: {price_change}</div>
                    <div class="w-lbl">{score}</div>
                </div>
                """
            except: continue
        
        html += "</div>"
        return html
    except Exception as e:
        return f"Error generating heatmap: {e}"
