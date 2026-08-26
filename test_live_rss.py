import json
import os
import re
import subprocess
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, urljoin

import feedparser
import requests


FEEDS_FILE = "feeds.json"
SEEN_FILE = "seen_news.json"

NEWS_WINDOW_HOURS = 2
MIN_IMAGE_WIDTH = 800

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def iran_now():
    return datetime.now(IRAN_TZ)


def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("feeds", [])

    return []


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except Exception as error:
        print(f"خطا در خواندن {SEEN_FILE}: {error}")
        return {}


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(
            seen,
            file,
            ensure_ascii=False,
            indent=2,
        )


def normalize_url(url):
    if not url:
        return ""

    url = html.unescape(str(url).strip())

    try:
        parts = urlsplit(url)

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/"),
                "",
                "",
            )
        )

    except Exception:
        return url.strip()


def normalize_title(title):
    if not title:
        return ""

    title = html.unescape(str(title))
    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"\s+", " ", title)
    title = title.strip().lower()

    title = re.sub(
        r"[\"'“”‘’`]",
        "",
        title,
    )

    title = re.sub(
        r"[.,!?;:()\[\]{}]",
        "",
        title,
    )

    return title.strip()


def get_published_time(entry):
    parsed_time = entry.get("published_parsed")

    if not parsed_time:
        parsed_time = entry.get("updated_parsed")

    if not parsed_time:
        return None

    return datetime(
        parsed_time.tm_year,
        parsed_time.tm_mon,
        parsed_time.tm_mday,
        parsed_time.tm_hour,
        parsed_time.tm_min,
        parsed_time.tm_sec,
        tzinfo=timezone.utc,
    )


def extract_image_url(item):
    if not isinstance(item, dict):
        return ""

    for key in ("url", "href"):
        value = item.get(key)

        if value:
            return html.unescape(str(value).strip())

    return ""


def get_image_dimensions(item):
    if not isinstance(item, dict):
        return 0, 0

    try:
        width = int(item.get("width", 0) or 0)
    except Exception:
        width = 0

    try:
        height = int(item.get("height", 0) or 0)
    except Exception:
        height = 0

    return width, height


def looks_like_thumbnail(url):
    if not url:
        return False

    lower = url.lower()

    patterns = [
        r"-\d{2,4}x\d{2,4}(?:\.[a-z0-9]+)(?:\?|$)",
        r"_\d{2,4}x\d{2,4}(?:\.[a-z0-9]+)(?:\?|$)",
        r"/\d{2,4}x\d{2,4}/",
        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",
        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",
    ]

    return any(
        re.search(pattern, lower)
        for pattern in patterns
    )


def get_jpeg_dimensions(data):
    try:
        if len(data) < 2 or data[:2] != b"\xff\xd8":
            return 0, 0

        index = 2

        while index + 4 <= len(data):
            if data[index] != 0xFF:
                index += 1
                continue

            while index < len(data) and data[index] == 0xFF:
                index += 1

            if index >= len(data):
                break

            marker = data[index]
            index += 1

            if marker in (0xD8, 0xD9):
                continue

            if index + 2 > len(data):
                break

            length = int.from_bytes(
                data[index:index + 2],
                "big",
            )

            if length < 2:
                break

            if marker in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):
                if index + 7 <= len(data):
                    height = int.from_bytes(
                        data[index + 3:index + 5],
                        "big",
                    )

                    width = int.from_bytes(
                        data[index + 5:index + 7],
                        "big",
                    )

                    return width, height

            index += length

    except Exception:
        pass

    return 0, 0


def get_real_image_dimensions(url):
    try:
        response = requests.get(
            url,
            headers={
                **REQUEST_HEADERS,
                "Range": "bytes=0-65535",
            },
            timeout=15,
            stream=True,
        )

        if not response.ok:
            return 0, 0

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        data = response.content

        if "jpeg" in content_type or url.lower().split("?")[0].endswith(
            (".jpg", ".jpeg")
        ):
            return get_jpeg_dimensions(data)

        if "png" in content_type or url.lower().split("?")[0].endswith(
            ".png"
        ):
            if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
                width = int.from_bytes(data[16:20], "big")
                height = int.from_bytes(data[20:24], "big")
                return width, height

        if "gif" in content_type or url.lower().split("?")[0].endswith(
            ".gif"
        ):
            if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
                width = int.from_bytes(data[6:8], "little")
                height = int.from_bytes(data[8:10], "little")
                return width, height

        return 0, 0

    except Exception:
        return 0, 0


def get_rss_image_candidates(entry):
    candidates = []

    for key, priority in (
        ("media_content", 100),
        ("media_thumbnail", 30),
        ("enclosures", 90),
    ):
        items = entry.get(key, [])

        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            url = extract_image_url(item)

            if not url:
                continue

            if key == "enclosures":
                media_type = item.get("type", "").lower()

                if media_type and not media_type.startswith("image/"):
                    continue

            width, height = get_image_dimensions(item)

            candidates.append(
                {
                    "url": url,
                    "width": width,
                    "height": height,
                    "priority": priority,
                }
            )

    for field in (
        "summary",
        "description",
    ):
        content = entry.get(field, "")

        if not content:
            continue

        matches = re.findall(
            r'<img[^>]+(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)["\']',
            str(content),
            re.IGNORECASE,
        )

        for url in matches:
            candidates.append(
                {
                    "url": html.unescape(url).strip(),
                    "width": 0,
                    "height": 0,
                    "priority": 70,
                }
            )

    unique = {}

    for candidate in candidates:
        url = candidate["url"]

        if not url:
            continue

        if url not in unique:
            unique[url] = candidate
            continue

        if candidate["width"] > unique[url]["width"]:
            unique[url] = candidate

    return list(unique.values())


def get_best_rss_image(entry):
    candidates = get_rss_image_candidates(entry)

    if not candidates:
        return "", False

    candidates.sort(
        key=lambda item: (
            item["width"],
            item["priority"],
        ),
        reverse=True,
    )

    fallback = candidates[0]["url"]

    for candidate in candidates:
        url = candidate["url"]
        width = candidate["width"]

        if width >= MIN_IMAGE_WIDTH:
            print(f"✓ تصویر RSS مناسب است: {width}px")
            return url, True

        if width > 0 and width < MIN_IMAGE_WIDTH:
            print(f"⚠️ تصویر RSS کوچک است: {width}px")
            continue

        if looks_like_thumbnail(url):
            print("⚠️ تصویر RSS بندانگشتی است.")
            continue

        real_width, _ = get_real_image_dimensions(url)

        if real_width >= MIN_IMAGE_WIDTH:
            print(f"✓ عرض واقعی تصویر RSS: {real_width}px")
            return url, True

        if real_width > 0 and real_width < MIN_IMAGE_WIDTH:
            print(f"⚠️ عرض واقعی تصویر RSS کم است: {real_width}px")
            continue

        print("✓ اندازه تصویر مشخص نیست، ولی URL بندانگشتی نیست.")
        return url, True

    return fallback, False


def make_absolute_url(image_url, article_url):
    if not image_url:
        return ""

    return urljoin(
        article_url,
        html.unescape(image_url).strip(),
    )


def get_article_image_candidates(content, article_url):
    candidates = []

    meta_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]

    for pattern in meta_patterns:
        for image_url in re.findall(
            pattern,
            content,
            re.IGNORECASE,
        ):
            image_url = make_absolute_url(
                image_url,
                article_url,
            )

            if image_url:
                candidates.append(
                    {
                        "url": image_url,
                        "priority": 100,
                    }
                )

    json_ld_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content,
        re.IGNORECASE | re.DOTALL,
    )

    for block in json_ld_blocks:
        try:
            data = json.loads(
                html.unescape(block.strip())
            )

            items = (
                [data]
                if isinstance(data, dict)
                else data
                if isinstance(data, list)
                else []
            )

            for item in items:
                if not isinstance(item, dict):
                    continue

                image = item.get("image")

                if isinstance(image, str):
                    image_url = make_absolute_url(
                        image,
                        article_url,
                    )

                    if image_url:
                        candidates.append(
                            {
                                "url": image_url,
                                "priority": 90,
                            }
                        )

                elif isinstance(image, list):
                    for image_item in image:
                        if isinstance(image_item, str):
                            image_url = make_absolute_url(
                                image_item,
                                article_url,
                            )

                            if image_url:
                                candidates.append(
                                    {
                                        "url": image_url,
                                        "priority": 90,
                                    }
                                )

        except Exception:
            continue

    img_tags = re.findall(
        r"<img\b[^>]*>",
        content,
        re.IGNORECASE,
    )

    for tag in img_tags:
        matches = re.findall(
            r'(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE,
        )

        for image_url in matches:
            image_url = make_absolute_url(
                image_url,
                article_url,
            )

            if image_url:
                candidates.append(
                    {
                        "url": image_url,
                        "priority": 50,
                    }
                )

    unique = {}

    for candidate in candidates:
        url = candidate["url"]

        if url and url not in unique:
            unique[url] = candidate

    return list(unique.values())


def get_best_article_image(article_url):
    try:
        print("در حال بررسی صفحهٔ خبر برای تصویر بهتر...")

        response = requests.get(
            article_url,
            headers=REQUEST_HEADERS,
            timeout=20,
        )

        if not response.ok:
            print(
                f"خطا در دریافت صفحه: {response.status_code}"
            )
            return ""

        candidates = get_article_image_candidates(
            response.text,
            article_url,
        )

        if not candidates:
            print("⚠️ تصویری در صفحه پیدا نشد.")
            return ""

        scored = []

        for candidate in candidates:
            url = candidate["url"]
            score = candidate["priority"]

            if looks_like_thumbnail(url):
                score -= 100

            real_width, _ = get_real_image_dimensions(url)

            if real_width >= MIN_IMAGE_WIDTH:
                score += 100
            elif real_width > 0:
                score -= 50

            scored.append(
                {
                    "url": url,
                    "score": score,
                    "width": real_width,
                }
            )

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        for item in scored:
            if item["score"] >= 100:
                print(
                    f"✓ تصویر باکیفیت صفحه پیدا شد: "
                    f"{item['width']}px"
                )
                print(
                    f"آدرس تصویر: {item['url']}"
                )
                return item["url"]

        print("⚠️ تصویر باکیفیت مناسبی در صفحه پیدا نشد.")
        return ""

    except Exception as error:
        print(
            f"خطا در بررسی صفحهٔ خبر: {error}"
        )
        return ""


def get_best_image(entry, article_url):
    rss_image, rss_is_good = get_best_rss_image(entry)

    if rss_image and rss_is_good:
        print("✓ از تصویر RSS استفاده می‌شود.")
        return rss_image

    if rss_image:
        print(
            "⚠️ تصویر RSS کوچک است؛ صفحهٔ خبر بررسی می‌شود."
        )

        article_image = get_best_article_image(
            article_url
        )

        if article_image:
            print(
                "✓ تصویر بهتر صفحهٔ خبر انتخاب شد."
            )
            return article_image

        print(
            "⚠️ تصویر بهتر پیدا نشد؛ "
            "همان تصویر RSS استفاده می‌شود."
        )

        return rss_image

    print(
        "⚠️ RSS تصویر ندارد؛ صفحهٔ خبر بررسی می‌شود."
    )

    return get_best_article_image(
        article_url
    )


def is_duplicate(news, seen):
    normalized_link = normalize_url(
        news["link"]
    )

    normalized_title = normalize_title(
        news["title"]
    )

    source = (
        news["source"]
        .strip()
        .lower()
    )

    if normalized_link and normalized_link in seen:
        return True

    for old_data in seen.values():
        old_title = normalize_title(
            old_data.get(
                "title",
                "",
            )
        )

        old_source = (
            old_data.get(
                "source",
                "",
            )
            .strip()
            .lower()
        )

        if (
            normalized_title
            and old_title == normalized_title
            and old_source == source
        ):
            return True

    return False


def mark_as_seen(news, seen):
    normalized_link = normalize_url(
        news["link"]
    )

    if not normalized_link:
        return

    seen[normalized_link] = {
        "title": news["title"],
        "normalized_title": normalize_title(
            news["title"]
        ),
        "source": news["source"],
        "published": (
            news["published"].isoformat()
            if news["published"]
            else ""
        ),
        "sent_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def escape_html(text):
    return html.escape(
        str(text),
        quote=False,
    )


def send_photo_to_telegram(news):
    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    if news["published"]:
        iran_time = news["published"].astimezone(
            IRAN_TZ
        )

        time_text = iran_time.strftime(
            "%H:%M"
        )
    else:
        time_text = "--:--"

    link = html.escape(
        news["link"],
        quote=True,
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
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=30,
        )

        if response.ok:
            print(
                "✓ عکس و خبر با موفقیت منتشر شد."
            )
            return True

        print(
            "خطا در ارسال عکس:",
            response.text,
        )

        return False

    except Exception as error:
        print(
            f"خطا در ارتباط با تلگرام: {error}"
        )
        return False


def send_text_to_telegram(news):
    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    if news["published"]:
        iran_time = news["published"].astimezone(
            IRAN_TZ
        )

        time_text = iran_time.strftime(
            "%H:%M"
        )
    else:
        time_text = "--:--"

    link = html.escape(
        news["link"],
        quote=True,
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
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=30,
        )

        if response.ok:
            print(
                "✓ خبر متنی با موفقیت منتشر شد."
            )
            return True

        print(
            "خطا در ارسال متن:",
            response.text,
        )

        return False

    except Exception as error:
        print(
            f"خطا در ارتباط با تلگرام: {error}"
        )
        return False


def send_to_telegram(news):
    if news.get("image"):
        if send_photo_to_telegram(news):
            return True

        print(
            "⚠️ ارسال عکس ناموفق بود؛ "
            "خبر به صورت متنی ارسال می‌شود."
        )

    return send_text_to_telegram(
        news
    )


def commit_seen_file():
    try:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                SEEN_FILE,
            ],
            capture_output=True,
            text=True,
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
                "github-actions[bot]",
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "add",
                SEEN_FILE,
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Update seen news",
            ],
            check=True,
        )

        subprocess.run(
            [
                "git",
                "push",
            ],
            check=True,
        )

        print(
            "✓ seen_news.json در GitHub ذخیره شد."
        )

        return True

    except Exception as error:
        print(
            f"خطا در ذخیره seen_news در GitHub: {error}"
        )

        return False


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
                    "",
                )
            ).strip()

            link = entry.get(
                "link",
                "",
            ).strip()

            if not title or not link:
                continue

            published = get_published_time(
                entry
            )

            if not published:
                continue

            news_list.append(
                {
                    "title": title,
                    "link": link,
                    "published": published,
                    "source": source,
                    "entry": entry,
                    "image": "",
                }
            )

        return news_list

    except Exception as error:
        print(
            f"خطا در RSS {source}: {error}"
        )

        return []


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
        ),
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
        ),
    )

    print(
        "تا زمان:",
        now_utc.astimezone(
            IRAN_TZ
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

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
                seen,
            ):
                continue

            all_news.append(
                news
            )

    all_news.sort(
        key=lambda news: news["published"]
    )

    print(
        f"\nتعداد خبرهای جدید واجد شرایط: "
        f"{len(all_news)}"
    )

    for news in all_news:
        print(
            "\nخبر جدید پیدا شد:"
        )

        print(
            f"عنوان: {news['title']}"
        )

        iran_published = news["published"].astimezone(
            IRAN_TZ
        )

        print(
            "زمان:",
            iran_published.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )

        print(
            f"منبع: {news['source']}"
        )

        news["image"] = get_best_image(
            news["entry"],
            news["link"],
        )

        if news["image"]:
            print(
                "عکس نهایی انتخاب شد."
            )
        else:
            print(
                "⚠️ هیچ عکسی پیدا نشد."
            )

        success = send_to_telegram(
            news
        )

        if not success:
            print(
                "⚠️ ارسال ناموفق بود؛ "
                "خبر در seen_news ثبت نشد."
            )
            continue

        mark_as_seen(
            news,
            seen
        )

        save_seen(
            seen
        )

        changed = True
        total_sent += 1

        print(
            "✓ خبر در seen_news ثبت شد."
        )

    if changed:
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
