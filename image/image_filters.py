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
