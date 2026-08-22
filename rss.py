import json
import feedparser
from datetime import datetime, timezone

from config import FEEDS_FILE, MAX_NEWS


def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("feeds", [])


def get_published_time(entry):
    """
    زمان انتشار خبر را از RSS به قالب استاندارد ISO تبدیل می‌کند.
    """

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

                published = get_published_time(entry)

                news.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                })

        except Exception as error:
            print(f"RSS error: {error}")

    return news[:MAX_NEWS]
