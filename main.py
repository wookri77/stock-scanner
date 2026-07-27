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

# 2. 국내/해외 시가총액 상위 종목 리스트 수집
def get_target_tickers():
    target_dict = {}

    # A. 미국 S&P 500 / 나스닥 상위 300개 티커
    print("미국 주요 300개 종목 수집 중...")
    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(sp500_url)
        us_df = tables[0]
        us_tickers = us_df['Symbol'].str.replace('.', '-').tolist()[:300]
        for ticker in us_tickers:
            target_dict[ticker] = ticker
    except Exception as e:
        print(f"미국 종목 수집 오류: {e}")

    # B. 한국 코스피/코스닥 상위 300개 티커
    print("한국 주요 300개 종목 수집 중...")
    try:
        krx_url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        krx_df = pd.read_html(krx_url, header=0)[0]
        krx_df['종목코드'] = krx_df['종목코드'].map('{:06d}'.format)
        
        for _, row in krx_df.head(300).iterrows():
            code = row['종목코드']
            name = row['회사명']
            target_dict[f"{name}"] = f"{code}.KS"
    except Exception as e:
        print(f"한국 종목 수집 오류: {e}")

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
        # 3년치 일봉 데이터 다운로드
        df = yf.download(symbol, period="3y", progress=False)
        if len(df) < 460:
            if symbol.endswith(".KS"):
                symbol = symbol.replace(".KS", ".KQ")
                df = yf.download(symbol, period="3y", progress=False)
                if len(df) < 460:
                    continue
            else:
                continue

        close = df['Close']
        low = df['Low']
        high = df['High']

        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]

        # 이동평균선 계산 (중장기 이평선 중심)
        ma60 = close.rolling(60).mean()
        ma112 = close.rolling(112).mean()
        ma224 = close.rolling(224).mean()
        ma448 = close.rolling(448).mean()

        # 최근 120봉(약 6개월) 데이터 슬라이싱
        lookback = 120
        recent_ma60 = ma60.iloc[-lookback:]
        recent_ma112 = ma112.iloc[-lookback:]
        recent_ma224 = ma224.iloc[-lookback:]
        recent_ma448 = ma448.iloc[-lookback:]
        recent_low = low.iloc[-lookback:]
        recent_high = high.iloc[-lookback:]

        # 조건 1: 중장기 이평선(60 > 112 > 224 > 448) 정배열 달성 확인
        mid_long_alignment = (
            (recent_ma60 > recent_ma112) & 
            (recent_ma112 > recent_ma224) & 
            (recent_ma224 > recent_ma448)
        )

        if not mid_long_alignment.any():
            continue

        align_indices = mid_long_alignment[mid_long_alignment].index
        last_align_idx = align_indices[-1]

        post_align_low = recent_low.loc[last_align_idx:]
        post_align_high = recent_high.loc[last_align_idx:]
        post_align_ma112 = recent_ma112.loc[last_align_idx:]

        # 조건 2: 112일선 지지 오차범위 (-2% ~ +1.5%)
        touch_112 = (post_align_low <= post_align_ma112 * 1.015) & (post_align_high >= post_align_ma112 * 0.98)
        touch_indices = touch_112[touch_112].index

        # 조건 3: 정배열 발생 후 '첫 번째' 지지가 '오늘' 터치되었는지 확인
        if len(touch_indices) > 0:
            first_touch_date = touch_indices[0]
            if first_touch_date == df.index[-1]:
                curr_price = close.iloc[-1]
                val_112 = ma112.iloc[-1]
                matched_stocks.append(
                    f"• *{name}* ({symbol})\n"
                    f"  - 현재가: {curr_price:,.2f} / 112일선: {val_112:,.2f}"
                )

    except Exception as e:
        continue

# 4. 결과 텔레그램 전송
if matched_stocks:
    msg = f"🎯 **[중장기 정배열(60>112>224>448) 후 112일선 첫 지지 포착!]**\n\n" + "\n\n".join(matched_stocks)
else:
    msg = "🔍 오늘 600개 주요 종목 중 중장기 정배열 후 112일선 '첫 번째' 지지가 발생한 종목이 없습니다."

send_telegram_msg(msg)
