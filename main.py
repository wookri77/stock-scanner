import os
import requests
import pandas as pd
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt

# 1. 텔레그램 설정
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"텔레그램 텍스트 전송 실패: {e}")

def send_telegram_photo(photo_path, caption=""):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and os.path.exists(photo_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(photo_path, 'rb') as photo:
                payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
                files = {"photo": photo}
                res = requests.post(url, data=payload, files=files, timeout=15)
                if not res.ok:
                    print(f"사진 전송 응답 오류 ({photo_path}): {res.text}")
        except Exception as e:
            print(f"텔레그램 사진 전송 예외: {e}")

# 2. 차트 생성 함수
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

# 3. 주요 종목 딕셔너리 (차단 없는 안정적 명단)
def get_target_stocks():
    return {
        # === 한국 대표 주요 종목 ===
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
        "삼성바이오로직스": "207940.KS", "현대차": "005380.KS", "기아": "000270.KS",
        "셀트리온": "068270.KS", "KB금융": "105560.KS", "NAVER": "035420.KS",
        "HD현대중공업": "329180.KS", "POSCO홀딩스": "005490.KS", "신한지주": "055550.KS",
        "삼성물산": "028260.KS", "현대모비스": "012330.KS", "카카오": "035720.KS",
        "LG화학": "051910.KS", "삼성SDI": "006400.KS", "하나금융지주": "086790.KS",
        "메리츠금융지주": "138040.KS", "삼성생명": "032830.KS", "에코프로비엠": "247540.KQ",
        "에코프로": "086520.KQ", "HLB": "028300.KQ", "알테오젠": "196170.KQ",
        "카카오뱅크": "377300.KS", "크래프톤": "259960.KS", "한화에어로스페이스": "012450.KS",
        "한국전력": "015760.KS", "HMM": "011200.KS", "LG전자": "066570.KS",
        "S-Oil": "010950.KS", "우리금융지주": "316140.KS", "KT&G": "033780.KS",
        "삼성화재": "000810.KS", "HD한국조선해양": "009540.KS", "SK이노베이션": "096770.KS",
        "한화오션": "042660.KS", "두산에너빌리티": "034020.KS", "기업은행": "024110.KS",
        
        # === 미국 대표 주요 종목 ===
        "애플": "AAPL", "엔비디아": "NVDA", "마이크로소프트": "MSFT", "아마존": "AMZN",
        "구글(알파벳A)": "GOOGL", "메타": "META", "테슬라": "TSLA", "버크셔해서웨이": "BRK-B",
        "일라이릴리": "LLY", "브로드컴": "AVGO", "JP모건": "JPM", "비자": "V",
        "월마트": "WMT", "마스터카드": "MA", "엑손모빌": "XOM", "존슨앤드존슨": "JNJ",
        "프록터앤드갬블": "PG", "코스트코": "COST", "Home Depot": "HD", "AMD": "AMD",
        "넷플릭스": "NFLX", "쉐브론": "CVX", "머크": "MRK", "아베비": "ABBV",
        "피프티세븐": "PLTR", "코카콜라": "KO", "펩시코": "PEP", "뱅크오브아메리카": "BAC",
        "퀄컴": "QCOM", "암젠": "AMGN", "디즈니": "DIS", "인텔": "INTC",
        "나이키": "NKE", "코인베이스": "COIN", "아이온큐": "IONQ", "SOXL": "SOXL"
    }

# 4. 메인 실행 로직
send_telegram_msg("🚀 [주식 이평선 스캐너] 스캔을 시작합니다.")

TARGET_STOCKS = get_target_stocks()
matched_summary = []
matched_charts = []

for name, symbol in TARGET_STOCKS.items():
    try:
        # 데이터 수집
        df = yf.download(symbol, period="3y", progress=False)
        if df.empty or len(df) < 450:
            continue

        # yfinance MultiIndex 데이터프레임 구조 강제 단일화
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 데이터 가공
        clean_df = pd.DataFrame({
            'Open': df['Open'],
            'High': df['High'],
            'Low': df['Low'],
            'Close': df['Close'],
            'Volume': df['Volume']
        }).dropna()

        if len(clean_df) < 450:
            continue

        close_s = clean_df['Close'].astype(float)
        low_s = clean_df['Low'].astype(float)
        high_s = clean_df['High'].astype(float)

        ma112 = close_s.rolling(112).mean()
        ma224 = close_s.rolling(224).mean()
        ma448 = close_s.rolling(448).mean()

        # 정배열 조건 검증 (최근 120일 중 112 > 224 > 448 정배열 순간 존재)
        recent_112 = ma112.iloc[-120:]
        recent_224 = ma224.iloc[-120:]
        recent_448 = ma448.iloc[-120:]

        alignment_6m = (recent_112 > recent_224) & (recent_224 > recent_448)
        if not alignment_6m.any():
            continue

        # 최근 3봉 기준 이평선 지지 여부
        recent_low = low_s.iloc[-3:]
        recent_high = high_s.iloc[-3:]
        recent_ma112 = ma112.iloc[-3:]
        recent_ma224 = ma224.iloc[-3:]
        recent_ma448 = ma448.iloc[-3:]

        curr_price = float(close_s.iloc[-1])
        
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
        print(f"종목 오류 ({symbol}): {e}")
        continue

# 5. 최종 결과 발송
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
