import os
import requests
import pandas as pd
import yfinance as yf

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
            print(f"텔레그램 전송 실패: {e}")

# 2. 국내/해외 주요 종목 리스트 수집
def get_target_tickers():
    target_dict = {}

    # A. 미국 주요 종목 (S&P 500 크롤링 + 핵심 백업)
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

    # B. 한국 주요 종목 (KRX 크롤링 + 핵심 백업)
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

# 3. 메인 분석 로직
TARGET_STOCKS = get_target_tickers()
print(f"총 {len(TARGET_STOCKS)}개 종목 분석을 시작합니다.")

matched_stocks = []
count = 0

for name, symbol in TARGET_STOCKS.items():
    count += 1
    if count % 50 == 0:
        print(f"진행 상황: {count}/{len(TARGET_STOCKS)} 종목 분석 완료...")

    try:
        # 3년치 일봉 데이터 불러오기
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

        # [조건 1] 최근 6개월(120봉) 이내에 112 > 224 > 448 정배열 흐름이 존재했었는지 확인
        lookback_6m = 120
        recent_112 = ma112.iloc[-lookback_6m:]
        recent_224 = ma224.iloc[-lookback_6m:]
        recent_448 = ma448.iloc[-lookback_6m:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue  # 최근 6개월 내 정배열 추세가 없었다면 스킵

        # [조건 2] 최근 3일 봉(오늘, 어제, 그저께) 중 장기 이평선 터치/지지가 발생했는지 직접 확인
        recent_low = low.iloc[-3:]
        recent_high = high.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        curr_price = close.iloc[-1]

        # A. 112일선 지지 체크 (저가가 112일선 -3% ~ +2% 사이에 닿은 경우)
        touch_112 = (recent_low <= recent_ma112 * 1.02) & (recent_high >= recent_ma112 * 0.97)
        if touch_112.any():
            val = ma112.iloc[-1]
            matched_stocks.append(f"• *{name}* ({symbol})\n  - 🟠 [112일선 지지] 현재가: {curr_price:,.2f} / 112선: {val:,.2f}")
            continue

        # B. 224일선 지지 체크
        touch_224 = (recent_low <= recent_ma224 * 1.02) & (recent_high >= recent_ma224 * 0.97)
        if touch_224.any():
            val = ma224.iloc[-1]
            matched_stocks.append(f"• *{name}* ({symbol})\n  - 🔴 [224일선 지지] 현재가: {curr_price:,.2f} / 224선: {val:,.2f}")
            continue

        # C. 448일선 지지 체크
        touch_448 = (recent_low <= recent_ma448 * 1.02) & (recent_high >= recent_ma448 * 0.97)
        if touch_448.any():
            val = ma448.iloc[-1]
            matched_stocks.append(f"• *{name}* ({symbol})\n  - ⚪ [448일선 지지] 현재가: {curr_price:,.2f} / 448선: {val:,.2f}")
            continue

    except Exception as e:
        continue

# 4. 결과 전송
if matched_stocks:
    msg = f"🎯 **[장기 이평선(112/224/448) 지지 타점 포착!]**\n\n" + "\n\n".join(matched_stocks)
else:
    msg = "🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다."

send_telegram_msg(msg)
