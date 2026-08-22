import requests

from config import BOT_TOKEN, CHANNEL_ID


def send_message(text):
    """ارسال یک پیام متنی به کانال تلگرام"""

    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN پیدا نشد.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False,
    }

    response = requests.post(url, data=data, timeout=30)

    if not response.ok:
        raise RuntimeError(
            f"Telegram error: {response.status_code} - {response.text}"
        )

    return response.json()
