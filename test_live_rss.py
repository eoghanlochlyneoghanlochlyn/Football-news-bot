import json
import os
import re
import subprocess
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, urljoin

import feedparser
import requests


# ============================================================
# تنظیمات
# ============================================================

FEEDS_FILE = "feeds.json"
SEEN_FILE = "seen_news.json"

# فقط خبرهای ۲ ساعت اخیر
NEWS_WINDOW_HOURS = 2

# حداقل عرض قابل قبول تصویر
MIN_IMAGE_WIDTH = 800

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


# ============================================================
# تنظیمات درخواست
# ============================================================

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
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

    with open(
        FEEDS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

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

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as error:

        print(
            f"خطا در خواندن {SEEN_FILE}: {error}"
        )

        return {}


# ============================================================
# ذخیره seen_news
# ============================================================

def save_seen(seen):

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
# نرمال‌سازی لینک
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(
        str(url).strip()
    )

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

    title = html.unescape(
        str(title)
    )

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
# استخراج URL تصویر
# ============================================================

def extract_image_url(item):

    if not isinstance(item, dict):
        return ""

    for key in [
        "url",
        "href"
    ]:

        value = item.get(key)

        if value:

            return html.unescape(
                str(value).strip()
            )

    return ""


# ============================================================
# استخراج ابعاد تصویر
# ============================================================

def get_image_dimensions(item):

    if not isinstance(item, dict):
        return 0, 0

    try:
        width = int(
            item.get("width", 0) or 0
        )
    except Exception:
        width = 0

    try:
        height = int(
            item.get("height", 0) or 0
        )
    except Exception:
        height = 0

    return width, height


# ============================================================
# تشخیص بندانگشتی از روی URL
# ============================================================

def looks_like_thumbnail_url(url):

    if not url:
        return False

    lower = url.lower()

    thumbnail_patterns = [

        # مثل:
        # image-150x150.jpg
        # image-300x169.jpg
        r"-\d{2,3}x\d{2,3}(?:\.[a-z0-9]+)(?:\?|$)",

        # مثل:
        # /150x150/
        r"/\d{2,3}x\d{2,3}/",

        # پارامترهای رایج
        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",

        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)"
    ]

    for pattern in thumbnail_patterns:

        if re.search(
            pattern,
            lower
        ):

            return True

    thumbnail_words = [
        "thumbnail",
        "thumb",
        "small",
        "tiny"
    ]

    for word in thumbnail_words:

        if word in lower:
            return True

    return False


# ============================================================
# بررسی ابعاد واقعی تصویر
#
# این تابع بدون دانلود کامل تصویر، فقط هدرهای تصویری
# را تا حد امکان بررسی می‌کند.
# ============================================================

def get_real_image_dimensions(image_url):

    if not image_url:
        return 0, 0

    try:

        response = requests.get(
            image_url,
            headers={
                **REQUEST_HEADERS,
                "Range": "bytes=0-65535"
            },
            timeout=15,
            stream=True
        )

        if not response.ok:
            return 0, 0

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if not content_type.startswith("image/"):
            return 0, 0

        data = response.content

        # ----------------------------------------------------
        # JPEG
        # ----------------------------------------------------

        if (
            content_type in [
                "image/jpeg",
                "image/jpg"
            ]
            or image_url.lower().split("?")[0].endswith(
                (".jpg", ".jpeg")
            )
        ):

            width, height = (
                get_jpeg_dimensions(data)
            )

            if width:
                return width, height

        # ----------------------------------------------------
        # PNG
        # ----------------------------------------------------

        if (
            content_type == "image/png"
            or image_url.lower().split("?")[0].endswith(
                ".png"
            )
        ):

            if len(data) >= 24:

                if data[:8] == b"\x89PNG\r\n\x1a\n":

                    width = int.from_bytes(
                        data[16:20],
                        "big"
                    )

                    height = int.from_bytes(
                        data[20:24],
                        "big"
                    )

                    return width, height

        # ----------------------------------------------------
        # GIF
        # ----------------------------------------------------

        if (
            content_type == "image/gif"
            or image_url.lower().split("?")[0].endswith(
                ".gif"
            )
        ):

            if len(data) >= 10:

                if data[:6] in [
                    b"GIF87a",
                    b"GIF89a"
                ]:

                    width = int.from_bytes(
                        data[6:8],
                        "little"
                    )

                    height = int.from_bytes(
                        data[8:10],
                        "little"
                    )

                    return width, height

        # ----------------------------------------------------
        # WebP
        # ----------------------------------------------------

        if (
            content_type == "image/webp"
            or image_url.lower().split("?")[0].endswith(
                ".webp"
            )
        ):

            if len(data) >= 30:

                if data[:4] == b"RIFF" and data[8:12] == b"WEBP":

                    # VP8X
                    if data[12:16] == b"VP8X":

                        width = (
                            1
                            + int.from_bytes(
                                data[24:27],
                                "little"
                            )
                        )

                        height = (
                            1
                            + int.from_bytes(
                                data[27:30],
                                "little"
                            )
                        )

                        return width, height

        return 0, 0

    except Exception:

        return 0, 0


# ============================================================
# تشخیص ابعاد JPEG
# ============================================================

def get_jpeg_dimensions(data):

    try:

        if len(data) < 2:
            return 0, 0

        if data[0:2] != b"\xff\xd8":
            return 0, 0

        index = 2

        while index < len(data):

            if data[index] != 0xFF:

                index += 1
                continue

            while (
                index < len(data)
                and data[index] == 0xFF
            ):

                index += 1

            if index >= len(data):
                break

            marker = data[index]
            index += 1

            # مارکرهای بدون طول
            if marker in [
                0xD8,
                0xD9
            ]:
                continue

            if index + 2 > len(data):
                break

            segment_length = int.from_bytes(
                data[index:index + 2],
                "big"
            )

            if segment_length < 2:
                break

            # SOF markers
            if marker in [
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
                0xCF
            ]:

                if index + 7 <= len(data):

                    height = int.from_bytes(
                        data[index + 3:index + 5],
                        "big"
                    )

                    width = int.from_bytes(
                        data[index + 5:index + 7],
                        "big"
                    )

                    return width, height

            index += segment_length

        return 0, 0

    except Exception:

        return 0, 0


# ============================================================
# استخراج تصاویر RSS
# ============================================================

def get_rss_image_candidates(entry):

    candidates = []

    # --------------------------------------------------------
    # media_content
    # --------------------------------------------------------

    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(
        media_content,
        list
    ):

        for item in media_content:

            url = extract_image_url(item)

            if not url:
                continue

            width, height = (
                get_image_dimensions(item)
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 100,
                "source": "media_content"
            })

    # --------------------------------------------------------
    # media_thumbnail
    # --------------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(
        media_thumbnail,
        list
    ):

        for item in media_thumbnail:

            url = extract_image_url(item)

            if not url:
                continue

            width, height = (
                get_image_dimensions(item)
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 30,
                "source": "media_thumbnail"
            })

    # --------------------------------------------------------
    # enclosures
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(
        enclosures,
        list
    ):

        for item in enclosures:

            if not isinstance(item, dict):
                continue

            url = extract_image_url(item)

            if not url:
                continue

            media_type = (
                item.get(
                    "type",
                    ""
                )
                .lower()
            )

            if (
                media_type
                and not media_type.startswith("image/")
            ):
                continue

            width, height = (
                get_image_dimensions(item)
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 90,
                "source": "enclosure"
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

        if isinstance(
            content,
            list
        ):

            content = " ".join(
                str(
                    item.get(
                        "value",
                        ""
                    )
                )
                for item in content
                if isinstance(
                    item,
                    dict
                )
            )

        if not content:
            continue

        # img src
        matches = re.findall(
            r'<img[^>]+(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)["\']',
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
                    "width": 0,
                    "height": 0,
                    "priority": 70,
                    "source": "rss_html"
                })

        # srcset
        srcsets = re.findall(
            r'srcset=["\']([^"\']+)["\']',
            str(content),
            re.IGNORECASE
        )

        for srcset in srcsets:

            for part in srcset.split(","):

                pieces = part.strip().split()

                if not pieces:
                    continue

                image_url = pieces[0]

                width = 0

                if len(pieces) > 1:

                    width_match = re.search(
                        r"(\d+)w",
                        pieces[1]
                    )

                    if width_match:
                        width = int(
                            width_match.group(1)
                        )

                candidates.append({
                    "url": html.unescape(
                        image_url
                    ).strip(),
                    "width": width,
                    "height": 0,
                    "priority": 80,
                    "source": "rss_srcset"
                })

    # --------------------------------------------------------
    # حذف URLهای تکراری
    # --------------------------------------------------------

    unique = {}

    for candidate in candidates:

        url = candidate["url"]

        if not url:
            continue

        if url not in unique:

            unique[url] = candidate

        else:

            old = unique[url]

            if (
                candidate["width"]
                > old["width"]
            ):

                unique[url] = candidate

    return list(
        unique.values()
    )


# ============================================================
# پیدا کردن بهترین تصویر RSS
# ============================================================

def get_best_rss_image(entry):

    candidates = (
        get_rss_image_candidates(
            entry
        )
    )

    if not candidates:

        return {
            "url": "",
            "good_quality": False
        }

    # اول بر اساس ابعاد اعلام‌شده
    candidates.sort(
        key=lambda item: (
            item["width"],
            item["priority"]
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # هر کاندید را بررسی می‌کنیم
    # --------------------------------------------------------

    for candidate in candidates:

        url = candidate["url"]

        width = candidate["width"]

        # اگر RSS خودش عرض را داده
        if width > 0:

            if width >= MIN_IMAGE_WIDTH:

                print(
                    f"✓ تصویر RSS مناسب است "
                    f"({width}px)"
                )

                return {
                    "url": url,
                    "good_quality": True
                }

            print(
                f"⚠️ تصویر RSS کوچک است "
                f"({width}px)"
            )

            continue

        # اگر URL نشانهٔ واضحی از thumbnail دارد
        if looks_like_thumbnail_url(url):

            print(
                "⚠️ تصویر RSS بندانگشتی به نظر می‌رسد."
            )

            continue

        # ----------------------------------------------------
        # عرض واقعی تصویر را بررسی می‌کنیم
        # ----------------------------------------------------

        real_width, real_height = (
            get_real_image_dimensions(
                url
            )
        )

        if real_width > 0:

            print(
                f"عرض واقعی تصویر RSS: "
                f"{real_width}px"
            )

            if real_width >= MIN_IMAGE_WIDTH:

                print(
                    "✓ تصویر RSS کیفیت مناسب دارد."
                )

                return {
                    "url": url,
                    "good_quality": True
                }

            print(
                "⚠️ تصویر RSS کیفیت کافی ندارد."
            )

            continue

        # اگر نتوانستیم اندازه را بفهمیم،
        # ولی URL هم نشانه‌ای از thumbnail ندارد،
        # فعلاً آن را قابل‌قبول در نظر می‌گیریم.

        print(
            "✓ اندازه تصویر مشخص نشد، "
            "ولی نشانه‌ای از بندانگشتی بودن وجود ندارد."
        )

        return {
            "url": url,
            "good_quality": True
        }

    # اگر هیچ تصویر مناسبی نبود،
    # بهترین تصویر موجود RSS را به عنوان fallback نگه می‌داریم.

    fallback = candidates[0]["url"]

    return {
        "url": fallback,
        "good_quality": False
    }


# ============================================================
# تبدیل لینک نسبی به کامل
# ============================================================

def make_absolute_url(
    image_url,
    article_url
):

    if not image_url:
        return ""

    image_url = html.unescape(
        image_url
    ).strip()

    return urljoin(
        article_url,
        image_url
    )


# ============================================================
# استخراج تصاویر صفحهٔ خبر
# ============================================================

def get_article_images(
    content,
    article_url
):

    candidates = []

    # --------------------------------------------------------
    # og:image
    # --------------------------------------------------------

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            content,
            re.IGNORECASE
        )

        for image_url in matches:

            image_url = make_absolute_url(
                image_url,
                article_url
            )

            if image_url:

                candidates.append({
                    "url": image_url,
                    "priority": 100
                })

    # --------------------------------------------------------
    # تصاویر JSON-LD
    # --------------------------------------------------------

    json_ld_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content,
        re.IGNORECASE | re.DOTALL
    )

    for block in json_ld_blocks:

        try:

            data = json.loads(
                html.unescape(
                    block.strip()
                )
            )

            if isinstance(
                data,
                dict
            ):

                items = [data]

            elif isinstance(
                data,
                list
            ):

                items = data

            else:

                items = []

            for item in items:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                image = item.get(
                    "image"
                )

                if isinstance(
                    image,
                    str
                ):

                    image_url = make_absolute_url(
                        image,
                        article_url
                    )

                    if image_url:

                        candidates.append({
                            "url": image_url,
                            "priority": 90
                        })

                elif isinstance(
                    image,
                    list
                ):

                    for image_item in image:

                        if isinstance(
                            image_item,
                            str
                        ):

                            image_url = make_absolute_url(
                                image_item,
                                article_url
                            )

                            if image_url:

                                candidates.append({
                                    "url": image_url,
                                    "priority": 90
                                })

        except Exception:
            continue

    # --------------------------------------------------------
    # تصاویر img
    # --------------------------------------------------------

    img_tags = re.findall(
        r"<img\b[^>]*>",
        content,
        re.IGNORECASE
    )

    for tag in img_tags:

        src_matches = re.findall(
            r'(?:src|data-src|data-original|data-lazy-src)=["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for image_url in src_matches:

            image_url = make_absolute_url(
                image_url,
                article_url
            )

            if image_url:

                candidates.append({
                    "url": image_url,
                    "priority": 50
                })

        srcset_matches = re.findall(
            r'srcset=["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for srcset in srcset_matches:

            for part in srcset.split(","):

                pieces = part.strip().split()

                if not pieces:
                    continue

                image_url = make_absolute_url(
                    pieces[0],
                    article_url
                )

                if image_url:

                    width = 0

                    if len(pieces) > 1:

                        match = re.search(
                            r"(\d+)w",
                            pieces[1]
                        )

                        if match:
                            width = int(
                                match.group(1)
                            )

                    candidates.append({
                        "url": image_url,
                        "width": width,
                        "priority": 60
                    })

    # --------------------------------------------------------
    # حذف تکراری‌ها
    # --------------------------------------------------------

    unique = {}

    for candidate in candidates:

        url = candidate.get(
            "url",
            ""
        )

        if not url:
            continue

        if url not in unique:

            unique[url] = candidate

    return list(
        unique.values()
    )


# ============================================================
# پیدا کردن بهترین تصویر صفحهٔ خبر
# ============================================================

def get_best_article_image(
    article_url
):

    if not article_url:
        return ""

    try:

        print(
            "در حال بررسی صفحهٔ خبر برای تصویر بهتر..."
        )

        response = requests.get(
            article_url,
            headers=REQUEST_HEADERS,
            timeout=20
        )

        if not response.ok:

            print(
                f"خطا در دریافت صفحه: "
                f"{response.status_code}"
            )

            return ""

        content = response.text

        candidates = get_article_images(
            content,
            article_url
        )

        if not candidates:

            print(
                "⚠️ هیچ تصویری در صفحه پیدا نشد."
            )

            return ""

        # ----------------------------------------------------
        # ارزیابی واقعی تصاویر
        # ----------------------------------------------------

        scored = []

        for candidate in candidates:

            image_url = candidate["url"]

            priority = candidate.get(
                "priority",
                0
            )

            width = candidate.get(
                "width",
                0
            )

            score = priority

            # بندانگشتی را شدیداً جریمه می‌کنیم
            if looks_like_thumbnail_url(
                image_url
            ):

                score -= 100

            # اگر عرض از srcset مشخص است
            if width >= MIN_IMAGE_WIDTH:

                score += 100

            elif (
                width > 0
                and width < MIN_IMAGE_WIDTH
            ):

                score -= 50

            # در غیر این صورت ابعاد واقعی را بررسی می‌کنیم
            else:

                real_width, real_height = (
                    get_real_image_dimensions(
                        image_url
                    )
                )

                if real_width >= MIN_IMAGE_WIDTH:

                    score += 100

                    width = real_width

                elif (
                    real_width > 0
                    and real_width < MIN_IMAGE_WIDTH
                ):

                    score -= 50

            scored.append({
                "score": score,
                "url": image_url,
                "width": width
            })

        scored.sort(
            key=lambda item:
                item["score"],
            reverse=True
        )

        # ----------------------------------------------------
        # انتخاب بهترین تصویر
        # ----------------------------------------------------

        for item in scored:

            if item["score"] >= 100:

                print(
                    "✓ تصویر باکیفیت از صفحهٔ خبر پیدا شد."
                )

                print(
                    f"عرض تصویر: "
                    f"{item['width']}px"
                )

                print(
                    f"آدرس تصویر: "
                    f"{item['url']}"
                )

                return item["url"]

        print(
            "⚠️ تصویر باکیفیت قابل‌اعتمادی در صفحه پیدا نشد."
        )

        return ""

    except Exception as error:

        print(
            f"خطا در بررسی صفحهٔ خبر: {error}"
        )

        return ""


# ============================================================
# انتخاب نهایی تصویر
# ============================================================

def get_best_image(
    entry,
    article_url
):

    rss_result = get_best_rss_image(
        entry
    )

    rss_image = rss_result["url"]

    rss_is_good = (
        rss_result["good_quality"]
    )

    # --------------------------------------------------------
    # عکس RSS خوب است
    # --------------------------------------------------------

    if (
        rss_image
        and rss_is_good
    ):

        print(
            "✓ از تصویر RSS استفاده می‌شود."
        )

        return rss_image

    # --------------------------------------------------------
    # RSS عکس دارد ولی بی‌کیفیت است
    # --------------------------------------------------------

    if rss_image:

        print(
            "⚠️ تصویر RSS کیفیت کافی ندارد."
        )

        better_image = (
            get_best_article_image(
                article_url
            )
        )

        if better_image:

            print(
                "✓ تصویر بهتر صفحهٔ خبر انتخاب شد."
            )

            return better_image

        print(
            "⚠️ تصویر بهتر پیدا نشد."
        )

        print(
            "✓ تصویر RSS به عنوان جایگزین استفاده می‌شود."
        )

        return rss_image

    # --------------------------------------------------------
    # RSS اصلاً عکس ندارد
    # --------------------------------------------------------

    print(
        "⚠️ RSS تصویر ندارد."
    )

    article_image = (
        get_best_article_image(
            article_url
        )
    )

    if article_image:

        return article_image

    return ""


# ============================================================
# بررسی تکراری بودن
# ============================================================

def is_duplicate(
    news,
    seen
):

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

    if (
        normalized_link
        and normalized_link in seen
    ):

        return True

    for old_data in seen.values():

        old_title = normalize_title(
            old_data.get(
                "title",
                ""
            )
        )

        old_source = (
            old_data.get(
                "source",
                ""
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


# ============================================================
# ثبت خبر
# ============================================================

def mark_as_seen(
    news,
    seen
):

    normalized_link = normalize_url(
        news["link"]
    )

    if not normalized_link:
        return

    seen[normalized_link] = {

        "title":
            news["title"],

        "normalized_title":
            normalize_title(
                news["title"]
            ),

        "source":
            news["source"],

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
# HTML
# ============================================================

def escape_html(text):

    return html.escape(
        str(text),
        quote=False
    )


# ============================================================
# ارسال عکس به تلگرام
# ============================================================

def send_photo_to_telegram(
    news
):

    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    if news["published"]:

        iran_time = (
            news["published"]
            .astimezone(
                IRAN_TZ
            )
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
            "خطا در ارسال عکس:",
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

def send_text_to_telegram(
    news
):

    title = escape_html(
        news["title"]
    )

    source = escape_html(
        news["source"]
    )

    if news["published"]:

        iran_time = (
            news["published"]
            .astimezone(
                IRAN_TZ
            )
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
            "خطا در ارسال متن:",
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

def send_to_telegram(
    news
):

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

    except Exception as error:

        print(
            f"خطا در ذخیره seen_news در GitHub: {error}"
        )

        return False


# ============================================================
# دریافت خبرهای RSS
# ============================================================

def get_news_from_feed(
    feed_info
):

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
            f"تعداد خبرهای RSS: "
            f"{len(feed.entries)}"
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

            if (
                not title
                or not link
            ):
                continue

            published = (
                get_published_time(
                    entry
                )
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
# بررسی همه RSS ها
# ============================================================

def check_feeds(
    seen
):

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
        cutoff_time
        .astimezone(
            IRAN_TZ
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        "تا زمان:",
        now_utc
        .astimezone(
            IRAN_TZ
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # --------------------------------------------------------
    # جمع‌آوری
    # --------------------------------------------------------

    all_news = []

    for feed_info in load_feeds():

        news_list = (
            get_news_from_feed(
                feed_info
            )
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
    # مرتب‌سازی زمانی
    # --------------------------------------------------------

    all_news.sort(
        key=lambda news:
            news["published"]
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
            .astimezone(
                IRAN_TZ
            )
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
        # انتخاب تصویر
        # ----------------------------------------------------

        news["image"] = get_best_image(
            news["entry"],
            news["link"]
        )

        if news["image"]:

            print(
                "عکس نهایی انتخاب شد."
            )

        else:

            print(
                "⚠️ هیچ عکسی پیدا نشد."
            )

        # ----------------------------------------------------
        # ارسال
        # ----------------------------------------------------

        success = send_to_telegram(
            news
        )

        if not success:

            print(
                "⚠️ ارسال ناموفق بود؛ "
                "خبر در seen_news ثبت نشد."
            )

            continue

        # ----------------------------------------------------
        # ثبت خبر
        # ----------------------------------------------------

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

        print(
            f"تعداد خبرهای ثبت‌شده: "
            f"{len(seen)}"
        )

    # --------------------------------------------------------
    # ذخیره GitHub
    # --------------------------------------------------------

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
        f"تعداد خبرهای قبلاً ثبت‌شده: "
        f"{len(seen)}"
    )

    print("=" * 70)

    sent = check_feeds(
        seen
    )

    print("=" * 70)

    print(
        f"تعداد خبرهای جدید ارسال‌شده: "
        f"{sent}"
    )

    print(
        "بررسی RSS این اجرا تمام شد."
    )

    print("=" * 70)


if __name__ == "__main__":

    main()
```
