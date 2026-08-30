import html
import json
import re
from urllib.parse import (
    parse_qs,
    unquote,
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
from image.image_filters import (
    safe_int,
    unwrap_image_proxy_url,
    looks_like_thumbnail_url,
)

# ============================================================
# تنظیمات داخلی
# ============================================================

# چند روش مختلف برای دریافت صفحه امتحان شود
ARTICLE_REQUEST_PROFILES = 3

# حداقل امتیاز قابل قبول برای تصویر صفحه
MIN_ARTICLE_IMAGE_SCORE = 100

# صفحهٔ اصلی خبر همیشه قبل از RSS بررسی شود
ALWAYS_CHECK_ARTICLE_PAGE = True

# حداکثر تعداد تصاویری که برای تشخیص ابعاد واقعی بررسی می‌شوند
MAX_REAL_DIMENSION_CHECKS = 2


# ============================================================
# ابزارهای عمومی
# ============================================================

def extract_image_url(item):

    if not isinstance(item, dict):
        return ""

    for key in ("url", "href", "src"):

        value = item.get(key)

        if value:
            return html.unescape(
                str(value).strip()
            )

    return ""


def get_image_dimensions(item):

    if not isinstance(item, dict):
        return 0, 0

    width = safe_int(
        item.get("width", 0)
    )

    height = safe_int(
        item.get("height", 0)
    )

    return width, height



# ============================================================
# استخراج تصاویر RSS
# ============================================================

def get_rss_image_candidates(entry):

    candidates = []

    if not entry:
        return candidates

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
                "source": "media_content",
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
                "source": "media_thumbnail",
            })

    # --------------------------------------------------------
    # enclosures
    # --------------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(enclosures, list):

        for item in enclosures:

            if not isinstance(item, dict):
                continue

            url = extract_image_url(item)

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
                "source": "enclosure",
            })

    # --------------------------------------------------------
    # تصاویر HTML داخل RSS
    # --------------------------------------------------------

    html_fields = [
        entry.get("summary", ""),
        entry.get("description", ""),
        entry.get("content", ""),
    ]

    for content in html_fields:

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict):

                    parts.append(
                        str(
                            item.get(
                                "value",
                                ""
                            )
                        )
                    )

            content = " ".join(parts)

        if not content:
            continue

        content = str(content)

        image_tags = re.findall(
            r"<img\b[^>]*>",
            content,
            re.IGNORECASE
        )

        for tag in image_tags:

            attributes = re.findall(
                r'(?:src|data-src|data-original|'
                r'data-lazy-src|data-image|data-url)='
                r'["\']([^"\']+)["\']',
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
            r'(?:https?:)?//[^"\'>\s]+?\.'
            r'(?:jpg|jpeg|png|webp)'
            r'(?:\?[^"\'>\s]*)?',
            content,
            re.IGNORECASE
        )

        for image_url in standalone_urls:

            if image_url.startswith("//"):
                image_url = "https:" + image_url

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

def deduplicate_candidates(candidates):

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

            old_size = (
                old.get("width", 0)
                * old.get("height", 0)
            )

            new_size = (
                candidate.get("width", 0)
                * candidate.get("height", 0)
            )

            if new_size > old_size:

                unique[key] = candidate

            elif (
                new_size == old_size
                and candidate.get("priority", 0)
                > old.get("priority", 0)
            ):

                unique[key] = candidate

    return list(
        unique.values()
    )


# ============================================================
# اندازهٔ واقعی تصویر
# ============================================================

def get_real_image_dimensions(image_url):

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

        # JPEG
        if (
            "image/jpeg" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith((".jpg", ".jpeg"))
        ):

            return get_jpeg_dimensions(data)

        # PNG
        if (
            "image/png" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".png")
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

        # GIF
        if (
            "image/gif" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".gif")
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

        # WebP
        if (
            "image/webp" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".webp")
        ):

            return get_webp_dimensions(data)

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

            if marker in (0xD8, 0xD9):
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

        # VP8X
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

        # VP8
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

        # VP8L
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
# امتیازدهی RSS
# ============================================================

def evaluate_rss_candidate_without_download(candidate):

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
            "score": -9999,
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
            "score": -5000,
            "url": original_url,
            "width": width,
            "height": height,
        }

    if looks_like_site_asset_url(
        original_url
    ):

        return {
            "score": -5000,
            "url": original_url,
            "width": width,
            "height": height,
        }

  
    score = priority

    # تصویر دارای ابعاد اعلام‌شده ارزش بیشتری دارد
    if width > 0:
        score += min(width, 2500)

    if height > 0:
        score += min(height, 1600)

    # تصاویر بزرگ‌تر امتیاز اضافه می‌گیرند
    area = width * height

    if area >= 1600 * 900:
        score += 500

    elif area >= 1280 * 720:
        score += 350

    elif area >= 1024 * 576:
        score += 200

    return {
        "score": score,
        "url": original_url,
        "width": width,
        "height": height,
    }


# ============================================================
# بهترین تصویر RSS
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

        result = (
            evaluate_rss_candidate_without_download(
                candidate
            )
        )

        if result["score"] > -1000:

            evaluated.append(result)

    if not evaluated:

        return {
            "url": "",
            "good_quality": False,
        }

    evaluated.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # اول تصاویر دارای ابعاد مناسب
    # --------------------------------------------------------

    for item in evaluated:

        if (
            item["width"] >= MIN_IMAGE_WIDTH
            and item["height"] >= MIN_IMAGE_HEIGHT
        ):

            print(
                "✓ تصویر باکیفیت از RSS پیدا شد."
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

    # --------------------------------------------------------
    # بررسی تعداد محدودی از تصاویر بدون ابعاد
    # --------------------------------------------------------

    unknown = [
        item
        for item in evaluated
        if (
            item["width"] <= 0
            or item["height"] <= 0
        )
    ]

    checked = 0

    for item in unknown:

        if checked >= MAX_REAL_DIMENSION_CHECKS:
            break

        checked += 1

        print(
            f"بررسی ابعاد واقعی تصویر RSS "
            f"({checked}/{MAX_REAL_DIMENSION_CHECKS})..."
        )

        real_width, real_height = (
            get_real_image_dimensions(
                item["url"]
            )
        )

        if (
            real_width >= MIN_IMAGE_WIDTH
            and real_height >= MIN_IMAGE_HEIGHT
        ):

            print(
                "✓ تصویر مناسب RSS پیدا شد."
            )

            print(
                f"عرض: {real_width}px"
            )

            print(
                f"ارتفاع: {real_height}px"
            )

            print(
                f"آدرس: {item['url']}"
            )

            return {
                "url": item["url"],
                "good_quality": True,
            }

    # --------------------------------------------------------
    # fallback
    # --------------------------------------------------------

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
# دریافت صفحهٔ خبر
# ============================================================

def fetch_article_page(article_url):

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
        profiles[:ARTICLE_REQUEST_PROFILES],
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

            if not response.ok:

                print(
                    f"⚠️ پاسخ صفحه: "
                    f"{response.status_code}"
                )

                continue

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
                .lower()
            )

            if (
                "text/html" in content_type
                or not content_type
            ):

                print(
                    "✓ صفحهٔ خبر دریافت شد."
                )

                return response.text

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
# استخراج تصاویر Meta
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
# استخراج JSON-LD
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

        if isinstance(data, dict):

            objects.append(data)

            graph = data.get("@graph")

            if isinstance(graph, list):

                objects.extend(graph)

        elif isinstance(data, list):

            objects.extend(data)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            obj_type = obj.get(
                "@type",
                ""
            )

            if isinstance(obj_type, list):

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

            image = obj.get("image")

            image_items = []

            if isinstance(image, str):

                image_items.append({
                    "url": image,
                    "width": 0,
                    "height": 0,
                })

            elif isinstance(image, dict):

                image_items.append({
                    "url": image.get(
                        "url",
                        ""
                    ),
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
                })

            elif isinstance(image, list):

                for item in image:

                    if isinstance(item, str):

                        image_items.append({
                            "url": item,
                            "width": 0,
                            "height": 0,
                        })

                    elif isinstance(item, dict):

                        image_items.append({
                            "url": item.get(
                                "url",
                                ""
                            ),
                            "width": safe_int(
                                item.get(
                                    "width",
                                    0
                                )
                            ),
                            "height": safe_int(
                                item.get(
                                    "height",
                                    0
                                )
                            ),
                        })

            for image_item in image_items:

                image_url = make_absolute_url(
                    image_item["url"],
                    article_url
                )

                if not image_url:
                    continue

                candidates.append({
                    "url": image_url,
                    "width": image_item["width"],
                    "height": image_item["height"],
                    "priority": (
                        320
                        if article_object
                        else 160
                    ),
                    "source": "jsonld",
                })

    return candidates


# ============================================================
# استخراج تصاویر HTML
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
                priority=110,
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
# تمام تصاویر صفحه
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

def score_article_image(candidate):

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

    lower = original_url.lower()


    # --------------------------------------------------------
    # asset عمومی
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
    # thumbnail
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

        "og:image": 300,

        "og:image:url": 280,

        "twitter:image": 220,

        "jsonld": 350,

        "srcset": 180,

        "img": 50,
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
            2500
        )

        if width >= MIN_IMAGE_WIDTH:
            score += 500

        else:
            score -= 300

    if height > 0:

        score += min(
            height,
            1600
        )

        if height >= MIN_IMAGE_HEIGHT:
            score += 300

        else:
            score -= 150

    # --------------------------------------------------------
    # مساحت تصویر
    # --------------------------------------------------------

    area = width * height

    if area >= 1920 * 1080:
        score += 700

    elif area >= 1600 * 900:
        score += 600

    elif area >= 1320 * 742:
        score += 500

    elif area >= 1200 * 675:
        score += 400

    elif area >= 1024 * 576:
        score += 250

    # --------------------------------------------------------
    # الگوهای تصویر بزرگ در URL
    # --------------------------------------------------------

    large_size_patterns = (
        "1320x742",
        "1200x675",
        "1200x800",
        "1280x720",
        "1600x900",
        "1920x1080",
        "2048x",
        "2160x",
    )

    for pattern in large_size_patterns:

        if pattern in lower:

            score += 300
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

        if pattern in lower:

            score -= 600
            break

    return {
        "score": score,
        "url": original_url,
        "width": width,
        "height": height,
    }


# ============================================================
# بهترین تصویر صفحه
# ============================================================

def get_best_article_image(article_url):

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
            "⚠️ هیچ تصویر قابل استخراجی "
            "در صفحه پیدا نشد."
        )

        return ""

    scored = []

    for candidate in candidates:

        result = score_article_image(
            candidate
        )

        if result["score"] > -1000:

            scored.append(result)

    if not scored:

        print(
            "⚠️ هیچ تصویر قابل استفاده‌ای "
            "در صفحه پیدا نشد."
        )

        return ""

    scored.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # ========================================================
    # مرحلهٔ اول:
    # تصویر بزرگ و باکیفیت دارای ابعاد مشخص
    # ========================================================

    known_quality = [

        item
        for item in scored
        if (
            item["width"] >= MIN_IMAGE_WIDTH
            and item["height"] >= MIN_IMAGE_HEIGHT
        )
    ]

    if known_quality:

        best = known_quality[0]

        print(
            "✓ بهترین تصویر با ابعاد مناسب "
            "از صفحه انتخاب شد."
        )

        print(
            f"منبع: {best.get('source', '')}"
        )

        print(
            f"عرض: {best['width']}px"
        )

        print(
            f"ارتفاع: {best['height']}px"
        )

        print(
            f"آدرس تصویر: {best['url']}"
        )

        return best["url"]

    # ========================================================
    # مرحلهٔ دوم:
    # تصاویر بدون ابعاد
    #
    # اینجا حداکثر دو گزینه را واقعاً بررسی می‌کنیم.
    # ========================================================

    unknown = [

        item
        for item in scored
        if (
            item["width"] <= 0
            or item["height"] <= 0
        )
    ]

    checked = 0

    for item in unknown:

        if checked >= MAX_REAL_DIMENSION_CHECKS:
            break

        checked += 1

        print(
            f"بررسی ابعاد واقعی تصویر "
            f"({checked}/{MAX_REAL_DIMENSION_CHECKS})..."
        )

        real_width, real_height = (
            get_real_image_dimensions(
                item["url"]
            )
        )

        if real_width <= 0:
            continue

        item["width"] = real_width
        item["height"] = real_height

        if (
            real_width >= MIN_IMAGE_WIDTH
            and real_height >= MIN_IMAGE_HEIGHT
        ):

            print(
                "✓ تصویر اصلی باکیفیت پیدا شد."
            )

            print(
                f"عرض: {real_width}px"
            )

            print(
                f"ارتفاع: {real_height}px"
            )

            print(
                f"آدرس تصویر: {item['url']}"
            )

            return item["url"]

    # ========================================================
    # مرحلهٔ سوم:
    # fallback
    # ========================================================

    # فقط اگر هیچ تصویر مناسب پیدا نشد،
    # بهترین گزینهٔ باقی‌مانده انتخاب می‌شود.

    fallback = scored[0]

    print(
        "⚠️ تصویر باکیفیت قطعی پیدا نشد."
    )

    print(
        f"✓ تصویر fallback صفحه: "
        f"{fallback['url']}"
    )

    return fallback["url"]


# ============================================================
# انتخاب نهایی تصویر
# ============================================================

def get_best_image(
    entry,
    article_url
):

    """
    سیاست انتخاب تصویر:

    1. صفحهٔ خبر بررسی می‌شود.
    2. تمام منابع تصویر صفحه جمع‌آوری می‌شوند.
    3. تصویر بزرگ و باکیفیت بر اساس امتیاز انتخاب می‌شود.
    4. OG کوچک دیگر به‌صورت خودکار بر تصویر بزرگ‌تر غلبه نمی‌کند.
    5. srcset با نسخهٔ بزرگ‌تر امتیاز بیشتری می‌گیرد.
    6. تصاویر لوگو و asset حذف می‌شوند.
    7. French Football Weekly به‌صورت ویژه فیلتر می‌شود.
    8. حداکثر دو تصویر بدون ابعاد واقعاً بررسی می‌شوند.
    9. در صورت شکست صفحه، RSS بررسی می‌شود.
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
            "✓ تصویر RSS به عنوان fallback "
            "استفاده می‌شود."
        )

        return rss_image

    print(
        "⚠️ هیچ تصویر قابل استفاده‌ای "
        "پیدا نشد."
    )

    return ""
