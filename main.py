import os
import requests
import pandas as pd
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. 텔레그램 환경변수
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"텔레그램 텍스트 전송 실패: {e}")

def send_telegram_photo(photo_path, caption=""):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and os.path.exists(photo_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(photo_path, 'rb') as photo:
                payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
                files = {"photo": photo}
                requests.post(url, data=payload, files=files)
        except Exception as e:
            print(f"텔레그램 사진 전송 실패: {e}")

# 2. 차트 생성 함수
def create_stock_chart(df, name, symbol, line_type):
    chart_df = df.iloc[-120:].copy()
    if isinstance(chart_df.columns, pd.MultiIndex):
        chart_df.columns = chart_df.columns.get_level_values(0)

    ma112 = chart_df['Close'].rolling(112).mean()
    ma224 = chart_df['Close'].rolling(224).mean()
    ma448 = chart_df['Close'].rolling(448).mean()

    add_plots = [
        mpf.makeaddplot(ma112, color='orange', width=1.5),
        mpf.makeaddplot(ma224, color='red', width=1.5),
        mpf.makeaddplot(ma448, color='purple', width=1.5)
    ]

    mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    file_name = f"{symbol}_chart.png"
    mpf.plot(
        chart_df,
        type='candle',
        style=s,
        addplot=add_plots,
        title=f"\n{name} ({symbol}) - {line_type}",
        savefig=file_name,
        volume=False,
        figratio=(12, 7),
        figscale=1.1
    )
    plt.close('all')
    return file_name

# 3. 주요 종목 수집 (미국+한국 500여개)
def get_target_tickers():
    target_dict = {}

    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(sp500_url)
        us_df = tables[0]
        us_tickers = us_df['Symbol'].str.replace('.', '-').tolist()[:200]
        for ticker in us_tickers:
            target_dict[ticker] = ticker
    except Exception as e:
        print(f"미국 목록 수집 예외: {e}")

    us_backup = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "NFLX", "INTC"]
    for t in us_backup:
        target_dict[t] = t

    try:
        krx_url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        krx_df = pd.read_html(krx_url, header=0)[0]
        krx_df['종목코드'] = krx_df['종목코드'].map('{:06d}'.format)
        for _, row in krx_df.head(200).iterrows():
            target_dict[row['회사명']] = f"{row['종목코드']}.KS"
    except Exception as e:
        print(f"한국 목록 수집 예외: {e}")

    return target_dict

# 4. 분석 실행
send_telegram_msg("🚀 스캐너가 정상 동작 중입니다! 종목 분석을 시작합니다.")

TARGET_STOCKS = get_target_tickers()
matched_count = 0

for name, symbol in TARGET_STOCKS.items():
    try:
        df = yf.download(symbol, period="3y", progress=False)
        if df.empty or len(df) < 450:
            if symbol.endswith(".KS"):
                symbol = symbol.replace(".KS", ".KQ")
                df = yf.download(symbol, period="3y", progress=False)
                if df.empty or len(df) < 450:
                    continue
            else:
                continue

        close = df['Close']
        low = df['Low']
        high = df['High']

        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]

        ma112 = close.rolling(112).mean()
        ma224 = close.rolling(224).mean()
        ma448 = close.rolling(448).mean()

        recent_112 = ma112.iloc[-120:]
        recent_224 = ma224.iloc[-120:]
        recent_448 = ma448.iloc[-120:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        recent_low = low.iloc[-3:]
        recent_high = high.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        curr_price = close.iloc[-1]
        detected = False
        line_info = ""
        val = 0

        if ((recent_low <= recent_ma112 * 1.02) & (recent_high >= recent_ma112 * 0.97)).any():
            detected = True
            line_info = "112일선 지지"
            val = ma112.iloc[-1]
        elif ((recent_low <= recent_ma224 * 1.02) & (recent_high >= recent_ma224 * 0.97)).any():
            detected = True
            line_info = "224일선 지지"
            val = ma224.iloc[-1]
        elif ((recent_low <= recent_ma448 * 1.02) & (recent_high >= recent_ma448 * 0.97)).any():
            detected = True
            line_info = "448일선 지지"
            val = ma448.iloc[-1]

        if detected:
            matched_count += 1
            caption = f"🎯 *[{name}]* ({symbol})\n• 상태: *{line_info}*\n• 현재가: {curr_price:,.2f} / 해당 이평선: {val:,.2f}"
            chart_file = create_stock_chart(df, name, symbol, line_info)
            send_telegram_photo(chart_file, caption=caption)
            if os.path.exists(chart_file):
                os.remove(chart_file)
    except Exception as e:
        continue

if matched_count == 0:
    send_telegram_msg("🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다.")
