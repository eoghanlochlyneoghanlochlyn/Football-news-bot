import os
import urllib.request
import urllib.parse

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = "@footballiiiiiiiiiiiiiiiiiiiiii"

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": "🤖 تست موفق بود! ربات می‌تواند در کانال پیام بفرستد."
}).encode()

urllib.request.urlopen(url, data=data)

print("Message sent successfully!")
