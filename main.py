from rss import get_news
from telegram import send_message


def main():
    print("در حال دریافت اخبار...")

    news = get_news()

    if not news:
        print("هیچ خبری پیدا نشد.")
        return

    print(f"{len(news)} خبر پیدا شد.")

    # فعلاً فقط اولین خبر را برای تست ارسال می‌کنیم
    item = news[0]

    message = (
        f"⚽ {item['title']}\n\n"
        f"{item['summary']}\n\n"
        f"🔗 {item['link']}"
    )

    print("در حال ارسال خبر به تلگرام...")

    send_message(message)

    print("خبر با موفقیت ارسال شد.")


if __name__ == "__main__":
    main()
