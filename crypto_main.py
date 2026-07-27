import os
import time
import requests
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from tvdatafeed import TvDatafeed, Interval

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

# 3. 트레이딩뷰(TvDatafeed) 객체 생성 (비로그인 상태로 사용 가능)
tv = TvDatafeed()

# 타임프레임 매핑 (트레이딩뷰 규격)
TIMEFRAME_MAP = {
    "5m": Interval.in_5_minute,
    "1h": Interval.in_1_hour,
    "4h": Interval.in_4_hour,
    "12h": Interval.in_2_hour, # tvdatafeed에서 12h 미지원 시 대안 또는 1d/4h 조합 사용
    "1d": Interval.in_daily
}

def fetch_tv_btc(timeframe_str):
    """트레이딩뷰에서 BTC/USDT 차트 데이터 수집"""
    # BYBIT 소스 우선, 실패 시 BINANCE 소스 사용
    exchanges = ["BYBIT", "BINANCE"]
    interval = TIMEFRAME_MAP.get(timeframe_str, Interval.in_1_hour)
    
    for ex in exchanges:
        try:
            df = tv.get_hist(symbol='BTCUSDT', exchange=ex, interval=interval, n_bars=1000)
            if df is not None and not df.empty:
                # 컬럼명 통일 (open -> Open 등)
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                })
                print(f"[{timeframe_str}] 트레이딩뷰 데이터 수집 성공 ({ex})")
                return df
        except Exception as e:
            print(f"[{timeframe_str}] {ex} 트레이딩뷰 수집 실패: {e}")
            time.sleep(0.5)
            
    raise Exception("트레이딩뷰 데이터 수집 전체 실패")

TIMEFRAMES = ["5m", "1h", "4h", "1d"]  # 안정적인 지원 타임프레임

print("=== BTC 스캐너 시작 (TradingView Engine) ===")

any_matched = False
status_reports = []

for tf in TIMEFRAMES:
    try:
        time.sleep(0.5)

        df = fetch_tv_btc(tf)

        close_s = df['Close']
        low_s = df['Low']
        high_s = df['High']

        ema112 = close_s.ewm(span=112, adjust=False).mean()
        ema224 = close_s.ewm(span=224, adjust=False).mean()
        ema448 = close_s.ewm(span=448, adjust=False).mean()
        ema896 = close_s.ewm(span=896, adjust=False).mean()

        recent_112 = ema112.iloc[-300:]
        recent_224 = ema224.iloc[-300:]
        recent_448 = ema448.iloc[-300:]
        recent_896 = ema896.iloc[-300:]

        alignment_main = (recent_112 > recent_224) & (recent_224 > recent_448)
        alignment_full = alignment_main & (recent_448 > recent_896)

        is_aligned = alignment_full.any() or alignment_main.any()

        if not is_aligned:
            status_reports.append(f"• {tf}: 최근 정배열 미충족")
            print(f"[{tf}] 정배열 미충족 스킵")
            continue

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
            if ((recent_low <= recent_ema * 1.001) & (recent_high >= recent_ema * 0.999)).any():
                val = float(ema_series.dropna().iloc[-1])
                caption = (
                    f"⚡ [비트코인(BTC/USDT) 포착 - TradingView]\n"
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
            print(f"[{tf}] 이평선 0.1% 범위 터치 없음")

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        status_reports.append(f"• {tf}: 조회 실패 ({e})")
        continue

if not any_matched:
    report_text = (
        "ℹ️ [BTC/USDT 스캔 안내 - TradingView]\n"
        "현재 조건(정배열 + 이평선 ±0.1% 터치)에 부합하는 타임프레임이 없습니다.\n\n"
        "[타임프레임별 상태 요약]\n" + "\n".join(status_reports)
    )
    send_telegram_msg(report_text)

print("=== BTC 스캐너 완료 ===")
