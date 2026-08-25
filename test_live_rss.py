import json
import re
import html
import os
import time
import requests
import feedparser

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import FEEDS_FILE


# ============================================================
# تنظیمات
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = "@footballiiiiiiiiiiiiiiiiiiiiii"

IRAN_TZ = ZoneInfo("Asia/Tehran")

# فقط خبرهای منتشرشده از این ساعت به بعد
START_HOUR = 19
START_MINUTE = 0

# فاصله بین هر بررسی RSS
CHECK_INTERVAL = 5 * 60

# فایل ثبت خبرهای ارسال‌شده
SEEN_FILE = "seen_news.json"

# حداکثر طول خلاصه RSS
MAX_SUMMARY_LENGTH = 700


# ============================================================
# دریافت RSS ها
# ============================================================

def load_feeds():

    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # ساختار:
    # [
    #   {"name": "...", "url": "..."}
    # ]
    if isinstance(data, list):
        return data

    # ساختار:
    # {"feeds": [...]}
    if isinstance(data, dict):
        return data.get("feeds", [])

    return []


# ============================================================
# خواندن خبرهای ارسال‌شده
# ============================================================

def load_seen_news():

    try:

        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except FileNotFoundError:

        return {}

    except json.JSONDecodeError:

        print(
            "هشدار: seen_news.json خراب است."
        )

        return {}


# ============================================================
# ذخیره خبرهای ارسال‌شده
# ============================================================

def save_seen_news(seen):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            seen,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# تبدیل زمان RSS
# ============================================================

def get_published_datetime(entry):

    parsed_time = entry.get(
        "published_parsed"
    )

    if not parsed_time:

        parsed_time = entry.get(
            "updated_parsed"
        )

    if not parsed_time:
        return None

    try:

        return datetime(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
            parsed_time.tm_hour,
            parsed_time.tm_min,
            parsed_time.tm_sec,
            tzinfo=timezone.utc
        )

    except Exception:

        return None


# ============================================================
# پاک‌سازی HTML
# ============================================================

def clean_html(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# ساخت خلاصه کوتاه
# ============================================================

def make_short_summary(text):

    text = clean_html(text)

    if not text:
        return ""

    text = re.sub(
        r"(read more|click here|find out more|sign up).*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    if len(text) <= MAX_SUMMARY_LENGTH:
        return text

    shortened = text[
        :MAX_SUMMARY_LENGTH
    ]

    last_dot = max(
        shortened.rfind("."),
        shortened.rfind("!"),
        shortened.rfind("?")
    )

    if last_dot > 250:

        shortened = shortened[
            :last_dot + 1
        ]

    else:

        shortened = (
            shortened.rsplit(" ", 1)[0]
            + "..."
        )

    return shortened


# ============================================================
# شناسه خبر
# ============================================================

def get_news_id(entry):

    link = entry.get(
        "link",
        ""
    ).strip()

    if link:
        return link

    guid = entry.get(
        "id",
        ""
    ).strip()

    if guid:
        return guid

    return entry.get(
        "title",
        ""
    ).strip()


# ============================================================
# زمان شروع انتشار
# ============================================================

def get_cutoff_time():

    now = datetime.now(
        IRAN_TZ
    )

    return now.replace(
        hour=START_HOUR,
        minute=START_MINUTE,
        second=0,
        microsecond=0
    )


# ============================================================
# ارسال به تلگرام
# ============================================================

def send_to_telegram(
    title,
    summary,
    source,
    published
):

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    message = (
        f"📰 <b>{html.escape(title)}</b>\n\n"
    )

    if summary:

        message += (
            f"{html.escape(summary)}\n\n"
        )

    message += (
        f"📌 {html.escape(source)}\n"
    )

    message += (
        f"🕐 {published.strftime('%H:%M')}"
    )

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    payload = {

        "chat_id": TELEGRAM_CHAT_ID,

        "text": message,

        "parse_mode": "HTML",

        "disable_web_page_preview": False
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    if not response.ok:

        raise RuntimeError(
            f"Telegram error: {response.text}"
        )


# ============================================================
# یک دور کامل بررسی RSS ها
# ============================================================

def check_feeds(seen):

    print()
    print("=" * 70)

    print(
        "شروع یک دور بررسی RSS ها"
    )

    print(
        "زمان ایران:",
        datetime.now(
            IRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print("=" * 70)

    feeds = load_feeds()

    new_count = 0

    # زمان شروع انتشار
    cutoff = get_cutoff_time()

    print(
        "شروع انتشار اخبار:",
        cutoff.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # اگر هنوز ساعت تعیین‌شده نرسیده
    now = datetime.now(
        IRAN_TZ
    )

    if now < cutoff:

        print(
            "هنوز به ساعت شروع انتشار نرسیده‌ایم."
        )

        return 0

    print(
        f"تعداد RSS ها: {len(feeds)}"
    )

    # ========================================================
    # بررسی تک‌تک فیدها
    # ========================================================

    for feed_info in feeds:

        if not isinstance(
            feed_info,
            dict
        ):

            continue

        name = feed_info.get(
            "name",
            "Unknown"
        )

        url = feed_info.get(
            "url",
            ""
        )

        if not url:
            continue

        print()
        print(
            f"در حال بررسی: {name}"
        )

        try:

            feed = feedparser.parse(
                url
            )

            print(
                f"تعداد خبرهای RSS: "
                f"{len(feed.entries)}"
            )

            # =================================================
            # بررسی خبرهای فید
            # =================================================

            for entry in feed.entries:

                title = entry.get(
                    "title",
                    ""
                ).strip()

                link = entry.get(
                    "link",
                    ""
                ).strip()

                if not title or not link:
                    continue

                news_id = get_news_id(
                    entry
                )

                # قبلاً ارسال شده؟
                if news_id in seen:
                    continue

                # زمان انتشار
                published_utc = (
                    get_published_datetime(
                        entry
                    )
                )

                # اگر زمان ندارد، فعلاً رد می‌کنیم
                if not published_utc:

                    continue

                # تبدیل UTC به ایران
                published_iran = (
                    published_utc.astimezone(
                        IRAN_TZ
                    )
                )

                # =================================================
                # فیلتر زمانی
                # =================================================

                if published_iran < cutoff:

                    continue

                # =================================================
                # خبر جدید
                # =================================================

                print()
                print(
                    "خبر جدید پیدا شد:"
                )

                print(
                    f"عنوان: {title}"
                )

                print(
                    "زمان:",
                    published_iran.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                summary = entry.get(
                    "summary",
                    ""
                )

                summary = make_short_summary(
                    summary
                )

                # =================================================
                # ارسال تلگرام
                # =================================================

                try:

                    send_to_telegram(

                        title,

                        summary,

                        name,

                        published_iran
                    )

                    print(
                        "✓ خبر با موفقیت "
                        "در تلگرام منتشر شد."
                    )

                    # فقط بعد از ارسال موفق
                    # خبر را ثبت می‌کنیم

                    seen[news_id] = {

                        "title": title,

                        "source": name,

                        "published": (
                            published_utc.isoformat()
                        ),

                        "sent_at": (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        )
                    }

                    save_seen_news(
                        seen
                    )

                    new_count += 1

                except Exception as error:

                    print(
                        "✗ خطا در ارسال تلگرام:",
                        error
                    )

        except Exception as error:

            print(
                f"✗ خطا در RSS {name}:",
                error
            )

    print()
    print(
        f"این دور تمام شد. "
        f"تعداد خبرهای جدید: {new_count}"
    )

    return new_count


# ============================================================
# برنامه اصلی
# ============================================================

def main():

    print("=" * 70)

    print(
        "سیستم تست زنده RSS"
    )

    print(
        "بررسی خودکار هر ۵ دقیقه"
    )

    print("=" * 70)

    if not TELEGRAM_TOKEN:

        print(
            "خطا: TELEGRAM_BOT_TOKEN "
            "در Secrets وجود ندارد."
        )

        return

    seen = load_seen_news()

    print(
        f"تعداد خبرهای ثبت‌شده قبلی: "
        f"{len(seen)}"
    )

    print(
        "سیستم شروع شد."
    )

    print(
        "برای توقف، اجرای GitHub Action را لغو کنید."
    )

    # ========================================================
    # حلقه دائمی
    # ========================================================

    while True:

        try:

            check_feeds(
                seen
            )

        except Exception as error:

            print()
            print(
                "خطای کلی در بررسی:"
            )

            print(
                error
            )

        print()
        print(
            "۵ دقیقه تا بررسی بعدی..."
        )

        time.sleep(
            CHECK_INTERVAL
        )


# ============================================================
# اجرا
# ============================================================

if __name__ == "__main__":

    main()
