import os
import requests
import pandas as pd
import yfinance as yf
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

# 2. 차트 생성 함수 (종목명 포함)
def create_stock_chart(clean_df, name, symbol, line_type):
    chart_df = clean_df.iloc[-120:].copy()
    
    close_s = chart_df['Close']
    ma112 = close_s.rolling(112).mean()
    ma224 = close_s.rolling(224).mean()
    ma448 = close_s.rolling(448).mean()

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
        title=f"\n{name} ({symbol}) - {line_type}",
        savefig=file_name,
        volume=False,
        figratio=(12, 7),
        figscale=1.1
    )
    plt.close('all')
    return file_name

# 3. 미국(300개) + 한국(300개) 종목명 및 티커 수집
def get_stock_dictionary():
    stock_dict = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # [미국] S&P 500 종목명 & 티커 300개 수집
    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        req = requests.get(sp500_url, headers=headers)
        tables = pd.read_html(req.text)
        df_us = tables[0][['Symbol', 'Security']].iloc[:300]
        for _, row in df_us.iterrows():
            sym = str(row['Symbol']).replace('.', '-')
            name = str(row['Security'])
            stock_dict[name] = sym
        print(f"미국 주식 {len(stock_dict)}개 종목 수집 완료")
    except Exception as e:
        print(f"미국 종목 크롤링 예외: {e}")

    # [한국] 네이버 금융 시가총액 상위 종목 수집 (KOSPI & KOSDAQ 상위 300개)
    kr_count = 0
    for page in range(1, 7): # 페이지당 50개씩 총 300개
        for sosok in [0, 1]: # 0: 코스피, 1: 코스닥
            try:
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers=headers)
                df_list = pd.read_html(res.text, encoding='euc-kr')
                df_kr = df_list[1].dropna(how='all')
                
                # HTML에서 종목 코드 및 종목명 추출
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.select("table.type_2 a.tlto")
                
                for link in links:
                    code = link['href'].split('code=')[-1]
                    name = link.text.strip()
                    suffix = ".KS" if sosok == 0 else ".KQ"
                    symbol = f"{code}{suffix}"
                    if name not in stock_dict:
                        stock_dict[name] = symbol
                        kr_count += 1
            except Exception as e:
                continue

    print(f"한국 주식 {kr_count}개 종목 수집 완료 (전체 스캔 대상: {len(stock_dict)}개)")
    return stock_dict

# 4. 분석 실행
send_telegram_msg("🚀 [주식 이평선 스캐너] 스캔을 시작합니다.")

TARGET_STOCKS = get_stock_dictionary()
matched_summary = []
matched_charts = []

for name, symbol in TARGET_STOCKS.items():
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

            item_text = (
                f"📌 {name} ({symbol})\n"
                f"• 현재가: {fmt_price}{unit}\n"
                f"• 상태: {line_info} (이평선: {fmt_val}{unit})"
            )
            matched_summary.append(item_text)

            caption = f"🎯 [{name}] ({symbol})\n• 상태: {line_info}\n• 현재가: {fmt_price}{unit} / 이평선: {fmt_val}{unit}"
            
            try:
                chart_file = create_stock_chart(clean_df, name, symbol, line_info)
                matched_charts.append((chart_file, caption))
            except Exception as chart_err:
                print(f"차트 생성 실패 ({symbol}): {chart_err}")

    except Exception as e:
        continue

# 5. 최종 알림 발송
if matched_summary:
    divider = "\n" + "-" * 28 + "\n\n"
    summary_text = (
        f"🎯 [주식 장기 이평선 지지 종목 포착 ({len(matched_summary)}건)]\n\n"
        + divider.join(matched_summary)
    )
    send_telegram_msg(summary_text)

    for chart_file, caption in matched_charts:
        send_telegram_photo(chart_file, caption=caption)
        if chart_file and os.path.exists(chart_file):
            os.remove(chart_file)
else:
    send_telegram_msg("🔍 오늘 주요 종목 중 장기 이평선(112/224/448일선) 지지가 발생한 종목이 없습니다.")
