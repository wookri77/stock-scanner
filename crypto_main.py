import os
import requests
import pandas as pd
import ccxt
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. 텔레그램 환경변수
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

for tf in TIMEFRAMES:
    try:
        # EMA896 계산 및 충분한 300캔들 검사를 위해 1800개 데이터 수집
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe=tf, limit=1800)
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

        # 최근 300개 캔들 내 정배열(112 > 224 > 448 > 896) 형성 이력 확인
        recent_112 = ema112.iloc[-300:]
        recent_224 = ema224.iloc[-300:]
        recent_448 = ema448.iloc[-300:]
        recent_896 = ema896.iloc[-300:]

        alignment = (recent_112 > recent_224) & (recent_224 > recent_448) & (recent_448 > recent_896)
        if not alignment.any():
            print(f"[{tf}] 최근 300캔들 내 정배열 조건 미충족")
            continue

        # 최근 5개 캔들 내 이평선 지지(±2.5% 범위) 검사
        recent_low = low_s.iloc[-5:]
        recent_high = high_s.iloc[-5:]

        curr_price = float(close_s.iloc[-1])

        # 각 이평선별 지지 여부 체크
        lines_to_check = [
            ("112이평 지지", ema112),
            ("224이평 지지", ema224),
            ("448이평 지지", ema448),
            ("896이평 지지", ema896)
        ]

        for line_name, ema_series in lines_to_check:
            recent_ema = ema_series.iloc[-5:]
            # 캔들의 고가~저가가 이평선 근처(±2.5%)에 닿았는지 체크
            if ((recent_low <= recent_ema * 1.025) & (recent_high >= recent_ema * 0.975)).any():
                val = float(ema_series.dropna().iloc[-1])
                caption = (
                    f"⚡ [비트코인(BTC/USDT) 포착]\n"
                    f"• 타임프레임: {tf}\n"
                    f"• 상태: {line_name} (최근 300캔들 내 정배열 달성 후)\n"
                    f"• 현재가: ${curr_price:,.2f}\n"
                    f"• 해당 이평선: ${val:,.2f}"
                )
                
                chart_file = None
                try:
                    chart_file = create_btc_chart(df, tf, line_name)
                    send_telegram_photo(chart_file, caption=caption)
                except Exception as chart_err:
                    print(f"차트 생성 실패 ({tf}): {chart_err}")
                    send_telegram_msg(caption)

                if chart_file and os.path.exists(chart_file):
                    os.remove(chart_file)
                
                # 해당 타임프레임에서 포착되면 1회 발송 후 다음 타임프레임으로
                break

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        continue
