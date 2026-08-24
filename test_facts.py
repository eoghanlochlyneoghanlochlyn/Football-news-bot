import os
import re
import requests
from bs4 import BeautifulSoup
from google import genai

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cdrvr73egnlo?at_medium=RSS&at_campaign=rss"

print("در حال دریافت خبر...")

response = requests.get(
    NEWS_URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
    tag.decompose()

paragraphs = []

for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)

    if len(text) >= 40:
        paragraphs.append(text)

news_text = "\n\n".join(paragraphs)

print(f"تعداد پاراگراف‌ها: {len(paragraphs)}")
print(f"تعداد کاراکترها: {len(news_text)}")

# تقسیم متن به جمله‌ها
sentences = re.split(r'(?<=[.!?])\s+', news_text)

numbered_text = "\n".join(
    f"[{i}] {sentence}"
    for i, sentence in enumerate(sentences, 1)
)

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو یک تحلیلگر خبر هستی.

متن زیر یک خبر کامل است.

وظیفه تو استخراج مهم‌ترین واقعیت‌های خبر است.

برای هر واقعیت این اطلاعات را بده:

FACT:
یک واقعیت کوتاه و دقیق که مستقیماً از متن قابل اثبات باشد.

EVIDENCE:
شماره جمله یا جمله‌هایی که آن واقعیت را پشتیبانی می‌کنند.

قوانین:

- فقط اطلاعاتی را استخراج کن که صراحتاً در متن وجود دارند.
- هیچ اطلاعاتی از دانش قبلی خودت اضافه نکن.
- هیچ رابطه علت و معلولی جدید ایجاد نکن.
- اگر متن فقط دو اتفاق را پشت سر هم بیان کرده، آنها را به عنوان رابطه علت و معلولی بیان نکن.
- اگر موضوعی قطعی نیست، میزان قطعیت متن اصلی را حفظ کن.
- هر FACT باید مستقل و قابل بررسی باشد.
- واقعیت‌های تکراری را ادغام کن.
- حداکثر 10 واقعیت اصلی استخراج کن.
- اخبار فرعی را فقط اگر برای فهم موضوع اصلی ضروری هستند وارد کن.
- شماره جمله‌ها باید دقیقاً از شماره‌هایی باشند که در متن آمده‌اند.

قالب خروجی دقیقاً:

FACT 1:
...
EVIDENCE:
[شماره]

FACT 2:
...
EVIDENCE:
[شماره]

و به همین ترتیب.

متن خبر:

========================

{numbered_text}

========================
"""

print("در حال استخراج واقعیت‌های اتمی توسط Gemini...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

print()
print("========== واقعیت‌های استخراج‌شده ==========")
print(response.text)
print("============================================")
