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
# پرامپت انتخاب جمله‌ها
# ==========================================

prompt = f"""
تو سردبیر یک کانال خبری فوتبال هستی.

متن زیر یک خبر کامل است و تمام جمله‌های آن شماره‌گذاری شده‌اند.

وظیفه تو فقط انتخاب مهم‌ترین جمله‌های موجود در متن است.

قوانین بسیار مهم:

1. فقط جمله‌های موجود در متن را انتخاب کن.
2. حق بازنویسی، ترجمه، اصلاح یا تغییر حتی یک کلمه از جمله‌ها را نداری.
3. جمله جدید نساز.
4. اطلاعاتی از خودت اضافه نکن.
5. بین 3 تا 6 جمله انتخاب کن.
6. جمله‌هایی را انتخاب کن که اگر خواننده فقط همان‌ها را بخواند، اصل خبر را بفهمد.
7. اولویت با اتفاق اصلی، نتیجه اصلی و مهم‌ترین جزئیات مرتبط با اتفاق اصلی است.
8. جمله‌های صرفاً تحلیلی، کلی یا مبهم را تا حد امکان انتخاب نکن.
9. جمله‌هایی را که بدون داشتن متن قبلی معنای ناقصی دارند انتخاب نکن، مگر اینکه برای فهم خبر ضروری باشند.
10. نقل‌قول یا نظر افراد را فقط در صورتی انتخاب کن که برای اصل خبر اهمیت داشته باشد.
11. اطلاعات تکراری را انتخاب نکن.
12. اگر یک جمله خبری اطلاعات بیشتری نسبت به یک جمله دیگر ارائه می‌کند، جمله کامل‌تر را ترجیح بده.
13. ترتیب شماره‌ها باید مطابق ترتیب ظاهر شدن جمله‌ها در متن اصلی باشد.
14. فقط شماره جمله‌ها را با کاما جدا کن.
15. هیچ توضیح دیگری ننویس.

مثال خروجی:

2, 3, 15, 19

متن خبر:

{news_text}
"""


# ==========================================
# تنها درخواست Gemini
# ==========================================

print()
print("در حال انتخاب جمله‌های کلیدی توسط Gemini...")

gemini_response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=prompt
)

selected_text = gemini_response.text.strip()

print()
print("========== شماره جمله‌های انتخاب‌شده ==========")
print(selected_text)
print("==============================================")


# ==========================================
# استخراج شماره جمله‌ها
# ==========================================

numbers = re.findall(r'\d+', selected_text)

selected_numbers = []

for number in numbers:
    n = int(number)

    if 1 <= n <= len(sentences):
        if n not in selected_numbers:
            selected_numbers.append(n)


# ==========================================
# ساخت خروجی نهایی توسط Python
# ==========================================

final_sentences = []

for number in selected_numbers:
    final_sentences.append(sentences[number - 1])

final_news = "\n\n".join(final_sentences)


print()
print("========== خبر نهایی ==========")
print(final_news)
print("================================")


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
