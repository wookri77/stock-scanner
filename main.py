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

# 2. 차트 생성 함수 (데이터 구조 오류 수정)
def create_stock_chart(df, name, symbol, line_type):
    # 최근 120봉 분량 슬라이싱
    chart_df = df.iloc[-120:].copy()
    
    # yfinance MultiIndex 컬럼 문제 강제 정리
    if isinstance(chart_df.columns, pd.MultiIndex):
        chart_df.columns = chart_df.columns.get_level_values(0)

    close_series = chart_df['Close']
    if isinstance(close_series, pd.DataFrame):
        close_series = close_series.iloc[:, 0]

    # 이평선 계산
    ma112 = close_series.rolling(112).mean()
    ma224 = close_series.rolling(224).mean()
    ma448 = close_series.rolling(448).mean()

    # 차트용 데이터프레감 필수 컬럼만 정제
    clean_df = pd.DataFrame({
        'Open': chart_df['Open'].iloc[:, 0] if isinstance(chart_df['Open'], pd.DataFrame) else chart_df['Open'],
        'High': chart_df['High'].iloc[:, 0] if isinstance(chart_df['High'], pd.DataFrame) else chart_df['High'],
        'Low': chart_df['Low'].iloc[:, 0] if isinstance(chart_df['Low'], pd.DataFrame) else chart_df['Low'],
        'Close': close_series,
        'Volume': chart_df['Volume'].iloc[:, 0] if isinstance(chart_df['Volume'], pd.DataFrame) else chart_df['Volume']
    }, index=chart_df.index)

    add_plots = [
        mpf.makeaddplot(ma112, color='orange', width=1.5),
        mpf.makeaddplot(ma224, color='red', width=1.5),
        mpf.makeaddplot(ma448, color='purple', width=1.5)
    ]

    mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    file_name = f"{symbol}_chart.png"
    mpf.plot(
        clean_df,
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

# 3. 대상 종목 리스트
def get_target_tickers():
    return {
        "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA", "마이크로소프트": "MSFT",
        "아마존": "AMZN", "구글": "GOOGL", "메타": "META", "AMD": "AMD",
        "넷플릭스": "NFLX", "인텔": "INTC", "팔란티어": "PLTR", "코인베이스": "COIN",
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS",
        "NAVER": "035420.KS", "카카오": "035720.KS", "LG에너지솔루션": "373220.KS",
        "삼성바이오로직스": "207940.KS", "기아": "000270.KS", "셀트리온": "068270.KS",
        "KB금융": "105560.KS", "POSCO홀딩스": "005490.KS", "에코프로비엠": "247540.KQ"
    }

# 4. 분석 실행
send_telegram_msg("🚀 스캐너 분석을 시작합니다!")

TARGET_STOCKS = get_target_tickers()
matched_count = 0

for name, symbol in TARGET_STOCKS.items():
    try:
        df = yf.download(symbol, period="3y", progress=False)
        if df.empty or len(df) < 450:
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

        # 최근 6개월 정배열 이력 확인
        recent_112 = ma112.iloc[-120:]
        recent_224 = ma224.iloc[-120:]
        recent_448 = ma448.iloc[-120:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        # 최근 3일 이내 지지 확인
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
            
            # 차트 이미지 생성 및 전송
            chart_file = create_stock_chart(df, name, symbol, line_info)
            send_telegram_photo(chart_file, caption=caption)
            
            if os.path.exists(chart_file):
                os.remove(chart_file)

    except Exception as e:
        print(f"Error on {symbol}: {e}")
        continue

if matched_count == 0:
    send_telegram_msg("🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다.")
