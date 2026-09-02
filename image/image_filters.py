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

def looks_like_site_asset_url(url):

    if not url:
        return False

    lower = url.lower()

    patterns = (
        "logo",
        "site-logo",
        "header-logo",
        "footer-logo",
        "avatar",
        "author",
        "profile",
        "favicon",
        "site-icon",
        "icon",
        "cropped-",
        "wordpress-logo",
        "wp-logo",
    )

    for pattern in patterns:

        if pattern in lower:
            return True

    return False

def parse_srcset(
    srcset,
    priority=80,
    source="srcset"
):

    candidates = []

    for part in srcset.split(","):

        pieces = part.strip().split()

        if not pieces:
            continue

        image_url = html.unescape(
            pieces[0]
        ).strip()

        width = 0

        if len(pieces) > 1:

            match = re.search(
                r"(\d+)w",
                pieces[1]
            )

            if match:
                width = int(match.group(1))

        if image_url:

            candidates.append({
                "url": image_url,
                "width": width,
                "height": 0,
                "priority": priority,
                "source": source,
            })

    return candidates


def deduplicate_candidates(candidates):

    unique = {}

    for candidate in candidates:

        url = candidate.get("url", "")

        if not url:
            continue

        key = url.strip()

        if key not in unique:

            unique[key] = candidate

        else:

            old = unique[key]

            old_size = (
                old.get("width", 0)
                * old.get("height", 0)
            )

            new_size = (
                candidate.get("width", 0)
                * candidate.get("height", 0)
            )

            if new_size > old_size:

                unique[key] = candidate

            elif (
                new_size == old_size
                and candidate.get("priority", 0)
                > old.get("priority", 0)
            ):

                unique[key] = candidate

    return list(unique.values())
