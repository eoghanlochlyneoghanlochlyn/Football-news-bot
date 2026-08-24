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
print(f"تعداد کاراکترهای متن: {len(news_text)}")

# تقسیم متن به جمله‌ها
sentences = re.split(r'(?<=[.!?])\s+', news_text)

# شماره‌گذاری جمله‌ها
numbered_text = "\n".join(
    f"[{i}] {sentence}"
    for i, sentence in enumerate(sentences, 1)
)

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
تو یک تحلیلگر دقیق اخبار فوتبال هستی.

متن زیر یک خبر کامل است.

وظیفه تو استخراج مهم‌ترین واقعیت‌های خبر است.

برای هر واقعیت، سه مورد ارائه کن:

FACT:
یک واقعیت کوتاه و دقیق.

EVIDENCE:
شماره جمله یا جمله‌هایی که مستقیماً آن واقعیت را پشتیبانی می‌کنند.

EVIDENCE TEXT:
متن دقیق همان جمله‌ها، بدون هیچ تغییر، ترجمه یا بازنویسی.

قوانین بسیار مهم:

1. فقط اطلاعاتی را استخراج کن که صراحتاً در متن وجود دارند.

2. هیچ اطلاعاتی از دانش قبلی خودت اضافه نکن.

3. هیچ رابطه علت و معلولی جدید ایجاد نکن.

4. اگر متن فقط دو اتفاق را پشت سر هم بیان کرده، آنها را به عنوان رابطه علت و معلولی بیان نکن.

5. اگر موضوعی قطعی نیست، میزان قطعیت متن اصلی را حفظ کن.

6. هر FACT باید مستقیماً توسط EVIDENCE TEXT قابل اثبات باشد.

7. EVIDENCE TEXT باید دقیقاً کپی جمله‌های اصلی باشد.

8. حتی یک کلمه از EVIDENCE TEXT را تغییر نده.

9. اگر چند جمله برای اثبات یک واقعیت لازم است، همه آنها را بیاور.

10. واقعیت‌های تکراری را ادغام کن.

11. حداکثر 10 واقعیت اصلی استخراج کن.

12. اطلاعات فرعی را فقط در صورتی انتخاب کن که برای فهم خبر اصلی مهم باشند.

13. شماره جمله‌ها باید دقیقاً مطابق شماره‌گذاری متن باشند.

14. ترتیب واقعیت‌ها را مطابق ترتیب وقوع یا مطرح‌شدن آنها در متن حفظ کن.

قالب خروجی:

FACT 1:
...

EVIDENCE:
[شماره]

EVIDENCE TEXT:
[متن دقیق جمله]

FACT 2:
...

EVIDENCE:
[شماره]

EVIDENCE TEXT:
[متن دقیق جمله]

و به همین ترتیب.

متن خبر:

========================

{numbered_text}

========================
"""

print("در حال استخراج واقعیت‌ها توسط Gemini...")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

print()
print("========== واقعیت‌های استخراج‌شده ==========")
print(response.text)
print("============================================")
