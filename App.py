import streamlit as st
import pandas as pd
import json
import os
import requests

# 1. 페이지 설정
st.set_page_config(page_title="나의 반려주식 다이어리", page_icon="🌱")
st.title("🌱 나의 반려주식 다이어리")
st.caption("딱딱한 주식 계좌를 나만의 추억 앨범으로 만들어보세요.")

# --- 🌟 해결사: 네이버증권(Naver Finance) API 연결 ---
def get_current_price(ticker):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    # .KS 등 불필요한 기호 제거 (한국 주식용)
    clean_ticker = ticker.replace('.KS', '').replace('.KQ', '').strip().upper()
    
    # 1. 미국 주식 먼저 찔러보기 (네이버 모바일 해외주식 API)
    us_url = f"https://m.stock.naver.com/front-api/v1/overseas/item/{clean_ticker}/basic"
    try:
        res = requests.get(us_url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get('isSuccess') and data.get('result'):
                price_str = str(data['result'].get('closePrice', '0')).replace(',', '')
                return float(price_str)
    except:
        pass
        
    # 2. 없다면 한국 주식 찔러보기 (네이버 모바일 국내주식 API)
    kr_url = f"https://m.stock.naver.com/api/stock/{clean_ticker}/integration"
    try:
        res = requests.get(kr_url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if 'dealInfo' in data:
                price_str = str(data['dealInfo'].get('closePrice', '0')).replace(',', '')
                return float(price_str)
    except:
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

# 3. 데이터 업로드 및 파싱
uploaded_file = st.file_uploader("NH투자증권 거래내역 CSV(엑셀) 파일을 올려주세요", type=['csv', 'xlsx'])

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
            for i in range(min(20, len(df))):
                row_str = "".join(df.iloc[i].fillna('').astype(str))
                if '거래유형' in row_str or '종목명' in row_str:
                    header_idx = i
                    break
            
            if header_idx != -1:
                df.columns = df.iloc[header_idx]
                df = df[header_idx + 1:].reset_index(drop=True)
                df.columns = [str(col).replace('[merged] ', '').strip() for col in df.columns]
                
                buys_df = df[df['거래유형'] == '매수'].drop_duplicates(subset=['고유코드'], keep='first')
                
                for index, row in buys_df.iterrows():
                    uid = str(row['고유코드'])
                    if uid not in db:
                        qty = float(str(row['수량']).replace(',', ''))
                        raw_price = row.get('거래금액', row.get('정산금액', row.get('매수금액', 0)))
                        total_price = float(str(raw_price).replace(',', ''))
                        
                        unregistered_stocks.append({
                            'uid': uid,
                            'date': row['실거래일자'],
                            'name': row['종목명'],
                            'qty': qty,
                            'total_price': total_price
                        })
    except Exception as e:
        st.error(f"파일을 분석하는 중 에러가 발생했습니다: {e}")

# 5. UI: 새 주식 입양소
if uploaded_file is not None:
    if unregistered_stocks:
        st.subheader("💌 새로운 반려주식이 도착했어요!")
        for stock in unregistered_stocks:
            with st.expander(f"✨ {stock['name']} {stock['qty']:,.2f}주 ({stock['date']})"):
                with st.form(key=f"form_{stock['uid']}"):
                    title = st.text_input("이 주식의 이름을 지어주세요 (예: 첫 월급 기념)")
                    memo = st.text_area("어떤 다짐이나 추억으로 샀나요?")
                    emoji = st.selectbox("오늘의 기분", ["😎", "🥳", "🥺", "🔥", "💸", "🌱"])
                    
                    known_ticker = ticker_db.get(stock['name'], "")
                    ticker_input = ""
                    if not known_ticker:
                        st.caption("⚠️ 실시간 수익률 계산을 위해 티커를 알려주세요! (미국: AAPL, 한국: 005930)")
                        ticker_input = st.text_input("티커/종목코드")
                    
                    submit = st.form_submit_button("도장 찍고 다이어리에 넣기")
                    if submit and title:
                        db[stock['uid']] = {
                            "date": stock['date'],
                            "name": stock['name'],
                            "qty": stock['qty'],
                            "total_price": stock['total_price'],
                            "title": title,
                            "memo": memo,
                            "emoji": emoji
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
                error_msg = "네이버증권에서 가격을 찾지 못했습니다. 티커(종목코드)가 맞는지 확인해주세요."
                
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
                # 네이버 기준이므로 아주 심플하게 입력 가능합니다.
                new_ticker = st.text_input("티커 (미국: SPLG, 한국: 005930)", value=ticker_symbol, key=f"input_{name}")
                if st.form_submit_button("티커 저장/수정"):
                    ticker_db[name] = new_ticker.strip().upper()
                    save_ticker_db(ticker_db)
                    st.rerun()
                    
        for mem in info['memories']:
            st.info(f"{mem['emoji']} **{mem['title']}** ({mem['date']})\n\n\"{mem['memo']}\"")
