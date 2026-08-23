import requests
from bs4 import BeautifulSoup

NEWS_URL = "https://www.bbc.co.uk/sport/football/articles/cdx7x90dxywo?at_medium=RSS&at_campaign=rss"

print("در حال دریافت خبر...")

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(
    NEWS_URL,
    headers=headers,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# حذف بخش‌هایی که متن اصلی خبر نیستند
for element in soup([
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside"
]):
    element.decompose()

# پیدا کردن پاراگراف‌ها
paragraphs = []

for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)

    if len(text) >= 40:
        paragraphs.append(text)

print()
print("========== متن استخراج‌شده ==========")
print()

for paragraph in paragraphs:
    print(paragraph)
    print()

print("======================================")
print()
print(f"تعداد پاراگراف‌ها: {len(paragraphs)}")
print(f"تعداد کاراکترها: {sum(len(p) for p in paragraphs)}")
