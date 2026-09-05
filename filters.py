import re


# ============================================================
# URLهایی که باید رد شوند
# ============================================================

BLOCKED_URL_PATTERNS = [

    # 101GreatGoals
    r"^https?://(?:www\.)?101greatgoals\.com/match-previews/",
    r"^https?://(?:www\.)?101greatgoals\.com/live/",

    # Football Italia
    r"^https?://(?:www\.)?football-italia\.net/serie-a-week-\d+-liveblog-",

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

            return True

    return False
