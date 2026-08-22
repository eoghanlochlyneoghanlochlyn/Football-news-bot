from rss import get_news
from scraper import get_article_text
from telegram import send_message


def main():
    print("در حال دریافت اخبار...")

    news = get_news()

    if not news:
        print("هیچ خبری پیدا نشد.")
        return

    print(f"{len(news)} خبر پیدا شد.")

    item = news[0]

    print(f"خبر انتخاب‌شده: {item['title']}")
    print("در حال دریافت متن کامل خبر...")

    try:
        article_text = get_article_text(item["link"])
    except Exception as error:
        print(f"خطا در دریافت متن خبر: {error}")
        article_text = item["summary"]

    if not article_text:
        print("متن خبر پیدا نشد.")
        return

    print(f"متن خبر دریافت شد: {len(article_text)} کاراکتر")

    message = (
        f"⚽ {item['title']}\n\n"
        f"{article_text[:3000]}\n\n"
        f"🔗 {item['link']}"
    )

    print("در حال ارسال خبر به تلگرام...")

    send_message(message)

    print("خبر با موفقیت ارسال شد.")


if __name__ == "__main__":
    main()
