import re


# ============================================================
# URLهایی که باید رد شوند
# ============================================================

BLOCKED_URL_PATTERNS = [

    # ========================================================
    # 101GreatGoals
    # ========================================================

    # Match previews
    r"^https?://(?:www\.)?101greatgoals\.com/match-previews/",

    # Live pages
    r"^https?://(?:www\.)?101greatgoals\.com/live/",

    # Confirmed line-ups
    r"^https?://(?:www\.)?101greatgoals\.com/.*/line-ups-confirmed(?:/|$)",

    # Where to watch
    r"^https?://(?:www\.)?101greatgoals\.com/.*/where-to-watch(?:/|$)",

    # Prediction
    r"^https?://(?:www\.)?101greatgoals\.com/.*/prediction(?:/|$)",


    # ========================================================
    # Football Italia
    # ========================================================

    # Serie A live blog
    r"^https?://(?:www\.)?football-italia\.net/serie-a-week-\d+-liveblog-",


    # ========================================================
    # FourFourTwo
    # ========================================================

    # Watch / Streaming guides
    r"^https?://(?:www\.)?fourfourtwo\.com/.*/watch-.*",


    # ========================================================
    # Bulinews
    # ========================================================

    # Confirmed lineups
    r"^https?://(?:www\.)?bulinews\.com/confirmed-lineups-.*",

]


# ============================================================
# بررسی URL
# ============================================================

def is_blocked_url(url):
    """
    اگر URL جزو صفحات غیرقابل انتشار باشد True برمی‌گرداند.
    """

    if not url:
        return False

    url = url.strip().lower()

    for pattern in BLOCKED_URL_PATTERNS:

        if re.match(pattern, url):

            print(f"⛔ Blocked URL: {url}")

            return True

    return False
