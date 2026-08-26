import json
import os
from datetime import datetime, timezone, timedelta

from utils import normalize_url, normalize_title
from config import SEEN_FILE, SEEN_RETENTION_HOURS


# ============================================================
# خواندن seen_news
# ============================================================

def load_seen():
    """
    seen_news.json را می‌خواند.
    در صورت نبودن یا خراب بودن فایل، دیکشنری خالی برمی‌گرداند.
    """

    if not os.path.exists(SEEN_FILE):
        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

        print(
            f"⚠️ ساختار {SEEN_FILE} معتبر نیست."
        )

        return {}

    except Exception as error:

        print(
            f"⚠️ خطا در خواندن {SEEN_FILE}: {error}"
        )

        return {}


# ============================================================
# ذخیره seen_news
# ============================================================

def save_seen(seen):
    """
    seen_news.json را ذخیره می‌کند.
    """

    temporary_file = f"{SEEN_FILE}.tmp"

    try:

        with open(
            temporary_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                seen,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temporary_file,
            SEEN_FILE
        )

        return True

    except Exception as error:

        print(
            f"⚠️ خطا در ذخیره {SEEN_FILE}: {error}"
        )

        try:

            if os.path.exists(
                temporary_file
            ):
                os.remove(
                    temporary_file
                )

        except Exception:
            pass

        return False


# ============================================================
# زمان ثبت خبر
# ============================================================

def get_seen_time(data):
    """
    زمان ثبت خبر را از sent_at می‌خواند.
    """

    if not isinstance(data, dict):
        return None

    sent_at = data.get(
        "sent_at",
        ""
    )

    if not sent_at:
        return None

    try:

        parsed = datetime.fromisoformat(
            sent_at
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:

        return None


# ============================================================
# پاک‌سازی خبرهای قدیمی
# ============================================================

def cleanup_seen(seen):
    """
    خبرهای قدیمی‌تر از SEEN_RETENTION_HOURS را حذف می‌کند.

    مثال:
    اگر ساعت فعلی 11:00 باشد و مقدار نگهداری 24 ساعت باشد،
    فقط مواردی که از 11:00 روز قبل به بعد ثبت شده‌اند
    نگه داشته می‌شوند.
    """

    if not seen:
        return 0

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            hours=SEEN_RETENTION_HOURS
        )
    )

    keys_to_delete = []

    for key, data in seen.items():

        sent_time = get_seen_time(
            data
        )

        # اگر زمان ثبت نامعتبر باشد،
        # فعلاً حذف نمی‌کنیم تا اطلاعات از بین نرود.
        if sent_time is None:
            continue

        if sent_time < cutoff:

            keys_to_delete.append(
                key
            )

    for key in keys_to_delete:

        del seen[key]

    if keys_to_delete:

        print(
            f"🧹 تعداد {len(keys_to_delete)} "
            f"خبر قدیمی از seen_news حذف شد."
        )

    return len(keys_to_delete)


# ============================================================
# بررسی تکراری بودن خبر
# ============================================================

def is_duplicate(news, seen):
    """
    خبر را هم بر اساس لینک و هم بر اساس
    عنوان + منبع بررسی می‌کند.
    """

    normalized_link = normalize_url(
        news.get(
            "link",
            ""
        )
    )

    normalized_title = normalize_title(
        news.get(
            "title",
            ""
        )
    )

    source = (
        str(
            news.get(
                "source",
                ""
            )
        )
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # بررسی لینک
    # --------------------------------------------------------

    if (
        normalized_link
        and normalized_link in seen
    ):

        return True

    # --------------------------------------------------------
    # بررسی عنوان + منبع
    # --------------------------------------------------------

    for old_data in seen.values():

        if not isinstance(
            old_data,
            dict
        ):
            continue

        old_title = normalize_title(
            old_data.get(
                "title",
                ""
            )
        )

        old_source = (
            str(
                old_data.get(
                    "source",
                    ""
                )
            )
            .strip()
            .lower()
        )

        if (
            normalized_title
            and old_title == normalized_title
            and old_source == source
        ):

            return True

    return False


# ============================================================
# ثبت خبر
# ============================================================

def mark_as_seen(news, seen):
    """
    خبر ارسال‌شده را در seen ثبت می‌کند.
    """

    normalized_link = normalize_url(
        news.get(
            "link",
            ""
        )
    )

    if not normalized_link:
        return False

    published = news.get(
        "published"
    )

    if published:

        try:

            published_text = (
                published.isoformat()
            )

        except Exception:

            published_text = str(
                published
            )

    else:

        published_text = ""

    seen[normalized_link] = {

        "title":
            news.get(
                "title",
                ""
            ),

        "normalized_title":
            normalize_title(
                news.get(
                    "title",
                    ""
                )
            ),

        "source":
            news.get(
                "source",
                ""
            ),

        "published":
            published_text,

        "sent_at":
            datetime.now(
                timezone.utc
            ).isoformat()
    }

    return True


# ============================================================
# آماده‌سازی seen
# ============================================================

def prepare_seen(seen):
    """
    قبل از شروع بررسی RSS،
    خبرهای قدیمی را حذف می‌کند.

    خروجی:
        (seen, changed)
    """

    removed = cleanup_seen(
        seen
    )

    changed = removed > 0

    return seen, changed
