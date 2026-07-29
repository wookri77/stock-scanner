import os
import requests
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import mplfinance as mpf

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram Msg Error: {e}")

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": photo}, timeout=20)
    except Exception as e:
        print(f"Telegram Photo Error: {e}")

# ==========================================
# 스캔 대상 종목 리스트 (축소 절대 없음)
# ==========================================
STOCK_MARKETS = {
    # --- [국내주식: 코스피/코스닥 주요 개별주] ---
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "068270.KS": "셀트리온",
    "207940.KS": "삼성바이오로직스",
    "005935.KS": "삼성전자우",
    "006400.KS": "삼성SDI",
    "051910.KS": "LG화학",
    "373220.KS": "LG에너지솔루션",
    "003550.KS": "LG",
    "015760.KS": "한국전력",
    "032830.KS": "삼성생명",
    "012330.KS": "현대모비스",
    "055550.KS": "신한지주",
    "105560.KS": "KB금융",
    "086790.KS": "하나금융지주",
    "010140.KS": "삼성중공업",
    "009540.KS": "HD한국조선해양",
    "011200.KS": "HMM",
    "034020.KS": "두산에너빌리티",
    "010950.KS": "S-Oil",
    "036570.KS": "엔씨소프트",
    "251270.KS": "넷마블",
    "259960.KS": "크래프톤",
    "247540.KQ": "에코프로비엠",
    "086520.KQ": "에코프로",
    "091990.KQ": "셀트리온제약",
    "293490.KQ": "카카오게임즈",
    "112040.KQ": "위메이드",
    "035900.KQ": "JYP Ent.",
    "122870.KQ": "와이지엔터테인먼트",
    "352820.KS": "하이브",

    # --- [미국주식: Big Tech / AI / 반도체 개별주] ---
    "NVDA": "엔비디아 (NVIDIA)",
    "AAPL": "애플 (Apple)",
    "MSFT": "마이크로소프트 (Microsoft)",
    "AMZN": "아마존 (Amazon)",
    "GOOGL": "구글 (Alphabet)",
    "TSLA": "테슬라 (Tesla)",
    "META": "메타 (Meta)",
    "AMD": "AMD",
    "AVGO": "브로드컴 (Broadcom)",
    "QCOM": "퀄컴 (Qualcomm)",
    "INTC": "인텔 (Intel)",
    "PLTR": "팔란티어 (Palantir)",
    "ARM": "ARM 홀딩스",
    "SMCI": "슈퍼마이크로컴퓨터",
    "ASML": "ASML",
    "TSM": "TSMC",
    "MU": "마이크론 (Micron)",
    "AMAT": "어플라이드 머티리얼즈",
    "LRCX": "렘리서치",
    "ORCL": "오라클 (Oracle)",
    "IBM": "IBM",
    "ADBE": "어도비 (Adobe)",
    "CRM": "세일즈포스 (Salesforce)",
    "NOW": "서비스나우 (ServiceNow)",
    "CSCO": "시스코 (Cisco)",

    # --- [미국주식: 성장주 / 플랫폼 / 전기차 개별주] ---
    "RBLX": "로블록스 (Roblox)",
    "SNOW": "스노우플레이크 (Snowflake)",
    "U": "유니티 (Unity)",
    "SHOP": "쇼피파이 (Shopify)",
    "SQ": "블록 (Block/Square)",
    "PYPL": "페이팔 (PayPal)",
    "COIN": "코인베이스 (Coinbase)",
    "HOOD": "로빈후드 (Robinhood)",
    "MSTR": "마이크로스트래티지",
    "RIVN": "리비안 (Rivian)",
    "LCID": "루시드 (Lucid)",
    "NIO": "니오 (NIO)",
    "XPEV": "샤오펑 (XPeng)",

    # --- [미국주식: 소비재 / 엔터 / 산업 / 방산 개별주] ---
    "NFLX": "넷플릭스 (Netflix)",
    "DIS": "디즈니 (Disney)",
    "SBUX": "스타벅스 (Starbucks)",
    "NKE": "나이키 (Nike)",
    "COST": "코스트코 (Costco)",
    "WMT": "월마트 (Walmart)",
    "TGT": "타겟 (Target)",
    "MCD": "맥도날드 (McDonald's)",
    "KO": "코카콜라 (Coca-Cola)",
    "PEP": "펩시코 (PepsiCo)",
    "ABNB": "에어비앤비 (Airbnb)",
    "BKNG": "부킹홀딩스",
    "LMT": "록히드마틴 (Lockheed Martin)",
    "RTX": "RTX (레이시온)",
    "BA": "보잉 (Boeing)",
    "CAT": "캐터필러 (Caterpillar)",
    "GE": "GE 에어로스페이스",
    "XOM": "엑슨모빌 (Exxon Mobil)",
    "CVX": "쉐브론 (Chevron)",

    # --- [미국주식: 금융 / 헬스케어 / 제약 개별주] ---
    "JPM": "JP모건 체이스",
    "BAC": "뱅크오브아메리카",
    "MS": "모건스탠리",
    "GS": "골드만삭스",
    "V": "비자 (Visa)",
    "MA": "마스터카드 (Mastercard)",
    "LLY": "일라이릴리 (Eli Lilly)",
    "NVO": "노보노디스크 (Novo Nordisk)",
    "PFE": "화이자 (Pfizer)",
    "JNJ": "존슨앤드존슨",
    "UNH": "유나이티드헬스",
    "MRNA": "모더나 (Moderna)"
}

def main():
    send_telegram_msg("🚀 *[주식 이평선 스캐너]* 스캔을 시작합니다.")
    matched_count = 0
    
    for ticker, name in STOCK_MARKETS.items():
        try:
            df = yf.download(ticker, period="2y", progress=False)
            if df is None or df.empty or len(df) < 224:
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            if len(df) < 224:
                continue

            close_s = df['Close'].astype(float)
            high_s = df['High'].astype(float)
            low_s = df['Low'].astype(float)

            ma112 = close_s.rolling(112).mean()
            ma224 = close_s.rolling(224).mean()
            ma448 = close_s.rolling(448).mean()

            # 1) 최근 지지 체크 (112선/224선/448선)
            recent_low = low_s.iloc[-5:]
            recent_high = high_s.iloc[-5:]
            curr_price = float(close_s.iloc[-1])

            is_us_stock = not (ticker.endswith(".KS") or ticker.endswith(".KQ"))
            unit_str = "$" if is_us_stock else "원"
            price_fmt = f"{curr_price:,.2f}" if is_us_stock else f"{curr_price:,.0f}"

            lines = [("112일선 지지", ma112), ("224일선 지지", ma224)]
            if len(df) >= 448:
                lines.append(("448일선 지지", ma448))

            for line_name, ma_series in lines:
                recent_ma = ma_series.iloc[-5:]
                # 여유 있는 범위(±2.5%)로 지지 여부 탐지
                touch_condition = (recent_low <= recent_ma * 1.025) & (recent_high >= recent_ma * 0.975)
                
                if touch_condition.any():
                    val = float(ma_series.iloc[-1])
                    val_fmt = f"{val:,.2f}" if is_us_stock else f"{val:,.0f}"
                    
                    msg = f"⚡ *[{name}({ticker})]* {line_name}\n• 현재가: `{price_fmt}{unit_str}` | 이평선: `{val_fmt}{unit_str}`"
                    matched_count += 1

                    # 차트 생성 및 전송
                    chart_df = df.tail(150).copy()
                    chart_df['MA112'] = ma112.tail(150)
                    chart_df['MA224'] = ma224.tail(150)
                    if len(df) >= 448:
                        chart_df['MA448'] = ma448.tail(150)

                    add_plots = [
                        mpf.makeaddplot(chart_df['MA112'], color='blue', width=1.5),
                        mpf.makeaddplot(chart_df['MA224'], color='orange', width=1.5)
                    ]
                    if len(df) >= 448:
                        add_plots.append(mpf.makeaddplot(chart_df['MA448'], color='red', width=1.5))

                    filename = f"stock_{ticker.replace('.', '_')}.png"
                    mpf.plot(chart_df, type='candle', style='charles', addplot=add_plots, 
                             savefig=filename, volume=False, title=f"\n{name} ({ticker})")
                    
                    send_telegram_photo(filename, caption=msg)
                    if os.path.exists(filename): 
                        os.remove(filename)
                    break
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            continue

    send_telegram_msg(f"🏁 *[주식 스캐너]* 스캔 완료! (발견된 종목: {matched_count}개)")

if __name__ == "__main__":
    main()
