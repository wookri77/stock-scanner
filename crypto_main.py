name: BTC Multi-Timeframe Scanner

on:
  schedule:
    # 5분마다 실행 (GitHub Actions 정책상 최소 실행 주기는 약 5분~10분 단위입니다)
    - cron: '*/5 * * * *'
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run BTC Scanner
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python crypto_main.py
