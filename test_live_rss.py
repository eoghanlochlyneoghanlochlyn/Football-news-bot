import json
import re
import html
import os
import requests
import feedparser

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import FEEDS_FILE


# ==========================================
# تنظیمات
# ==========================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = "@footballiiiiiiiiiiiiiiiiiiiiii"

# منطقه زمانی ایران
IRAN_TZ = ZoneInfo("Asia/Tehran")

# فقط اخبار منتشرشده از این ساعت به بعد
START_HOUR = 19
START_MINUTE = 0

# فایل ثبت خبرهای ارسال‌شده
SEEN_FILE = "seen_news.json"

# حداکثر طول خلاصه
MAX_SUMMARY_LENGTH = 700


# ==========================================
# دریافت فهرست RSSها
# ==========================================

def load_feeds():

    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # اگر feeds.json یک آرایه مستقیم باشد
    if isinstance(data, list):
        return data

    # اگر ساختار {"feeds": [...]} باشد
    if isinstance(data, dict):
        return data.get("feeds", [])

    return []


# ==========================================
# خواندن خبرهای قبلاً ارسال‌شده
# ==========================================

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

        print("هشدار: seen_news.json خراب است. فایل جدید ساخته می‌شود.")

        return {}


# ==========================================
# ذخیره خبرهای ارسال‌شده
# ==========================================

def save_seen_news(seen):

    with open(SEEN_FILE, "w", encoding="utf-8") as file:

        json.dump(
            seen,
            file,
            ensure_ascii=False,
            indent=2
        )


# ==========================================
# تبدیل زمان RSS به datetime
# ==========================================

def get_published_datetime(entry):

    parsed_time = entry.get("published_parsed")

    if not parsed_time:
        parsed_time = entry.get("updated_parsed")

    if not parsed_time:
        return None

    try:

        dt = datetime(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
            parsed_time.tm_hour,
            parsed_time.tm_min,
            parsed_time.tm_sec,
            tzinfo=timezone.utc
        )

        return dt

    except Exception:

        return None


# ==========================================
# پاک‌سازی HTML
# ==========================================

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


# ==========================================
# ساخت خلاصه کوتاه
# ==========================================

def make_short_summary(text):

    text = clean_html(text)

    if not text:
        return ""

    # حذف بعضی متن‌های تبلیغاتی رایج
    text = re.sub(
        r"(read more|click here|find out more|sign up).*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    if len(text) <= MAX_SUMMARY_LENGTH:
        return text

    shortened = text[:MAX_SUMMARY_LENGTH]

    # تلاش برای قطع کردن در پایان جمله
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


# ==========================================
# ساخت شناسه خبر
# ==========================================

def get_news_id(entry):

    # لینک بهترین شناسه است
    link = entry.get(
        "link",
        ""
    ).strip()

    if link:
        return link

    # اگر لینک وجود نداشت
    guid = entry.get(
        "id",
        ""
    ).strip()

    if guid:
        return guid

    # آخرین راه: عنوان
    return entry.get(
        "title",
        ""
    ).strip()


# ==========================================
# زمان شروع انتشار
# ==========================================

def get_cutoff_time():

    now = datetime.now(IRAN_TZ)

    cutoff = now.replace(
        hour=START_HOUR,
        minute=START_MINUTE,
        second=0,
        microsecond=0
    )

    return cutoff


# ==========================================
# ارسال پیام به تلگرام
# ==========================================

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


# ==========================================
# برنامه اصلی
# ==========================================

def main():

    print("=" * 70)

    print(
        "شروع بررسی RSS"
    )

    print("=" * 70)

    # بررسی توکن
    if not TELEGRAM_TOKEN:

        print(
            "خطا: TELEGRAM_BOT_TOKEN در Secrets وجود ندارد."
        )

        return

    # زمان فعلی ایران
    now = datetime.now(IRAN_TZ)

    # زمان شروع
    cutoff = get_cutoff_time()

    print(
        "زمان فعلی ایران:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        "شروع انتشار اخبار:",
        cutoff.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # اگر هنوز ساعت 18 نشده
    if now < cutoff:

        print(
            "هنوز به ساعت 18:00 نرسیده‌ایم."
        )

        return

    # دریافت RSSها
    feeds = load_feeds()

    print(
        f"تعداد RSSها: {len(feeds)}"
    )

    # دریافت خبرهای قبلی
    seen = load_seen_news()

    new_count = 0

    # ======================================
    # بررسی تک‌تک RSSها
    # ======================================

    for feed_info in feeds:

        # پشتیبانی از ساختار فعلی feeds.json
        if isinstance(feed_info, dict):

            name = feed_info.get(
                "name",
                "Unknown"
            )

            url = feed_info.get(
                "url",
                ""
            )

        else:

            print(
                "RSS نامعتبر:",
                feed_info
            )

            continue

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

            # ==================================
            # بررسی خبرهای RSS
            # ==================================

            for entry in feed.entries:

                title = entry.get(
                    "title",
                    ""
                ).strip()

                link = entry.get(
                    "link",
                    ""
                ).strip()

                # خبر ناقص
                if not title or not link:

                    continue

                # شناسه خبر
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

                # بدون زمان انتشار
                # منتشر نمی‌کنیم تا خبر قدیمی
                # اشتباهی وارد کانال نشود.
                if not published_utc:

                    print(
                        "بدون زمان انتشار:",
                        title
                    )

                    continue

                # تبدیل UTC به وقت ایران
                published_iran = (
                    published_utc.astimezone(
                        IRAN_TZ
                    )
                )

                # فقط اخبار بعد از ساعت 18
                if published_iran < cutoff:

                    continue

                # ==================================
                # خبر جدید پیدا شد
                # ==================================

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

                # خلاصه RSS
                summary = entry.get(
                    "summary",
                    ""
                )

                summary = make_short_summary(
                    summary
                )

                # ==================================
                # ارسال تلگرام
                # ==================================

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

                    # ثبت خبر فقط بعد از
                    # ارسال موفق
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

                    new_count += 1

                except Exception as error:

                    print(
                        "✗ خطا در ارسال:",
                        error
                    )

        except Exception as error:

            print(
                f"✗ خطا در RSS {name}:",
                error
            )

    # ==========================================
    # ذخیره فهرست خبرهای ارسال‌شده
    # ==========================================

    save_seen_news(
        seen
    )

    print()
    print("=" * 70)

    print(
        "تعداد خبرهای جدید ارسال‌شده:",
        new_count
    )

    print("=" * 70)


# ==========================================
# اجرای برنامه
# ==========================================

if __name__ == "__main__":

    main()
