import html
import re

from urllib.parse import (
    parse_qs,
    unquote,
    urlsplit,
)


def safe_int(value):

    try:
        return int(value)

    except Exception:
        return 0
def unwrap_image_proxy_url(url):

    if not url:
        return ""

    try:

        parsed = urlsplit(url)

        query = parse_qs(
            parsed.query
        )

        for key in (
            "url",
            "src",
            "image",
            "image_url",
            "original",
        ):

            values = query.get(key)

            if not values:
                continue

            original = values[0]

            original = unquote(
                html.unescape(
                    original
                )
            ).strip()

            if (
                original.startswith("http://")
                or original.startswith("https://")
            ):

                return original

    except Exception:
        pass

    return url

def looks_like_thumbnail_url(url):

    if not url:
        return False

    lower = url.lower()

    patterns = [

        r"-\d{2,4}x\d{2,4}(?:\.[a-z0-9]+)(?:\?|$)",

        r"/\d{2,4}x\d{2,4}/",

        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",

        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)(?:&|$)",

        r"[?&]width=(?:120|150|160|180|200|240|300|320|400|480|640)[^0-9]",

        r"[?&]w=(?:120|150|160|180|200|240|300|320|400|480|640)[^0-9]",
    ]

    for pattern in patterns:

        if re.search(pattern, lower):
            return True

    words = (
        "thumbnail",
        "thumb",
        "small",
        "tiny",
        "avatar",
        "favicon",
    )

    for word in words:

        if word in lower:
            return True

    return False
