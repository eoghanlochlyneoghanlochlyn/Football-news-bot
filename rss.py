import json
import feedparser

from config import FEEDS_FILE, MAX_NEWS


def load_feeds():
    """خواندن فهرست RSSها از feeds.json"""
    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("feeds", [])


def get_news():
    """دریافت خبرها از تمام RSSهای موجود"""
    feeds = load_feeds()
    news = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()

                if not title or not link:
                    continue

                news.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                })

        except Exception as error:
            print(f"RSS error: {error}")

    # محدود کردن تعداد خبرها
    return news[:MAX_NEWS]
