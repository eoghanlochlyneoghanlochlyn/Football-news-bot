import json
import os
import time
from typing import Optional

import requests


# ============================================================
# تنظیمات
# ============================================================

# حداکثر ۵ کلید Gemini
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1", "").strip(),
    os.getenv("GEMINI_API_KEY_2", "").strip(),
    os.getenv("GEMINI_API_KEY_3", "").strip(),
    os.getenv("GEMINI_API_KEY_4", "").strip(),
    os.getenv("GEMINI_API_KEY_5", "").strip(),
]

# حذف کلیدهای خالی
GEMINI_API_KEYS = [
    key for key in GEMINI_API_KEYS
    if key
]

# مدل را می‌توان بدون تغییر کد عوض کرد.
# اگر در GitHub متغیر GEMINI_MODEL تعریف نشده باشد،
# این مقدار استفاده می‌شود.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
).strip()

# آدرس API
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# حداکثر طول متن ورودی
# برای جلوگیری از مصرف بی‌مورد توکن
MAX_ARTICLE_LENGTH = 12000

# زمان انتظار درخواست
REQUEST_TIMEOUT = 60

# تعداد تلاش برای هر کلید
MAX_ATTEMPTS_PER_KEY = 1

# فاصله کوتاه بین تلاش‌ها
RETRY_DELAY_SECONDS = 2
# محدودیت سرعت Gemini
# حدود 12 درخواست در دقیقه
GEMINI_RATE_LIMIT_DELAY = 5.2


# ============================================================
# دستور اصلی به Gemini
# ============================================================

SYSTEM_PROMPT = """
تو یک ویراستار و مترجم حرفه‌ای اخبار فوتبال برای یک کانال خبری فارسی هستی.

وظیفه تو این است که خبر فوتبال انگلیسی را به فارسی طبیعی، روان و خبری ترجمه و بازنویسی کنی.

قوانین بسیار مهم:

1. اطلاعات جدیدی که در متن اصلی وجود ندارد اضافه نکن.

2. حدس نزن.

3. اگر درباره بازیکن، مربی، باشگاه، مبلغ، تاریخ، قرارداد یا هر موضوع دیگری
اطلاعاتی در متن اصلی وجود دارد، همان اطلاعات را حفظ کن.

4. اسم بازیکنان، مربیان، باشگاه‌ها و رقابت‌ها را به شکل رایج فارسی بنویس.
اگر درباره شکل فارسی یک نام مطمئن نیستی، نام اصلی را حفظ کن.

5. ترجمه نباید کلمه‌به‌کلمه و خشک باشد.
متن باید مثل یک خبر فوتبال فارسی نوشته شود.

6. لحن باید حرفه‌ای، طبیعی و نسبتاً کوتاه باشد.

7. از ایموجی استفاده نکن.
ایموجی‌ها در مرحله قالب‌بندی اضافه خواهند شد.

8. لینک، نشانی اینترنتی یا کد HTML تولید نکن.

9. عنوان را جذاب و خبری ترجمه کن، اما معنای آن را تغییر نده.

10. اگر متن اصلی شامل نقل‌قول است، مفهوم نقل‌قول را حفظ کن و چیزی به آن اضافه نکن.

11. اگر متن اصلی مبهم است، ابهام را حفظ کن و آن را به یک واقعیت قطعی تبدیل نکن.

12. از عباراتی مانند «به نظر می‌رسد» یا «احتمالاً» فقط زمانی استفاده کن که
خود متن اصلی چنین احتمالی را بیان کرده باشد.

13. خروجی باید فقط یک شیء JSON معتبر باشد و هیچ متن دیگری خارج از JSON نباشد.

ساختار دقیق خروجی:

{
  "title": "عنوان فارسی خبر",
  "body": "متن فارسی خبر"
}
"""


# ============================================================
# تمیز کردن پاسخ Gemini
# ============================================================

def clean_model_response(text: str) -> str:

    if not text:
        return ""

    text = text.strip()

    # اگر مدل به اشتباه Markdown code fence اضافه کرد
    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ============================================================
# استخراج متن پاسخ Gemini
# ============================================================

def extract_gemini_text(data: dict) -> str:

    try:

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:
            return ""

        first_candidate = candidates[0]

        content = first_candidate.get(
            "content",
            {}
        )

        parts = content.get(
            "parts",
            []
        )

        texts = []

        for part in parts:

            if not isinstance(part, dict):
                continue

            text = part.get(
                "text",
                ""
            )

            if text:
                texts.append(text)

        return "\n".join(texts).strip()

    except Exception:

        return ""


# ============================================================
# اعتبارسنجی خروجی
# ============================================================

def validate_translation(data):

    if not isinstance(data, dict):
        return None

    title = data.get(
        "title",
        ""
    )

    body = data.get(
        "body",
        ""
    )

    if not isinstance(title, str):
        return None

    if not isinstance(body, str):
        return None

    title = title.strip()
    body = body.strip()

    if not title:
        return None

    if not body:
        return None

    # جلوگیری از خروجی‌های خیلی غیرعادی
    if len(title) > 500:
        return None

    if len(body) > 15000:
        return None

    return {
        "title": title,
        "body": body
    }


# ============================================================
# ارسال درخواست به Gemini
# ============================================================

def request_gemini(
    api_key: str,
    article_title: str,
    article_text: str
):

    prompt = (
        SYSTEM_PROMPT
        + "\n\n"
        + "عنوان اصلی:\n"
        + article_title.strip()
        + "\n\n"
        + "متن خبر:\n"
        + article_text.strip()
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    url = (
        GEMINI_API_URL
        + "?key="
        + api_key
    )
    
time.sleep(GEMINI_RATE_LIMIT_DELAY)

response = requests.post(
    url,
    json=payload,
    headers={
        "Content-Type": "application/json"
    },
    timeout=REQUEST_TIMEOUT
)
    
    response = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json"
        },
        timeout=REQUEST_TIMEOUT
    )

    # --------------------------------------------------------
    # موفق
    # --------------------------------------------------------

    if response.ok:

        try:

            response_data = response.json()

        except Exception:

            raise RuntimeError(
                "پاسخ Gemini قابل خواندن نیست."
            )

        text = extract_gemini_text(
            response_data
        )

        if not text:

            raise RuntimeError(
                "Gemini پاسخ متنی معتبری برنگرداند."
            )

        text = clean_model_response(
            text
        )

        try:

            parsed = json.loads(
                text
            )

        except json.JSONDecodeError:

            raise RuntimeError(
                "خروجی Gemini JSON معتبر نیست."
            )

        result = validate_translation(
            parsed
        )

        if not result:

            raise RuntimeError(
                "ساختار خروجی Gemini معتبر نیست."
            )

        return result

    # --------------------------------------------------------
    # خطا
    # --------------------------------------------------------

    status_code = response.status_code

    try:

        error_data = response.json()

        error_message = (
            error_data
            .get("error", {})
            .get("message", "")
        )

    except Exception:

        error_message = ""

    if not error_message:
        error_message = response.text[:500]

    raise RuntimeError(
        f"Gemini HTTP {status_code}: "
        f"{error_message}"
    )


# ============================================================
# استخراج متن خبر
# ============================================================

def extract_article_text(news):

    if not isinstance(news, dict):
        return ""

    # --------------------------------------------------------
    # متن اصلی اگر قبلاً استخراج شده باشد
    # --------------------------------------------------------

    for key in [
        "text",
        "content",
        "description",
        "summary"
    ]:

        value = news.get(key)

        if isinstance(value, str) and value.strip():

            return value.strip()

    # --------------------------------------------------------
    # بعضی ساختارهای RSS
    # --------------------------------------------------------

    entry = news.get(
        "entry"
    )

    if isinstance(entry, dict):

        for key in [
            "content",
            "description",
            "summary"
        ]:

            value = entry.get(key)

            if isinstance(
                value,
                list
            ):

                parts = []

                for item in value:

                    if isinstance(
                        item,
                        dict
                    ):

                        text = item.get(
                            "value",
                            ""
                        )

                        if text:
                            parts.append(
                                str(text)
                            )

                if parts:

                    return "\n".join(
                        parts
                    ).strip()

            elif isinstance(
                value,
                str
            ) and value.strip():

                return value.strip()

    return ""


# ============================================================
# حذف HTML از متن
# ============================================================

def strip_html(text):

    if not text:
        return ""

    import re
    import html

    text = html.unescape(
        str(text)
    )

    # حذف script و style
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # تبدیل چند تگ رایج به فاصله
    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"</p\s*>",
        "\n",
        text,
        flags=re.IGNORECASE
    )

    # حذف سایر تگ‌ها
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # فشرده‌سازی فاصله‌ها
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# کوتاه کردن متن بسیار طولانی
# ============================================================

def limit_article_length(text):

    if len(text) <= MAX_ARTICLE_LENGTH:
        return text

    print(
        f"⚠️ متن خبر بیش از {MAX_ARTICLE_LENGTH} "
        "کاراکتر است و کوتاه می‌شود."
    )

    return text[:MAX_ARTICLE_LENGTH].rstrip()


# ============================================================
# ترجمه و بازنویسی خبر
# ============================================================

def translate_news(news):

    if not isinstance(news, dict):

        return {
            "success": False,
            "title": "",
            "body": "",
            "error": "ساختار خبر نامعتبر است."
        }

    article_title = str(
        news.get(
            "title",
            ""
        )
    ).strip()

    if not article_title:

        return {
            "success": False,
            "title": "",
            "body": "",
            "error": "عنوان خبر وجود ندارد."
        }

    article_text = extract_article_text(
        news
    )

    article_text = strip_html(
        article_text
    )

    # --------------------------------------------------------
    # اگر متن خبر موجود نبود
    # --------------------------------------------------------

    if not article_text:

        print(
            "⚠️ متن کامل خبر موجود نیست."
        )

        # در این حالت فقط عنوان را برای Gemini می‌فرستیم.
        article_text = (
            "متن کامل خبر در دسترس نیست. "
            "فقط بر اساس عنوان، آن را به عنوان یک "
            "عنوان خبری فارسی ترجمه کن و در body "
            "توضیح اضافه‌ای ارائه نکن."
        )

    article_text = limit_article_length(
        article_text
    )

    # --------------------------------------------------------
    # بررسی کلیدها
    # --------------------------------------------------------

    if not GEMINI_API_KEYS:

        return {
            "success": False,
            "title": "",
            "body": "",
            "error": (
                "هیچ GEMINI_API_KEY_1 تا "
                "GEMINI_API_KEY_5 تنظیم نشده است."
            )
        }

    print(
        f"در حال ترجمه خبر با Gemini "
        f"(تعداد کلیدهای فعال: {len(GEMINI_API_KEYS)})..."
    )

    # --------------------------------------------------------
    # امتحان کردن کلیدها
    # --------------------------------------------------------

    errors = []

    for index, api_key in enumerate(
        GEMINI_API_KEYS,
        start=1
    ):

        print(
            f"در حال امتحان کلید Gemini شماره {index}..."
        )

        for attempt in range(
            MAX_ATTEMPTS_PER_KEY
        ):

            try:

                result = request_gemini(
                    api_key=api_key,
                    article_title=article_title,
                    article_text=article_text
                )

                print(
                    f"✓ ترجمه با کلید Gemini شماره "
                    f"{index} با موفقیت انجام شد."
                )

                return {
                    "success": True,
                    "title": result["title"],
                    "body": result["body"],
                    "error": ""
                }

            except Exception as error:

                error_text = str(
                    error
                )

                errors.append(
                    f"کلید {index}: {error_text}"
                )

                print(
                    f"⚠️ کلید Gemini شماره {index} "
                    f"ناموفق بود: {error_text}"
                )

                if (
                    attempt
                    < MAX_ATTEMPTS_PER_KEY - 1
                ):

                    time.sleep(
                        RETRY_DELAY_SECONDS
                    )

        # ----------------------------------------------------
        # قبل از رفتن به کلید بعدی
        # ----------------------------------------------------

        if index < len(
            GEMINI_API_KEYS
        ):

            print(
                "در حال استفاده از کلید Gemini بعدی..."
            )

    # --------------------------------------------------------
    # همه کلیدها شکست خوردند
    # --------------------------------------------------------

    print(
        "❌ تمام کلیدهای Gemini ناموفق بودند."
    )

    return {
        "success": False,
        "title": "",
        "body": "",
        "error": " | ".join(errors)
    }


# ============================================================
# تابع ساده برای استفاده در main.py
# ============================================================

def translate_title_and_text(
    title,
    text
):

    news = {
        "title": title,
        "text": text
    }

    return translate_news(
        news
    )


# ============================================================
# تست مستقیم فایل
# ============================================================

if __name__ == "__main__":

    test_news = {

        "title":
            "Arsenal consider move for midfielder",

        "text":
            (
                "Arsenal are considering a move for "
                "the midfielder as they look to "
                "strengthen their squad."
            )
    }

    result = translate_news(
        test_news
    )

    print("\nنتیجه:")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )
