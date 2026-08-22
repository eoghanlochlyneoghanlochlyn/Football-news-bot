import os

# تنظیمات تلگرام
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "@footballiiiiiiiiiiiiiiiiiiiiii"

# فایل RSS
FEEDS_FILE = "feeds.json"

# فایل ذخیره خبرهای ارسال‌شده
CACHE_FILE = "cache.json"

# حداکثر تعداد خبرهایی که در هر اجرا بررسی می‌شوند
MAX_NEWS = 5
