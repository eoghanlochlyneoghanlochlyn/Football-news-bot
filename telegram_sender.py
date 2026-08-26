import os
import time

import requests


# ============================================================
# تنظیمات
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

TELEGRAM_CHANNEL = os.getenv(
    "TELEGRAM_CHANNEL",
    ""
).strip()

TELEGRAM_API_BASE = (
    "https://api.telegram.org/bot"
)

# تعداد تلاش مجدد برای خطاهای موقت
MAX_SEND_RETRIES = 3

# فاصله پایه بین تلاش‌ها
RETRY_DELAY = 2


# ============================================================
# بررسی تنظیمات
# ============================================================

def validate_config():

    if not TELEGRAM_BOT_TOKEN:

        return False, (
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    if not TELEGRAM_CHANNEL:

        return False, (
            "TELEGRAM_CHANNEL تنظیم نشده است."
        )

    return True, ""


# ============================================================
# ساخت آدرس API
# ============================================================

def telegram_url(method):

    return (
        f"{TELEGRAM_API_BASE}"
        f"{TELEGRAM_BOT_TOKEN}"
        f"/{method}"
    )


# ============================================================
# تشخیص خطای موقت
# ============================================================

def is_retryable_response(response):

    # خطاهای رایج موقت HTTP
    if response.status_code in {
        408,
        429,
        500,
        502,
        503,
        504,
    }:

        return True

    return False


# ============================================================
# زمان انتظار از پاسخ تلگرام
# ============================================================

def get_retry_after(response):

    try:

        data = response.json()

        parameters = data.get(
            "parameters",
            {}
        )

        retry_after = parameters.get(
            "retry_after",
            0
        )

        retry_after = int(
            retry_after or 0
        )

        if retry_after > 0:

            return retry_after

    except Exception:

        pass

    return RETRY_DELAY


# ============================================================
# ارسال درخواست به API تلگرام
# ============================================================

def telegram_post(
    method,
    payload
):

    for attempt in range(
        1,
        MAX_SEND_RETRIES + 1
    ):

        try:

            response = requests.post(
                telegram_url(
                    method
                ),
                data=payload,
                timeout=60
            )

        except requests.RequestException as error:

            if attempt < MAX_SEND_RETRIES:

                delay = (
                    RETRY_DELAY
                    * attempt
                )

                print(
                    f"⚠️ خطای ارتباطی با تلگرام. "
                    f"تلاش مجدد در {delay} ثانیه..."
                )

                time.sleep(
                    delay
                )

                continue

            return {
                "success": False,
                "response": None,
                "error": (
                    f"خطای ارتباط با تلگرام: "
                    f"{error}"
                )
            }

        # ----------------------------------------------------
        # پاسخ موفق
        # ----------------------------------------------------

        if response.ok:

            try:

                data = response.json()

            except Exception:

                data = {}

            if data.get(
                "ok",
                False
            ):

                return {
                    "success": True,
                    "response": response,
                    "error": ""
                }

        # ----------------------------------------------------
        # خطای موقت
        # ----------------------------------------------------

        if (
            is_retryable_response(
                response
            )
            and attempt < MAX_SEND_RETRIES
        ):

            delay = get_retry_after(
                response
            )

            print(
                f"⚠️ خطای موقت تلگرام "
                f"({response.status_code}). "
                f"تلاش مجدد در {delay} ثانیه..."
            )

            time.sleep(
                delay
            )

            continue

        # ----------------------------------------------------
        # خطای نهایی
        # ----------------------------------------------------

        return {
            "success": False,
            "response": response,
            "error": get_telegram_error(
                response
            )
        }

    return {
        "success": False,
        "response": None,
        "error": "ارسال به تلگرام ناموفق بود."
    }


# ============================================================
# ارسال عکس
# ============================================================

def send_photo(
    message,
    image_url
):

    if not image_url:

        return {
            "success": False,
            "method": "photo",
            "error": "آدرس تصویر خالی است."
        }

    valid, error = validate_config()

    if not valid:

        return {
            "success": False,
            "method": "photo",
            "error": error
        }

    payload = {

        "chat_id":
            TELEGRAM_CHANNEL,

        "photo":
            image_url,

        "caption":
            message,

        "parse_mode":
            "HTML"
    }

    print(
        "در حال ارسال عکس به تلگرام..."
    )

    result = telegram_post(
        "sendPhoto",
        payload
    )

    if result["success"]:

        print(
            "✓ عکس و پست با موفقیت ارسال شد."
        )

        return {
            "success": True,
            "method": "photo",
            "error": ""
        }

    error_text = result["error"]

    print(
        f"❌ ارسال عکس ناموفق بود: "
        f"{error_text}"
    )

    return {
        "success": False,
        "method": "photo",
        "error": error_text
    }


# ============================================================
# ارسال متن
# ============================================================

def send_text(
    message
):

    if not message:

        return {
            "success": False,
            "method": "text",
            "error": "متن پیام خالی است."
        }

    valid, error = validate_config()

    if not valid:

        return {
            "success": False,
            "method": "text",
            "error": error
        }

    payload = {

        "chat_id":
            TELEGRAM_CHANNEL,

        "text":
            message,

        "parse_mode":
            "HTML",

        # جلوگیری از پیش‌نمایش لینک
        "disable_web_page_preview":
            True
    }

    print(
        "در حال ارسال متن به تلگرام..."
    )

    result = telegram_post(
        "sendMessage",
        payload
    )

    if result["success"]:

        print(
            "✓ پست متنی با موفقیت ارسال شد."
        )

        return {
            "success": True,
            "method": "text",
            "error": ""
        }

    error_text = result["error"]

    print(
        f"❌ ارسال متن ناموفق بود: "
        f"{error_text}"
    )

    return {
        "success": False,
        "method": "text",
        "error": error_text
    }


# ============================================================
# استخراج خطای تلگرام
# ============================================================

def get_telegram_error(
    response
):

    if response is None:

        return (
            "پاسخی از API تلگرام دریافت نشد."
        )

    try:

        data = response.json()

        description = data.get(
            "description",
            ""
        )

        error_code = data.get(
            "error_code",
            response.status_code
        )

        if description:

            return (
                f"HTTP {error_code}: "
                f"{description}"
            )

    except Exception:

        pass

    if response.text:

        return (
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return (
        f"HTTP {response.status_code}"
    )


# ============================================================
# ارسال خبر
# ============================================================

def send_news(
    message,
    image_url=""
):

    """
    اگر تصویر وجود داشته باشد:

        ابتدا ارسال عکس امتحان می‌شود.

    اگر ارسال عکس شکست بخورد:

        همان خبر به صورت متنی ارسال می‌شود.

    اگر عکس وجود نداشته باشد:

        مستقیماً متن ارسال می‌شود.
    """

    if not message:

        return {
            "success": False,
            "method": "none",
            "error": "متن پیام خالی است."
        }

    # --------------------------------------------------------
    # ابتدا عکس
    # --------------------------------------------------------

    if image_url:

        photo_result = send_photo(
            message,
            image_url
        )

        if photo_result["success"]:

            return photo_result

        print(
            "⚠️ ارسال عکس شکست خورد."
        )

        print(
            "⚠️ خبر به صورت متنی ارسال می‌شود."
        )

    # --------------------------------------------------------
    # حالت متنی
    # --------------------------------------------------------

    return send_text(
        message
    )


# ============================================================
# تابع جایگزین برای استفاده در main.py
# ============================================================

def publish_news(news):

    if not isinstance(
        news,
        dict
    ):

        return {
            "success": False,
            "method": "none",
            "error": "ساختار خبر نامعتبر است."
        }

    message = news.get(
        "message",
        ""
    )

    image_url = news.get(
        "image",
        ""
    )

    return send_news(
        message=message,
        image_url=image_url
    )


# ============================================================
# تست اتصال به ربات
# ============================================================

def test_bot():

    valid, error = validate_config()

    if not valid:

        print(
            f"❌ تنظیمات تلگرام ناقص است: {error}"
        )

        return False

    try:

        response = requests.get(
            telegram_url(
                "getMe"
            ),
            timeout=30
        )

    except requests.RequestException as error:

        print(
            f"❌ خطا در اتصال به تلگرام: {error}"
        )

        return False

    except Exception as error:

        print(
            f"❌ خطای غیرمنتظره: {error}"
        )

        return False

    if not response.ok:

        print(
            "❌ اتصال به API تلگرام ناموفق بود."
        )

        print(
            get_telegram_error(
                response
            )
        )

        return False

    try:

        data = response.json()

    except Exception:

        print(
            "❌ پاسخ تلگرام JSON معتبر نیست."
        )

        return False

    if not data.get(
        "ok",
        False
    ):

        print(
            "❌ تلگرام پاسخ معتبر نداد."
        )

        print(
            get_telegram_error(
                response
            )
        )

        return False

    bot = data.get(
        "result",
        {}
    )

    print(
        "✓ اتصال به ربات تلگرام موفق بود."
    )

    print(
        f"نام ربات: "
        f"{bot.get('first_name', '')}"
    )

    print(
        f"نام کاربری ربات: "
        f"@{bot.get('username', '')}"
    )

    return True


# ============================================================
# اجرای مستقیم برای تست
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("تست telegram_sender.py")
    print("=" * 60)

    test_bot()

    print("=" * 60)
