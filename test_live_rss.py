import json
import re
import html
import requests
import feedparser

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import FEEDS_FILE


# ==========================================
# تنظیمات
# ==========================================

TELEGRAM_TOKEN = None
TELEGRAM_CHAT_ID = "@footballiiiiiiiiiiiiiiiiiiiiii"

IRAN_TZ = ZoneInfo("Asia/Tehran")

# فقط اخبار امروز از ساعت 18:00 به بعد
START_HOUR = 18
START_MINUTE = 0

SEEN_FILE = "seen_news.json"

MAX_SUMMARY_LENGTH = 700


# ==========================================
# ابزارها
# ==========================================

def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("feeds", [])


def load_seen_news():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_seen_news(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(seen, file, ensure_ascii=False, indent=2)


def get_published_datetime(entry):

    parsed_time = entry.get("published_parsed")

    if not parsed_time:
        parsed_time = entry.get("updated_parsed")

    if not parsed_time:
        return None

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


def clean_html(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def make_short_summary(text):

    text = clean_html(text)

    if not text:
        return ""

    # حذف متن‌های خیلی تکراری و تبلیغاتی رایج
    text = re.sub(
        r"(read more|click here|find out more|sign up).*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    if len(text) <= MAX_SUMMARY_LENGTH:
        return text

    # ترجیحاً در پایان یک جمله قطع شود
    shortened = text[:MAX_SUMMARY_LENGTH]

    last_dot = max(
        shortened.rfind("."),
        shortened.rfind("!"),
        shortened.rfind("?")
    )

    if last_dot > 250:
        shortened = shortened[:last_dot + 1]
    else:
        shortened = shortened.rsplit(" ", 1)[0] + "..."

    return shortened


def get_news_id(entry):

    # لینک بهترین شناسه برای جلوگیری از انتشار دوباره است
    link = entry.get("link", "").strip()

    if link:
        return link

    guid = entry.get("id", "").strip()

    if guid:
        return guid

    return entry.get("title", "").strip()


# ==========================================
# زمان شروع تست
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
# ارسال تلگرام
# ==========================================

def send_to_telegram(title, summary, source, published):

    global TELEGRAM_TOKEN

    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")

    message = f"📰 <b>{html.escape(title)}</b>\n\n"

    if summary:
        message += f"{html.escape(summary)}\n\n"

    message += f"📌 {html.escape(source)}\n"
    message += f"🕐 {published.strftime('%H:%M')}"

    url = (
        f"https://api.telegram.org/bot"
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
# دریافت و پردازش RSS
# ==========================================

def main():

    global TELEGRAM_TOKEN

    import os

    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not TELEGRAM_TOKEN:
        print("خطا: TELEGRAM_BOT_TOKEN وجود ندارد.")
        return

    now = datetime.now(IRAN_TZ)
    cutoff = get_cutoff_time()

    print("=" * 70)
    print("شروع بررسی RSS")
    print("=" * 70)

    print(f"زمان فعلی ایران: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"شروع انتشار اخبار: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")

    # اگر اکشن در روز دیگری اجرا شود،
    # فقط اخبار همان روز بعد از ساعت 18 بررسی می‌شوند.
    if now < cutoff:
        print("هنوز به ساعت 18:00 نرسیده‌ایم.")
        return

    feeds = load_feeds()
    seen = load_seen_news()

    new_count = 0

    for feed_info in feeds:

        name = feed_info.get("name", "Unknown")
        url = feed_info.get("url", "")

        print()
        print(f"در حال بررسی: {name}")

        try:

            feed = feedparser.parse(url)

            for entry in feed.entries:

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()

                if not title or not link:
                    continue

                news_id = get_news_id(entry)

                # قبلاً منتشر شده
                if news_id in seen:
                    continue

                published_utc = get_published_datetime(entry)

                # اگر RSS زمان انتشار ندارد، فعلاً رد می‌کنیم
                # تا خبر قدیمی اشتباهی منتشر نشود.
                if not published_utc:
                    print(f"بدون زمان انتشار: {title}")
                    continue

                published_iran = published_utc.astimezone(IRAN_TZ)

                # فقط اخبار امروز بعد از ساعت 18
                if published_iran < cutoff:
                    continue

                # خبر جدید پیدا شد
                print()
                print("خبر جدید:")
                print(title)
                print(
                    f"زمان: "
                    f"{published_iran.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                summary = entry.get("summary", "")
                summary = make_short_summary(summary)

                try:

                    send_to_telegram(
                        title,
                        summary,
                        name,
                        published_iran
                    )

                    print("✓ با موفقیت ارسال شد.")

                    seen[news_id] = {
                        "title": title,
                        "source": name,
                        "published": published_utc.isoformat(),
                        "sent_at": datetime.now(
                            timezone.utc
                        ).isoformat()
                    }

                    new_count += 1

                except Exception as error:

                    print(
                        f"خطا در ارسال به تلگرام: {error}"
                    )

        except Exception as error:

            print(
                f"خطا در RSS {name}: {error}"
            )

    save_seen_news(seen)

    print()
    print("=" * 70)
    print(f"تعداد خبرهای جدید ارسال‌شده: {new_count}")
    print("=" * 70)


if __name__ == "__main__":
    main()
