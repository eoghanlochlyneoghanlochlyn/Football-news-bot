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

# فقط خبرهای ۲ ساعت اخیر
NEWS_WINDOW_HOURS = 2

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


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
# تشخیص ابعاد تصویر
# ============================================================

def get_image_size(item):

    if not isinstance(item, dict):
        return 0

    width = item.get("width")
    height = item.get("height")

    try:

        width = int(width or 0)
        height = int(height or 0)

        return width * height

    except Exception:

        return 0


# ============================================================
# استخراج URL تصویر از یک آیتم
# ============================================================

def extract_image_url(item):

    if not isinstance(item, dict):
        return ""

    for key in ["url", "href"]:

        value = item.get(key)

        if value:
            return html.unescape(
                str(value).strip()
            )

    return ""


# ============================================================
# بهبود URL تصویر
# ============================================================

def upgrade_image_url(url):

    if not url:
        return ""

    original = url

    replacements = [

        # BBC
        ("/240/", "/1200/"),
        ("/320/", "/1200/"),
        ("/480/", "/1200/"),
        ("/640/", "/1200/"),
        ("/720/", "/1200/"),

        # الگوهای رایج عرض تصویر
        ("width=240", "width=1200"),
        ("width=320", "width=1200"),
        ("width=480", "width=1200"),
        ("width=640", "width=1200"),
        ("width=720", "width=1200"),

        ("w=240", "w=1200"),
        ("w=320", "w=1200"),
        ("w=480", "w=1200"),
        ("w=640", "w=1200"),
        ("w=720", "w=1200"),

        # پارامترهای کیفیت رایج
        ("quality=60", "quality=90"),
        ("quality=70", "quality=90"),
        ("quality=75", "quality=90"),
        ("quality=80", "quality=90"),
    ]

    upgraded = original

    for old, new in replacements:
        upgraded = upgraded.replace(
            old,
            new
        )

    return upgraded


# ============================================================
# پیدا کردن بهترین تصویر داخل RSS
# ============================================================

def get_best_rss_image(entry):

    candidates = []

    # --------------------------------------------------------
    # media_content
    # --------------------------------------------------------

    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(media_content, list):

        for item in media_content:

            url = extract_image_url(item)

            if url:

                candidates.append({
                    "url": url,
                    "size": get_image_size(item)
                })

    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(media_thumbnail, list):

        for item in media_thumbnail:

            url = extract_image_url(item)

            if url:

                candidates.append({
                    "url": url,
                    "size": get_image_size(item)
                })

    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(enclosures, list):

        for item in enclosures:

            if not isinstance(item, dict):
                continue

            media_type = (
                item.get("type", "")
                .lower()
            )

            url = extract_image_url(item)

            if (
                url
                and (
                    media_type.startswith("image/")
                    or not media_type
                )
            ):

                candidates.append({
                    "url": url,
                    "size": get_image_size(item)
                })

    # --------------------------------------------------------
    # HTML داخل RSS
    # --------------------------------------------------------

    html_fields = [
        entry.get("summary", ""),
        entry.get("description", ""),
        entry.get("content", "")
    ]

    for content in html_fields:

        if isinstance(content, list):

            content = " ".join(
                str(x.get("value", ""))
                for x in content
                if isinstance(x, dict)
            )

        if not content:
            continue

        # src
        matches = re.findall(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            str(content),
            re.IGNORECASE
        )

        for image_url in matches:

            image_url = html.unescape(
                image_url
            ).strip()

            if image_url:

                candidates.append({
                    "url": image_url,
                    "size": 0
                })

        # srcset
        srcset_matches = re.findall(
            r'srcset=["\']([^"\']+)["\']',
            str(content),
            re.IGNORECASE
        )

        for srcset in srcset_matches:

            parts = srcset.split(",")

            for part in parts:

                url_part = part.strip().split(" ")[0]

                if url_part:

                    candidates.append({
                        "url": html.unescape(
                            url_part
                        ).strip(),
                        "size": 0
                    })

    if not candidates:
        return ""

    # حذف URLهای تکراری
    unique = {}

    for candidate in candidates:

        url = candidate["url"]

        if url not in unique:

            unique[url] = candidate

        elif (
            candidate["size"]
            > unique[url]["size"]
        ):

            unique[url] = candidate

    candidates = list(
        unique.values()
    )

    # بزرگ‌ترین تصویر RSS
    candidates.sort(
        key=lambda x: x["size"],
        reverse=True
    )

    best = candidates[0]["url"]

    # اگر نسخهٔ کوچک بود، نسخهٔ بزرگ‌تر را امتحان می‌کنیم
    upgraded = upgrade_image_url(
        best
    )

    if upgraded != best:

        print(
            "✓ نسخهٔ باکیفیت‌تر تصویر RSS پیدا شد."
        )

        return upgraded

    return best


# ============================================================
# استخراج تصویر اصلی از صفحهٔ خبر
# ============================================================

def get_image_from_article_page(url):

    if not url:
        return ""

    try:

        print(
            "در حال جستجوی تصویر اصلی صفحهٔ خبر..."
        )

        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=20
        )

        if not response.ok:

            print(
                f"صفحهٔ خبر با خطای "
                f"{response.status_code} باز شد."
            )

            return ""

        content = response.text

        # ----------------------------------------------------
        # اولویت ۱: og:image
        # ----------------------------------------------------

        patterns = [

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                content,
                re.IGNORECASE
            )

            if match:

                image_url = html.unescape(
                    match.group(1)
                ).strip()

                if image_url:

                    # اگر URL نسبی بود
                    if image_url.startswith("//"):

                        image_url = (
                            "https:"
                            + image_url
                        )

                    elif image_url.startswith("/"):

                        parts = urlsplit(url)

                        image_url = (
                            f"{parts.scheme}://"
                            f"{parts.netloc}"
                            f"{image_url}"
                        )

                    image_url = upgrade_image_url(
                        image_url
                    )

                    print(
                        "✓ تصویر اصلی از og:image "
                        "پیدا شد."
                    )

                    return image_url

        # ----------------------------------------------------
        # اولویت ۲: لینک preload تصویر
        # ----------------------------------------------------

        preload_patterns = [

            r'<link[^>]+rel=["\']preload["\'][^>]+href=["\']([^"\']+)["\']',

            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']preload["\']'
        ]

        for pattern in preload_patterns:

            matches = re.findall(
                pattern,
                content,
                re.IGNORECASE
            )

            for image_url in matches:

                image_url = html.unescape(
                    image_url
                ).strip()

                if not image_url:
                    continue

                if (
                    ".jpg" in image_url.lower()
                    or ".jpeg" in image_url.lower()
                    or ".png" in image_url.lower()
                    or ".webp" in image_url.lower()
                ):

                    if image_url.startswith("//"):

                        image_url = (
                            "https:"
                            + image_url
                        )

                    elif image_url.startswith("/"):

                        parts = urlsplit(url)

                        image_url = (
                            f"{parts.scheme}://"
                            f"{parts.netloc}"
                            f"{image_url}"
                        )

                    image_url = upgrade_image_url(
                        image_url
                    )

                    print(
                        "✓ تصویر از preload پیدا شد."
                    )

                    return image_url

        # ----------------------------------------------------
        # اولویت ۳: اولین تصویر بزرگ HTML
        # ----------------------------------------------------

        image_candidates = []

        img_tags = re.findall(
            r"<img\b[^>]*>",
            content,
            re.IGNORECASE
        )

        for tag in img_tags:

            src_matches = re.findall(
                r'(?:src|data-src|data-original)=["\']([^"\']+)["\']',
                tag,
                re.IGNORECASE
            )

            for image_url in src_matches:

                image_url = html.unescape(
                    image_url
                ).strip()

                if not image_url:
                    continue

                if image_url.startswith("//"):

                    image_url = (
                        "https:"
                        + image_url
                    )

                elif image_url.startswith("/"):

                    parts = urlsplit(url)

                    image_url = (
                        f"{parts.scheme}://"
                        f"{parts.netloc}"
                        f"{image_url}"
                    )

                image_candidates.append(
                    image_url
                )

        # حذف تکراری‌ها
        image_candidates = list(
            dict.fromkeys(
                image_candidates
            )
        )

        # اول تصاویر بزرگ‌تر و رایج‌تر
        preferred = []

        for image_url in image_candidates:

            lower = image_url.lower()

            if any(
                extension in lower
                for extension in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ]
            ):

                preferred.append(
                    image_url
                )

        if preferred:

            image_url = upgrade_image_url(
                preferred[0]
            )

            print(
                "✓ تصویر از HTML صفحه پیدا شد."
            )

            return image_url

    except Exception as error:

        print(
            f"خطا در استخراج تصویر صفحه: {error}"
        )

    return ""


# ============================================================
# پیدا کردن بهترین عکس
# ============================================================

def get_best_image(entry, article_url):

    # --------------------------------------------------------
    # مرحله ۱: RSS
    # --------------------------------------------------------

    rss_image = get_best_rss_image(
        entry
    )

    if rss_image:

        print(
            "✓ تصویر از RSS پیدا شد."
        )

        return rss_image

    # --------------------------------------------------------
    # مرحله ۲: صفحهٔ خبر
    # --------------------------------------------------------

    print(
        "⚠️ تصویر مناسب در RSS پیدا نشد."
    )

    page_image = get_image_from_article_page(
        article_url
    )

    if page_image:
        return page_image

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

    if normalized_link and normalized_link in seen:
        return True

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
# ثبت خبر
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
# HTML escaping
# ============================================================

def escape_html(text):

    if not text:
        return ""

    return html.escape(
        str(text),
        quote=False
    )


# ============================================================
# ارسال عکس
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
                "✓ عکس و خبر با موفقیت منتشر شد."
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
# ارسال متن
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
                "✓ خبر متنی با موفقیت منتشر شد."
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

            news_list.append({

                "title": title,

                "link": link,

                "published": published,

                "source": source,

                "entry": entry,

                "image": ""
            })

        return news_list

    except Exception as error:

        print(
            f"خطا در RSS {source}: {error}"
        )

        return []


# ============================================================
# بررسی RSS ها
# ============================================================

def check_feeds(seen):

    total_sent = 0
    changed = False

    now_utc = datetime.now(
        timezone.utc
    )

    cutoff_time = (
        now_utc
        - timedelta(
            hours=NEWS_WINDOW_HOURS
        )
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
    # جمع‌آوری خبرهای جدید
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
    # قدیمی‌ترها اول
    # --------------------------------------------------------

    all_news.sort(
        key=lambda news: news["published"]
    )

    print(
        f"\nتعداد خبرهای جدید واجد شرایط: "
        f"{len(all_news)}"
    )

    # --------------------------------------------------------
    # پردازش و ارسال
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

        # ----------------------------------------------------
        # پیدا کردن بهترین عکس
        # ----------------------------------------------------

        news["image"] = get_best_image(
            news["entry"],
            news["link"]
        )

        if news["image"]:

            print(
                "عکس: پیدا شد"
            )

            print(
                f"آدرس عکس: {news['image']}"
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
        # ثبت پس از ارسال موفق
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
    # ذخیره
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
