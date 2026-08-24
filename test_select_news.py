import os
import requests
from bs4 import BeautifulSoup
from google import genai

# ==========================================
# لینک خبر برای تست
# ==========================================

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cdrvr73egnlo?at_medium=RSS&at_campaign=rss"


# ==========================================
# دریافت متن خبر
# ==========================================

print("در حال دریافت خبر...")

response = requests.get(
    NEWS_URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# حذف بخش‌های غیرمرتبط
for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
    tag.decompose()

paragraphs = []

for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)

    if len(text) >= 40:
        paragraphs.append(text)

print(f"تعداد پاراگراف‌ها: {len(paragraphs)}")

# ==========================================
# تبدیل پاراگراف‌ها به جمله‌های شماره‌دار
# ==========================================

import re

sentences = []

for paragraph in paragraphs:
    parts = re.split(r'(?<=[.!?])\s+', paragraph)

    for part in parts:
        part = part.strip()

        if len(part) >= 20:
            sentences.append(part)

news_text = "\n".join(
    f"[{i}] {sentence}"
    for i, sentence in enumerate(sentences, start=1)
)

print(f"تعداد جمله‌ها: {len(sentences)}")
print(f"تعداد کاراکترهای متن: {len(news_text)}")

# ==========================================
# اتصال به Gemini
# ==========================================

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

# ==========================================
# دستور انتخاب جمله‌ها
# ==========================================

prompt = f"""
تو سردبیر یک کانال خبری هستی.

متن زیر یک خبر کامل است که جمله‌های آن شماره‌گذاری شده‌اند.

وظیفه تو فقط انتخاب مهم‌ترین جمله‌های موجود در متن است.

قوانین بسیار مهم:

1. تو حق بازنویسی، اصلاح، ترجمه یا تغییر هیچ جمله‌ای را نداری.
2. تو نباید جمله جدید بسازی.
3. تو نباید بخشی از یک جمله را تغییر بدهی.
4. فقط شماره جمله‌هایی را برگردان که برای یک خواننده مهم هستند.
5. بین 3 تا 6 جمله انتخاب کن.
6. جمله‌ها باید مهم‌ترین اطلاعات خبر را پوشش دهند.
7. اولویت با اصل اتفاق، نتیجه اصلی، اطلاعات کلیدی و پیامد مهم خبر است.
8. جمله‌های تکراری یا کم‌اهمیت را انتخاب نکن.
9. اگر یک جمله به‌تنهایی اطلاعات کافی ندارد، جمله مرتبط دیگری را انتخاب کن.
10. جمله‌های انتخاب‌شده باید تا حد امکان برای خواننده‌ای که مقاله کامل را نخوانده قابل فهم باشند.
11. ترتیب شماره‌ها باید مطابق ترتیب ظاهر شدن جمله‌ها در متن اصلی باشد.
12. اگر یک جمله نظر، ادعا یا نقل‌قول شخصی است، فقط در صورتی انتخابش کن که برای فهم اصل خبر اهمیت داشته باشد.
13. به هیچ عنوان اطلاعاتی را از خودت اضافه نکن.

فقط شماره جمله‌های انتخاب‌شده را با کاما جدا کن.

مثال:

3, 7, 12, 18

متن خبر:

{news_text}
"""

print()
print("در حال انتخاب جمله‌های کلیدی توسط Gemini...")

# ==========================================
# تنها درخواست Gemini برای این خبر
# ==========================================

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

selected_text = response.text.strip()

print()
print("========== شماره جمله‌های انتخاب‌شده ==========")
print(selected_text)
print("==============================================")

# ==========================================
# استخراج شماره‌ها
# ==========================================

numbers = re.findall(r'\d+', selected_text)

selected_numbers = []

for number in numbers:
    n = int(number)

    if 1 <= n <= len(sentences):
        if n not in selected_numbers:
            selected_numbers.append(n)

# ==========================================
# ساخت خبر نهایی توسط پایتون
# ==========================================

print()
print("========== خبر نهایی ==========")

for number in selected_numbers:
    print(sentences[number - 1])

print("================================")
