import html
import json
import re

import requests

from config import (
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)

from utils import make_absolute_url

from image.image_filters import (
    safe_int,
    parse_srcset,
    deduplicate_candidates,
)

# ============================================================
# دریافت صفحهٔ خبر
# ============================================================

def fetch_article_page(article_url):

    if not article_url:
        return ""

    profiles = [

        {
            **REQUEST_HEADERS,
            "Referer": article_url,
        },

        {
            **REQUEST_HEADERS,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": article_url,
        },

        {
            **REQUEST_HEADERS,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        },

        {
            **REQUEST_HEADERS,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
        },
    ]

    for index, headers in enumerate(
        profiles[:ARTICLE_REQUEST_PROFILES],
        start=1
    ):

        try:

            print(
                f"تلاش برای دریافت صفحه "
                f"(روش {index})..."
            )

            response = requests.get(
                article_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            if not response.ok:

                print(
                    f"⚠️ پاسخ صفحه: "
                    f"{response.status_code}"
                )

                continue

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
                .lower()
            )

            if (
                "text/html" in content_type
                or not content_type
            ):

                print(
                    "✓ صفحهٔ خبر دریافت شد."
                )

                return response.text

        except requests.RequestException as error:

            print(
                f"⚠️ خطای درخواست: {error}"
            )

        except Exception as error:

            print(
                f"⚠️ خطای غیرمنتظره: {error}"
            )

    return ""

# ============================================================
# استخراج تصاویر Meta
# ============================================================

def extract_meta_images(
    content,
    article_url
):

    candidates = []

    patterns = [

        (
            r'<meta[^>]+property=["\']og:image["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            250,
            "og:image",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+property=["\']og:image["\']',
            250,
            "og:image",
        ),

        (
            r'<meta[^>]+name=["\']twitter:image["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            180,
            "twitter:image",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+name=["\']twitter:image["\']',
            180,
            "twitter:image",
        ),

        (
            r'<meta[^>]+property=["\']og:image:url["\']'
            r'[^>]+content=["\']([^"\']+)["\']',
            230,
            "og:image:url",
        ),

        (
            r'<meta[^>]+content=["\']([^"\']+)["\']'
            r'[^>]+property=["\']og:image:url["\']',
            230,
            "og:image:url",
        ),
    ]

    for pattern, priority, source in patterns:

        matches = re.findall(
            pattern,
            content,
            re.IGNORECASE
        )

        for image_url in matches:

            image_url = make_absolute_url(
                image_url,
                article_url
            )

            if not image_url:
                continue

            candidates.append({
                "url": image_url,
                "width": 0,
                "height": 0,
                "priority": priority,
                "source": source,
            })

    return candidates

# ============================================================
# استخراج JSON-LD
# ============================================================

def extract_jsonld_images(
    content,
    article_url
):

    candidates = []

    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\']'
        r'[^>]*>(.*?)</script>',
        content,
        re.IGNORECASE | re.DOTALL
    )

    for block in blocks:

        try:

            data = json.loads(
                html.unescape(
                    block.strip()
                )
            )

        except Exception:

            continue

        objects = []

        if isinstance(data, dict):

            objects.append(data)

            graph = data.get("@graph")

            if isinstance(graph, list):

                objects.extend(graph)

        elif isinstance(data, list):

            objects.extend(data)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            obj_type = obj.get(
                "@type",
                ""
            )

            if isinstance(obj_type, list):

                article_object = any(
                    str(item).lower()
                    in (
                        "newsarticle",
                        "article",
                        "reportagenewsarticle",
                    )
                    for item in obj_type
                )

            else:

                article_object = (
                    str(obj_type).lower()
                    in (
                        "newsarticle",
                        "article",
                        "reportagenewsarticle",
                    )
                )

            image = obj.get("image")

            image_items = []

            if isinstance(image, str):

                image_items.append({
                    "url": image,
                    "width": 0,
                    "height": 0,
                })

            elif isinstance(image, dict):

                image_items.append({
                    "url": image.get(
                        "url",
                        ""
                    ),
                    "width": safe_int(
                        image.get(
                            "width",
                            0
                        )
                    ),
                    "height": safe_int(
                        image.get(
                            "height",
                            0
                        )
                    ),
                })

            elif isinstance(image, list):

                for item in image:

                    if isinstance(item, str):

                        image_items.append({
                            "url": item,
                            "width": 0,
                            "height": 0,
                        })

                    elif isinstance(item, dict):

                        image_items.append({
                            "url": item.get(
                                "url",
                                ""
                            ),
                            "width": safe_int(
                                item.get(
                                    "width",
                                    0
                                )
                            ),
                            "height": safe_int(
                                item.get(
                                    "height",
                                    0
                                )
                            ),
                        })

            for image_item in image_items:

                image_url = make_absolute_url(
                    image_item["url"],
                    article_url
                )

                if not image_url:
                    continue

                candidates.append({
                    "url": image_url,
                    "width": image_item["width"],
                    "height": image_item["height"],
                    "priority": (
                        320
                        if article_object
                        else 160
                    ),
                    "source": "jsonld",
                })

    return candidates



# ============================================================
# استخراج تصاویر HTML
# ============================================================

def extract_html_images(
    content,
    article_url
):

    candidates = []

    tags = re.findall(
        r"<img\b[^>]*>",
        content,
        re.IGNORECASE
    )

    for position, tag in enumerate(tags):

        width = 0
        height = 0

        width_match = re.search(
            r'\bwidth=["\']?(\d+)',
            tag,
            re.IGNORECASE
        )

        height_match = re.search(
            r'\bheight=["\']?(\d+)',
            tag,
            re.IGNORECASE
        )

        if width_match:
            width = int(
                width_match.group(1)
            )

        if height_match:
            height = int(
                height_match.group(1)
            )

        attributes = re.findall(
            r'(?:src|data-src|data-original|'
            r'data-lazy-src|data-image|data-url)='
            r'["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for image_url in attributes:

            image_url = make_absolute_url(
                image_url,
                article_url
            )

            if image_url:

                candidates.append({
                    "url": image_url,
                    "width": width,
                    "height": height,
                    "priority": 70,
                    "source": "img",
                    "position": position,
                })

        srcsets = re.findall(
            r'srcset=["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        for srcset in srcsets:

            srcset_candidates = parse_srcset(
                srcset,
                priority=110,
                source="srcset"
            )

            for candidate in srcset_candidates:

                candidate["url"] = (
                    make_absolute_url(
                        candidate["url"],
                        article_url
                    )
                )

                candidate["position"] = position

                candidates.append(
                    candidate
                )

    return candidates


# ============================================================
# تمام تصاویر صفحه
# ============================================================

def get_article_image_candidates(
    content,
    article_url
):

    candidates = []

    candidates.extend(
        extract_meta_images(
            content,
            article_url
        )
    )

    candidates.extend(
        extract_jsonld_images(
            content,
            article_url
        )
    )

    candidates.extend(
        extract_html_images(
            content,
            article_url
        )
    )

    return deduplicate_candidates(
        candidates
    )

