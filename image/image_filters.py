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
