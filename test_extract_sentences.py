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
print(f"تعداد کاراکترهای متن دریافت‌شده: {len(news_text)}")

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو یک دبیر خبر فوتبال هستی.

متن زیر یک مقاله خبری کامل است.

وظیفه تو فقط انتخاب جمله‌های موجود در متن است.

هدف:
انتخاب 5 تا 8 جمله که در کنار یکدیگر مهم‌ترین اطلاعات خبر اصلی را منتقل کنند.

قوانین بسیار مهم:

1. فقط جمله‌هایی را انتخاب کن که عیناً در متن وجود دارند.
2. هیچ جمله‌ای را بازنویسی نکن.
3. هیچ کلمه‌ای را تغییر نده.
4. هیچ جمله جدیدی تولید نکن.
5. هیچ اطلاعاتی از خودت اضافه نکن.
6. جمله‌هایی را انتخاب کن که مستقیماً به خبر اصلی مربوط هستند.
7. تحلیل، نظر، پیش‌بینی و اطلاعات فرعی را تا حد امکان انتخاب نکن.
8. ترتیب جمله‌ها باید همان ترتیب قرارگیری آنها در متن اصلی باشد.
9. اگر یک جمله بدون جمله قبلی معنای ناقصی دارد، جمله مرتبط قبلی را نیز انتخاب کن.
10. فقط شماره جمله‌های انتخاب‌شده را برگردان.
11. شماره‌ها را از 1 شروع کن.
12. هیچ توضیح دیگری ننویس.

مثال خروجی:

2, 3, 5, 7, 8, 11

متن مقاله:

-------------------------

{news_text}

-------------------------
"""

print("در حال انتخاب جمله‌های کلیدی توسط Gemini...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

selected_text = response.text.strip()

print()
print("========== شماره جمله‌های انتخاب‌شده ==========")
print(selected_text)
print("==============================================")

# جدا کردن جمله‌های متن اصلی
sentences = re.split(r'(?<=[.!?])\s+', news_text)

print()
print("========== جمله‌های انتخاب‌شده ==========")

selected_numbers = re.findall(r'\d+', selected_text)

for number in selected_numbers:
    index = int(number) - 1

    if 0 <= index < len(sentences):
        print(f"\n[{number}] {sentences[index]}")

print()
print("==========================================")
