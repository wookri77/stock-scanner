import os
import requests
import pandas as pd
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. 텔레그램 환경변수 불러오기
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

# 2. 차트 이미지 생성 함수
def create_stock_chart(df, name, symbol, line_type):
    # 최근 120봉(약 6개월) 분량만 차트로 시각화
    chart_df = df.iloc[-120:].copy()
    
    # yfinance 데이터 칼럼 구조 정리
    if isinstance(chart_df.columns, pd.MultiIndex):
        chart_df.columns = chart_df.columns.get_level_values(0)

    # 장기 이평선 계산
    ma112 = chart_df['Close'].rolling(112).mean()
    ma224 = chart_df['Close'].rolling(224).mean()
    ma448 = chart_df['Close'].rolling(448).mean()

    # 이평선 추가 선 설정 (주황: 112일선, 빨강: 224일선, 보라: 448일선)
    add_plots = [
        mpf.makeaddplot(ma112, color='orange', width=1.5),
        mpf.makeaddplot(ma224, color='red', width=1.5),
        mpf.makeaddplot(ma448, color='purple', width=1.5)
    ]

    # 차트 스타일 설정
    mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    file_name = f"{symbol}_chart.png"
    
    # 차트 그리기 및 파일 저장
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

# 3. 국내/해외 주요 종목 리스트 수집
def get_target_tickers():
    target_dict = {}

    # A. 미국 주요 종목
    print("미국 주요 종목 수집 중...")
    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(sp500_url)
        us_df = tables[0]
        us_tickers = us_df['Symbol'].str.replace('.', '-').tolist()[:250]
        for ticker in us_tickers:
            target_dict[ticker] = ticker
    except Exception as e:
        print(f"미국 크롤링 예외: {e}")

    us_backup = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "NFLX", "INTC"]
    for t in us_backup:
        target_dict[t] = t

    # B. 한국 주요 종목
    print("한국 주요 종목 수집 중...")
    try:
        krx_url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        krx_df = pd.read_html(krx_url, header=0)[0]
        krx_df['종목코드'] = krx_df['종목코드'].map('{:06d}'.format)
        
        for _, row in krx_df.head(250).iterrows():
            code = row['종목코드']
            name = row['회사명']
            target_dict[f"{name}"] = f"{code}.KS"
    except Exception as e:
        print(f"한국 크롤링 예외: {e}")

    kr_backup = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
        "삼성바이오로직스": "207940.KS", "현대차": "005380.KS", "기아": "000270.KS",
        "셀트리온": "068270.KS", "KB금융": "105560.KS", "NAVER": "035420.KS"
    }
    target_dict.update(kr_backup)

    return target_dict

# 4. 메인 분석 로직
TARGET_STOCKS = get_target_tickers()
print(f"총 {len(TARGET_STOCKS)}개 종목 분석을 시작합니다.")

matched_count = 0
count = 0

for name, symbol in TARGET_STOCKS.items():
    count += 1
    if count % 50 == 0:
        print(f"진행 상황: {count}/{len(TARGET_STOCKS)} 종목 분석 완료...")

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

        # 장기 이동평균선 계산
        ma112 = close.rolling(112).mean()
        ma224 = close.rolling(224).mean()
        ma448 = close.rolling(448).mean()

        # [조건 1] 최근 6개월(120봉) 내 정배열 이력 검증
        lookback_6m = 120
        recent_112 = ma112.iloc[-lookback_6m:]
        recent_224 = ma224.iloc[-lookback_6m:]
        recent_448 = ma448.iloc[-lookback_6m:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        # [조건 2] 최근 3일 이내 장기 이평선 터치/지지 확인
        recent_low = low.iloc[-3:]
        recent_high = high.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        curr_price = close.iloc[-1]
        
        detected = False
        line_info = ""
        val = 0

        # A. 112일선 지지
        touch_112 = (recent_low <= recent_ma112 * 1.02) & (recent_high >= recent_ma112 * 0.97)
        if touch_112.any():
            detected = True
            line_info = "112일선 지지"
            val = ma112.iloc[-1]

        # B. 224일선 지지
        elif (recent_low <= recent_ma224 * 1.02).any() and (recent_high >= recent_ma224 * 0.97).any():
            detected = True
            line_info = "224일선 지지"
            val = ma224.iloc[-1]

        # C. 448일선 지지
        elif (recent_low <= recent_ma448 * 1.02).any() and (recent_high >= recent_ma448 * 0.97).any():
            detected = True
            line_info = "448일선 지지"
            val = ma448.iloc[-1]

        # 포착 시 텔레그램으로 텍스트 + 차트 사진 함께 발송
        if detected:
            matched_count += 1
            caption = (
                f"🎯 *[{name}]* ({symbol})\n"
                f"• 상태: *{line_info}*\n"
                f"• 현재가: {curr_price:,.2f} / 해당 이평선: {val:,.2f}"
            )
            
            # 차트 이미지 생성
            chart_file = create_stock_chart(df, name, symbol, line_info)
            
            # 사진 전송
            send_telegram_photo(chart_file, caption=caption)
            
            # 임시 이미지 파일 삭제
            if os.path.exists(chart_file):
                os.remove(chart_file)

    except Exception as e:
        continue

# 포착된 종목이 없을 때만 안내 메시지 전송
if matched_count == 0:
    send_telegram_msg("🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다.")
