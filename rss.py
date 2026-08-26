import html
import json
from datetime import datetime, timezone, timedelta

import feedparser
import requests

from config import (
    FEEDS_FILE,
    NEWS_WINDOW_HOURS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)

from utils import clean_text


# ============================================================
# خواندن فهرست RSSها
# ============================================================

def load_feeds():
    """
    feeds.json را می‌خواند و فهرست RSSها را برمی‌گرداند.
    """

    try:

        with open(
            FEEDS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, list):

            return data

        if isinstance(data, dict):

            feeds = data.get(
                "feeds",
                []
            )

            if isinstance(feeds, list):

                return feeds

        print(
            f"⚠️ ساختار {FEEDS_FILE} معتبر نیست."
        )

        return []

    except FileNotFoundError:

        print(
            f"❌ فایل {FEEDS_FILE} پیدا نشد."
        )

        return []

    except json.JSONDecodeError as error:

        print(
            f"❌ خطا در ساختار JSON فایل "
            f"{FEEDS_FILE}: {error}"
        )

        return []

    except Exception as error:

        print(
            f"❌ خطا در خواندن {FEEDS_FILE}: {error}"
        )

        return []


# ============================================================
# تبدیل زمان RSS به UTC
# ============================================================

def get_published_time(entry):
    """
    زمان انتشار یا به‌روزرسانی خبر را از RSS استخراج می‌کند
    و به UTC تبدیل می‌کند.
    """

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

    except Exception as error:

        print(
            f"⚠️ خطا در تبدیل زمان خبر: {error}"
        )

        return None


# ============================================================
# استخراج عنوان
# ============================================================

def get_entry_title(entry):
    """
    عنوان خبر را تمیز و HTML-decoded برمی‌گرداند.
    """

    title = entry.get(
        "title",
        ""
    )

    if not title:

        return ""

    title = html.unescape(
        str(title)
    )

    return clean_text(
        title
    )


# ============================================================
# استخراج لینک
# ============================================================

def get_entry_link(entry):
    """
    لینک اصلی خبر را استخراج می‌کند.
    """

    link = entry.get(
        "link",
        ""
    )

    if not link:

        return ""

    return html.unescape(
        str(link).strip()
    )


# ============================================================
# دریافت RSS
# ============================================================

def fetch_feed(feed_url):
    """
    RSS را دریافت و parse می‌کند.

    از requests استفاده می‌کنیم تا کنترل بیشتری روی
    timeout و headerها داشته باشیم.
    """

    if not feed_url:

        return None

    try:

        response = requests.get(
            feed_url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        return feed

    except requests.RequestException as error:

        print(
            f"❌ خطا در دریافت RSS "
            f"{feed_url}: {error}"
        )

        return None

    except Exception as error:

        print(
            f"❌ خطا در پردازش RSS "
            f"{feed_url}: {error}"
        )

        return None


# ============================================================
# دریافت خبرهای یک RSS
# ============================================================

def get_news_from_feed(feed_info):
    """
    تمام خبرهای معتبر یک RSS را استخراج می‌کند.
    """

    if not isinstance(
        feed_info,
        dict
    ):

        return []

    source = str(
        feed_info.get(
            "name",
            "Unknown"
        )
    ).strip()

    feed_url = str(
        feed_info.get(
            "url",
            ""
        )
    ).strip()

    print(
        f"\nدر حال بررسی: {source}"
    )

    if not feed_url:

        print(
            "⚠️ آدرس RSS خالی است."
        )

        return []

    feed = fetch_feed(
        feed_url
    )

    if feed is None:

        return []

    entries = getattr(
        feed,
        "entries",
        []
    )

    print(
        f"تعداد خبرهای RSS: {len(entries)}"
    )

    news_list = []

    for entry in entries:

        title = get_entry_title(
            entry
        )

        link = get_entry_link(
            entry
        )

        if not title or not link:

            continue

        published = get_published_time(
            entry
        )

        if not published:

            continue

        news = {

            "title": title,

            "link": link,

            "published": published,

            "source": source,

            # کل entry را نگه می‌داریم.
            # برای پیدا کردن تصویر و اطلاعات
            # تکمیلی خبر استفاده خواهد شد.
            "entry": entry,

            # بعداً در مرحله پردازش تکمیل می‌شود.
            "image": "",

            # بعداً توسط مترجم تکمیل می‌شود.
            "translated_title": "",

            "translated_body": ""
        }

        news_list.append(
            news
        )

    return news_list


# ============================================================
# دریافت خبرهای تمام RSSها
# ============================================================

def collect_all_news():
    """
    خبرهای تمام RSSها را جمع‌آوری می‌کند.
    """

    feeds = load_feeds()

    if not feeds:

        print(
            "⚠️ هیچ منبع RSS برای بررسی وجود ندارد."
        )

        return []

    all_news = []

    for feed_info in feeds:

        if not isinstance(
            feed_info,
            dict
        ):

            print(
                "⚠️ یک ورودی RSS نامعتبر نادیده گرفته شد."
            )

            continue

        news_list = get_news_from_feed(
            feed_info
        )

        all_news.extend(
            news_list
        )

    return all_news


# ============================================================
# محدود کردن خبرها به پنجره زمانی
# ============================================================

def filter_by_time(
    news_list,
    window_hours=NEWS_WINDOW_HOURS
):
    """
    فقط خبرهای منتشرشده در بازه زمانی تعیین‌شده
    را نگه می‌دارد.
    """

    if not news_list:

        return []

    now_utc = datetime.now(
        timezone.utc
    )

    cutoff_time = (
        now_utc
        - timedelta(
            hours=window_hours
        )
    )

    filtered = []

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):

            continue

        published = news.get(
            "published"
        )

        if not published:

            continue

        # اگر زمان بدون timezone باشد،
        # برای جلوگیری از مقایسه نادرست
        # آن را UTC در نظر می‌گیریم.
        if published.tzinfo is None:

            published = published.replace(
                tzinfo=timezone.utc
            )

        # خبر آینده را قبول نمی‌کنیم.
        if published > now_utc:

            continue

        # خبر قدیمی‌تر از پنجره را حذف می‌کنیم.
        if published < cutoff_time:

            continue

        filtered.append(
            news
        )

    return filtered


# ============================================================
# مرتب‌سازی زمانی
# ============================================================

def sort_news_by_time(
    news_list,
    newest_first=False
):
    """
    خبرها را بر اساس زمان انتشار مرتب می‌کند.
    """

    if not news_list:

        return []

    return sorted(

        news_list,

        key=lambda news:
            news.get(
                "published",
                datetime.min.replace(
                    tzinfo=timezone.utc
                )
            ),

        reverse=newest_first
    )


# ============================================================
# حذف خبرهای تکراری داخل همان RSSها
# ============================================================

def remove_duplicate_news(
    news_list
):
    """
    خبرهایی که لینک یکسان دارند را حذف می‌کند.

    این تابع فقط تکراری‌های موجود در همان اجرای فعلی
    را حذف می‌کند.

    تشخیص خبرهایی که قبلاً در کانال منتشر شده‌اند
    وظیفه seen_news است.
    """

    if not news_list:

        return []

    unique_news = []

    seen_links = set()

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):

            continue

        link = str(
            news.get(
                "link",
                ""
            )
        ).strip()

        if not link:

            continue

        if link in seen_links:

            continue

        seen_links.add(
            link
        )

        unique_news.append(
            news
        )

    return unique_news


# ============================================================
# دریافت خبرهای جدید در پنجره زمانی
# ============================================================

def collect_recent_news():
    """
    RSSها را بررسی می‌کند و فقط خبرهای داخل
    پنجره زمانی را برمی‌گرداند.
    """

    all_news = collect_all_news()

    if not all_news:

        print(
            "\nهیچ خبری از RSSها دریافت نشد."
        )

        return []

    recent_news = filter_by_time(
        all_news
    )

    recent_news = remove_duplicate_news(
        recent_news
    )

    recent_news = sort_news_by_time(
        recent_news,
        newest_first=False
    )

    print(
        f"\nتعداد خبرهای داخل پنجره زمانی: "
        f"{len(recent_news)}"
    )

    return recent_news
