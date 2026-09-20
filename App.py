import streamlit as st
import pandas as pd
import json
import os
import requests
import re

# 1. 페이지 설정
st.set_page_config(page_title="나의 반려주식 다이어리", page_icon="🌱")
st.title("🌱 나의 반려주식 다이어리")
st.caption("딱딱한 주식 계좌를 나만의 추억 앨범으로 만들어보세요.")

# --- 🌟 증권사별 종목명 ➔ 티커 자동 번역 사전 ---
# 사용자가 선택한 증권사에 따라 엑셀의 한글 종목명을 실제 티커로 번역합니다.
AUTO_TICKER_MAP = {
    "NH투자증권": {
        "SPDR S&P500 포트폴리오 ETF": "SPYM",
        "INVESCO QQQ TRUST SRS 1 ETF": "QQQ",
        "애플": "AAPL",
        "테슬라": "TSLA",
        "엔비디아": "NVDA",
        "마이크로소프트": "MSFT",
        "알파벳 A": "GOOGL",
        "삼성전자": "005930",
        "SK하이닉스": "000660"
    },
    "키움증권": {
        "SPDR S&P 500 ETF TRUST": "SPY",
        "애플": "AAPL",
        "테슬라": "TSLA",
        "삼성전자": "005930"
    },
    "토스증권": {
        "Apple": "AAPL",
        "Tesla": "TSLA",
        "삼성전자": "005930"
    }
}

# --- 🌟 야후 파이낸스 직통 연결 ---
def get_current_price(ticker):
    clean_ticker = ticker.strip().upper()
    if clean_ticker.isdigit() and len(clean_ticker) == 6:
        clean_ticker += ".KS"
        
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
    except Exception:
        pass
    return 0

# 2. 데이터베이스 설정
DB_FILE = 'my_stock_diary_v3.json'
TICKER_FILE = 'ticker_db_v3.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_ticker_db():
    if os.path.exists(TICKER_FILE):
        with open(TICKER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_ticker_db(data):
    with open(TICKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()
ticker_db = load_ticker_db()

# --- 🌟 스마트 컬럼 탐색기 ---
def find_col(columns, keywords):
    for col in columns:
        for kw in keywords:
            if kw in str(col):
                return col
    return None

def extract_auto_ticker(code_val):
    code_str = str(code_val).strip()
    if code_str.startswith('A') and len(code_str) == 7 and code_str[1:].isdigit():
        return code_str[1:]
    if re.match(r'^[A-Z0-9]+$', code_str) and len(code_str) <= 6:
        return code_str
    return ""

# 3. 데이터 업로드 및 파싱
st.markdown("### 📥 엑셀 업로드")
broker = st.selectbox("이용 중인 증권사를 선택해주세요 (자동 인식에 사용됩니다)", ["NH투자증권", "키움증권", "토스증권", "기타 증권사"])
uploaded_file = st.file_uploader(f"{broker} 거래내역 CSV(엑셀) 파일을 올려주세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    unregistered_stocks = []
    df = None
    
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=None)
        else:
            xls = pd.ExcelFile(uploaded_file)
            for sheet in xls.sheet_names:
                temp_df = pd.read_excel(xls, sheet_name=sheet, header=None)
                if len(temp_df) > 0:
                    df = temp_df
                    break
        
        if df is not None and len(df) > 0:
            header_idx = -1
            for i in range(min(30, len(df))):
                row_str = "".join(df.iloc[i].fillna('').astype(str))
                if '종목' in row_str or '수량' in row_str:
                    header_idx = i
                    break
            
            if header_idx != -1:
                df.columns = df.iloc[header_idx]
                df = df[header_idx + 1:].reset_index(drop=True)
                df.columns = [str(col).replace('[merged] ', '').strip() for col in df.columns]
                
                col_type = find_col(df.columns, ['거래유형', '매매구분', '구분', '종류'])
                col_code = find_col(df.columns, ['고유코드', '종목코드', '단축코드'])
                col_date = find_col(df.columns, ['실거래일자', '체결일', '거래일', '일자'])
                col_name = find_col(df.columns, ['종목명', '종목이름', '종목'])
                col_qty = find_col(df.columns, ['수량', '체결수량'])
                col_price = find_col(df.columns, ['거래금액', '정산금액', '약정금액', '매수금액'])
                
                if col_type:
                    buys_df = df[df[col_type].astype(str).str.contains('매수')].copy()
                else:
                    buys_df = df.copy()
                
                if col_code:
                    buys_df = buys_df.drop_duplicates(subset=[col_code], keep='first')
                
                for index, row in buys_df.iterrows():
                    uid = str(row[col_code]) if col_code else str(row[col_name])
                    
                    if uid not in db:
                        qty = float(str(row[col_qty]).replace(',', '')) if col_qty else 0
                        total_price = float(str(row[col_price]).replace(',', '')) if col_price else 0
                        
                        stock_name = str(row[col_name]).strip() if col_name else ""
                        auto_ticker = ""
                        
                        # 💡 1순위: 증권사별 번역 사전에서 종목명으로 티커 찾기
                        if broker in AUTO_TICKER_MAP and stock_name in AUTO_TICKER_MAP[broker]:
                            auto_ticker = AUTO_TICKER_MAP[broker][stock_name]
                        else:
                            # 💡 2순위: 엑셀 고유코드 규칙으로 티커 찾기
                            auto_ticker = extract_auto_ticker(row[col_code]) if col_code else ""
                        
                        unregistered_stocks.append({
                            'uid': uid,
                            'date': row[col_date] if col_date else '날짜 미상',
                            'name': stock_name,
                            'qty': qty,
                            'total_price': total_price,
                            'auto_ticker': auto_ticker
                        })
    except Exception as e:
        st.error(f"파일 분석 중 에러가 발생했습니다: {e}")

# 5. UI: 새 주식 입양소
if uploaded_file is not None:
    if unregistered_stocks:
        st.subheader("💌 새로운 반려주식이 도착했어요!")
        for stock in unregistered_stocks:
            with st.expander(f"✨ {stock['name']} {stock['qty']:,.2f}주 ({stock['date']})"):
                with st.form(key=f"form_{stock['uid']}"):
                    title = st.text_input("이 주식의 이름을 지어주세요 (예: 첫 월급 기념)")
                    memo = st.text_area("어떤 다짐이나 추억으로 샀나요?")
                    
                    known_ticker = ticker_db.get(stock['name'], "")
                    auto_ticker = stock.get('auto_ticker', '')
                    ticker_input = ""
                    
                    if not known_ticker:
                        if auto_ticker:
                            # 💡 앱이 사전을 통해 티커를 알아채면, 사용자에게 칭찬(?)을 받으며 자동으로 채워 넣습니다.
                            st.success(f"🤖 {broker} 분석 완료: '{stock['name']}'의 티커는 [{auto_ticker}]입니다!")
                            ticker_input = st.text_input("티커 (자동 인식됨)", value=auto_ticker)
                        else:
                            st.caption("⚠️ 티커 자동 인식에 실패했습니다. 직접 알려주세요!")
                            ticker_input = st.text_input("티커/종목코드")
                    
                    submit = st.form_submit_button("도장 찍고 다이어리에 넣기")
                    if submit and title:
                        db[stock['uid']] = {
                            "date": stock['date'],
                            "name": stock['name'],
                            "qty": stock['qty'],
                            "total_price": stock['total_price'],
                            "title": title,
                            "memo": memo
                        }
                        save_db(db)
                        
                        if not known_ticker and ticker_input:
                            ticker_db[stock['name']] = ticker_input.strip().upper()
                            save_ticker_db(ticker_db)
                            
                        st.success("저장되었습니다! 새로고침을 눌러주세요.")
                        st.rerun()
    else:
        st.info("새로 이름 지어줄 주식이 없습니다. 앨범을 확인해보세요!")

# 6. UI: 나의 반려주식 도감 뷰
st.subheader("📖 나의 반려주식 도감")

if not db:
    st.write("아직 다이어리에 기록된 주식이 없어요. 파일을 업로드하고 이름을 지어주세요!")
else:
    portfolio = {}
    for uid, data in db.items():
        name = data['name']
        qty = float(data.get('qty', 0))
        total_price = float(data.get('total_price', 0))
        
        if name not in portfolio:
            portfolio[name] = {'total_qty': 0, 'total_invested': 0, 'memories': []}
            
        portfolio[name]['total_qty'] += qty
        portfolio[name]['total_invested'] += total_price
        portfolio[name]['memories'].append(data)
        
    for name, info in portfolio.items():
        avg_price = info['total_invested'] / info['total_qty'] if info['total_qty'] > 0 else 0
        current_price = 0
        ticker_symbol = ticker_db.get(name, "")
        error_msg = ""
        
        if ticker_symbol:
            current_price = get_current_price(ticker_symbol)
            if current_price == 0:
                error_msg = "가격을 불러오지 못했습니다. 티커가 정확한지 확인해주세요."
                
        if current_price > 0 and avg_price > 0:
            return_rate = ((current_price - avg_price) / avg_price) * 100
            color = "#FF4B4B" if return_rate > 0 else "#4B4BFF"
            sign = "+" if return_rate > 0 else ""
            price_text = f"{current_price:,.2f}"
            return_text = f"<span style='color:{color}; font-weight:bold;'>{sign}{return_rate:.1f}%</span>"
        else:
            price_text = "조회 불가"
            return_text = f"<span style='color:gray; font-size:12px;'>(현재 등록된 티커: {ticker_symbol if ticker_symbol else '없음'})</span>"
            
        st.markdown(f"""
        <div style="background-color:#ffffff; padding:20px; border-radius:15px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="margin-top:0px; color:#1E1E1E;">🌱 {name}</h3>
            <p style="font-size:16px; color:#555;">
                <b>보유 수량:</b> {info['total_qty']:,.2f}주 &nbsp;|&nbsp; 
                <b>평단가:</b> {avg_price:,.2f} &nbsp;|&nbsp; 
                <b>현재가:</b> {price_text} &nbsp;|&nbsp; 
                <b>수익률:</b> {return_text}
            </p>
            <hr style="border:1px solid #EAEAEA;">
            <p style="font-size:14px; color:#888; margin-bottom:5px;">나의 입양 기록 📝</p>
        </div>
        """, unsafe_allow_html=True)
        
        if error_msg and ticker_symbol:
            st.error(f"⚠️ 현재가 업데이트 실패: {error_msg}")
        
        with st.expander(f"⚙️ '{name}' 티커 설정/수정 (현재: {ticker_symbol if ticker_symbol else '없음'})"):
            with st.form(key=f"rescue_{name}"):
                new_ticker = st.text_input("수동 변경 (자동 인식 오류 시 사용)", value=ticker_symbol, key=f"input_{name}")
                if st.form_submit_button("티커 저장/수정"):
                    ticker_db[name] = new_ticker.strip().upper()
                    save_ticker_db(ticker_db)
                    st.rerun()
                    
        for mem in info['memories']:
            st.info(f"**{mem['title']}** ({mem['date']})\n\n\"{mem['memo']}\"")
