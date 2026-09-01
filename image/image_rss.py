import html
import re

from config import (
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
)

from image.image_dimensions import (
    get_real_image_dimensions,
)

from image.image_filters import (
    safe_int,
    unwrap_image_proxy_url,
    looks_like_thumbnail_url,
    looks_like_site_asset_url,
)

MAX_REAL_DIMENSION_CHECKS = 2


# ============================================================
# ابزارهای عمومی
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


def get_image_dimensions(item):

    if not isinstance(item, dict):
        return 0, 0

    width = safe_int(
        item.get(
            "width",
            0
        )
    )

    height = safe_int(
        item.get(
            "height",
            0
        )
    )

    return width, height


# ============================================================
# پردازش srcset
# ============================================================

def parse_srcset(
    srcset,
    priority=80,
    source="srcset"
):

    candidates = []

    if not srcset:
        return candidates

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

            continue

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
            and candidate.get(
                "priority",
                0
            )
            > old.get(
                "priority",
                0
            )
        ):

            unique[key] = candidate

    return list(
        unique.values()
    )


# ============================================================
# استخراج تصاویر RSS
# ============================================================

def get_rss_image_candidates(
    entry
):

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

    # --------------------------------------------------------
    # محتوای HTML داخل RSS
    # --------------------------------------------------------

    html_fields = [
        entry.get(
            "summary",
            ""
        ),
        entry.get(
            "description",
            ""
        ),
        entry.get(
            "content",
            ""
        ),
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

        # ----------------------------------------------------
        # تگ‌های img
        # ----------------------------------------------------

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

                if not image_url:
                    continue

                candidates.append({
                    "url": image_url,
                    "width": 0,
                    "height": 0,
                    "priority": 70,
                    "source": "rss_html",
                })

            # ------------------------------------------------
            # srcset
            # ------------------------------------------------

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

        # ----------------------------------------------------
        # آدرس‌های مستقیم تصاویر داخل HTML
        # ----------------------------------------------------

        standalone_urls = re.findall(
            r'(?:https?:)?//[^"\'>\s]+?\.'
            r'(?:jpg|jpeg|png|webp)'
            r'(?:\?[^"\'>\s]*)?',
            content,
            re.IGNORECASE
        )

        for image_url in standalone_urls:

            if image_url.startswith(
                "//"
            ):

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
# امتیازدهی تصویر RSS
# ============================================================

def evaluate_rss_candidate_without_download(
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

    original_url = (
        unwrap_image_proxy_url(
            url
        )
    )

    if not original_url:

        return {
            "score": -9999,
            "url": "",
            "width": 0,
            "height": 0,
        }

    # --------------------------------------------------------
    # حذف assetهای عمومی سایت
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
            "score": -5000,
            "url": original_url,
            "width": width,
            "height": height,
        }

    score = priority

    # --------------------------------------------------------
    # امتیاز منبع
    # --------------------------------------------------------

    source_bonus = {

        "media_content": 250,

        "enclosure": 220,

        "rss_srcset": 180,

        "rss_html": 120,

        "rss_url": 100,

        "media_thumbnail": 30,
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
    # مساحت
    # --------------------------------------------------------

    area = (
        width
        * height
    )

    if area >= 1920 * 1080:

        score += 700

    elif area >= 1600 * 900:

        score += 600

    elif area >= 1280 * 720:

        score += 500

    elif area >= 1024 * 576:

        score += 250

    return {
        "score": score,
        "url": original_url,
        "width": width,
        "height": height,
    }


# ============================================================
# بهترین تصویر RSS
# ============================================================

def get_best_rss_image(
    entry
):

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

            evaluated.append(
                result
            )

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
            item["width"]
            >= MIN_IMAGE_WIDTH
            and
            item["height"]
            >= MIN_IMAGE_HEIGHT
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
    # بررسی تصاویر بدون ابعاد
    # --------------------------------------------------------

    unknown = [

        item
        for item in evaluated

        if (
            item["width"] <= 0
            or
            item["height"] <= 0
        )
    ]

    checked = 0

    for item in unknown:

        if (
            checked
            >= MAX_REAL_DIMENSION_CHECKS
        ):

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
            real_width
            >= MIN_IMAGE_WIDTH
            and
            real_height
            >= MIN_IMAGE_HEIGHT
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
