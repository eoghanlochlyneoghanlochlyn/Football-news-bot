import html
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, urljoin

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def iran_now():
    """Current time in Iran."""
    return datetime.now(IRAN_TZ)


def normalize_url(url: str) -> str:
    """Normalize URLs for duplicate detection."""
    if not url:
        return ""

    url = html.unescape(str(url).strip())

    try:
        parts = urlsplit(url)

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "",
            ""
        ))

    except Exception:
        return url.strip()


def normalize_title(title: str) -> str:
    """Normalize titles for duplicate detection."""
    if not title:
        return ""

    title = html.unescape(str(title))

    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"\s+", " ", title)

    title = title.strip().lower()

    title = re.sub(r"[\"'“”‘’`]", "", title)
    title = re.sub(r"[.,!?;:()\[\]{}]", "", title)

    return title.strip()


def escape_html(text: str) -> str:
    """Escape HTML for Telegram."""
    return html.escape(str(text), quote=False)


def make_absolute_url(url: str, base_url: str) -> str:
    """Convert relative URL to absolute."""
    if not url:
        return ""

    return urljoin(base_url, html.unescape(url).strip())


def safe_int(value, default=0):
    """Convert value to int safely."""
    try:
        return int(value)
    except Exception:
        return default


def format_iran_time(dt: datetime) -> str:
    """Convert UTC datetime to HH:MM Iran time."""
    if not dt:
        return "--:--"

    return (
        dt.astimezone(IRAN_TZ)
        .strftime("%H:%M")
    )


def clean_text(text: str) -> str:
    """Remove unnecessary whitespace."""
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()
