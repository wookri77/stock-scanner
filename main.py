import os
import requests
import pandas as pd
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt

# 텔레그램 설정
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

def create_stock_chart(clean_df, symbol, line_type):
    chart_df = clean_df.iloc[-120:].copy()
    
    close_s = chart_df['Close']
    ma112 = close_s.rolling(112).mean()
    ma224 = close_s.rolling(224).mean()
    ma448 = close_s.rolling(448).mean()

    # mpf.make_addplot (오타 수정완료)
    add_plots = [
        mpf.make_addplot(ma112, color='orange', width=1.5),
        mpf.make_addplot(ma224, color='red', width=1.5),
        mpf.make_addplot(ma448, color='purple', width=1.5)
    ]

    mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    file_name = f"{symbol.replace('.', '_')}_chart.png"
    mpf.plot(
        chart_df,
        type='candle',
        style=s,
        addplot=add_plots,
        title=f"\n{symbol} - {line_type}",
        savefig=file_name,
        volume=False,
        figratio=(12, 7),
        figscale=1.1
    )
    plt.close('all')
    return file_name

def get_stock_tickers():
    tickers = []
    
    # 1. 미국 주요 300개 티커 동적 가져오기 (S&P 500 위키피디아)
    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(sp500_url)
        us_tickers = tables[0]['Symbol'].str.replace('.', '-').tolist()[:300]
        tickers.extend(us_tickers)
        print(f"미국 주식 {len(us_tickers)}개 티커 수집 완료")
    except Exception as e:
        print(f"미국 티커 수집 실패, 기본 목록 사용: {e}")
        tickers.extend(["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "NFLX", "INTC", "PLTR", "COIN"])

    # 2. 한국 대표 300개 티커 (네이버/KOSPI/KOSDAQ 주요 상위 종목 코드)
    # yfinance 포맷에 맞춰 .KS, .KQ 붙임
    kr_base_codes = [
        "005930", "000660", "005380", "035420", "035720", "373220", "207940", "000270", "068270", "105560",
        "005490", "247540", "086520", "006400", "051910", "003550", "012330", "000810", "066570", "032830",
        "055550", "015760", "018260", "033780", "009150", "011200", "010140", "034730", "010130", "003670",
        "009540", "030200", "017670", "096770", "000150", "036570", "005935", "086790", "010950", "259960"
    ]
    # 필요시 추가 커스텀 가능, .KS 및 .KQ 구분 결합
    kr_tickers = [f"{code}.KS" for code in kr_base_codes]
    tickers.extend(kr_tickers)
    
    return tickers

send_telegram_msg("🚀 [주식/암호화폐 통합 스캐너] 스캔을 시작합니다.")

TARGET_TICKERS = get_stock_tickers()
print(f"총 {len(TARGET_TICKERS)}개 종목 스캔을 시작합니다...")

matched_summary = []
matched_charts = []

for symbol in TARGET_TICKERS:
    try:
        df = yf.download(symbol, period="3y", progress=False)
        if df.empty or len(df) < 450:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        def clean_series(data):
            if isinstance(data, pd.DataFrame):
                data = data.iloc[:, 0]
            return data

        open_s = clean_series(df['Open'])
        high_s = clean_series(df['High'])
        low_s = clean_series(df['Low'])
        close_s = clean_series(df['Close'])
        volume_s = clean_series(df['Volume'])

        clean_df = pd.DataFrame({
            'Open': open_s, 'High': high_s, 'Low': low_s, 'Close': close_s, 'Volume': volume_s
        }, index=df.index).dropna()

        if len(clean_df) < 450:
            continue

        close_s = clean_df['Close']
        low_s = clean_df['Low']
        high_s = clean_df['High']

        ma112 = close_s.rolling(112).mean()
        ma224 = close_s.rolling(224).mean()
        ma448 = close_s.rolling(448).mean()

        recent_112 = ma112.iloc[-120:]
        recent_224 = ma224.iloc[-120:]
        recent_448 = ma448.iloc[-120:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        curr_price = float(close_s.dropna().iloc[-1])
        
        detected = False
        line_info = ""
        val = 0.0

        if ((recent_low <= recent_ma112 * 1.02) & (recent_high >= recent_ma112 * 0.97)).any():
            detected = True
            line_info = "112일선 지지"
            val = float(ma112.dropna().iloc[-1])
        elif ((recent_low <= recent_ma224 * 1.02) & (recent_high >= recent_ma224 * 0.97)).any():
            detected = True
            line_info = "224일선 지지"
            val = float(ma224.dropna().iloc[-1])
        elif ((recent_low <= recent_ma448 * 1.02) & (recent_high >= recent_ma448 * 0.97)).any():
            detected = True
            line_info = "448일선 지지"
            val = float(ma448.dropna().iloc[-1])

        if detected:
            unit = "원" if ".KS" in symbol or ".KQ" in symbol else "$"
            fmt_price = f"{curr_price:,.0f}" if unit == "원" else f"{curr_price:,.2f}"
            fmt_val = f"{val:,.0f}" if unit == "원" else f"{val:,.2f}"

            item_text = f"📌 {symbol}\n• 현재가: {fmt_price}{unit}\n• 상태: {line_info} (이평선: {fmt_val}{unit})"
            matched_summary.append(item_text)

            caption = f"🎯 [{symbol}]\n• 상태: {line_info}\n• 현재가: {fmt_price}{unit} / 이평선: {fmt_val}{unit}"
            
            try:
                chart_file = create_stock_chart(clean_df, symbol, line_info)
                matched_charts.append((chart_file, caption))
            except Exception as chart_err:
                print(f"차트 생성 실패 ({symbol}): {chart_err}")

    except Exception as e:
        continue

# 최종 전송
if matched_summary:
    divider = "\n" + "-" * 28 + "\n\n"
    summary_text = f"🎯 [주식 장기 이평선 지지 종목 포착 ({len(matched_summary)}건)]\n\n" + divider.join(matched_summary)
    send_telegram_msg(summary_text)

    for chart_file, caption in matched_charts:
        send_telegram_photo(chart_file, caption=caption)
        if chart_file and os.path.exists(chart_file):
            os.remove(chart_file)
else:
    send_telegram_msg("🔍 주식 종목 중 장기 이평선 조건에 부합하는 종목이 없습니다.")
