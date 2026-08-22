import json
import os
from datetime import datetime, timezone

from rss import get_news
from scraper import get_article_text
from telegram import send_message

from config import CACHE_FILE


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {
            "sent": [],
            "last_check": None
        }

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {
            "sent": [],
            "last_check": None
        }


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def get_item_date(item):
    """
    زمان انتشار خبر را از اطلاعات RSS استخراج می‌کند.
    اگر زمان قابل تشخیص نباشد، None برمی‌گرداند.
    """

    published = item.get("published")

    if not published:
        return None

    try:
        parsed = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    except Exception:
        return None


def main():
    print("در حال دریافت اخبار...")

    news = get_news()

    if not news:
        print("هیچ خبری پیدا نشد.")
        return

    print(f"{len(news)} خبر پیدا شد.")

    cache = load_cache()

    sent = set(cache.get("sent", []))

    last_check = None

    if cache.get("last_check"):
        try:
            last_check = datetime.fromisoformat(
                cache["last_check"]
            )
        except Exception:
            last_check = None

    new_news = []

    for item in news:
        link = item["link"]

        # قبلاً ارسال شده
        if link in sent:
            continue

        published_date = get_item_date(item)

        # اگر زمان خبر مشخص باشد،
        # فقط خبرهای بعد از آخرین بررسی را قبول می‌کنیم.
        if last_check and published_date:
            if published_date <= last_check:
                continue

        new_news.append(item)

    if not new_news:
        print("خبر جدیدی وجود ندارد.")

        # زمان بررسی را به‌روز می‌کنیم
        cache["last_check"] = datetime.now(
            timezone.utc
        ).isoformat()

        save_cache(cache)

        return

    # قدیمی‌ترین خبر جدید را اول می‌فرستیم
    new_news.sort(
        key=lambda item: get_item_date(item)
        or datetime.min.replace(tzinfo=timezone.utc)
    )

    item = new_news[0]

    print(f"خبر جدید: {item['title']}")

    print("در حال دریافت متن کامل خبر...")

    try:
        article_text = get_article_text(item["link"])
    except Exception as error:
        print(f"خطا در دریافت متن خبر: {error}")
        article_text = item.get("summary", "")

    if not article_text:
        print("متن خبر پیدا نشد.")
        return

    message = (
        f"⚽ {item['title']}\n\n"
        f"{article_text[:3000]}\n\n"
        f"🔗 {item['link']}"
    )

    print("در حال ارسال خبر به تلگرام...")

    try:
        send_message(message)
    except Exception as error:
        print(f"خطا در ارسال به تلگرام: {error}")
        return

    # ثبت خبر پس از ارسال موفق
    sent.add(item["link"])

    cache["sent"] = list(sent)[-1000:]

    cache["last_check"] = datetime.now(
        timezone.utc
    ).isoformat()

    save_cache(cache)

    print("خبر با موفقیت ارسال و ثبت شد.")


if __name__ == "__main__":
    main()
