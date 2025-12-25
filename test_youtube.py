from youtube_analyzer import analyze_youtube_alpha
import os
from dotenv import load_dotenv

load_dotenv()

print("Running YouTube Analyzer with dummy data...")
summary = "Market is bullish. BTC is 100k."
try:
    result = analyze_youtube_alpha(summary)
    print("Result length:", len(result))
    print("First 100 chars:", result[:100])
    if "⚠️" in result and "failed" in result:
        print("❌ Analysis Failed")
    else:
        print("✅ Analysis Success")
except Exception as e:
    print(f"❌ Exception: {e}")
