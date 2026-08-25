import json
import re
import feedparser

from config import FEEDS_FILE


# کلمات و عبارت‌های مرتبط با لیگ برتر
PREMIER_LEAGUE_KEYWORDS = [
    "premier league",
    "english premier league",
    "epl",
    "arsenal",
    "aston villa",
    "bournemouth",
    "brentford",
    "brighton",
    "burnley",
    "chelsea",
    "crystal palace",
    "everton",
    "fulham",
    "leeds",
    "liverpool",
    "manchester city",
    "man city",
    "manchester united",
    "man united",
    "newcastle",
    "nottingham forest",
    "sunderland",
    "tottenham",
    "spurs",
    "west ham",
    "wolves",
    "wolverhampton"
]


WOMENS_KEYWORDS = [
    "women",
    "women's",
    "wsl",
    "women football",
    "women's football",
    "female"
]


OTHER_SPORTS_KEYWORDS = [
    "tennis",
    "formula 1",
    "f1",
    "cricket",
    "rugby",
    "golf",
    "nba",
    "nfl",
    "boxing",
    "ufc",
    "cycling",
    "athletics",
    "motorsport"
]


OTHER_LEAGUE_KEYWORDS = [
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "champions league",
    "europa league",
    "conference league",
    "championship",
    "league one",
    "league two",
    "mls",
    "eredivisie",
    "primeira liga",
    "scottish premiership"
]


def contains_keyword(text, keywords):
    text = text.lower()

    for keyword in keywords:
        if keyword in text:
            return True

    return False


def classify_article(title, summary=""):
    text = f"{title} {summary}".lower()

    if contains_keyword(text, OTHER_SPORTS_KEYWORDS):
        return "other_sports"

    if contains_keyword(text, WOMENS_KEYWORDS):
        return "womens_football"

    if contains_keyword(text, PREMIER_LEAGUE_KEYWORDS):
        return "premier_league"

    if contains_keyword(text, OTHER_LEAGUE_KEYWORDS):
        return "other_football"

    return "unknown"


def main():

    print("=" * 70)
    print("تحلیل محتوای RSS ها")
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

            if not feed.entries:
                print("هیچ خبری دریافت نشد.")
                continue

            results = {
                "premier_league": [],
                "other_football": [],
                "womens_football": [],
                "other_sports": [],
                "unknown": []
            }

            for entry in feed.entries:

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                if not title:
                    continue

                category = classify_article(title, summary)

                results[category].append(title)

            total = sum(len(items) for items in results.values())

            print(f"تعداد کل خبرها: {total}")
            print()

            print(
                f"Premier League: {len(results['premier_league'])}"
            )

            print(
                f"Other Football: {len(results['other_football'])}"
            )

            print(
                f"Women's Football: {len(results['womens_football'])}"
            )

            print(
                f"Other Sports: {len(results['other_sports'])}"
            )

            print(
                f"Unknown: {len(results['unknown'])}"
            )

            print()
            print("نمونه خبرهای Premier League:")

            for title in results["premier_league"][:5]:
                print(f"  - {title}")

            print()
            print("نمونه خبرهای Other Football:")

            for title in results["other_football"][:5]:
                print(f"  - {title}")

            print()
            print("نمونه خبرهای Unknown:")

            for title in results["unknown"][:5]:
                print(f"  - {title}")

        except Exception as error:
            print(f"خطا: {error}")

    print()
    print("=" * 70)
    print("تحلیل تمام RSS ها تمام شد.")
    print("=" * 70)


if __name__ == "__main__":
    main()
