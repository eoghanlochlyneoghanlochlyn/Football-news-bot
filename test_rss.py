import json
import feedparser
from datetime import datetime, timezone

from config import FEEDS_FILE


def get_published_time(entry):
    parsed_time = entry.get("published_parsed")

    if not parsed_time:
        parsed_time = entry.get("updated_parsed")

    if parsed_time:
        dt = datetime(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
            parsed_time.tm_hour,
            parsed_time.tm_min,
            parsed_time.tm_sec,
            tzinfo=timezone.utc
        )

        return dt.isoformat()

    return ""


def main():
    print("=" * 70)
    print("شروع تست RSS ها")
    print("=" * 70)

    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        feeds = json.load(file)

    for feed_info in feeds:

        name = feed_info.get("name", "Unknown")
        url = feed_info.get("url", "")

        print()
        print("=" * 70)
        print(f"منبع: {name}")
        print(f"RSS: {url}")
        print("=" * 70)

        try:
            feed = feedparser.parse(url)

            print(f"تعداد خبرهای موجود در RSS: {len(feed.entries)}")

            if feed.bozo:
                print("هشدار: RSS دارای مشکل در ساختار یا دریافت است.")

            if not feed.entries:
                print("هیچ خبری دریافت نشد.")
                continue

            print()
            print("پنج خبر اول:")

            for i, entry in enumerate(feed.entries[:5], start=1):

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                published = get_published_time(entry)

                print()
                print(f"{i}. {title}")
                print(f"   زمان: {published}")
                print(f"   لینک: {link}")

        except Exception as error:
            print(f"خطا در دریافت RSS: {error}")

    print()
    print("=" * 70)
    print("تست همه RSS ها تمام شد.")
    print("=" * 70)


if __name__ == "__main__":
    main()
