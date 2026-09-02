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
    looks_like_site_asset_url,
)

from image.image_dimensions import (
    get_real_image_dimensions,
)

from image.image_rss import (
    get_best_rss_image,
    parse_srcset,
    deduplicate_candidates,
)

from image.image_page import (
    fetch_article_page,
    extract_meta_images,
    extract_jsonld_images,
    extract_html_images,
    get_article_image_candidates,
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
