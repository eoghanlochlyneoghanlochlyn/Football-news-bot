import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import feedparser
import requests

from config import (
    RSS_FEEDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)

from image_handler import get_best_image
from news_translator import translate_news
from telegram_formatter import format_telegram_post

# ------------------------------------------------------------
# اگر اسم توابع seen_news متفاوت بود،
# فقط همین import را بعداً اصلاح می‌کنیم.
# ------------------------------------------------------------

from seen_news import (
    is_seen,
    mark_seen,
)


# ============================================================
# Telegram API
# ============================================================

TELEGRAM_API = (
    f"https://api.telegram.org/bot"
    f"{TELEGRAM_BOT_TOKEN}"
)


# ============================================================
# چاپ لاگ
# ============================================================

def log(message: str):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    print(
        f"[{now}] {message}"
    )


# ============================================================
# تبدیل زمان RSS
# ============================================================

def parse_published(entry):

    published = getattr(
        entry,
        "published_parsed",
        None
    )

    if published:

        try:

            return datetime(
                published.tm_year,
                published.tm_mon,
                published.tm_mday,
                published.tm_hour,
                published.tm_min,
                published.tm_sec,
                tzinfo=timezone.utc
            )

        except Exception:

            pass

    return datetime.now(
        timezone.utc
    )


# ============================================================
# ساخت دیکشنری خبر
# ============================================================

def build_news_object(
    entry,
    source
):

    news = {

        "title":
            str(
                getattr(
                    entry,
                    "title",
                    ""
                )
            ).strip(),

        "link":
            str(
                getattr(
                    entry,
                    "link",
                    ""
                )
            ).strip(),

        "source":
            source,

        "published":
            parse_published(
                entry
            ),

        # برای image_handler
        "entry":
            dict(entry)
    }

    # --------------------------------------------------------
    # نگه داشتن فیلدهای متنی RSS
    # --------------------------------------------------------

    for key in (
        "summary",
        "description",
        "content",
        "text",
    ):

        if hasattr(
            entry,
            key
        ):

            news[key] = getattr(
                entry,
                key
            )

    return news


# ============================================================
# دریافت RSS
# ============================================================

def fetch_feed(feed):

    if isinstance(
        feed,
        str
    ):

        url = feed
        source = feed

    else:

        url = str(
            feed.get(
                "url",
                ""
            )
        ).strip()

        source = str(
            feed.get(
                "source",
                ""
            )
            or url
        ).strip()

    if not url:

        return source, []

    log(
        f"دریافت RSS: {source}"
    )

    try:

        response = requests.get(

            url,

            headers=REQUEST_HEADERS,

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

        parsed = feedparser.parse(
            response.content
        )

        entries = getattr(
            parsed,
            "entries",
            []
        )

        log(
            f"{len(entries)} خبر دریافت شد."
        )

        return source, entries

    except Exception as error:

        log(
            f"خطا در RSS: {error}"
        )

        return source, []


# ============================================================
# ارسال درخواست به تلگرام
# ============================================================

def telegram_request(
    method,
    payload
):

    url = (
        TELEGRAM_API
        + "/"
        + method
    )

    response = requests.post(

        url,

        data=payload,

        timeout=REQUEST_TIMEOUT

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
                "Telegram Error"
            )
        )

    return data


# ============================================================
# ارسال پیام یا عکس
# ============================================================

def send_to_telegram(

    message,

    image_url=""

):

    if image_url:

        return telegram_request(

            "sendPhoto",

            {

                "chat_id":
                    TELEGRAM_CHANNEL_ID,

                "photo":
                    image_url,

                "caption":
                    message,

                "parse_mode":
                    "HTML"

            }

        )

    return telegram_request(

        "sendMessage",

        {

            "chat_id":
                TELEGRAM_CHANNEL_ID,

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
    """
    یک خبر را از ابتدا تا انتها پردازش می‌کند:

    1. بررسی تکراری نبودن خبر
    2. ترجمه و بازنویسی
    3. پیدا کردن تصویر
    4. ساخت پیام تلگرام
    5. ارسال به کانال
    6. ثبت خبر به عنوان ارسال‌شده
    """

    if not isinstance(news, dict):

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

    # --------------------------------------------------------
    # بررسی اطلاعات ضروری
    # --------------------------------------------------------

    if not title:

        log(
            "⚠️ خبر بدون عنوان نادیده گرفته شد."
        )

        return False

    if not link:

        log(
            f"⚠️ خبر «{title}» لینک ندارد."
        )

        return False

    # --------------------------------------------------------
    # بررسی خبر تکراری
    # --------------------------------------------------------

    try:

        if is_seen(news):

            log(
                f"خبر قبلاً ارسال شده است: {title}"
            )

            return False

    except Exception as error:

        log(
            f"❌ خطا هنگام بررسی seen_news: "
            f"{error}"
        )

        return False

    # --------------------------------------------------------
    # شروع پردازش
    # --------------------------------------------------------

    log(
        f"📰 پردازش خبر جدید: {title}"
    )

    # --------------------------------------------------------
    # ترجمه و بازنویسی
    # --------------------------------------------------------

    log(
        "در حال ترجمه و بازنویسی خبر..."
    )

    try:

        translation = translate_news(
            news
        )

    except Exception as error:

        log(
            f"❌ خطا در ترجمه خبر: {error}"
        )

        return False

    if not isinstance(
        translation,
        dict
    ):

        log(
            "❌ پاسخ مترجم ساختار معتبری ندارد."
        )

        return False

    if not translation.get(
        "success",
        False
    ):

        error_message = translation.get(
            "error",
            "خطای نامشخص"
        )

        log(
            f"❌ ترجمه انجام نشد: "
            f"{error_message}"
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
            "❌ ترجمه عنوان خالی است."
        )

        return False

    # --------------------------------------------------------
    # قرار دادن ترجمه داخل news
    # --------------------------------------------------------

    news["translated_title"] = (
        translated_title
    )

    news["translated_body"] = (
        translated_body
    )

    log(
        "✓ ترجمه با موفقیت انجام شد."
    )

    # --------------------------------------------------------
    # پیدا کردن تصویر
    # --------------------------------------------------------

    log(
        "در حال بررسی تصویر خبر..."
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
            "✓ تصویر برای خبر انتخاب شد."
        )

    else:

        log(
            "⚠️ تصویر مناسبی پیدا نشد؛ "
            "خبر به صورت متنی ارسال می‌شود."
        )

    # --------------------------------------------------------
    # ساخت پیام تلگرام
    # --------------------------------------------------------

    log(
        "در حال ساخت پیام تلگرام..."
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
            f"❌ ساخت پیام ناموفق بود: "
            f"{formatted.get('error', '')}"
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
        "در حال ارسال خبر به کانال..."
    )

    try:

        telegram_result = send_to_telegram(

            message=message,

            image_url=image_url

        )

    except Exception as error:

        log(
            f"❌ ارسال به تلگرام ناموفق بود: "
            f"{error}"
        )

        # ----------------------------------------------------
        # بسیار مهم:
        # اگر ارسال شکست خورد، خبر ثبت نمی‌شود.
        # بنابراین اجرای بعدی دوباره آن را امتحان می‌کند.
        # ----------------------------------------------------

        return False

    # --------------------------------------------------------
    # بررسی نتیجه ارسال
    # --------------------------------------------------------

    if not isinstance(
        telegram_result,
        dict
    ):

        log(
            "❌ پاسخ تلگرام نامعتبر است."
        )

        return False

    if not telegram_result.get(
        "ok",
        False
    ):

        log(
            "❌ تلگرام ارسال خبر را تأیید نکرد."
        )

        return False

    log(
        "✓ خبر با موفقیت در کانال منتشر شد."
    )

    # --------------------------------------------------------
    # ثبت خبر به عنوان ارسال‌شده
    # --------------------------------------------------------

    try:

        mark_seen(news)

    except Exception as error:

        log(
            f"⚠️ خبر ارسال شد اما ثبت آن در "
            f"seen_news ناموفق بود: {error}"
        )

        # ----------------------------------------------------
        # اینجا False برنمی‌گردانیم؛ چون خبر واقعاً
        # در تلگرام منتشر شده است.
        # ----------------------------------------------------

        return True

    log(
        "✓ خبر در seen_news ثبت شد."
    )

    return True


# ============================================================
# پردازش خبرهای یک RSS
# ============================================================

def process_feed(
    feed
):
    """
    یک منبع RSS را دریافت و خبرهای جدید آن را پردازش می‌کند.
    """

    source, entries = fetch_feed(
        feed
    )

    if not entries:

        return 0

    processed_count = 0

    # --------------------------------------------------------
    # تبدیل خبرها به ساختار داخلی
    # --------------------------------------------------------

    news_items = []

    for entry in entries:

        try:

            news = build_news_object(

                entry,

                source

            )

        except Exception as error:

            log(
                f"⚠️ خطا در ساخت خبر RSS: "
                f"{error}"
            )

            continue

        if not news.get(
            "title"
        ):

            continue

        if not news.get(
            "link"
        ):

            continue

        news_items.append(
            news
        )

    # --------------------------------------------------------
    # جدیدترین خبرها اول
    # --------------------------------------------------------

    news_items.sort(

        key=lambda item:
            item.get(
                "published",
                datetime.min.replace(
                    tzinfo=timezone.utc
                )
            ),

        reverse=True

    )

    # --------------------------------------------------------
    # پردازش
    # --------------------------------------------------------

    for news in news_items:

        try:

            success = process_news(
                news
            )

            if success:

                processed_count += 1

        except Exception as error:

            log(
                f"❌ خطای غیرمنتظره هنگام "
                f"پردازش خبر: {error}"
            )

    return processed_count


# ============================================================
# پردازش تمام منابع RSS
# ============================================================

def process_all_feeds():
    """
    تمام منابع RSS موجود در config.py را پردازش می‌کند.
    """

    if not RSS_FEEDS:

        log(
            "⚠️ هیچ منبع RSS تنظیم نشده است."
        )

        return 0

    total_processed = 0

    log(
        f"شروع بررسی {len(RSS_FEEDS)} منبع RSS..."
    )

    for index, feed in enumerate(
        RSS_FEEDS,
        start=1
    ):

        log(
            f"--- منبع {index} از "
            f"{len(RSS_FEEDS)} ---"
        )

        try:

            processed = process_feed(
                feed
            )

            total_processed += processed

        except Exception as error:

            log(
                f"❌ خطا در پردازش منبع RSS: "
                f"{error}"
            )

    return total_processed

# ============================================================
# اجرای یک چرخه
# ============================================================

def run_cycle():
    """
    یک بار تمام منابع RSS را بررسی می‌کند.
    """

    log("")
    log("=" * 60)
    log("شروع چرخهٔ جدید بررسی اخبار")
    log("=" * 60)

    try:

        processed = process_all_feeds()

        if processed > 0:

            log(
                f"✓ در این چرخه {processed} خبر منتشر شد."
            )

        else:

            log(
                "خبر جدیدی برای انتشار وجود نداشت."
            )

    except Exception as error:

        log(
            f"❌ خطای کلی در چرخه: {error}"
        )

    log(
        "پایان چرخهٔ بررسی."
    )


# ============================================================
# حلقهٔ اصلی
# ============================================================

def main():
    """
    اجرای دائمی ربات.
    """

    log("")
    log("=" * 60)
    log("🤖 ربات اخبار فوتبال شروع به کار کرد.")
    log("=" * 60)

    # --------------------------------------------------------
    # بررسی اولیه
    # --------------------------------------------------------

    if not RSS_FEEDS:

        log(
            "❌ هیچ منبع RSS در config.py تنظیم نشده است."
        )

        return

    log(
        f"تعداد منابع RSS: {len(RSS_FEEDS)}"
    )

    log(
        f"فاصلهٔ بررسی: {CHECK_INTERVAL} ثانیه"
    )

    # --------------------------------------------------------
    # اجرای دائمی
    # --------------------------------------------------------

    while True:

        try:

            run_cycle()

        except KeyboardInterrupt:

            log(
                "ربات توسط کاربر متوقف شد."
            )

            break

        except Exception as error:

            log(
                f"❌ خطای پیش‌بینی‌نشده: {error}"
            )

        # ----------------------------------------------------
        # انتظار تا چرخهٔ بعدی
        # ----------------------------------------------------

        log(
            f"⏳ انتظار {CHECK_INTERVAL} ثانیه "
            "تا بررسی بعدی..."
        )

        try:

            time.sleep(
                CHECK_INTERVAL
            )

        except KeyboardInterrupt:

            log(
                "ربات توسط کاربر متوقف شد."
            )

            break


# ============================================================
# نقطهٔ شروع برنامه
# ============================================================

if __name__ == "__main__":

    main()
