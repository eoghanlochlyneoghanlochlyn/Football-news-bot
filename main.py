import json
import os

from rss import get_news
from scraper import get_article_text
from telegram import send_message

from config import CACHE_FILE


def load_cache():
    """خواندن فهرست خبرهایی که قبلاً ارسال شده‌اند."""
    if not os.path.exists(CACHE_FILE):
        return {"sent": []}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"sent": []}


def save_cache(cache):
    """ذخیره فهرست خبرهای ارسال‌شده."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def main():
    print("در حال دریافت اخبار...")

    news = get_news()

    if not news:
        print("هیچ خبری پیدا نشد.")
        return

    print(f"{len(news)} خبر پیدا شد.")

    cache = load_cache()
    sent = set(cache.get("sent", []))

    # فقط خبرهایی که قبلاً ارسال نشده‌اند
    new_news = [
        item for item in news
        if item["link"] not in sent
    ]

    if not new_news:
        print("خبر جدیدی وجود ندارد.")
        return

    # فعلاً فقط جدیدترین خبر را ارسال می‌کنیم
    item = new_news[0]

    print(f"خبر جدید: {item['title']}")
    print("در حال دریافت متن کامل خبر...")

    try:
        article_text = get_article_text(item["link"])
    except Exception as error:
        print(f"خطا در دریافت متن خبر: {error}")
        article_text = item["summary"]

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

    # فقط بعد از ارسال موفق، خبر را ثبت می‌کنیم
    sent.add(item["link"])

    cache["sent"] = list(sent)[-1000:]
    save_cache(cache)

    print("خبر با موفقیت ارسال و در حافظه ثبت شد.")


if __name__ == "__main__":
    main()
