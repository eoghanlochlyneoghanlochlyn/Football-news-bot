name: Gemini News V2 Test

on:
  workflow_dispatch:

jobs:
  test-news:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run test
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python test_news_v2.py
