import os
import youtube_analyzer
from unittest.mock import patch

def test_provider_selection():
    print("Testing Provider Selection Logic...")
    
    # Test 1: Only Gemini Key
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test", "GROQ_API_KEY": "", "HF_TOKEN": ""}):
        # Mocking generate functions to avoid actual API calls
        with patch('youtube_analyzer.generate_with_gemini') as mock_gemini:
             mock_gemini.return_value = "Gemini Response"
             # We also need to mock fetching to avoid networking
             with patch('youtube_analyzer.get_latest_video_id', return_value=("123", "Test Title")):
                 with patch('youtube_analyzer.get_transcript', return_value="Transcript"):
                     res = youtube_analyzer.analyze_youtube_alpha("Market Data")
                     print(f"Test Gemini Only: {'Pass' if 'Gemini Response' in res else 'Fail'}")

    # Test 2: Groq Key Present (Should take priority)
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test", "GROQ_API_KEY": "groq_key", "HF_TOKEN": ""}):
        with patch('youtube_analyzer.generate_with_groq') as mock_groq:
             mock_groq.return_value = "Groq Response"
             with patch('youtube_analyzer.get_latest_video_id', return_value=("123", "Test Title")):
                 with patch('youtube_analyzer.get_transcript', return_value="Transcript"):
                     res = youtube_analyzer.analyze_youtube_alpha("Market Data")
                     print(f"Test Groq Priority: {'Pass' if 'Groq Response' in res else 'Fail'}")

    # Test 3: HF Token Present (No Groq)
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test", "GROQ_API_KEY": "", "HF_TOKEN": "hf_token"}):
        with patch('youtube_analyzer.generate_with_huggingface') as mock_hf:
             mock_hf.return_value = "HF Response"
             with patch('youtube_analyzer.get_latest_video_id', return_value=("123", "Test Title")):
                 with patch('youtube_analyzer.get_transcript', return_value="Transcript"):
                     res = youtube_analyzer.analyze_youtube_alpha("Market Data")
                     print(f"Test HF Priority: {'Pass' if 'HF Response' in res else 'Fail'}")

if __name__ == "__main__":
    try:
        test_provider_selection()
        print("✅ Logic verification complete.")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
