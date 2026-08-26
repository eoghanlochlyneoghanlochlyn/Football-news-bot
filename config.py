import os


# ============================================================
# تنظیمات تلگرام
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHANNEL = os.getenv(
    "TELEGRAM_CHANNEL",
    ""
)


# ============================================================
# تنظیمات RSS
# ============================================================

RSS_FEEDS_FILE = "feeds.json"

# فاصلهٔ بررسی منابع بر حسب ثانیه
POLL_INTERVAL_SECONDS = int(
    os.getenv(
        "POLL_INTERVAL_SECONDS",
        "300"
    )
)


# ============================================================
# تنظیمات خبر
# ============================================================

# فقط خبرهای منتشرشده در این بازه بررسی می‌شوند.
NEWS_WINDOW_HOURS = int(
    os.getenv(
        "NEWS_WINDOW_HOURS",
        "24"
    )
)

# مدت نگهداری خبرهای ثبت‌شده در seen_news
SEEN_RETENTION_HOURS = int(
    os.getenv(
        "SEEN_RETENTION_HOURS",
        "168"
    )
)


# ============================================================
# تنظیمات درخواست‌های اینترنتی
# ============================================================

REQUEST_TIMEOUT = int(
    os.getenv(
        "REQUEST_TIMEOUT",
        "20"
    )
)

IMAGE_REQUEST_TIMEOUT = int(
    os.getenv(
        "IMAGE_REQUEST_TIMEOUT",
        "15"
    )
)


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "en-US,en;q=0.9"
    ),
}


# ============================================================
# تنظیمات تصویر
# ============================================================

MIN_IMAGE_WIDTH = int(
    os.getenv(
        "MIN_IMAGE_WIDTH",
        "640"
    )
)

MIN_IMAGE_HEIGHT = int(
    os.getenv(
        "MIN_IMAGE_HEIGHT",
        "360"
    )
)


# ============================================================
# تنظیمات لاگ
# ============================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)
