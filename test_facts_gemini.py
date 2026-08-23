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

for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
    tag.decompose()

paragraphs = []

for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)

    if len(text) >= 40:
        paragraphs.append(text)

news_text = "\n\n".join(paragraphs)

print(f"تعداد کاراکترهای متن دریافت‌شده: {len(news_text)}")

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو یک استخراج‌کننده دقیق اطلاعات خبری هستی.

وظیفه تو این است که فقط واقعیت‌های صریح و قابل استناد موجود در متن منبع را استخراج کنی.

فعلاً هیچ خبر، خلاصه، تیتر یا بازنویسی تولید نکن.

قوانین بسیار مهم:

1. فقط اطلاعاتی را بنویس که مستقیماً در متن منبع وجود دارند.
2. هیچ چیزی را از دانش قبلی یا حدس خودت اضافه نکن.
3. بین «ادعا»، «گزارش»، «اظهارنظر»، «تصمیم رسمی» و «واقعیت قطعی» تفاوت قائل شو.
4. اگر نتیجه یک پرونده، تحقیق یا تصمیم رسماً تأیید نشده، آن را تأییدشده معرفی نکن.
5. دو اتفاق جداگانه را به رابطه علت و معلولی تبدیل نکن.
6. اگر منبع درباره موضوعی عدم قطعیت دارد، همان عدم قطعیت را حفظ کن.
7. اطلاعات نامرتبط با موضوع اصلی مقاله را حذف کن.
8. هر واقعیت را در یک مورد جداگانه بنویس.
9. اعداد، تاریخ‌ها، نام افراد، باشگاه‌ها و وضعیت قراردادها را دقیقاً مطابق منبع حفظ کن.
10. اگر درباره یک موضوع اطلاعات کافی وجود ندارد، چیزی درباره آن حدس نزن.

موضوع اصلی خبر را ابتدا در یک خط مشخص کن.

سپس حداکثر 12 واقعیت مهم و مستقیم درباره موضوع اصلی را استخراج کن.

فرمت خروجی دقیقاً:

موضوع اصلی:
...

واقعیت‌ها:
1. ...
2. ...
3. ...
4. ...

متن منبع:
--------------------
{news_text}
--------------------
"""

print("در حال استخراج واقعیت‌ها توسط Gemini...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

print()
print("========== واقعیت‌های استخراج‌شده ==========")
print(response.text)
print("=============================================")
