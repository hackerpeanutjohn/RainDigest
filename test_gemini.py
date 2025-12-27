import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Fallback to input if not in env
    api_key = input("Enter your Gemini API Key: ")

print(f"Using Key: {api_key[:5]}...{api_key[-3:]}")
genai.configure(api_key=api_key)

print("\n--- Listing Available Models ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Name: {m.name}")
            print(f" - Display: {m.display_name}")
            print(f" - Version: {m.version}")

    model_name = 'gemini-1.5-flash-latest' # Try the one we used
    print(f"\n--- Testing Generation with {model_name} ---")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Hello, can you hear me?")
    print(f"Response: {response.text}")
    print("SUCCESS!")

except Exception as e:
    print(f"\nERROR: {e}")
    print("If you got a 404 on the model, try using one of the names listed above.")
