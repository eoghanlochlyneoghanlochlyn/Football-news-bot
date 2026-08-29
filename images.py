import html
import json
import re
from urllib.parse import (
    parse_qs,
    unquote,
    urljoin,
    urlsplit,
)

import requests

from config import (
    IMAGE_REQUEST_TIMEOUT,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)
from utils import make_absolute_url


# ============================================================
# تنظیمات داخلی
# ============================================================

ARTICLE_REQUEST_PROFILES = 4

MIN_ARTICLE_IMAGE_SCORE = 100

# اگر صفحهٔ خبر تصویر مناسبی داشته باشد،
# همیشه قبل از RSS بررسی می‌شود.
ALWAYS_CHECK_ARTICLE_PAGE = True


# ============================================================
# استخراج URL تصویر از یک آیتم
# ============================================================

def extract_image_url(item):

    if not isinstance(item, dict):
        return ""

    for key in (
        "url",
        "href",
        "src",
    ):

        value = item.get(key)

        if value:
            return html.unescape(
                str(value).strip()
            )

    return ""


# ============================================================
# استخراج ابعاد اعلام‌شده
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
# تشخیص thumbnail از URL
# ============================================================

def looks_like_thumbnail_url(url):

    if not url:
        return False

    lower = url.lower()

    patterns = [

        r"-\d{2,4}x\d{2,4}(?:\.[a-z0-9]+)(?:\?|$)",

        r"/\d{2,4}x\d{2,4}/",

        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",

        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",

        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)[^0-9]",

        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)[^0-9]",
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            lower
        ):
            return True

    words = (
        "thumbnail",
        "thumb",
        "small",
        "tiny",
        "avatar",
        "favicon",
    )

    for word in words:

        if word in lower:
            return True

    return False


# ============================================================
# تشخیص تصویر غیرمقاله‌ای
# ============================================================

def looks_like_site_asset_url(url):

    if not url:
        return False

    lower = url.lower()

    # --------------------------------------------------------
    # مواردی که معمولاً لوگو، آواتار یا تصویر عمومی سایت هستند
    # --------------------------------------------------------

    patterns = (
        "logo",
        "site-logo",
        "header-logo",
        "footer-logo",
        "avatar",
        "author",
        "profile",
        "favicon",
        "site-icon",
        "icon",
        "cropped-",
        "wordpress-logo",
        "wp-logo",
    )

    for pattern in patterns:

        if pattern in lower:
            return True

    return False


# ============================================================
# تشخیص URL تصویر واسطه‌ای
# ============================================================

def unwrap_image_proxy_url(url):

    if not url:
        return ""

    try:

        parsed = urlsplit(url)

        query = parse_qs(
            parsed.query
        )

        for key in (
            "url",
            "src",
            "image",
            "image_url",
            "original",
        ):

            values = query.get(key)

            if not values:
                continue

            original = values[0]

            original = unquote(
                html.unescape(
                    original
                )
            ).strip()

            if (
                original.startswith("http://")
                or original.startswith("https://")
            ):

                return original

    except Exception:
        pass

    return url


# ============================================================
# استخراج تصاویر RSS
# ============================================================

def get_rss_image_candidates(entry):

    candidates = []

    if not entry:
        return candidates

    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(
        media_content,
        list
    ):

        for item in media_content:

            url = extract_image_url(
                item
            )

            if not url:
                continue

            width, height = (
                get_image_dimensions(
                    item
                )
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 100,
                "source": "media_content",
            })

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(
        media_thumbnail,
        list
    ):

        for item in media_thumbnail:

            url = extract_image_url(
                item
            )

            if not url:
                continue

            width, height = (
                get_image_dimensions(
                    item
                )
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 30,
                "source": "media_thumbnail",
            })

    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(
        enclosures,
        list
    ):

        for item in enclosures:

            if not isinstance(
                item,
                dict
            ):
                continue

            url = extract_image_url(
                item
            )

            if not url:
                continue

            media_type = str(
                item.get(
                    "type",
                    ""
                )
            ).lower()

            if (
                media_type
                and not media_type.startswith(
                    "image/"
                )
            ):
                continue

            width, height = (
                get_image_dimensions(
                    item
                )
            )

            candidates.append({
                "url": url,
                "width": width,
                "height": height,
                "priority": 90,
                "source": "enclosure",
            })

    html_fields = [
        entry.get("summary", ""),
        entry.get("description", ""),
        entry.get("content", ""),
    ]

    for content in html_fields:

        if isinstance(
            content,
            list
        ):

            parts = []

            for item in content:

                if isinstance(
                    item,
                    dict
                ):

                    parts.append(
                        str(
                            item.get(
                                "value",
                                ""
                            )
                        )
                    )

            content = " ".join(
                parts
            )

        if not content:
            continue

        content = str(
            content
        )

        image_tags = re.findall(
            r"<img\b[^>]*>",
            content,
            re.IGNORECASE
        )

        for tag in image_tags:

            attributes = re.findall(
                r'(?:src|data-src|data-original|data-lazy-src|data-image)=["\']([^"\']+)["\']',
                tag,
                re.IGNORECASE
            )

            for image_url in attributes:

                image_url = html.unescape(
                    image_url
                ).strip()

                if image_url:

                    candidates.append({
                        "url": image_url,
                        "width": 0,
                        "height": 0,
                        "priority": 70,
                        "source": "rss_html",
                    })

            srcsets = re.findall(
                r'srcset=["\']([^"\']+)["\']',
                tag,
                re.IGNORECASE
            )

            for srcset in srcsets:

                candidates.extend(
                    parse_srcset(
                        srcset,
                        priority=80,
                        source="rss_srcset"
                    )
                )

        standalone_urls = re.findall(
            r'(?:https?:)?//[^"\'>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'>\s]*)?',
            content,
            re.IGNORECASE
        )

        for image_url in standalone_urls:

            if image_url.startswith("//"):

                image_url = (
                    "https:"
                    + image_url
                )

            candidates.append({
                "url": html.unescape(
                    image_url
                ).strip(),
                "width": 0,
                "height": 0,
                "priority": 60,
                "source": "rss_url",
            })

    return deduplicate_candidates(
        candidates
    )


# ============================================================
# پردازش srcset
# ============================================================

def parse_srcset(
    srcset,
    priority=80,
    source="srcset"
):

    candidates = []

    for part in srcset.split(","):

        pieces = part.strip().split()

        if not pieces:
            continue

        image_url = html.unescape(
            pieces[0]
        ).strip()

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

        if image_url:

            candidates.append({
                "url": image_url,
                "width": width,
                "height": 0,
                "priority": priority,
                "source": source,
            })

    return candidates


# ============================================================
# حذف تصاویر تکراری
# ============================================================

def deduplicate_candidates(
    candidates
):

    unique = {}

    for candidate in candidates:

        url = candidate.get(
            "url",
            ""
        )

        if not url:
            continue

        key = url.strip()

        if key not in unique:

            unique[key] = candidate

        else:

            old = unique[key]

            if (
                candidate.get("width", 0)
                > old.get("width", 0)
            ):

                unique[key] = candidate

    return list(
        unique.values()
    )


# ============================================================
# اندازه واقعی تصویر
# ============================================================

def get_real_image_dimensions(
    image_url
):

    if not image_url:
        return 0, 0

    try:

        response = requests.get(
            image_url,
            headers={
                **REQUEST_HEADERS,
                "Range": "bytes=0-65535",
            },
            timeout=IMAGE_REQUEST_TIMEOUT,
            stream=True,
            allow_redirects=True,
        )

        if not response.ok:
            return 0, 0

        content_type = (
            response.headers.get(
                "Content-Type",
                ""
            )
            .lower()
        )

        data = response.content

        if (
            "image/jpeg" in content_type
            or image_url.lower().split("?")[0].endswith(
                (".jpg", ".jpeg")
            )
        ):

            return get_jpeg_dimensions(
                data
            )

        if (
            "image/png" in content_type
            or image_url.lower().split("?")[0].endswith(
                ".png"
            )
        ):

            if (
                len(data) >= 24
                and data[:8]
                == b"\x89PNG\r\n\x1a\n"
            ):

                width = int.from_bytes(
                    data[16:20],
                    "big"
                )

                height = int.from_bytes(
                    data[20:24],
                    "big"
                )

                return width, height

        if (
            "image/gif" in content_type
            or image_url.lower().split("?")[0].endswith(
                ".gif"
            )
        ):

            if (
                len(data) >= 10
                and data[:6] in (
                    b"GIF87a",
                    b"GIF89a",
                )
            ):

                width = int.from_bytes(
                    data[6:8],
                    "little"
                )

                height = int.from_bytes(
                    data[8:10],
                    "little"
                )

                return width, height

        if (
            "image/webp" in content_type
            or image_url.lower().split("?")[0].endswith(
                ".webp"
            )
        ):

            return get_webp_dimensions(
                data
            )

        return 0, 0

    except Exception:

        return 0, 0


# ============================================================
# ابعاد JPEG
# ============================================================

def get_jpeg_dimensions(data):

    try:

        if len(data) < 2:
            return 0, 0

        if data[:2] != b"\xff\xd8":
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

            if marker in (
                0xD8,
                0xD9,
            ):
                continue

            if index + 2 > len(data):
                break

            segment_length = int.from_bytes(
                data[index:index + 2],
                "big"
            )

            if segment_length < 2:
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
# ابعاد WebP
# ============================================================

def get_webp_dimensions(data):

    try:

        if (
            len(data) < 16
            or data[:4] != b"RIFF"
            or data[8:12] != b"WEBP"
        ):
            return 0, 0

        if data[12:16] == b"VP8X":

            if len(data) < 30:
                return 0, 0

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

        if data[12:16] == b"VP8 ":

            if len(data) < 30:
                return 0, 0

            frame_start = data.find(
                b"\x9d\x01\x2a"
            )

            if frame_start != -1:

                pos = frame_start + 3

                if pos + 4 <= len(data):

                    width = int.from_bytes(
                        data[pos:pos + 2],
                        "little"
                    ) & 0x3FFF

                    height = int.from_bytes(
                        data[pos + 2:pos + 4],
                        "little"
                    ) & 0x3FFF

                    return width, height

        if data[12:16] == b"VP8L":

            if len(data) < 25:
                return 0, 0

            if data[20] == 0x2F:

                bits = int.from_bytes(
                    data[21:25],
                    "little"
                )

                width = (
                    (bits & 0x3FFF)
                    + 1
                )

                height = (
                    ((bits >> 14) & 0x3FFF)
                    + 1
                )

                return width, height

        return 0, 0

    except Exception:

        return 0, 0


# ============================================================
# ارزیابی کیفیت تصویر RSS
# ============================================================

def evaluate_rss_candidate(
    candidate
):

    url = candidate.get(
        "url",
        ""
    )

    width = candidate.get(
        "width",
        0
    )

    height = candidate.get(
        "height",
        0
    )

    priority = candidate.get(
        "priority",
        0
    )

    if not url:

        return {
            "good": False,
            "score": -999,
            "url": "",
            "width": 0,
            "height": 0,
        }

    original_url = unwrap_image_proxy_url(
        url
    )

    if looks_like_thumbnail_url(
        original_url
    ):

        return {
            "good": False,
            "score": -500,
            "url": original_url,
            "width": width,
            "height": height,
        }

    if looks_like_site_asset_url(
        original_url
    ):

        return {
            "good": False,
            "score": -800,
            "url": original_url,
            "width": width,
            "height": height,
        }

    if width > 0:

        if width < MIN_IMAGE_WIDTH:

            return {
                "good": False,
                "score": -300,
                "url": original_url,
                "width": width,
                "height": height,
            }

        score = (
            priority
            + width
        )

        if (
            height >= MIN_IMAGE_HEIGHT
        ):
            score += 200

        return {
            "good": True,
            "score": score,
            "url": original_url,
            "width": width,
            "height": height,
        }

    real_width, real_height = (
        get_real_image_dimensions(
            original_url
        )
    )

    if real_width > 0:

        if real_width < MIN_IMAGE_WIDTH:

            return {
                "good": False,
                "score": -300,
                "url": original_url,
                "width": real_width,
                "height": real_height,
            }

        score = (
            priority
            + real_width
        )

        if (
            real_height >= MIN_IMAGE_HEIGHT
        ):
            score += 200

        return {
            "good": True,
            "score": score,
            "url": original_url,
            "width": real_width,
            "height": real_height,
        }

    return {
        "good": False,
        "score": priority,
        "url": original_url,
        "width": 0,
        "height": 0,
    }


# ============================================================
# انتخاب بهترین تصویر RSS
# ============================================================

def get_best_rss_image(entry):

    candidates = get_rss_image_candidates(
        entry
    )

    if not candidates:

        return {
            "url": "",
            "good_quality": False,
        }

    evaluated = []

    for candidate in candidates:

        result = evaluate_rss_candidate(
            candidate
        )

        evaluated.append(
            result
        )

    evaluated.sort(
        key=lambda item:
            item["score"],
        reverse=True
    )

    for item in evaluated:

        if item["good"]:

            print(
                "✓ تصویر مناسب از RSS پیدا شد."
            )

            print(
                f"عرض: {item['width']}px"
            )

            print(
                f"ارتفاع: {item['height']}px"
            )

            print(
                f"آدرس: {item['url']}"
            )

            return {
                "url": item["url"],
                "good_quality": True,
            }

    fallback = evaluated[0]

    print(
        "⚠️ تصویر باکیفیت در RSS پیدا نشد."
    )

    print(
        f"✓ تصویر fallback RSS: "
        f"{fallback['url']}"
    )

    return {
        "url": fallback["url"],
        "good_quality": False,
    }


# ============================================================
# درخواست صفحهٔ خبر
# ============================================================

def fetch_article_page(
    article_url
):

    if not article_url:
        return ""

    profiles = [

        {
            **REQUEST_HEADERS,
            "Referer": article_url,
        },

        {
            **REQUEST_HEADERS,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": article_url,
        },

        {
            **REQUEST_HEADERS,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        },

        {
            **REQUEST_HEADERS,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
        },
    ]

    for index, headers in enumerate(
        profiles[
            :ARTICLE_REQUEST_PROFILES
        ],
        start=1
    ):

        try:

            print(
                f"تلاش برای دریافت صفحه "
                f"(روش {index})..."
            )

            response = requests.get(
                article_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            if response.ok:

                content_type = (
                    response.headers.get(
                        "Content-Type",
                        ""
                    )
                    .lower()
                )

                if (
                    "text/html"
                    in content_type
                    or not content_type
                ):

                    print(
                        "✓ صفحهٔ خبر دریافت شد."
                    )

                    return response.text

            else:

                print(
                    f"⚠️ پاسخ صفحه: "
                    f"{response.status_code}"
                )

        except requests.RequestException as error:

            print(
                f"⚠️ خطای درخواست: {error}"
            )

        except Exception as error:

            print(
                f"⚠️ خطای غیرمنتظره: {error}"
            )

    return ""


# ============================================================
# استخراج URL از meta
# ============================================================

def extract_meta_images(
    content,
    article_url
):

    candidates = []

    patterns = [

        (
            r'<meta[^>]+property=["\']og:image["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            250,
            "og:image",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+property=["\']og:image["\']',
            250,
            "og:image",
        ),

        (
            r'<meta[^>]+name=["\']twitter:image["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            180,
            "twitter:image",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+name=["\']twitter:image["\']',
            180,
            "twitter:image",
        ),

        (
            r'<meta[^>]+property=["\']og:image:url["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            230,
            "og:image:url",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+property=["\']og:image:url["\']',
            230,
            "og:image:url",
        ),
    ]

    for pattern, priority, source in patterns:

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

            if not image_url:
                continue

            candidates.append({
                "url": image_url,
                "width": 0,
                "height": 0,
                "priority": priority,
                "source": source,
            })

    return candidates


# ============================================================
# استخراج تصاویر JSON-LD
# ============================================================

def extract_jsonld_images(
    content,
    article_url
):

    candidates = []

    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\']'
        r'[^>]*>(.*?)</script>',
        content,
        re.IGNORECASE | re.DOTALL
    )

    for block in blocks:

        try:

            data = json.loads(
                html.unescape(
                    block.strip()
                )
            )

        except Exception:

            continue

        objects = []

        if isinstance(
            data,
            dict
        ):

            objects.append(
                data
            )

            graph = data.get(
                "@graph"
            )

            if isinstance(
                graph,
                list
            ):

                objects.extend(
                    graph
                )

        elif isinstance(
            data,
            list
        ):

            objects.extend(
                data
            )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue

            # فقط تصویر موجود در NewsArticle / Article
            # اولویت بسیار بالایی دارد.
            obj_type = obj.get(
                "@type",
                ""
            )

            if isinstance(
                obj_type,
                list
            ):

                article_object = any(
                    str(item).lower()
                    in (
                        "newsarticle",
                        "article",
                        "reportagenewsarticle",
                    )
                    for item in obj_type
                )

            else:

                article_object = (
                    str(obj_type).lower()
                    in (
                        "newsarticle",
                        "article",
                        "reportagenewsarticle",
                    )
                )

            image = obj.get(
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
                        "width": 0,
                        "height": 0,
                        "priority": (
                            300
                            if article_object
                            else 150
                        ),
                        "source": "jsonld",
                    })

            elif isinstance(
                image,
                dict
            ):

                image_url = image.get(
                    "url",
                    ""
                )

                image_url = make_absolute_url(
                    image_url,
                    article_url
                )

                if image_url:

                    candidates.append({
                        "url": image_url,
                        "width": safe_int(
                            image.get(
                                "width",
                                0
                            )
                        ),
                        "height": safe_int(
                            image.get(
                                "height",
                                0
                            )
                        ),
                        "priority": (
                            320
                            if article_object
                            else 160
                        ),
                        "source": "jsonld",
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
                                "width": 0,
                                "height": 0,
                                "priority": (
                                    300
                                    if article_object
                                    else 150
                                ),
                                "source": "jsonld",
                            })

                    elif isinstance(
                        image_item,
                        dict
                    ):

                        image_url = image_item.get(
                            "url",
                            ""
                        )

                        image_url = make_absolute_url(
                            image_url,
                            article_url
                        )

                        if image_url:

                            candidates.append({
                                "url": image_url,
                                "width": safe_int(
                                    image_item.get(
                                        "width",
                                        0
                                    )
                                ),
                                "height": safe_int(
                                    image_item.get(
                                        "height",
                                        0
                                    )
                                ),
                                "priority": (
                                    320
                                    if article_object
                                    else 160
                                ),
                                "source": "jsonld",
                            })

    return candidates


# ============================================================
# استخراج تصاویر img
# ============================================================

def extract_html_images(
    content,
    article_url
):

    candidates = []

    tags = re.findall(
        r"<img\b[^>]*>",
        content,
        re.IGNORECASE
    )

    for position, tag in enumerate(tags):

        width = 0
        height = 0

        width_match = re.search(
            r'\bwidth=["\']?(\d+)',
            tag,
            re.IGNORECASE
        )

        height_match = re.search(
            r'\bheight=["\']?(\d+)',
            tag,
            re.IGNORECASE
        )

        if width_match:
            width = int(
                width_match.group(1)
            )

        if height_match:
            height = int(
                height_match.group(1)
            )

        attributes = re.findall(
            r'(?:src|data-src|data-original|'
            r'data-lazy-src|data-image|data-url)='
            r'["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for image_url in attributes:

            image_url = make_absolute_url(
                image_url,
                article_url
            )

            if image_url:

                candidates.append({
                    "url": image_url,
                    "width": width,
                    "height": height,
                    "priority": 70,
                    "source": "img",
                    "position": position,
                })

        srcsets = re.findall(
            r'srcset=["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for srcset in srcsets:

            srcset_candidates = parse_srcset(
                srcset,
                priority=85,
                source="srcset"
            )

            for candidate in srcset_candidates:

                candidate["url"] = (
                    make_absolute_url(
                        candidate["url"],
                        article_url
                    )
                )

                candidate["position"] = position

                candidates.append(
                    candidate
                )

    return candidates


# ============================================================
# استخراج تمام تصاویر صفحه
# ============================================================

def get_article_image_candidates(
    content,
    article_url
):

    candidates = []

    candidates.extend(
        extract_meta_images(
            content,
            article_url
        )
    )

    candidates.extend(
        extract_jsonld_images(
            content,
            article_url
        )
    )

    candidates.extend(
        extract_html_images(
            content,
            article_url
        )
    )

    return deduplicate_candidates(
        candidates
    )


# ============================================================
# امتیازدهی تصویر صفحه
# ============================================================

def score_article_image(
    candidate
):

    url = candidate.get(
        "url",
        ""
    )

    width = candidate.get(
        "width",
        0
    )

    height = candidate.get(
        "height",
        0
    )

    priority = candidate.get(
        "priority",
        0
    )

    source = candidate.get(
        "source",
        ""
    )

    if not url:

        return {
            "score": -9999,
            "url": "",
            "width": 0,
            "height": 0,
        }

    original_url = unwrap_image_proxy_url(
        url
    )

    lower_original_url = (
        original_url.lower()
    )

    # --------------------------------------------------------
    # حذف صریح لوگوی مشکل‌دار French Football Weekly
    # --------------------------------------------------------

    if (
        "frenchfootballweekly.com"
        in lower_original_url
        and (
            "cropped-french-football-weekly"
            in lower_original_url
            or "french-football-weekly-1024x1024"
            in lower_original_url
        )
    ):

        return {
            "score": -10000,
            "url": original_url,
            "width": width,
            "height": height,
        }

    # --------------------------------------------------------
    # حذف تصاویر عمومی سایت
    # --------------------------------------------------------

    if looks_like_site_asset_url(
        original_url
    ):

        return {
            "score": -5000,
            "url": original_url,
            "width": width,
            "height": height,
        }

    # --------------------------------------------------------
    # حذف thumbnail
    # --------------------------------------------------------

    if looks_like_thumbnail_url(
        original_url
    ):

        return {
            "score": -3000,
            "url": original_url,
            "width": width,
            "height": height,
        }

    score = priority

    # --------------------------------------------------------
    # امتیاز منبع
    # --------------------------------------------------------

    source_bonus = {

        # تصویر معرفی اصلی مقاله
        "og:image": 500,

        "og:image:url": 480,

        "twitter:image": 300,

        # تصویر Article در JSON-LD
        "jsonld": 350,

        "srcset": 100,

        "img": 60,
    }

    score += source_bonus.get(
        source,
        20
    )

    # --------------------------------------------------------
    # ابعاد
    # --------------------------------------------------------

    if width > 0:

        score += min(
            width,
            2000
        )

        if width >= MIN_IMAGE_WIDTH:
            score += 300

        else:
            score -= 250

    if height > 0:

        score += min(
            height,
            1200
        )

        if height >= MIN_IMAGE_HEIGHT:
            score += 200

        else:
            score -= 100

    # --------------------------------------------------------
    # الگوهای تصویر بزرگ
    # --------------------------------------------------------

    large_size_patterns = (
        "1320x742",
        "1200x675",
        "1200x800",
        "1280x720",
        "1024x576",
        "1600x900",
        "1920x1080",
        "2048x",
        "2160x",
    )

    for pattern in large_size_patterns:

        if pattern in lower_original_url:

            score += 250
            break

    # --------------------------------------------------------
    # الگوهای کوچک
    # --------------------------------------------------------

    small_size_patterns = (
        "150x150",
        "300x300",
        "300x169",
        "320x180",
        "400x225",
        "480x270",
        "640x360",
    )

    for pattern in small_size_patterns:

        if pattern in lower_original_url:

            score -= 400
            break

    return {
        "score": score,
        "url": original_url,
        "width": width,
        "height": height,
    }


# ============================================================
# پیدا کردن بهترین تصویر صفحه
# ============================================================

def get_best_article_image(
    article_url
):

    if not article_url:
        return ""

    print(
        "در حال بررسی صفحهٔ خبر برای تصویر اصلی..."
    )

    content = fetch_article_page(
        article_url
    )

    if not content:

        print(
            "⚠️ صفحهٔ خبر قابل دریافت نیست."
        )

        return ""

    candidates = get_article_image_candidates(
        content,
        article_url
    )

    if not candidates:

        print(
            "⚠️ هیچ تصویر قابل استخراجی در صفحه پیدا نشد."
        )

        return ""

    scored = []

    for candidate in candidates:

        result = score_article_image(
            candidate
        )

        if (
            result["score"] > -1000
            and result["width"] == 0
        ):

            real_width, real_height = (
                get_real_image_dimensions(
                    result["url"]
                )
            )

            if real_width > 0:

                result["width"] = (
                    real_width
                )

                result["height"] = (
                    real_height
                )

                result["score"] += (
                    min(
                        real_width,
                        2000
                    )
                )

                if (
                    real_width
                    >= MIN_IMAGE_WIDTH
                ):

                    result["score"] += 400

                else:

                    result["score"] -= 300

                if (
                    real_height
                    >= MIN_IMAGE_HEIGHT
                ):

                    result["score"] += 200

        scored.append(
            result
        )

    scored.sort(
        key=lambda item:
            item["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # چاپ چند گزینهٔ برتر برای اشکال‌زدایی
    # --------------------------------------------------------

    print(
        "تصاویر برتر صفحه:"
    )

    for item in scored[:5]:

        print(
            f"  امتیاز={item['score']} | "
            f"{item['width']}x{item['height']} | "
            f"{item['url']}"
        )

    # --------------------------------------------------------
    # انتخاب بهترین تصویر
    # --------------------------------------------------------

    for item in scored:

        if (
            item["score"]
            >= MIN_ARTICLE_IMAGE_SCORE
        ):

            print(
                "✓ تصویر اصلی صفحهٔ خبر انتخاب شد."
            )

            print(
                f"عرض: {item['width']}px"
            )

            print(
                f"ارتفاع: {item['height']}px"
            )

            print(
                f"آدرس تصویر: {item['url']}"
            )

            return item["url"]

    print(
        "⚠️ تصویر مناسب و قابل‌اعتمادی "
        "در صفحه پیدا نشد."
    )

    return ""


# ============================================================
# انتخاب نهایی تصویر
# ============================================================

def get_best_image(
    entry,
    article_url
):

    """
    سیاست جدید:

    1. همیشه ابتدا صفحهٔ خود خبر بررسی می‌شود.
    2. اگر صفحه تصویر اصلی مناسبی داشت، همان انتخاب می‌شود.
    3. اگر صفحه تصویر مناسبی نداشت، RSS بررسی می‌شود.
    4. اگر RSS هم مناسب نبود، بهترین fallback استفاده می‌شود.
    """

    article_image = ""

    # --------------------------------------------------------
    # اول صفحهٔ خبر
    # --------------------------------------------------------

    if (
        ALWAYS_CHECK_ARTICLE_PAGE
        and article_url
    ):

        article_image = (
            get_best_article_image(
                article_url
            )
        )

        if article_image:

            print(
                "✓ تصویر صفحهٔ خبر "
                "به عنوان تصویر نهایی انتخاب شد."
            )

            return article_image

    # --------------------------------------------------------
    # سپس RSS
    # --------------------------------------------------------

    rss_result = get_best_rss_image(
        entry
    )

    rss_image = rss_result.get(
        "url",
        ""
    )

    rss_is_good = rss_result.get(
        "good_quality",
        False
    )

    if (
        rss_image
        and rss_is_good
    ):

        print(
            "✓ تصویر مناسب RSS "
            "به عنوان fallback انتخاب شد."
        )

        return rss_image

    if rss_image:

        print(
            "⚠️ تصویر RSS کیفیت ایده‌آلی ندارد."
        )

        print(
            "✓ تصویر RSS به عنوان fallback استفاده می‌شود."
        )

        return rss_image

    print(
        "⚠️ هیچ تصویر قابل استفاده‌ای پیدا نشد."
    )

    return ""


# ============================================================
# تبدیل امن به عدد
# ============================================================

def safe_int(value):

    try:
        return int(
            value
        )
    except Exception:
        return 0
