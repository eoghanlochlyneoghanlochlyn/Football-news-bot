import os
from google import genai


api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY پیدا نشد.")


client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="در یک جمله کوتاه بگو فوتبال چیست؟"
)

print("پاسخ هوش مصنوعی:")
print(response.text)
