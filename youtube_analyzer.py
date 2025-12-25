import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
import config
import os
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential


# New Providers
from huggingface_hub import InferenceClient
from groq import Groq
import time
import random


# YouTube Channel IDs - Reduced to 3 to prevent IP bans
CHANNELS = {
    # Top 3 Most Important Channels (to avoid YouTube IP blocking)
    "MoreCryptoOnline": "UCngIhBkikUe6e7tZTjpKK7Q",
    "Coin Bureau": "UCqK_GSMbpiV8spgD3ZGloSw",
    "Cilinix Crypto": "UC8QWLZNoN3whQ7QMwoDp78A"
}

def get_latest_video_id(channel_id):
    """Fetches the latest video ID from a YouTube channel via RSS."""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            return feed.entries[0].id.split(':')[-1], feed.entries[0].title
    except Exception as e:
        print(f"[ERROR] RSS fetch failed for {channel_id}: {e}")
    return None, None

def get_transcript(video_id):
    """Retrieves the text transcript of a YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id, languages=['en', 'tr'])
        text = " ".join([i.text for i in transcript_list])
        return text
    except Exception as e:
        print(f"[ERROR] Transcript fetch failed for {video_id}: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_with_gemini(api_key, prompt):
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=prompt
    )
    return response.text

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_with_groq(api_key, prompt):
    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    )
    return chat_completion.choices[0].message.content

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_with_huggingface(api_key, prompt):
    client = InferenceClient(api_key=api_key)
    messages = [{"role": "user", "content": prompt}]
    # Using a reliable free model
    response = client.chat_completion(
        model="mistralai/Mistral-7B-Instruct-v0.3",
        messages=messages,
        max_tokens=2000 
    )
    return response.choices[0].message.content

def analyze_youtube_alpha(market_data_summary):
    """
    Fetches latest video transcripts and analyzes them with the best available LLM.
    Priority: Groq (Fast) -> Hugging Face (Backup) -> Gemini (Fallback)
    """
    

    # Retrieve keys
    groq_key = os.getenv("GROQ_API_KEY")
    hf_token = os.getenv("HF_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # Priority Order
    providers = []
    if groq_key: providers.append(("GROQ", groq_key))
    if hf_token: providers.append(("HF", hf_token))
    if gemini_key: providers.append(("GEMINI", gemini_key))

    if not providers:
        return "⚠️ No API keys found (Groq, HF, or Gemini). Check .env file."

    # Fetch Data
    all_content = []
    print(f"[INFO] Fetching transcripts from {len(CHANNELS)} channels...")
    
    for name, cid in CHANNELS.items():
        vid, title = get_latest_video_id(cid)
        if vid:
            print(f"[DEBUG] Fetching transcript for {name}: {title}")
            delay = random.uniform(5, 10)
            time.sleep(delay)
            text = get_transcript(vid)
            if text:
                all_content.append(f"CHANNEL: {name}\nTITLE: {title}\nTRANSCRIPT: {text[:10000]}")

    if not all_content:
        return "⚠️ Could not retrieve any recent YouTube transcripts."

    # SMART CONTEXT MANAGEMENT
    # Limit to 3 videos for small models (Groq/HF), but 20 for Gemini
    # We prepare short context first
    short_context_content = all_content[:3]
    long_context_content = all_content[:20]

    # Try providers in order
    last_error = ""
    
    for provider_name, api_key in providers:
        try:
            print(f"[INFO] Attempting analysis with Provider: {provider_name}")
            
            # Select appropriate context
            if provider_name in ["GROQ", "HF"]:
                current_content = short_context_content
                if len(all_content) > 3:
                     print(f"[WARN] {provider_name} has small context. Analyzing top 3 videos.")
            else:
                current_content = long_context_content

            combined_transcripts = "\n\n===\n\n".join(current_content)
            
            prompt = f"""
            You are an expert Crypto Market Analyst.
            
            MARKET DATA: {market_data_summary}
            TRANSCRIPTS: {combined_transcripts}

            Task:
            1. Identify coins mentioned in these specific videos.
            2. Summarize the sentiment (Bullish/Bearish) for each.
            3. Cross-reference with the provided Market Data (RSI, Price, etc.).
            4. Provide an 'Alpha Rating' (1-10) based on specific trade potential.

            **IMPORTANT:** ALL OUTPUT MUST BE IN ENGLISH.

            Output Markdown:
            # 📺 YouTube Alpha Report ({provider_name})
            ## 🪙 Coin Insights
            * **[Coin Symbol]**: [Sentiment]
              - *Reasoning*: ...
              - *Tech Check*: ... (Matches market data?)
            ## 🚀 Top Opportunities
            * [List high confidence plays]
            """
            
            if provider_name == "GROQ":
                return generate_with_groq(api_key, prompt)
            elif provider_name == "HF":
                return generate_with_huggingface(api_key, prompt)
            elif provider_name == "GEMINI":
                return generate_with_gemini(api_key, prompt)
                
        except Exception as e:
            print(f"[WARN] Provider {provider_name} failed: {e}")
            last_error = str(e)
            continue # Try next provider

    return f"⚠️ All analysis providers failed. Last error: {last_error}"
