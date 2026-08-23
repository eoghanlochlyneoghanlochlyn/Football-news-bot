import os
import requests
from bs4 import BeautifulSoup
from google import genai

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cdx7x90dxywo?at_medium=RSS&at_campaign=rss"

print("در حال دریافت خبر...")

response = requests.get(
    NEWS_URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for tag in soup(["script","style","nav","footer","header","aside"]):
    tag.decompose()

paragraphs = []

for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)
    if len(text) >= 40:
        paragraphs.append(text)

news_text = "\n\n".join(paragraphs)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = f"""
تو سردبیر یک کانال خبری فوتبال هستی.

از متن زیر یک خبر حرفه‌ای فارسی تولید کن.

قوانین:

- ترجمه تحت‌اللفظی نکن.
- تیتر جذاب بنویس.
- متن ۴ تا ۶ جمله باشد.
- هر جمله باید اطلاعات جدیدی نسبت به جمله قبل داشته باشد.
- فقط از اطلاعات موجود در متن استفاده کن.
- هیچ چیز از خودت اضافه نکن.
- اگر موضوعی قطعی نیست، آن را قطعی بیان نکن.
- لحن شبیه رسانه‌های حرفه‌ای فارسی باشد.
- از ایموجی استفاده نکن.

متن:

{news_text}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

print()
print("========== نتیجه Gemini ==========")
print(response.text)
print("==================================")
