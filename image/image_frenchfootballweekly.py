import re

from bs4 import BeautifulSoup

from utils import make_absolute_url

from image.image_filters import (
    safe_int,
    looks_like_thumbnail_url,
    looks_like_site_asset_url,
    parse_srcset,
)


# ============================================================
# تنظیمات French Football Weekly
# ============================================================

FRENCH_FOOTBALL_WEEKLY_DOMAIN = (
    "frenchfootballweekly.com"
)

# لوگوی سایت — همیشه و در هر شرایطی مسدود است
FRENCH_FOOTBALL_WEEKLY_LOGO = (
    "https://frenchfootballweekly.com/"
    "wp-content/uploads/2025/01/"
    "French-Football-Weekly-1024x1024-1.png"
)


# ============================================================
# بررسی دامنه
# ============================================================

def is_french_football_weekly(
    article_url
):
    if not article_url:
        return False

    return (
        FRENCH_FOOTBALL_WEEKLY_DOMAIN
        in article_url.lower()
    )


# ============================================================
# بررسی تصویر مسدودشده
# ============================================================

def is_french_football_weekly_blocked_image(
    image_url
):
    if not image_url:
        return True

    image_url = image_url.strip()

    return (
        image_url.rstrip("/")
        == FRENCH_FOOTBALL_WEEKLY_LOGO.rstrip("/")
    )


# ============================================================
# بررسی تصویر قابل استفاده
# ============================================================

def is_valid_french_football_weekly_image(
    image_url,
    width=0,
    height=0
):
    if not image_url:
        return False

    image_url = image_url.strip()

    # --------------------------------------------------------
    # لوگوی سایت
    # --------------------------------------------------------
    if is_french_football_weekly_blocked_image(
        image_url
    ):
        return False

    # --------------------------------------------------------
    # assetهای عمومی
    # --------------------------------------------------------
    if looks_like_site_asset_url(
        image_url
    ):
        return False

    # --------------------------------------------------------
    # thumbnail
    # --------------------------------------------------------
    if looks_like_thumbnail_url(
        image_url
    ):
        return False

    # --------------------------------------------------------
    # تصویر خیلی کوچک
    # فقط زمانی اعمال می‌شود که ابعاد واقعاً مشخص باشند.
    # --------------------------------------------------------
    if width > 0 and height > 0:

        if width < 500 or height < 280:
            return False

    return True


# ============================================================
# استخراج URLهای تصویر از یک تگ
# ============================================================

def extract_image_urls_from_tag(
    tag,
    article_url
):
    results = []

    # --------------------------------------------------------
    # img
    # --------------------------------------------------------
    attributes = (
        "src",
        "data-src",
        "data-original",
        "data-lazy-src",
        "data-image",
        "data-url",
    )

    for attribute in attributes:

        image_url = tag.get(
            attribute,
            ""
        )

        if not image_url:
            continue

        image_url = make_absolute_url(
            image_url,
            article_url
        )

        if image_url:
            results.append({
                "url": image_url,
                "width": safe_int(
                    tag.get(
                        "width",
                        0
                    )
                ),
                "height": safe_int(
                    tag.get(
                        "height",
                        0
                    )
                ),
                "source": attribute,
            })

    # --------------------------------------------------------
    # srcset
    # --------------------------------------------------------
    srcset = tag.get(
        "srcset",
        ""
    )

    if srcset:

        srcset_candidates = parse_srcset(
            srcset,
            priority=0,
            source="srcset"
        )

        for candidate in srcset_candidates:

            image_url = make_absolute_url(
                candidate.get(
                    "url",
                    ""
                ),
                article_url
            )

            if not image_url:
                continue

            results.append({
                "url": image_url,
                "width": candidate.get(
                    "width",
                    0
                ),
                "height": candidate.get(
                    "height",
                    0
                ),
                "source": "srcset",
            })

    return results


# ============================================================
# استخراج تصویر اصلی French Football Weekly
# ============================================================

def get_french_football_weekly_image(
    content,
    article_url
):
    if not content:
        return ""

    if not is_french_football_weekly(
        article_url
    ):
        return ""

    print(
        "🔎 بررسی اختصاصی تصویر "
        "French Football Weekly..."
    )

    try:
        soup = BeautifulSoup(
            content,
            "html.parser"
        )

    except Exception as error:

        print(
            "⚠️ خطا در پردازش HTML "
            f"French Football Weekly: {error}"
        )

        return ""

    # ========================================================
    # مرحله ۱:
    # پیدا کردن عنوان اصلی خبر
    # ========================================================

    title = soup.find(
        "h1"
    )

    if not title:

        print(
            "⚠️ عنوان اصلی خبر پیدا نشد."
        )

        return ""

    # ========================================================
    # مرحله ۲:
    # پیدا کردن محدوده مقاله
    # ========================================================

    article = title.find_parent(
        "article"
    )

    # اگر article وجود نداشت، از والدهای h1
    # برای پیدا کردن محدوده مناسب استفاده می‌کنیم.
    if not article:

        current = title

        for _ in range(6):

            current = current.parent

            if not current:
                break

            text = current.get_text(
                " ",
                strip=True
            )

            image_count = len(
                current.find_all(
                    "img"
                )
            )

            # محدوده‌ای که هم اطلاعات خبر
            # و هم حداقل یک تصویر دارد.
            if (
                "Published" in text
                and "By:" in text
                and image_count > 0
            ):

                article = current
                break

    if not article:

        print(
            "⚠️ محدوده مقاله پیدا نشد."
        )

        return ""

    # ========================================================
    # مرحله ۳:
    # پیدا کردن Published
    # ========================================================

    published_node = None

    for element in article.find_all(
        string=re.compile(
            r"\bPublished\b",
            re.IGNORECASE
        )
    ):

        published_node = element
        break

    if not published_node:

        print(
            "⚠️ بخش Published پیدا نشد."
        )

        return ""

    # ========================================================
    # مرحله ۴:
    # پیدا کردن By
    # ========================================================

    by_node = None

    for element in article.find_all(
        string=re.compile(
            r"\bBy\s*:",
            re.IGNORECASE
        )
    ):

        by_node = element
        break

    if not by_node:

        print(
            "⚠️ بخش By پیدا نشد."
        )

        return ""

    # ========================================================
    # مرحله ۵:
    # فقط تصاویری که بعد از By قرار دارند
    # ========================================================

    images_after_by = []

    # تمام تگ‌های img داخل مقاله
    for image_tag in article.find_all(
        "img"
    ):

        # بررسی اینکه img بعد از By قرار گرفته
        try:

            relation = by_node.find_all_next(
                "img"
            )

            if image_tag not in relation:
                continue

        except Exception:
            continue

        candidates = (
            extract_image_urls_from_tag(
                image_tag,
                article_url
            )
        )

        for candidate in candidates:

            image_url = candidate.get(
                "url",
                ""
            )

            if not is_valid_french_football_weekly_image(
                image_url,
                candidate.get(
                    "width",
                    0
                ),
                candidate.get(
                    "height",
                    0
                )
            ):
                continue

            candidate["alt"] = (
                image_tag.get(
                    "alt",
                    ""
                )
            )

            candidate["title"] = (
                image_tag.get(
                    "title",
                    ""
                )
            )

            images_after_by.append(
                candidate
            )

        # ----------------------------------------------------
        # نکته مهم:
        # اولین img معتبر بعد از By
        # تصویر اصلی است.
        # ----------------------------------------------------
        if images_after_by:

            best = images_after_by[0]

            print(
                "✓ تصویر اصلی "
                "French Football Weekly پیدا شد."
            )

            print(
                f"منبع: {best.get('source', '')}"
            )

            if best.get("width", 0):
                print(
                    f"عرض: {best['width']}px"
                )

            if best.get("height", 0):
                print(
                    f"ارتفاع: {best['height']}px"
                )

            print(
                f"آدرس تصویر: {best['url']}"
            )

            return best["url"]

    # ========================================================
    # مرحله ۶:
    # اگر روش اصلی شکست خورد
    # ========================================================

    print(
        "⚠️ تصویر اصلی "
        "French Football Weekly "
        "با ساختار اصلی پیدا نشد."
    )

    return ""
