import os
import requests
import yfinance as yf
import pandas as pd

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

# 2. 감시 대상 종목 리스트 (국내 코스피/코스닥 + 미국 주요 종목)
# 필요에 따라 종목을 자유롭게 추가/삭제할 수 있습니다.
TARGET_STOCKS = {
    # [국내 주식] 종목코드.KS(코스피) / 종목코드.KQ(코스닥)
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "기아": "000270.KS",
    "셀트리온": "068270.KS",
    "KB금융": "105560.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
    "알테오젠": "196170.KQ",
    "에코프로비엠": "247540.KQ",
    "HLB": "028300.KQ",
    
    # [해외 주식] 미국 티커
    "애플": "AAPL",
    "엔비디아": "NVDA",
    "마이크로소프트": "MSFT",
    "알파벳A(구글)": "GOOGL",
    "아마존": "AMZN",
    "메타": "META",
    "테슬라": "TSLA",
    "브로드컴": "AVGO",
    "AMD": "AMD",
    "소니": "SONY"
}

matched_stocks = []

for name, symbol in TARGET_STOCKS.items():
    try:
        # 이평선 계산을 위해 3년치 일봉 데이터 다운로드
        df = yf.download(symbol, period="3y", progress=False)
        if len(df) < 460: # 448일선 계산을 위한 최소 데이터 검증
            continue

        # 데이터 형태 정리 (Series 변환)
        close = df['Close']
        low = df['Low']
        high = df['High']
        
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]

        # 이동평균선 계산 (5, 20, 60, 112, 224, 448일선)
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma112 = close.rolling(112).mean()
        ma224 = close.rolling(224).mean()
        ma448 = close.rolling(448).mean()

        # 최근 120봉(약 6개월) 데이터 추출
        lookback = 120
        recent_ma5 = ma5.iloc[-lookback:]
        recent_ma20 = ma20.iloc[-lookback:]
        recent_ma60 = ma60.iloc[-lookback:]
        recent_ma112 = ma112.iloc[-lookback:]
        recent_ma224 = ma224.iloc[-lookback:]
        recent_ma448 = ma448.iloc[-lookback:]
        recent_low = low.iloc[-lookback:]
        recent_high = high.iloc[-lookback:]

        # 1. 완전 정배열(5 > 20 > 60 > 112 > 224 > 448)이 발생했던 날짜(인덱스) 달성 확인
        perfect_alignment = (
            (recent_ma5 > recent_ma20) & 
            (recent_ma20 > recent_ma60) & 
            (recent_ma60 > recent_ma112) & 
            (recent_ma112 > recent_ma224) & 
            (recent_ma224 > recent_ma448)
        )

        if not perfect_alignment.any():
            continue # 정배열이 한번도 없었던 종목은 제외

        # 가장 최근에 정배열이 완성되었던 위치(인덱스) 찾기
        align_indices = perfect_alignment[perfect_alignment].index
        last_align_idx = align_indices[-1]
        
        # 정배열 완성 이후의 데이터 슬라이싱
        post_align_low = recent_low.loc[last_align_idx:]
        post_align_high = recent_high.loc[last_align_idx:]
        post_align_ma112 = recent_ma112.loc[last_align_idx:]

        # 2. 정배열 완성 이후 112일선 지지(터치) 여부 확인
        # 지지 조건: 당일 저가가 112일선 근처(112일선 -2% ~ +1.5% 범위)에 도달
        touch_112 = (post_align_low <= post_align_ma112 * 1.015) & (post_align_high >= post_align_ma112 * 0.98)

        # 3. "첫 번째" 지지인지 확인
        touch_indices = touch_112[touch_112].index

        if len(touch_indices) > 0:
            first_touch_date = touch_indices[0] # 정배열 후 최초 112일선 지지 발생일
            
            # 오늘(최근 봉)이 바로 그 '최초 지지일'인 경우 포착!
            if first_touch_date == df.index[-1]:
                curr_price = close.iloc[-1]
                val_112 = ma112.iloc[-1]
                matched_stocks.append(
                    f"• *{name}* ({symbol})\n"
                    f"  - 현재가: {curr_price:,.2f}\n"
                    f"  - 112일선: {val_112:,.2f} (첫 지지 포착)"
                )

    except Exception as e:
        print(f"{name} ({symbol}) 계산 중 오류: {e}")

# 4. 결과 전송
if matched_stocks:
    msg = "🎯 **[정배열 후 112일선 첫번째 지지 포착 종목]**\n\n" + "\n\n".join(matched_stocks)
else:
    msg = "🔍 오늘 정배열 후 112일선 '첫 번째' 지지가 발생한 종목이 없습니다."

send_telegram_msg(msg)
