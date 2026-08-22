import json
import feedparser

from config import FEEDS_FILE, MAX_NEWS


def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("feeds", [])


def get_news():
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

                published = entry.get(
                    "published",
                    entry.get("updated", "")
                )

                news.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                })

        except Exception as error:
            print(f"RSS error: {error}")

    return news[:MAX_NEWS]
