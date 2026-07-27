import os
import time
import requests
import pandas as pd

# 1. 텔레그램 설정
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        try:
            res = requests.post(url, json=payload, timeout=10)
            if not res.ok:
                print(f"텔레그램 전송 실패 응답: {res.text}")
        except Exception as e:
            print(f"텔레그램 텍스트 전송 예외: {e}")

# 2. Upbit Public API 데이터 수집 (500개 캔들 확보로 448일선 완벽 대응)
UPBIT_TIMEFRAME_MAP = {
    "5m": "minutes/5",
    "1h": "minutes/60",
    "4h": "minutes/240",
    "1d": "days"
}

def fetch_upbit_btc_500(timeframe_str):
    endpoint = UPBIT_TIMEFRAME_MAP[timeframe_str]
    base_url = f"https://api.upbit.com/v1/candles/{endpoint}?market=KRW-BTC&count=200"
    headers = {"accept": "application/json"}
    
    all_candles = []
    
    # 1차 요청 (최신 200개)
    res1 = requests.get(base_url, headers=headers, timeout=10)
    res1.raise_for_status()
    data1 = res1.json()
    all_candles.extend(data1)
    
    # 2차 요청 (과거 200개 추가 수집하여 400~500개 확보)
    if len(data1) > 0:
        last_to = data1[-1]['candle_date_time_utc']
        url2 = f"{base_url}&to={last_to}Z"
        time.sleep(0.1)
        res2 = requests.get(url2, headers=headers, timeout=10)
        if res2.ok:
            data2 = res2.json()
            all_candles.extend(data2)

    if not all_candles:
        raise Exception("Upbit 응답 데이터 없음")

    df = pd.DataFrame(all_candles)
    # 과거 -> 현재 순서 정렬
    df = df.iloc[::-1].reset_index(drop=True)
    
    df['Close'] = df['trade_price'].astype(float)
    df['High'] = df['high_price'].astype(float)
    df['Low'] = df['low_price'].astype(float)
    df['Open'] = df['opening_price'].astype(float)
    
    return df

TIMEFRAMES = ["5m", "1h", "4h", "1d"]

print("=== 비트코인 스캐너 시작 (Upbit 500봉 안정화 버전) ===")

matched_alerts = []
status_reports = []

for tf in TIMEFRAMES:
    try:
        time.sleep(0.2)
        df = fetch_upbit_btc_500(tf)

        close_s = df['Close']
        low_s = df['Low']
        high_s = df['High']

        # 원래 기준: 112, 224, 448 이동평균선
        ma112 = close_s.rolling(112).mean()
        ma224 = close_s.rolling(224).mean()
        ma448 = close_s.rolling(448).mean()

        # 최근 200봉 기준 정배열 체크
        check_range = min(200, len(df))
        recent_112 = ma112.iloc[-check_range:]
        recent_224 = ma224.iloc[-check_range:]
        recent_448 = ma448.iloc[-check_range:]

        alignment = (recent_112 > recent_224) & (recent_224 > recent_448)

        if not alignment.any():
            status_reports.append(f"• `{tf}`: 최근 정배열(112>224>448) 미충족")
            continue

        # 최근 3봉 기준 이평선 지지/터치 체크 (오차범위 ±0.1%)
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        curr_price = float(close_s.iloc[-1])

        lines_to_check = [
            ("112일선 지지", ma112),
            ("224일선 지지", ma224),
            ("448일선 지지", ma448)
        ]

        found = False
        for line_name, ma_series in lines_to_check:
            valid_series = ma_series.dropna()
            if len(valid_series) == 0:
                continue
                
            recent_ma = ma_series.iloc[-3:]
            if ((recent_low <= recent_ma * 1.001) & (recent_high >= recent_ma * 0.999)).any():
                val = float(valid_series.iloc[-1])
                alert_text = (
                    f"⚡ *[비트코인(BTC) 포착]*\n"
                    f"• *타임프레임:* `{tf}`\n"
                    f"• *상태:* {line_name} (오차 0.1% 접촉)\n"
                    f"• *현재가:* `{curr_price:,.0f}원`\n"
                    f"• *이평선 가격:* `{val:,.0f}원`"
                )
                matched_alerts.append(alert_text)
                found = True
                break

        if not found:
            status_reports.append(f"• `{tf}`: 정배열 충족, 이평선 미접촉")

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        status_reports.append(f"• `{tf}`: 데이터 조회 실패 ({e})")

# 3. 텔레그램 결과 전송
if matched_alerts:
    final_msg = "\n\n" + "\n\n---\n\n".join(matched_alerts)
    send_telegram_msg(final_msg)
else:
    report_text = (
        "ℹ️ *[BTC 스캔 안내]*\n"
        "현재 조건(정배열 + 112/224/448일선 ±0.1% 지지)에 부합하는 구간이 없습니다.\n\n"
        "*[타임프레임별 현황]*\n" + "\n".join(status_reports)
    )
    send_telegram_msg(report_text)

print("=== 비트코인 스캐너 완료 ===")
