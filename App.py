import streamlit as st
import pandas as pd
import json
import os
import requests
import re
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="나의 반려주식, 펫스톡", page_icon="🪴")
st.title("🪴 나의 반려주식, 펫스톡")

# --- 🌟 야후 파이낸스 직통 연결 (현재가 조회용) ---
def get_current_price(ticker):
    clean_ticker = ticker.strip().upper()
    if clean_ticker.isdigit() and len(clean_ticker) == 6:
        clean_ticker += ".KS"
        
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0'
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

# --- 🌟 증권사 데이터 원본 해독기 ---
def find_col(columns, keywords):
    for col in columns:
        for kw in keywords:
            if kw in str(col):
                return col
    return None

def extract_auto_ticker(code_val):
    code_str = str(code_val).strip()
    
    if code_str.startswith('A') and len(code_str) == 7 and code_str[1:].isdigit():
        return code_str[1:] + ".KS"
        
    isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{9}[0-9])', code_str)
    if isin_match:
        isin = isin_match.group(1)
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={isin}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 200:
                quotes = res.json().get('quotes', [])
                if quotes:
                    return quotes[0]['symbol']
        except:
            pass
            
    if code_str.isdigit() and len(code_str) == 6:
        return code_str + ".KS"
        
    if re.match(r'^[A-Z]+$', code_str) and len(code_str) <= 5:
        return code_str
        
    return ""

# 3. 데이터 업로드 및 파싱
st.markdown("### 💌 엑셀 업로드")
uploaded_file = st.file_uploader("증권사 거래내역 CSV(엑셀) 파일을 올려주세요", type=['csv', 'xlsx'])

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
                        
                        auto_ticker = extract_auto_ticker(row[col_code]) if col_code else ""
                        
                        unregistered_stocks.append({
                            'uid': uid,
                            'date': row[col_date] if col_date else '날짜 미상',
                            'name': row[col_name] if col_name else '알 수 없는 종목',
                            'qty': qty,
                            'total_price': total_price,
                            'auto_ticker': auto_ticker
                        })
    except Exception as e:
        st.error(f"파일 분석 중 에러가 발생했습니다: {e}")

# 5. UI: 새 주식 입양소
if uploaded_file is not None:
    if unregistered_stocks:
        st.subheader("📬 새로운 반려주식이 도착했어요!")
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
                            st.success(f"🤖 종목 코드를 추적하여 티커가 [{auto_ticker}]임을 알아냈습니다.")
                            ticker_input = st.text_input("티커 (자동 인식됨)", value=auto_ticker)
                        else:
                            st.caption("⚠️ 국제표준코드가 없어 자동 인식에 실패했습니다. 직접 알려주세요!")
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
    st.write("아직 다이어리에 기록된 주식이 없어요. 엑셀을 업로드하고 이름을 지어주세요!")
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
        
        date_objects = []
        for mem in info['memories']:
            try:
                dt_str = mem['date'].replace('.', '-').strip()
                dt = datetime.strptime(dt_str, '%Y-%m-%d').date()
                date_objects.append(dt)
            except:
                pass
                
        if date_objects:
            first_date = min(date_objects)
            today = datetime.now().date()
            days_together = (today - first_date).days + 1
            if days_together < 1: days_together = 1
            days_text = f"함께한 지 {days_together}일째 💖"
        else:
            days_text = "함께한 지 1일째 💖"
        
        if ticker_symbol:
            current_price = get_current_price(ticker_symbol)
            if current_price == 0:
                error_msg = "가격을 불러오지 못했습니다. 티커가 정확한지 확인해주세요."
                
        # 💡 [핵심] 불필요한 감성 텍스트를 제거하고 심플하게 %만 표시
        if current_price > 0 and avg_price > 0:
            return_rate = ((current_price - avg_price) / avg_price) * 100
            if return_rate > 0:
                mood_html = f'<span style="font-size:20px;">🥰</span> <span style="color:#FF7B7B; font-weight:bold; font-size:15px; margin-left:5px;">+{return_rate:.1f}%</span>'
                point_color = "#FF9AA2"
            elif return_rate < 0:
                mood_html = f'<span style="font-size:20px;">😭</span> <span style="color:#6B90D8; font-weight:bold; font-size:15px; margin-left:5px;">{return_rate:.1f}%</span>'
                point_color = "#A2C2FF"
            else:
                mood_html = f'<span style="font-size:20px;">🤔</span> <span style="color:#888888; font-weight:bold; font-size:15px; margin-left:5px;">0.0%</span>'
                point_color = "#EAEAEA"
        else:
            mood_html = '<span style="font-size:20px;">💤</span> <span style="color:#888888; font-weight:bold; font-size:15px; margin-left:5px;">-</span>'
            point_color = "#EAEAEA"
            
        memories_html = ""
        for mem in info['memories']:
            title = mem.get('title', '')
            date = mem.get('date', '')
            memo = mem.get('memo', '')
            memories_html += f'<div style="background-color:#FFFFFF; padding:15px; border-radius:12px; margin-top:12px; border-left: 5px solid {point_color}; box-shadow: 0 2px 5px rgba(0,0,0,0.02);"><div style="font-size:14px; color:#4A4A4A; font-weight:bold;">{title} <span style="font-size:12px; color:#A0A0A0; font-weight:normal; margin-left:8px;">{date}</span></div><div style="font-size:14px; color:#666666; margin-top:8px; line-height:1.6; font-style:italic;">"{memo}"</div></div>'
            
        html_card = f"""<div style="background-color:#FAF8F5; padding:25px; border-radius:20px; margin-bottom:25px; box-shadow:0px 4px 10px rgba(0,0,0,0.05); border:1px solid #EFEBE4;"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;"><h3 style="margin:0; color:#5C4B4B; font-size:22px;">🪴 {name}</h3><div style="background-color:#FFEAEA; color:#D86B6B; padding:6px 14px; border-radius:20px; font-size:13px; font-weight:bold;">{days_text}</div></div><div style="color:#6D6060; font-size:15px; margin-bottom:20px; line-height:1.8;"><b>보유 수량:</b> {info['total_qty']:,.2f}주 <br><b>평단가:</b> {avg_price:,.2f} <span style="margin: 0 10px; color:#D5D5D5;">|</span> <b>현재가:</b> {current_price:,.2f} <br><div style="margin-top:12px; padding:10px 15px; background-color:#FFFFFF; border-radius:12px; display:inline-block; border:1px dashed #E5E0D8;"><b>오늘의 기분:</b> {mood_html}</div></div><div style="border-top:2px dashed #EFEBE4; padding-top:15px;">{memories_html}</div></div>"""
        
        st.markdown(html_card, unsafe_allow_html=True)
        
        if error_msg and ticker_symbol:
            st.error(f"⚠️ 현재가 업데이트 실패: {error_msg}")
        
        # 💡 [핵심] 설정 메뉴 안에 티커 변경뿐만 아니라 '기록(이름, 메모) 수정' 기능을 추가했습니다.
        with st.expander(f"⚙️ '{name}' 설정 (티커 및 기록 수정)"):
            st.markdown("**1. 티커(종목코드) 수정**")
            with st.form(key=f"rescue_{name}"):
                new_ticker = st.text_input("수동 변경", value=ticker_symbol, key=f"input_{name}")
                if st.form_submit_button("티커 저장"):
                    ticker_db[name] = new_ticker.strip().upper()
                    save_ticker_db(ticker_db)
                    st.rerun()
            
            st.markdown("---")
            st.markdown("**2. 내 기록 수정**")
            # 현재 종목에 해당하는 기록(메모)들만 모아서 수정 폼을 제공합니다.
            for uid_key, data_val in db.items():
                if data_val['name'] == name:
                    with st.form(key=f"edit_{uid_key}"):
                        st.caption(f"📅 매수일: {data_val['date']} | 💰 수량: {data_val['qty']}주")
                        new_title = st.text_input("이름 (타이틀)", value=data_val.get('title', ''))
                        new_memo = st.text_area("추억/다짐 (메모)", value=data_val.get('memo', ''))
                        if st.form_submit_button("기록 수정 저장"):
                            db[uid_key]['title'] = new_title
                            db[uid_key]['memo'] = new_memo
                            save_db(db)
                            st.rerun()
