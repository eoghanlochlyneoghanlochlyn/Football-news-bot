import os
import requests
from bs4 import BeautifulSoup
from google import genai

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cygj01pr0p0o?at_medium=RSS&at_campaign=rss"

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

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو سردبیر ارشد یک خبرگزاری فوتبال هستی.

متن زیر مستقیماً از یک صفحه خبری استخراج شده است.
ممکن است علاوه بر خبر اصلی شامل پیشینه، تحلیل، اخبار مرتبط، معرفی بازیکنان، لینک به مطالب دیگر و توضیحات جانبی نیز باشد.

قبل از تولید پاسخ، این مراحل را در ذهن خود انجام بده:

مرحله ۱:
موضوع اصلی مقاله را تشخیص بده.

مرحله ۲:
تمام اطلاعاتی که فقط به موضوع اصلی مربوط هستند انتخاب کن.

مرحله ۳:
اطلاعاتی که فقط پیشینه، تحلیل، خبر دیگر یا موضوع فرعی هستند حذف کن؛
مگر اینکه برای فهم خبر اصلی ضروری باشند.

مرحله ۴:
مطمئن شو که:

- هیچ واقعیتی تغییر نکرده باشد.
- هیچ اطلاعات جدیدی اضافه نشده باشد.
- هیچ نتیجه‌گیری شخصی انجام نشده باشد.
- رابطه علت و معلولی جدید ساخته نشده باشد.
- میزان قطعیت متن حفظ شده باشد.
- اگر متن گفته «منابع گفته‌اند»، «ادعا می‌شود»، «هنوز تأیید نشده»، «احتمال دارد»، همان سطح قطعیت حفظ شود.

مرحله ۵:
اکنون خبر نهایی را بنویس.

قوانین خروجی:

- فقط خبر نهایی را چاپ کن.
- مراحل بالا را نمایش نده.
- تیتر کوتاه و حرفه‌ای باشد.
- متن ۴ تا ۶ جمله باشد.
- هر جمله اطلاعات جدیدی اضافه کند.
- تیتر را دوباره تکرار نکن.
- متن کاملاً روان و شبیه رسانه‌های حرفه‌ای فارسی باشد.
- از ترجمه تحت‌اللفظی خودداری کن.
- از اغراق، تحلیل شخصی و پیش‌بینی استفاده نکن.
- اگر درباره موضوعی مطمئن نیستی، آن را حذف کن.
- از ایموجی استفاده نکن.

متن مقاله:

-------------------------

{news_text}

-------------------------
"""

print("در حال ارسال متن به Gemini...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

print()
print("========== نتیجه Gemini ==========")
print(response.text)
print("==================================")
