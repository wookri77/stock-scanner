import os
import requests
import pandas as pd
import ccxt
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. 텔레그램 환경변수 설정
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"텔레그램 텍스트 전송 실패: {e}")

def send_telegram_photo(photo_path, caption=""):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and os.path.exists(photo_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(photo_path, 'rb') as photo:
                payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
                files = {"photo": photo}
                res = requests.post(url, data=payload, files=files)
                if not res.ok:
                    print(f"사진 전송 응답 오류 ({photo_path}): {res.text}")
        except Exception as e:
            print(f"텔레그램 사진 전송 예외: {e}")

# 2. 비트코인 차트 생성 함수 (EMA 112, 224, 448, 896 적용)
def create_btc_chart(df, timeframe, line_type):
    chart_df = df.iloc[-150:].copy()
    
    close_s = chart_df['Close']
    ema112 = close_s.ewm(span=112, adjust=False).mean()
    ema224 = close_s.ewm(span=224, adjust=False).mean()
    ema448 = close_s.ewm(span=448, adjust=False).mean()
    ema896 = close_s.ewm(span=896, adjust=False).mean()

    add_plots = [
        mpf.makeaddplot(ema112, color='orange', width=1.2),
        mpf.makeaddplot(ema224, color='red', width=1.2),
        mpf.makeaddplot(ema448, color='purple', width=1.2),
        mpf.makeaddplot(ema896, color='green', width=1.2)
    ]

    mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    file_name = f"BTC_{timeframe}_chart.png"
    mpf.plot(
        chart_df,
        type='candle',
        style=s,
        addplot=add_plots,
        title=f"\nBTC/USDT ({timeframe}) - {line_type}",
        savefig=file_name,
        volume=False,
        figratio=(12, 7),
        figscale=1.1
    )
    plt.close('all')
    return file_name

# 3. 바이낸스 거래소 데이터 조회
exchange = ccxt.binance()

TIMEFRAMES = ["5m", "1h", "4h", "12h", "1d"]

print("=== BTC 스캐너 시작 ===")

any_matched = False
status_reports = []

for tf in TIMEFRAMES:
    try:
        # EMA896 및 300캔들 검사를 위해 1500개 데이터 수집
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe=tf, limit=1500)
        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        df.set_index('Timestamp', inplace=True)

        close_s = df['Close']
        low_s = df['Low']
        high_s = df['High']

        # EMA (지수이동평균) 계산
        ema112 = close_s.ewm(span=112, adjust=False).mean()
        ema224 = close_s.ewm(span=224, adjust=False).mean()
        ema448 = close_s.ewm(span=448, adjust=False).mean()
        ema896 = close_s.ewm(span=896, adjust=False).mean()

        # 최근 300개 캔들 내 정배열 유효성 판별
        recent_112 = ema112.iloc[-300:]
        recent_224 = ema224.iloc[-300:]
        recent_448 = ema448.iloc[-300:]
        recent_896 = ema896.iloc[-300:]

        alignment_main = (recent_112 > recent_224) & (recent_224 > recent_448)
        alignment_full = alignment_main & (recent_448 > recent_896)

        is_aligned = alignment_full.any() or alignment_main.any()

        if not is_aligned:
            status_reports.append(f"• {tf}: 최근 300캔들 내 정배열 미충족")
            print(f"[{tf}] 최근 300캔들 내 정배열 미충족 스킵")
            continue

        # 최근 3개 캔들 내 지지 여부 체크 (오차범위 ±0.1% 정밀 타격)
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]

        curr_price = float(close_s.iloc[-1])

        lines_to_check = [
            ("112이평 지지", ema112),
            ("224이평 지지", ema224),
            ("448이평 지지", ema448),
            ("896이평 지지", ema896)
        ]

        found_support = False

        for line_name, ema_series in lines_to_check:
            recent_ema = ema_series.iloc[-3:]
            # 캔들의 고가~저가가 이평선의 ±0.1% 범위 내에 정확히 닿았는지 판별
            if ((recent_low <= recent_ema * 1.001) & (recent_high >= recent_ema * 0.999)).any():
                val = float(ema_series.dropna().iloc[-1])
                caption = (
                    f"⚡ [비트코인(BTC/USDT) 포착]\n"
                    f"• 타임프레임: {tf}\n"
                    f"• 상태: {line_name} (오차 0.1% 터치)\n"
                    f"• 현재가: ${curr_price:,.2f}\n"
                    f"• 해당 이평선: ${val:,.2f}"
                )
                print(f"[{tf}] 포착 성공: {line_name}")
                
                chart_file = None
                try:
                    chart_file = create_btc_chart(df, tf, line_name)
                    send_telegram_photo(chart_file, caption=caption)
                except Exception as chart_err:
                    print(f"차트 생성/전송 오류 ({tf}): {chart_err}")
                    send_telegram_msg(caption)

                if chart_file and os.path.exists(chart_file):
                    os.remove(chart_file)
                
                found_support = True
                any_matched = True
                break

        if not found_support:
            status_reports.append(f"• {tf}: 정배열 충족, 이평선(±0.1%) 미접촉")
            print(f"[{tf}] 최근 3캔들 내 이평선 0.1% 범위 터치 없음")

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        status_reports.append(f"• {tf}: 조회 실패 및 에러")
        continue

# 조건에 부합하는 타임프레임이 하나도 없을 때 안내 메시지 발송
if not any_matched:
    report_text = (
        "ℹ️ [BTC/USDT 스캔 안내]\n"
        "현재 조건(정배열 + 이평선 ±0.1% 터치)에 부합하는 타임프레임이 없습니다.\n\n"
        "[타임프레임별 상태 요약]\n" + "\n".join(status_reports)
    )
    send_telegram_msg(report_text)

print("=== BTC 스캐너 완료 ===")
