from rss import get_news


def main():
    print("=" * 60)
    print("شروع تست RSS ها")
    print("=" * 60)

    news = get_news()

    print()
    print(f"تعداد کل خبرهای دریافت‌شده: {len(news)}")
    print()

    for i, item in enumerate(news, start=1):
        print(f"{i}. [{item['source']}]")
        print(f"   عنوان: {item['title']}")
        print(f"   لینک: {item['link']}")
        print(f"   زمان: {item['published']}")
        print("-" * 60)


if __name__ == "__main__":
    main()
