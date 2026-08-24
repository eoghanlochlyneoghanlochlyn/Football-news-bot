import os
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
print(f"تعداد کاراکترهای متن: {len(news_text)}")
print("در حال پردازش خبر توسط Gemini...")

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو سردبیر یک رسانه خبری حرفه‌ای هستی.

متن زیر یک خبر کامل است. وظیفه تو این است که فقط بر اساس همین متن، یک خبر فارسی کوتاه و دقیق تولید کنی.

قوانین بسیار مهم:

1. فقط از اطلاعات موجود در متن استفاده کن.
2. هیچ نام، عدد، آمار، نقل‌قول، علت، نتیجه، سابقه یا جزئیاتی را که صراحتاً در متن وجود ندارد اضافه نکن.
3. چیزی را حدس نزن.
4. اگر درباره رابطه علت و معلولی چیزی در متن گفته نشده، خودت رابطه علت و معلولی ایجاد نکن.
5. اگر متن درباره ادعای یک شخص صحبت می‌کند، آن را به عنوان واقعیت قطعی بیان نکن.
6. اگر متن درباره یک احتمال، گزارش، ادعا یا موضع یک طرف صحبت می‌کند، همان میزان قطعیت را حفظ کن.
7. اطلاعات مربوط به افراد، باشگاه‌ها، مسابقات، تاریخ‌ها و اعداد را دقیقاً مطابق متن منتقل کن.
8. چند جمله یا چند رویداد متفاوت را با یکدیگر ترکیب نکن.
9. هنگام فشرده‌سازی، اطلاعات را طوری کنار هم قرار نده که معنای جدیدی ایجاد شود.
10. اگر برای کوتاه‌تر کردن خبر مجبور به حذف اطلاعات هستی، اطلاعات فرعی را حذف کن؛ نه اینکه اطلاعات باقی‌مانده را تغییر بدهی.
11. متن را به فارسی طبیعی و حرفه‌ای بنویس؛ ترجمه تحت‌اللفظی نکن.
12. اصطلاحات را بر اساس معنای واقعی جمله ترجمه کن، نه صرفاً ترجمه کلمه‌به‌کلمه.
13. از ایموجی استفاده نکن.
14. هیچ توضیحی درباره روش کارت نده.
15. فقط خروجی نهایی را ارائه کن.

ساختار خروجی:

عنوان:
یک تیتر کوتاه و دقیق.

خبر:
۴ تا ۶ جمله فارسی.

متن خبر:
{news_text}
"""

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

print()
print("========== نتیجه Gemini ==========")
print(response.text)
print("==================================")
