import html
import re
from datetime import timezone, timedelta


# ============================================================
# تنظیمات
# ============================================================

IRAN_TZ = timezone(
    timedelta(
        hours=3,
        minutes=30
    )
)

# حداکثر طول عنوان
MAX_TITLE_LENGTH = 300

# حداکثر طول متن در پیام متنی
MAX_TEXT_BODY_LENGTH = 3500

# حداکثر طول متن در کپشن عکس
MAX_CAPTION_BODY_LENGTH = 900


# ============================================================
# پاک‌سازی متن
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    # حذف فاصله‌های اضافی
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # حذف بیش از دو خط خالی
    text = re.sub(
        r"\n\s*\n\s*\n+",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# حذف Markdown احتمالی از خروجی هوش مصنوعی
# ============================================================

def remove_markdown(text):

    if not text:
        return ""

    text = str(text)

    # حذف عنوان‌های Markdown
    text = re.sub(
        r"^\s*#{1,6}\s*",
        "",
        text,
        flags=re.MULTILINE
    )

    # حذف Bold و Italic رایج
    text = text.replace(
        "**",
        ""
    )

    text = text.replace(
        "__",
        ""
    )

    # حذف بک‌تیک‌های Markdown
    text = text.replace(
        "`",
        ""
    )

    # تبدیل لینک Markdown:
    # [متن](https://example.com)
    # به:
    # متن
    text = re.sub(
        r"\[([^\]]+)\]\((?:https?://|www\.)[^)]+\)",
        r"\1",
        text
    )

    return text.strip()


# ============================================================
# کوتاه کردن متن
# ============================================================

def shorten_text(
    text,
    max_length
):

    if not text:
        return ""

    text = text.strip()

    if len(text) <= max_length:
        return text

    shortened = text[:max_length]

    # ترجیح می‌دهیم در انتهای یک جمله قطع شود.
    sentence_positions = [
        shortened.rfind("."),
        shortened.rfind("!"),
        shortened.rfind("?"),
        shortened.rfind("؟"),
    ]

    best_position = max(
        sentence_positions
    )

    # فقط اگر نقطه مناسبی پیدا شد
    if best_position >= int(
        max_length * 0.6
    ):

        shortened = shortened[
            :best_position + 1
        ]

    else:

        # اگر نقطه مناسبی نبود،
        # روی آخرین فاصله قطع می‌کنیم.
        space_position = shortened.rfind(
            " "
        )

        if space_position >= int(
            max_length * 0.8
        ):

            shortened = shortened[
                :space_position
            ]

    return (
        shortened.rstrip()
        + "…"
    )


# ============================================================
# قالب‌بندی عنوان
# ============================================================

def format_title(title):

    title = clean_text(
        title
    )

    title = remove_markdown(
        title
    )

    if not title:
        return "خبر فوتبال"

    return shorten_text(
        title,
        MAX_TITLE_LENGTH
    )


# ============================================================
# قالب‌بندی متن خبر
# ============================================================

def format_body(
    body,
    max_length=MAX_TEXT_BODY_LENGTH
):

    body = clean_text(
        body
    )

    body = remove_markdown(
        body
    )

    if not body:
        return ""

    return shorten_text(
        body,
        max_length
    )


# ============================================================
# تبدیل زمان به ساعت ایران
# ============================================================

def format_time(published):

    if not published:
        return "--:--"

    try:

        iran_time = published.astimezone(
            IRAN_TZ
        )

        return iran_time.strftime(
            "%H:%M"
        )

    except Exception:

        return "--:--"


# ============================================================
# نام منبع
# ============================================================

def format_source(source):

    if not source:
        return "منبع نامشخص"

    source = clean_text(
        source
    )

    return source


# ============================================================
# لینک خبر
# ============================================================

def format_link(link):

    if not link:
        return ""

    return str(
        link
    ).strip()


# ============================================================
# ساخت متن نهایی پست
# ============================================================

def format_telegram_post(
    news,
    has_image=False
):

    if not isinstance(
        news,
        dict
    ):

        return {
            "success": False,
            "message": "",
            "error": "ساختار خبر نامعتبر است."
        }

    # --------------------------------------------------------
    # اطلاعات
    # --------------------------------------------------------

    translated_title = (
        news.get(
            "translated_title",
            ""
        )
    )

    translated_body = (
        news.get(
            "translated_body",
            ""
        )
    )

    source = format_source(
        news.get(
            "source",
            ""
        )
    )

    published = news.get(
        "published"
    )

    link = format_link(
        news.get(
            "link",
            ""
        )
    )

    # --------------------------------------------------------
    # عنوان
    # --------------------------------------------------------

    title = format_title(
        translated_title
        or news.get(
            "title",
            ""
        )
    )

    # --------------------------------------------------------
    # متن
    # --------------------------------------------------------

    if has_image:

        body = format_body(
            translated_body,
            MAX_CAPTION_BODY_LENGTH
        )

    else:

        body = format_body(
            translated_body,
            MAX_TEXT_BODY_LENGTH
        )

    # --------------------------------------------------------
    # زمان
    # --------------------------------------------------------

    time_text = format_time(
        published
    )

    # --------------------------------------------------------
    # HTML امن
    # --------------------------------------------------------

    safe_title = html.escape(
        title,
        quote=False
    )

    safe_body = html.escape(
        body,
        quote=False
    )

    safe_source = html.escape(
        source,
        quote=False
    )

    safe_link = html.escape(
        link,
        quote=True
    )

    # --------------------------------------------------------
    # ساخت پیام
    # --------------------------------------------------------

    parts = []

    # عنوان
    parts.append(
        f"📰 <b>{safe_title}</b>"
    )

    # متن خبر
    if safe_body:

        parts.append(
            safe_body
        )

    # منبع و زمان
    parts.append(
        f"📌 {safe_source}\n"
        f"🕐 {time_text}"
    )

    # لینک
    if safe_link:

        parts.append(
            f'🔗 <a href="{safe_link}">مطالعه خبر</a>'
        )

    message = "\n\n".join(
        parts
    )

    return {
        "success": True,
        "message": message,
        "error": ""
    }


# ============================================================
# تابع ساده برای استفاده در main.py
# ============================================================

def build_telegram_message(
    title,
    body,
    source,
    published,
    link
):

    news = {

        "translated_title":
            title,

        "translated_body":
            body,

        "source":
            source,

        "published":
            published,

        "link":
            link
    }

    return format_telegram_post(
        news,
        has_image=False
    )


# ============================================================
# تست مستقیم فایل
# ============================================================

if __name__ == "__main__":

    from datetime import datetime

    test_news = {

        "translated_title":
            "آرسنال به جذب یک هافبک نزدیک شده است",

        "translated_body":
            (
                "باشگاه آرسنال در حال بررسی شرایط "
                "جذب این هافبک است و قصد دارد خط میانی "
                "خود را تقویت کند."
            ),

        "source":
            "BBC Sport",

        "published":
            datetime.now(
                timezone.utc
            ),

        "link":
            "https://example.com/news"
    }

    result = format_telegram_post(
        test_news,
        has_image=False
    )

    print(
        result["message"]
    )
