import json
import os
import re
import subprocess
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests


# ============================================================
# تنظیمات
# ============================================================

FEEDS_FILE = "feeds.json"
SEEN_FILE = "seen_news.json"

# فقط خبرهای منتشرشده در ۲ ساعت اخیر بررسی می‌شوند
NEWS_WINDOW_HOURS = 2

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


# ============================================================
# زمان ایران
# ============================================================

def iran_now():
    return datetime.now(IRAN_TZ)


# ============================================================
# خواندن RSS ها
# ============================================================

def load_feeds():

    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("feeds", [])

    return []


# ============================================================
# خواندن seen_news
# ============================================================

def load_seen():

    if not os.path.exists(SEEN_FILE):
        return {}

    try:

        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as error:

        print(f"خطا در خواندن {SEEN_FILE}: {error}")
        return {}


# ============================================================
# ذخیره seen_news
# ============================================================

def save_seen(seen):

    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(
            seen,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# نرمال‌سازی لینک
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(url.strip())

    try:

        parts = urlsplit(url)

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "",
            ""
        ))

    except Exception:

        return url.strip()


# ============================================================
# نرمال‌سازی عنوان
# ============================================================

def normalize_title(title):

    if not title:
        return ""

    title = html.unescape(title)

    title = re.sub(
        r"<[^>]+>",
        " ",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    title = title.strip().lower()

    title = re.sub(
        r"[\"'“”‘’`]",
        "",
        title
    )

    title = re.sub(
        r"[.,!?;:()\[\]{}]",
        "",
        title
    )

    return title.strip()


# ============================================================
# پیدا کردن عکس خبر از RSS
# ============================================================

def get_image_url(entry):

    # --------------------------------------------------------
    # media_content
    # --------------------------------------------------------

    media_content = entry.get(
        "media_content",
        []
    )

    if media_content:

        for media in media_content:

            if isinstance(media, dict):

                url = media.get(
                    "url",
                    ""
                )

                if url:
                    return url.strip()

    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if media_thumbnail:

        for media in media_thumbnail:

            if isinstance(media, dict):

                url = media.get(
                    "url",
                    ""
                )

                if url:
                    return url.strip()

    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if enclosures:

        for enclosure in enclosures:

            if isinstance(enclosure, dict):

                url = enclosure.get(
                    "href",
                    ""
                ) or enclosure.get(
                    "url",
                    ""
                )

                media_type = enclosure.get(
                    "type",
                    ""
                ).lower()

                if url and (
                    media_type.startswith("image/")
                    or not media_type
                ):
                    return url.strip()

    # --------------------------------------------------------
    # استخراج عکس از HTML
    # --------------------------------------------------------

    html_fields = [
        entry.get("summary", ""),
        entry.get("description", "")
    ]

    for content in html_fields:

        if not content:
            continue

        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            content,
            re.IGNORECASE
        )

        if match:

            image_url = html.unescape(
                match.group(1)
            ).strip()

            if image_url:
                return image_url

    return ""


# ============================================================
# زمان انتشار خبر
# ============================================================

def get_published_time(entry):

    parsed_time = entry.get(
        "published_parsed"
    )

    if not parsed_time:

        parsed_time = entry.get(
            "updated_parsed"
        )

    if parsed_time:

        return datetime(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
            parsed_time.tm_hour,
            parsed_time.tm_min,
            parsed_time.tm_sec,
            tzinfo=timezone.utc
        )

    return None


# ============================================================
# بررسی تکراری بودن
# ============================================================

def is_duplicate(news, seen):

    normalized_link = normalize_url(
        news["link"]
    )

    normalized_title = normalize_title(
        news["title"]
    )

    new_source = (
        news["source"]
        .strip()
        .lower()
    )

    # بررسی لینک
    if normalized_link and normalized_link in seen:
        return True

    # بررسی عنوان + منبع
    if normalized_title:

        for old_data in seen.values():

            old_title = normalize_title(
                old_data.get("title", "")
            )

            old_source = (
                old_data
                .get("source", "")
                .strip()
                .lower()
            )

            if (
                old_title == normalized_title
                and old_source == new_source
            ):
                return True

    return False


# ============================================================
# ثبت خبر در seen_news
# ============================================================

def mark_as_seen(news, seen):

    normalized_link = normalize_url(
        news["link"]
    )

    if not normalized_link:
        return

    seen[normalized_link] = {

        "title": news["title"],

        "normalized_title":
            normalize_title(news["title"]),

        "source": news["source"],

        "published":
            news["published"].isoformat()
            if news["published"]
            else "",

        "sent_at":
            datetime.now(
                timezone.utc
            ).isoformat()
    }


# ============================================================
# فرار دادن کاراکترهای HTML
# ============================================================

def escape_html(text):

    if not text:
        return ""

    return html.escape(
        str(text),
        quote=False
    )


# ============================================================
# ارسال عکس به تلگرام
# ============================================================

def send_photo_to_telegram(news):

    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    published = news["published"]

    if published:

        iran_time = published.astimezone(
            IRAN_TZ
        )

        time_text = iran_time.strftime(
            "%H:%M"
        )

    else:

        time_text = "--:--"

    link = html.escape(
        news["link"],
        quote=True
    )

    caption = (
        f"📰 <b>{title}</b>\n\n"
        f"📌 {source}\n"
        f"🕐 {time_text}\n"
        f'🔗 <a href="{link}">مطالعه خبر</a>'
    )

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendPhoto"
    )

    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "photo": news["image"],
        "caption": caption,
        "parse_mode": "HTML"
    }

    try:

        response = requests.post(
            url,
            data=payload,
            timeout=30
        )

        if response.ok:

            print(
                "✓ عکس و خبر با موفقیت در تلگرام منتشر شد."
            )

            return True

        print(
            "خطا در ارسال عکس تلگرام:",
            response.text
        )

        return False

    except Exception as error:

        print(
            f"خطا در ارتباط با تلگرام: {error}"
        )

        return False


# ============================================================
# ارسال پیام متنی به تلگرام
# ============================================================

def send_text_to_telegram(news):

    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    published = news["published"]

    if published:

        iran_time = published.astimezone(
            IRAN_TZ
        )

        time_text = iran_time.strftime(
            "%H:%M"
        )

    else:

        time_text = "--:--"

    link = html.escape(
        news["link"],
        quote=True
    )

    message = (
        f"📰 <b>{title}</b>\n\n"
        f"📌 {source}\n"
        f"🕐 {time_text}\n"
        f'🔗 <a href="{link}">مطالعه خبر</a>'
    )

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:

        response = requests.post(
            url,
            data=payload,
            timeout=30
        )

        if response.ok:

            print(
                "✓ خبر متنی با موفقیت در تلگرام منتشر شد."
            )

            return True

        print(
            "خطا در ارسال تلگرام:",
            response.text
        )

        return False

    except Exception as error:

        print(
            f"خطا در ارتباط با تلگرام: {error}"
        )

        return False


# ============================================================
# ارسال خبر
# ============================================================

def send_to_telegram(news):

    # اگر عکس وجود دارد، ابتدا عکس را امتحان می‌کنیم
    if news.get("image"):

        success = send_photo_to_telegram(
            news
        )

        if success:
            return True

        print(
            "⚠️ ارسال عکس ناموفق بود؛ "
            "خبر به صورت متنی ارسال می‌شود."
        )

    # اگر عکس نداشت یا ارسال عکس شکست خورد
    return send_text_to_telegram(
        news
    )


# ============================================================
# ذخیره seen_news در GitHub
# ============================================================

def commit_seen_file():

    try:

        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                SEEN_FILE
            ],
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():

            print(
                "تغییری در seen_news.json وجود ندارد."
            )

            return True

        subprocess.run(
            [
                "git",
                "config",
                "user.name",
                "github-actions[bot]"
            ],
            check=True
        )

        subprocess.run(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]"
                "@users.noreply.github.com"
            ],
            check=True
        )

        subprocess.run(
            [
                "git",
                "add",
                SEEN_FILE
            ],
            check=True
        )

        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Update seen news"
            ],
            check=True
        )

        subprocess.run(
            [
                "git",
                "push"
            ],
            check=True
        )

        print(
            "✓ seen_news.json در GitHub ذخیره شد."
        )

        return True

    except subprocess.CalledProcessError as error:

        print(
            f"خطا در ذخیره seen_news در GitHub: {error}"
        )

        return False

    except Exception as error:

        print(
            f"خطای غیرمنتظره در GitHub: {error}"
        )

        return False


# ============================================================
# دریافت خبرهای یک RSS
# ============================================================

def get_news_from_feed(feed_info):

    source = feed_info["name"]
    feed_url = feed_info["url"]

    print(
        f"\nدر حال بررسی: {source}"
    )

    try:

        feed = feedparser.parse(
            feed_url
        )

        print(
            f"تعداد خبرهای RSS: {len(feed.entries)}"
        )

        news_list = []

        for entry in feed.entries:

            title = html.unescape(
                entry.get(
                    "title",
                    ""
                )
            ).strip()

            link = entry.get(
                "link",
                ""
            ).strip()

            if not title or not link:
                continue

            published = get_published_time(
                entry
            )

            if not published:
                continue

            image = get_image_url(
                entry
            )

            news_list.append({

                "title": title,

                "link": link,

                "published": published,

                "source": source,

                "image": image
            })

        return news_list

    except Exception as error:

        print(
            f"خطا در RSS {source}: {error}"
        )

        return []


# ============================================================
# بررسی تمام RSS ها
# ============================================================

def check_feeds(seen):

    total_sent = 0
    changed = False

    now_utc = datetime.now(
        timezone.utc
    )

    cutoff_time = (
        now_utc
        - timedelta(hours=NEWS_WINDOW_HOURS)
    )

    print(
        "\nزمان فعلی ایران:",
        iran_now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        f"پنجره بررسی: "
        f"{NEWS_WINDOW_HOURS} ساعت اخیر"
    )

    print(
        "از زمان:",
        cutoff_time.astimezone(
            IRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        "تا زمان:",
        now_utc.astimezone(
            IRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # --------------------------------------------------------
    # جمع‌آوری خبرهای واجد شرایط
    # --------------------------------------------------------

    all_news = []

    for feed_info in load_feeds():

        news_list = get_news_from_feed(
            feed_info
        )

        for news in news_list:

            if news["published"] < cutoff_time:
                continue

            if news["published"] > now_utc:
                continue

            if is_duplicate(
                news,
                seen
            ):
                continue

            all_news.append(
                news
            )

    # --------------------------------------------------------
    # مرتب‌سازی از قدیمی به جدید
    # --------------------------------------------------------

    all_news.sort(
        key=lambda news: news["published"]
    )

    print(
        f"\nتعداد خبرهای جدید واجد شرایط: "
        f"{len(all_news)}"
    )

    # --------------------------------------------------------
    # ارسال
    # --------------------------------------------------------

    for news in all_news:

        print(
            "\nخبر جدید پیدا شد:"
        )

        print(
            f"عنوان: {news['title']}"
        )

        iran_published = (
            news["published"]
            .astimezone(IRAN_TZ)
        )

        print(
            "زمان:",
            iran_published.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        print(
            f"منبع: {news['source']}"
        )

        if news.get("image"):

            print(
                "عکس: پیدا شد"
            )

        else:

            print(
                "عکس: پیدا نشد"
            )

        # ----------------------------------------------------
        # ارسال
        # ----------------------------------------------------

        success = send_to_telegram(
            news
        )

        if not success:

            print(
                "⚠️ خبر در seen_news ثبت نشد "
                "چون ارسال تلگرام ناموفق بود."
            )

            continue

        # ----------------------------------------------------
        # ثبت فقط پس از ارسال موفق
        # ----------------------------------------------------

        mark_as_seen(
            news,
            seen
        )

        changed = True
        total_sent += 1

        print(
            "✓ خبر در seen_news ثبت شد."
        )

    # --------------------------------------------------------
    # ذخیره در GitHub
    # --------------------------------------------------------

    if changed:

        save_seen(
            seen
        )

        print(
            "\nدر حال ذخیره seen_news.json در GitHub..."
        )

        commit_seen_file()

    else:

        print(
            "\nهیچ خبر جدیدی ارسال نشد؛ "
            "seen_news تغییری نکرد."
        )

    return total_sent


# ============================================================
# برنامه اصلی
# ============================================================

def main():

    print("=" * 70)
    print("شروع بررسی RSS")
    print("=" * 70)

    feeds = load_feeds()

    print(
        f"تعداد RSSها: {len(feeds)}"
    )

    seen = load_seen()

    print(
        f"تعداد خبرهای قبلاً ثبت‌شده: {len(seen)}"
    )

    print("=" * 70)

    sent = check_feeds(
        seen
    )

    print("=" * 70)

    print(
        f"تعداد خبرهای جدید ارسال‌شده: {sent}"
    )

    print(
        "بررسی RSS این اجرا تمام شد."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
