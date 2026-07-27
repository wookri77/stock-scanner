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
                requests.post(url, data=payload, files=files)
        except Exception as e:
            print(f"텔레그램 사진 전송 실패: {e}")

# 2. 비트코인 차트 생성 함수 (112, 224, 448, 896 이평선 적용)
def create_btc_chart(df, timeframe, line_type):
    chart_df = df.iloc[-120:].copy()
    
    close_s = chart_df['Close']
    ma112 = close_s.rolling(112).mean()
    ma224 = close_s.rolling(224).mean()
    ma448 = close_s.rolling(448).mean()
    ma896 = close_s.rolling(896).mean()

    add_plots = [
        mpf.makeaddplot(ma112, color='orange', width=1.2),
        mpf.makeaddplot(ma224, color='red', width=1.2),
        mpf.makeaddplot(ma448, color='purple', width=1.2),
        mpf.makeaddplot(ma896, color='green', width=1.2)
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

# 3. 바이낸스 거래소 객체 생성
exchange = ccxt.binance()

# 검사할 타임프레임 목록 (5분, 1시간, 4시간, 12시간, 1일)
TIMEFRAMES = ["5m", "1h", "4h", "12h", "1d"]

matched_count = 0

for tf in TIMEFRAMES:
    try:
        # 896이평선을 계산하기 위해 최소 1000개 이상의 캔들 데이터 수집
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe=tf, limit=1000)
        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        df.set_index('Timestamp', inplace=True)

        close_s = df['Close']
        low_s = df['Low']
        high_s = df['High']

        # 4대 이평선 계산
        ma112 = close_s.rolling(112).mean()
        ma224 = close_s.rolling(224).mean()
        ma448 = close_s.rolling(448).mean()
        ma896 = close_s.rolling(896).mean()

        # 최근 100개 캔들 동안 정배열(112 > 224 > 448 > 896) 이력 확인
        recent_112 = ma112.iloc[-100:]
        recent_224 = ma224.iloc[-100:]
        recent_448 = ma448.iloc[-100:]
        recent_896 = ma896.iloc[-100:]

        alignment = (recent_112 > recent_224) & (recent_224 > recent_448) & (recent_448 > recent_896)
        if not alignment.any():
            continue

        # 최근 3개 캔들 내에서 이평선 지지(±2% 오차범위) 체크
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]
        recent_ma896 = ma896.iloc[-3:]

        curr_price = float(close_s.iloc[-1])
        detected = False
        line_info = ""
        val = 0.0

        if ((recent_low <= recent_ma112 * 1.015) & (recent_high >= recent_ma112 * 0.985)).any():
            detected = True
            line_info = "112이평 지지"
            val = float(ma112.dropna().iloc[-1])
        elif ((recent_low <= recent_ma224 * 1.015) & (recent_high >= recent_ma224 * 0.985)).any():
            detected = True
            line_info = "224이평 지지"
            val = float(ma224.dropna().iloc[-1])
        elif ((recent_low <= recent_ma448 * 1.015) & (recent_high >= recent_ma448 * 0.985)).any():
            detected = True
            line_info = "448이평 지지"
            val = float(ma448.dropna().iloc[-1])
        elif ((recent_low <= recent_ma896 * 1.015) & (recent_high >= recent_ma896 * 0.985)).any():
            detected = True
            line_info = "896이평 지지"
            val = float(ma896.dropna().iloc[-1])

        if detected:
            matched_count += 1
            caption = (
                f"⚡ [비트코인(BTC/USDT) 포착]\n"
                f"• 타임프레임: {tf}\n"
                f"• 상태: {line_info} (정배열 달성 후)\n"
                f"• 현재가: ${curr_price:,.2f}\n"
                f"• 해당 이평선: ${val:,.2f}"
            )
            
            chart_file = None
            try:
                chart_file = create_btc_chart(df, tf, line_info)
                send_telegram_photo(chart_file, caption=caption)
            except Exception as chart_err:
                print(f"차트 생성 실패 ({tf}): {chart_err}")
                send_telegram_msg(caption)

            if chart_file and os.path.exists(chart_file):
                os.remove(chart_file)

    except Exception as e:
        print(f"비트코인 스캔 에러 ({tf}): {e}")
        continue
