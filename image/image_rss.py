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
    unwrap_image_proxy_url,
    looks_like_thumbnail_url,
    looks_like_site_asset_url,
)


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
# استخراج تصاویر RSS
# ============================================================

def get_rss_image_candidates(entry):

    candidates = []

    if not entry:
        return candidates

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


