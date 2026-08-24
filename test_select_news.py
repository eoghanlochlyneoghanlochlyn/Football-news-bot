import os
import re
import requests
from bs4 import BeautifulSoup
from google import genai

# ==========================================
# تنظیمات
# ==========================================

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cdrvr73egnlo?at_medium=RSS&at_campaign=rss"
GEMINI_MODEL = "gemini-3.5-flash-lite"


# ==========================================
# دریافت خبر
# ==========================================

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

print(f"تعداد پاراگراف‌ها: {len(paragraphs)}")


# ==========================================
# تبدیل متن به جمله‌های شماره‌دار
# ==========================================

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
# پرامپت
# ==========================================

prompt = f"""
تو مترجم و ویراستار یک کانال خبری فوتبال هستی.

متن زیر یک خبر کامل است و جمله‌های آن شماره‌گذاری شده‌اند.

وظیفه تو:
از میان جمله‌های خبر، مهم‌ترین جمله‌ها را انتخاب کن و همان اطلاعات را
به فارسی روان ترجمه کن.

این کار خلاصه‌سازی آزاد نیست.
تو نباید خبر را از خودت بازنویسی کنی.

قوانین:

1. بین 3 تا 6 جمله مهم را انتخاب کن.
2. فقط اطلاعات موجود در متن را منتقل کن.
3. هیچ اطلاعاتی از خودت اضافه نکن.
4. اطلاعات چند جمله را با هم ترکیب نکن.
5. رابطه علت و معلول جدید ایجاد نکن.
6. عدد، نتیجه، دقیقه، تاریخ، آمار و نام‌ها را دقیق حفظ کن.
7. ترتیب اتفاق‌ها را تغییر نده.
8. جمله‌های کلی و تحلیلی را تا حد امکان انتخاب نکن.
9. جمله‌ای که بدون زمینه قبلی مبهم است انتخاب نکن، مگر اینکه ضروری باشد.
10. نقل‌قول‌ها را تحریف نکن.
11. اصطلاحات فوتبال را با معادل رایج فارسی ترجمه کن.
12. برای مثال fast break در فوتبال را «ضدحمله» ترجمه کن.
13. ترجمه باید فارسی طبیعی باشد، اما نباید به بازنویسی آزاد تبدیل شود.
14. تیتر جدید نساز.
15. تحلیل یا نتیجه‌گیری جدید اضافه نکن.
16. فقط متن نهایی فارسی را خروجی بده.
17. بین بخش‌های مختلف یک خط خالی قرار بده.
18. متن نهایی برای انتشار در تلگرام کوتاه و خوانا باشد.

متن خبر:

{news_text}
"""


# ==========================================
# تنها درخواست Gemini
# ==========================================

print()
print("در حال پردازش خبر توسط Gemini...")

gemini_response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=prompt
)

final_news = gemini_response.text.strip()


# ==========================================
# نمایش نتیجه
# ==========================================

print()
print("========== نتیجه فارسی Gemini ==========")
print(final_news)
print("========================================")


# ==========================================
# ارسال به تلگرام
# ==========================================

print()
print("در حال ارسال خبر به تلگرام...")

telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

telegram_url = (
    f"https://api.telegram.org/bot{telegram_token}/sendMessage"
)

telegram_data = {
    "chat_id": telegram_chat_id,
    "text": final_news
}

telegram_response = requests.post(
    telegram_url,
    data=telegram_data,
    timeout=30
)

telegram_response.raise_for_status()

print("خبر با موفقیت در تلگرام منتشر شد.")
