import requests
from bs4 import BeautifulSoup


def get_article_text(url):
    """دریافت متن اصلی یک خبر از صفحهٔ وب"""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # حذف بخش‌هایی که معمولاً متن خبر نیستند
    for element in soup([
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form"
    ]):
        element.decompose()

    # تلاش برای پیدا کردن متن اصلی مقاله
    article = soup.find("article")

    if article:
        paragraphs = article.find_all("p")
    else:
        paragraphs = soup.find_all("p")

    texts = []

    for paragraph in paragraphs:
        text = paragraph.get_text(" ", strip=True)

        if text:
            texts.append(text)

    # حذف خطوط بسیار کوتاه و بی‌اهمیت
    texts = [
        text for text in texts
        if len(text) >= 30
    ]

    return "\n\n".join(texts)
