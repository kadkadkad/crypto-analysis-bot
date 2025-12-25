from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

try:
    print("Listing models...")
    # The new SDK might use a different way to list models, checking available methods
    # For now, let's try to infer from common names or if there is a list_models method
    # Looking at the message "Call ListModels to see the list..."
    
    for model in client.models.list():
        if "gemini" in model.name and "flash" in model.name:
            print(f"Model: {model.name}")

except Exception as e:
    print(f"Error listing models: {e}")
