import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not api_key:
    raise ValueError(f"Gemini API key not found. Checked: {ENV_PATH}")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model=model,
    contents="Explain an AI customer support assistant in two sentences."
)

print(response.text)