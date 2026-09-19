import streamlit as st
import pandas as pd
import json
import os
import yfinance as yf

# 1. 페이지 설정
st.set_page_config(page_title="나의 반려주식 다이어리", page_icon="🌱")
st.title("🌱 나의 반려주식 다이어리")
st.caption("딱딱한 주식 계좌를 나만의 추억 앨범으로 만들어보세요.")

# 2. 데이터베이스 설정 (v3로 완전 초기화)
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
                
                # 4. DB와 대조하여 새 주식 찾기
                buys_df = df[df['거래유형'] == '매수'].drop_duplicates(subset=['고유코드'], keep='first')
                
                for index, row in buys_df.iterrows():
                    uid = str(row['고유코드'])
                    if uid not in db:
                        # 💡 숫자 데이터(금액, 수량)의 쉼표(,)를 제거하고 숫자로 변환해서 저장합니다.
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
                    
                    # 💡 티커를 물어보는 조건 명확화
                    known_ticker = ticker_db.get(stock['name'], "")
                    ticker_input = ""
                    if not known_ticker:
                        st.caption("⚠️ 실시간 수익률 계산을 위해 티커를 한 번만 알려주세요! (예: AAPL, 한국주식은 005930.KS)")
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
        
        # 💡 [핵심] 주가 불러오기 방식을 2중 안전장치로 강화합니다.
        error_msg = ""
        if ticker_symbol:
            try:
                ticker_info = yf.Ticker(ticker_symbol)
                try:
                    # 1순위: 가장 빠른 방법 시도
                    current_price = float(ticker_info.fast_info['last_price'])
                except:
                    # 2순위: 실패하면 일반 차트(history) 데이터로 재시도
                    hist = ticker_info.history(period="1d")
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                    else:
                        current_price = 0
            except Exception as e:
                current_price = 0
                error_msg = str(e) # 진짜 에러 원인을 화면에 띄우기 위해 저장
                
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
        
        # 💡 [추가] 통신 에러가 났을 때 빨간 창으로 진짜 이유를 알려줍니다.
        if error_msg:
            st.error(f"야후 파이낸스에서 가격을 가져오지 못했습니다. 에러 원인: {error_msg}")
        
        # 💡 [추가] 언제든지 티커를 고치거나 새로 넣을 수 있는 '톱니바퀴' 메뉴를 엽니다.
        with st.expander(f"⚙️ '{name}' 티커 설정/수정 (현재: {ticker_symbol if ticker_symbol else '없음'})"):
            with st.form(key=f"rescue_{name}"):
                new_ticker = st.text_input("티커 (예: SPLG, 005930.KS)", value=ticker_symbol, key=f"input_{name}")
                if st.form_submit_button("티커 저장/수정"):
                    ticker_db[name] = new_ticker.strip().upper()
                    save_ticker_db(ticker_db)
                    st.rerun()
                    
        for mem in info['memories']:
            st.info(f"{mem['emoji']} **{mem['title']}** ({mem['date']})\n\n\"{mem['memo']}\"")
