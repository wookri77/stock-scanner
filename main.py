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
def create_stock_chart(clean_df, name, symbol, line_type):
    chart_df = clean_df.iloc[-120:].copy()
    
    close_s = chart_df['Close']
    ma112 = close_s.rolling(112).mean()
    ma224 = close_s.rolling(224).mean()
    ma448 = close_s.rolling(448).mean()

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

        # yfinance 데이터 칼럼 평탄화 (MultiIndex 및 1차원 추출 방어)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 결측치 제거 및 단일 Series로 변환
        def clean_series(data):
            if isinstance(data, pd.DataFrame):
                data = data.iloc[:, 0]
            return data

        open_s = clean_series(df['Open'])
        high_s = clean_series(df['High'])
        low_s = clean_series(df['Low'])
        close_s = clean_series(df['Close'])
        volume_s = clean_series(df['Volume'])

        clean_df = pd.DataFrame({
            'Open': open_s, 'High': high_s, 'Low': low_s, 'Close': close_s, 'Volume': volume_s
        }, index=df.index).dropna()

        if len(clean_df) < 450:
            continue

        close_s = clean_df['Close']
        low_s = clean_df['Low']
        high_s = clean_df['High']

        ma112 = close_s.rolling(112).mean()
        ma224 = close_s.rolling(224).mean()
        ma448 = close_s.rolling(448).mean()

        # 최근 6개월 정배열 이력 확인
        recent_112 = ma112.iloc[-120:]
        recent_224 = ma224.iloc[-120:]
        recent_448 = ma448.iloc[-120:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        # 최근 3일 이내 지지 확인
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        # nan 방지를 위해 dropna 처리 후 유효한 마지막 값 가져오기
        curr_price = close_s.dropna().iloc[-1]
        
        detected = False
        line_info = ""
        val = 0

        if ((recent_low <= recent_ma112 * 1.02) & (recent_high >= recent_ma112 * 0.97)).any():
            detected = True
            line_info = "112일선 지지"
            val = ma112.dropna().iloc[-1]
        elif ((recent_low <= recent_ma224 * 1.02) & (recent_high >= recent_ma224 * 0.97)).any():
            detected = True
            line_info = "224일선 지지"
            val = ma224.dropna().iloc[-1]
        elif ((recent_low <= recent_ma448 * 1.02) & (recent_high >= recent_ma448 * 0.97)).any():
            detected = True
            line_info = "448일선 지지"
            val = ma448.dropna().iloc[-1]

        if detected:
            matched_count += 1
            caption = f"🎯 *[{name}]* ({symbol})\n• 상태: *{line_info}*\n• 현재가: {curr_price:,.2f} / 해당 이평선: {val:,.2f}"
            
            try:
                chart_file = create_stock_chart(clean_df, name, symbol, line_info)
                send_telegram_photo(chart_file, caption=caption)
                if os.path.exists(chart_file):
                    os.remove(chart_file)
            except Exception as chart_err:
                print(f"차트 생성 실패 ({symbol}): {chart_err}")
                send_telegram_msg(caption)

    except Exception as e:
        print(f"종목 오류 ({symbol}): {e}")
        continue

if matched_count == 0:
    send_telegram_msg("🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다.")
