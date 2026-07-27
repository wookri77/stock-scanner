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

# 2. Bybit Public API로 BTCUSDT 캔들 데이터 가져오기 (GitHub Actions 차단 없음)
BYBIT_INTERVAL_MAP = {
    "5m": "5",
    "1h": "60",
    "4h": "240",
    "1d": "D"
}

def fetch_btc_data(timeframe_str):
    interval = BYBIT_INTERVAL_MAP.get(timeframe_str, "60")
    url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval={interval}&limit=1000"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()
    
    if data.get('retCode') != 0:
        raise Exception(f"Bybit API 오류: {data.get('retMsg')}")
        
    list_data = data['result']['list']
    
    # Bybit 데이터 [startTime, open, high, low, close, volume, turnover]
    df = pd.DataFrame(list_data, columns=['startTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'turnover'])
    
    # 최신 데이터가 인덱스 0이므로 과거->현재 순서로 역순 정렬
    df = df.iloc[::-1].reset_index(drop=True)
    
    df['Close'] = df['Close'].astype(float)
    df['High'] = df['High'].astype(float)
    df['Low'] = df['Low'].astype(float)
    
    return df

TIMEFRAMES = ["5m", "1h", "4h", "1d"]

print("=== 비트코인 스캐너 시작 (텍스트 전용) ===")

matched_alerts = []
status_reports = []

for tf in TIMEFRAMES:
    try:
        time.sleep(0.2)
        df = fetch_btc_data(tf)

        close_s = df['Close']
        low_s = df['Low']
        high_s = df['High']

        # 지수이동평균(EMA) 계산
        ema112 = close_s.ewm(span=112, adjust=False).mean()
        ema224 = close_s.ewm(span=224, adjust=False).mean()
        ema448 = close_s.ewm(span=448, adjust=False).mean()
        ema896 = close_s.ewm(span=896, adjust=False).mean()

        # 정배열 검증 (최근 300봉 내 정배열 구간 존재 여부)
        recent_112 = ema112.iloc[-300:]
        recent_224 = ema224.iloc[-300:]
        recent_448 = ema448.iloc[-300:]
        recent_896 = ema896.iloc[-300:]

        alignment_main = (recent_112 > recent_224) & (recent_224 > recent_448)
        alignment_full = alignment_main & (recent_448 > recent_896)

        if not (alignment_full.any() or alignment_main.any()):
            status_reports.append(f"• `{tf}`: 최근 정배열 미충족")
            continue

        # 최근 3봉 기준 이평선 접촉 여부 체크
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        curr_price = float(close_s.iloc[-1])

        lines_to_check = [
            ("112 EMA 지지", ema112),
            ("224 EMA 지지", ema224),
            ("448 EMA 지지", ema448),
            ("896 EMA 지지", ema896)
        ]

        found = False
        for line_name, ema_series in lines_to_check:
            recent_ema = ema_series.iloc[-3:]
            # 오차범위 ±0.1% 내 지지/터치 여부
            if ((recent_low <= recent_ema * 1.001) & (recent_high >= recent_ema * 0.999)).any():
                val = float(ema_series.dropna().iloc[-1])
                alert_text = (
                    f"⚡ *[비트코인(BTC/USDT) 포착]*\n"
                    f"• *타임프레임:* `{tf}`\n"
                    f"• *상태:* {line_name} (오차 0.1% 접촉)\n"
                    f"• *현재가:* `${curr_price:,.2f}`\n"
                    f"• *이평선 가격:* `${val:,.2f}`"
                )
                matched_alerts.append(alert_text)
                found = True
                break

        if not found:
            status_reports.append(f"• `{tf}`: 정배열 충족, 이평선 미접촉")

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        status_reports.append(f"• `{tf}`: 데이터 조회 실패")

# 3. 텔레그램 결과 전송
if matched_alerts:
    final_msg = "\n\n" + "\n\n---\n\n".join(matched_alerts)
    send_telegram_msg(final_msg)
else:
    report_text = (
        "ℹ️ *[BTC/USDT 스캔 안내]*\n"
        "현재 조건(정배열 + 이평선 ±0.1% 터치)에 부합하는 구간이 없습니다.\n\n"
        "*[타임프레임별 현황]*\n" + "\n".join(status_reports)
    )
    send_telegram_msg(report_text)

print("=== 비트코인 스캐너 완료 ===")
