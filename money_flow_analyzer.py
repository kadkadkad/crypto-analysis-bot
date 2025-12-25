"""
Smart Money Flow Analyzer
Tracks where whale money is flowing between coins
"""
import json
from datetime import datetime, timedelta

class MoneyFlowAnalyzer:
    def __init__(self):
        self.flow_history = []
        
    def analyze_flow(self, current_data, previous_data):
        """
        Analyze money flow between coins based on net accumulation changes
        
        Args:
            current_data: Current ALL_RESULTS data
            previous_data: Previous cycle's data
            
        Returns:
            dict: Flow analysis with source/target/amount
        """
        flows = []
        
        # Create lookup dict for previous data
        prev_lookup = {coin['Coin']: coin for coin in previous_data} if previous_data else {}
        
        for coin in current_data[:20]:  # Top 20 coins
            symbol = coin['Coin']
            current_accum_12h = coin.get('net_accum_12h', 0)
            current_accum_1d = coin.get('net_accum_1d', 0)
            
            if symbol in prev_lookup:
                prev_accum_12h = prev_lookup[symbol].get('net_accum_12h', 0)
                prev_accum_1d = prev_lookup[symbol].get('net_accum_1d', 0)
                
                # Calculate deltas
                delta_12h = current_accum_12h - prev_accum_12h
                delta_1d = current_accum_1d - prev_accum_1d
                
                # Convert to millions
                delta_12h_m = delta_12h / 1000000
                delta_1d_m = delta_1d / 1000000
                
                # Only track significant flows (>$10M)
                if abs(delta_12h_m) > 10:
                    flows.append({
                        'coin': symbol.replace('USDT', ''),
                        'delta_12h': delta_12h_m,
                        'delta_1d': delta_1d_m,
                        'current_accum_12h': current_accum_12h / 1000000,
                        'direction': 'inflow' if delta_12h_m > 0 else 'outflow',
                        'magnitude': abs(delta_12h_m),
                        'price': coin.get('Price', 0),
                        'ema_trend': coin.get('EMA Trend', 'Neutral')
                    })
        
        # Sort by magnitude
        flows.sort(key=lambda x: x['magnitude'], reverse=True)
        
        return flows[:15]  # Top 15 flows
    
    def generate_flow_report(self, flows):
        """Generate human-readable flow report"""
        if not flows:
            return "📊 No significant money flows detected in the last cycle."
        
        report = f"💰 <b>Smart Money Flow Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}</b>\n"
        report += "<i>Tracking whale accumulation changes (12H period)</i>\n\n"
        
        # Separate inflows and outflows
        inflows = [f for f in flows if f['direction'] == 'inflow']
        outflows = [f for f in flows if f['direction'] == 'outflow']
        
        if inflows:
            report += "🟢 <b>TOP INFLOWS (Whale Buying):</b>\n"
            for flow in inflows[:5]:
                emoji = "🚀" if "Bullish" in flow['ema_trend'] else "⚡"
                report += f"{emoji} <b>${flow['coin']}</b>: +${flow['delta_12h']:.1f}M"
                report += f" | {flow['ema_trend']}\n"
            report += "\n"
        
        if outflows:
            report += "🔴 <b>TOP OUTFLOWS (Whale Selling):</b>\n"
            for flow in outflows[:5]:
                emoji = "📉" if "Bearish" in flow['ema_trend'] else "⚠️"
                report += f"{emoji} <b>${flow['coin']}</b>: ${flow['delta_12h']:.1f}M"
                report += f" | {flow['ema_trend']}\n"
            report += "\n"
        
        # Add rotation insight
        if inflows and outflows:
            top_in = inflows[0]
            top_out = outflows[0]
            report += f"💡 <b>Key Insight:</b> Money rotating from ${top_out['coin']} "
            report += f"(${abs(top_out['delta_12h']):.1f}M out) to ${top_in['coin']} "
            report += f"(${top_in['delta_12h']:.1f}M in)\n"
        
        return report
    
    def get_flow_visualization_data(self, flows):
        """
        Prepare data for Sankey diagram visualization
        
        Returns:
            dict: {nodes, links} for visualization
        """
        if not flows:
            return {"nodes": [], "links": []}
        
        nodes = []
        links = []
        
        # Create virtual "Market" node
        nodes.append({"id": "market", "name": "MARKET"})
        
        # Add coin nodes and links
        for flow in flows:
            coin_id = flow['coin'].lower()
            nodes.append({
                "id": coin_id,
                "name": flow['coin'],
                "value": abs(flow['delta_12h'])
            })
            
            if flow['direction'] == 'inflow':
                # Market -> Coin (buying)
                links.append({
                    "source": "market",
                    "target": coin_id,
                    "value": abs(flow['delta_12h']),
                    "color": "#10b981"  # green
                })
            else:
                # Coin -> Market (selling)
                links.append({
                    "source": coin_id,
                    "target": "market",
                    "value": abs(flow['delta_12h']),
                    "color": "#ef4444"  # red
                })
        
        return {
            "nodes": nodes,
            "links": links,
            "timestamp": datetime.now().isoformat()
        }
