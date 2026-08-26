import os
from datetime import timezone, timedelta


# ============================================================
# فایل‌ها
# ============================================================

FEEDS_FILE = "feeds.json"
SEEN_FILE = "seen_news.json"


# ============================================================
# زمان‌بندی
# ============================================================

# فقط خبرهای منتشرشده در این بازه بررسی می‌شوند.
NEWS_WINDOW_HOURS = 2

# خبرهای قدیمی‌تر از این مدت از seen_news حذف می‌شوند.
SEEN_RETENTION_HOURS = 24


# ============================================================
# تصاویر
# ============================================================

# حداقل عرض قابل قبول تصویر.
MIN_IMAGE_WIDTH = 800

# حداقل ارتفاع قابل قبول تصویر.
MIN_IMAGE_HEIGHT = 450

# حداکثر حجم قابل قبول تصویر برای بررسی.
MAX_IMAGE_SIZE_MB = 15


# ============================================================
# درخواست‌های اینترنتی
# ============================================================

REQUEST_TIMEOUT = 20

IMAGE_REQUEST_TIMEOUT = 15

TELEGRAM_REQUEST_TIMEOUT = 30

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
}


# ============================================================
# منطقه زمانی ایران
# ============================================================

IRAN_TZ = timezone(
    timedelta(
        hours=3,
        minutes=30
    )
)


# ============================================================
# تلگرام
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHANNEL = os.environ.get(
    "TELEGRAM_CHANNEL",
    ""
)


# ============================================================
# بررسی تنظیمات ضروری
# ============================================================

def validate_config():
    """
    بررسی می‌کند تنظیمات ضروری وجود داشته باشند.
    """

    missing = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append(
            "TELEGRAM_BOT_TOKEN"
        )

    if not TELEGRAM_CHANNEL:
        missing.append(
            "TELEGRAM_CHANNEL"
        )

    if missing:

        raise RuntimeError(
            "متغیرهای محیطی زیر تنظیم نشده‌اند: "
            + ", ".join(missing)
        )
