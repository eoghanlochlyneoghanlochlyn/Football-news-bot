from datetime import datetime, timezone

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL,
)

from rss import collect_recent_news

from seen import (
    is_seen,
    mark_seen,
)

from news_translator import translate_news

from image_handler import get_best_image

from telegram_formatter import format_telegram_post


# ============================================================
# لاگ
# ============================================================

def log(message):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    print(
        f"[{now}] {message}"
    )


# ============================================================
# Telegram API
# ============================================================

TELEGRAM_API = (
    "https://api.telegram.org/bot"
    + TELEGRAM_BOT_TOKEN
)


# ============================================================
# درخواست به Telegram
# ============================================================

def telegram_request(
    method,
    payload
):

    import requests

    url = (
        TELEGRAM_API
        + "/"
        + method
    )

    response = requests.post(
        url,
        data=payload,
        timeout=30
    )

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            response.text
        )

    if not response.ok:

        raise RuntimeError(
            data.get(
                "description",
                response.text
            )
        )

    if not data.get(
        "ok",
        False
    ):

        raise RuntimeError(
            data.get(
                "description",
                "خطای نامشخص تلگرام"
            )
        )

    return data


# ============================================================
# ارسال خبر به تلگرام
# ============================================================

def send_to_telegram(
    message,
    image_url=""
):

    if not TELEGRAM_CHANNEL:

        raise RuntimeError(
            "TELEGRAM_CHANNEL تنظیم نشده است."
        )

    # --------------------------------------------------------
    # ارسال همراه تصویر
    # --------------------------------------------------------

    if image_url:

        return telegram_request(

            "sendPhoto",

            {
                "chat_id":
                    TELEGRAM_CHANNEL,

                "photo":
                    image_url,

                "caption":
                    message,

                "parse_mode":
                    "HTML"
            }
        )

    # --------------------------------------------------------
    # ارسال متنی
    # --------------------------------------------------------

    return telegram_request(

        "sendMessage",

        {
            "chat_id":
                TELEGRAM_CHANNEL,

            "text":
                message,

            "parse_mode":
                "HTML",

            "disable_web_page_preview":
                False
        }
    )


# ============================================================
# پردازش یک خبر
# ============================================================

def process_news(news):

    if not isinstance(
        news,
        dict
    ):

        log(
            "⚠️ ساختار خبر نامعتبر است."
        )

        return False

    title = str(
        news.get(
            "title",
            ""
        )
    ).strip()

    link = str(
        news.get(
            "link",
            ""
        )
    ).strip()

    source = str(
        news.get(
            "source",
            ""
        )
    ).strip()

    # --------------------------------------------------------
    # بررسی اطلاعات ضروری
    # --------------------------------------------------------

    if not title:

        log(
            "⚠️ خبر بدون عنوان."
        )

        return False

    if not link:

        log(
            f"⚠️ خبر بدون لینک: {title}"
        )

        return False

    # --------------------------------------------------------
    # بررسی تکراری بودن
    # --------------------------------------------------------

    try:

        if is_seen(news):

            log(
                f"⏭ خبر تکراری: {title}"
            )

            return False

    except Exception as error:

        log(
            f"❌ خطا در بررسی خبرهای ارسال‌شده: "
            f"{error}"
        )

        return False

    # --------------------------------------------------------
    # شروع پردازش
    # --------------------------------------------------------

    log("")
    log(
        "----------------------------------------"
    )

    log(
        f"📰 خبر جدید: {title}"
    )

    log(
        f"منبع: {source}"
    )

    log(
        f"لینک: {link}"
    )

    # --------------------------------------------------------
    # ترجمه و بازنویسی
    # --------------------------------------------------------

    log(
        "🤖 ترجمه و بازنویسی..."
    )

    try:

        translation = translate_news(
            news
        )

    except Exception as error:

        log(
            f"❌ خطا در ترجمه: {error}"
        )

        return False

    if not isinstance(
        translation,
        dict
    ):

        log(
            "❌ پاسخ مترجم نامعتبر است."
        )

        return False

    if not translation.get(
        "success",
        False
    ):

        log(
            "❌ ترجمه موفق نبود: "
            + str(
                translation.get(
                    "error",
                    "خطای نامشخص"
                )
            )
        )

        return False

    translated_title = str(
        translation.get(
            "title",
            ""
        )
    ).strip()

    translated_body = str(
        translation.get(
            "body",
            ""
        )
    ).strip()

    if not translated_title:

        log(
            "❌ عنوان ترجمه‌شده خالی است."
        )

        return False

    news["translated_title"] = (
        translated_title
    )

    news["translated_body"] = (
        translated_body
    )

    log(
        "✓ ترجمه انجام شد."
    )

    # --------------------------------------------------------
    # پیدا کردن تصویر
    # --------------------------------------------------------

    log(
        "🖼 بررسی تصویر..."
    )

    image_url = ""

    try:

        image_url = get_best_image(

            news.get(
                "entry",
                {}
            ),

            link

        )

    except Exception as error:

        log(
            f"⚠️ خطا در پیدا کردن تصویر: "
            f"{error}"
        )

        image_url = ""

    if image_url:

        log(
            "✓ تصویر پیدا شد."
        )

    else:

        log(
            "⚠️ تصویر پیدا نشد."
        )

    # --------------------------------------------------------
    # ساخت پیام
    # --------------------------------------------------------

    log(
        "📝 ساخت پیام تلگرام..."
    )

    try:

        formatted = format_telegram_post(

            news,

            has_image=bool(
                image_url
            )

        )

    except Exception as error:

        log(
            f"❌ خطا در قالب‌بندی پیام: "
            f"{error}"
        )

        return False

    if not isinstance(
        formatted,
        dict
    ):

        log(
            "❌ خروجی قالب‌بندی نامعتبر است."
        )

        return False

    if not formatted.get(
        "success",
        False
    ):

        log(
            "❌ ساخت پیام ناموفق بود: "
            + str(
                formatted.get(
                    "error",
                    ""
                )
            )
        )

        return False

    message = str(
        formatted.get(
            "message",
            ""
        )
    ).strip()

    if not message:

        log(
            "❌ پیام نهایی خالی است."
        )

        return False

    # --------------------------------------------------------
    # ارسال به تلگرام
    # --------------------------------------------------------

    log(
        "📤 ارسال به تلگرام..."
    )

    try:

        result = send_to_telegram(

            message=message,

            image_url=image_url

        )

    except Exception as error:

        log(
            f"❌ ارسال ناموفق بود: {error}"
        )

        return False

    if not isinstance(
        result,
        dict
    ):

        log(
            "❌ پاسخ تلگرام نامعتبر است."
        )

        return False

    if not result.get(
        "ok",
        False
    ):

        log(
            "❌ تلگرام ارسال را تأیید نکرد."
        )

        return False

    log(
        "✓ خبر با موفقیت منتشر شد."
    )

    # --------------------------------------------------------
    # ثبت خبر
    # --------------------------------------------------------

    try:

        mark_seen(
            news
        )

        log(
            "✓ خبر در seen_news ثبت شد."
        )

    except Exception as error:

        log(
            "⚠️ خبر منتشر شد اما ثبت نشد: "
            f"{error}"
        )

    log(
        "----------------------------------------"
    )

    return True


# ============================================================
# اجرای یک چرخه
# ============================================================

def run_cycle():

    log("")
    log(
        "=" * 60
    )

    log(
        "🤖 شروع بررسی اخبار فوتبال"
    )

    log(
        "=" * 60
    )

    # --------------------------------------------------------
    # دریافت خبرهای اخیر از rss.py
    # --------------------------------------------------------

    log(
        "📡 دریافت خبرها از RSS..."
    )

    try:

        news_list = collect_recent_news()

    except Exception as error:

        log(
            f"❌ خطا در دریافت خبرها: {error}"
        )

        return 0

    if not news_list:

        log(
            "ℹ️ هیچ خبر جدیدی در بازه زمانی پیدا نشد."
        )

        return 0

    log(
        f"✓ تعداد خبرهای دریافت‌شده: "
        f"{len(news_list)}"
    )

    # --------------------------------------------------------
    # پردازش خبرها
    # --------------------------------------------------------

    published_count = 0

    for index, news in enumerate(
        news_list,
        start=1
    ):

        log(
            ""
        )

        log(
            f"خبر {index} از "
            f"{len(news_list)}"
        )

        try:

            success = process_news(
                news
            )

            if success:

                published_count += 1

        except Exception as error:

            log(
                f"❌ خطای غیرمنتظره: "
                f"{error}"
            )

    # --------------------------------------------------------
    # نتیجه
    # --------------------------------------------------------

    log("")
    log(
        "=" * 60
    )

    log(
        f"✓ چرخه تمام شد. "
        f"{published_count} خبر منتشر شد."
    )

    log(
        "=" * 60
    )

    return published_count


# ============================================================
# اجرای اصلی
# ============================================================

def main():

    log(
        "🚀 Football News Bot"
    )

    # --------------------------------------------------------
    # بررسی تنظیمات
    # --------------------------------------------------------

    try:

        validate_config()

    except Exception as error:

        log(
            f"❌ تنظیمات نامعتبر است: {error}"
        )

        return

    if not TELEGRAM_BOT_TOKEN:

        log(
            "❌ TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

        return

    if not TELEGRAM_CHANNEL:

        log(
            "❌ TELEGRAM_CHANNEL تنظیم نشده است."
        )

        return

    # --------------------------------------------------------
    # اجرای یک چرخه
    # --------------------------------------------------------

    run_cycle()

    # --------------------------------------------------------
    # فعلاً فقط یک بار اجرا می‌شود.
    #
    # دلیل:
    # GitHub Actions خودش اجرای زمان‌بندی‌شده را انجام می‌دهد.
    # بنابراین نیازی به while True و sleep نداریم.
    # --------------------------------------------------------

    log(
        "🏁 اجرای برنامه به پایان رسید."
    )


# ============================================================
# نقطه شروع
# ============================================================

if __name__ == "__main__":

    main()
