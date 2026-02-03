
from market_calendar import init_market_calendar

print("Initializing Calendar...")
calendar = init_market_calendar()
print("Getting Risk Context...")
ctx = calendar.get_live_risk_context()
print(f"Risk Context: {ctx}")
