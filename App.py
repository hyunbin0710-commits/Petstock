import streamlit as st
import pandas as pd
import json
import os

# 1. 내 추억을 저장할 로컬 DB 파일 설정
DB_FILE = 'my_stock_diary.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()

# 2. UI 기본 설정
st.set_page_config(page_title="나의 반려주식 다이어리 펫스톡", page_icon="🌱", layout="centered")
st.title("🌱 나의 반려주식 다이어리")
st.markdown("딱딱한 주식 계좌를 나만의 추억 앨범으로 만들어보세요.")

# 3. 데이터 업로드 및 파싱 (표 자동 인식 및 빈 파일 방어 기능 추가)
uploaded_file = st.file_uploader("NH투자증권 거래내역 CSV(엑셀) 파일을 올려주세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    unregistered_stocks = []
    
    try:
        # 파일 형식에 맞춰 전체 데이터를 불러옵니다.
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=None)
        else:
            # 엑셀은 다중 시트일 가능성이 있어 명확히 첫 번째 시트를 가져옵니다.
            xls = pd.ExcelFile(uploaded_file)
            df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)
        
        # 데이터가 텅 비어있는지 확인하는 안전장치
        if len(df) == 0:
            st.error("업로드하신 파일에 데이터가 없습니다. 빈 파일이 아닌지 확인해 주세요.")
        else:
            # 위에서부터 15줄을 뒤져서 '거래유형'이나 '종목명'이 있는 줄을 찾습니다.
            header_idx = 0
            for i in range(min(15, len(df))):
                row_str = "".join(df.iloc[i].fillna('').astype(str))
                if '거래유형' in row_str or '종목명' in row_str:
                    header_idx = i
                    break
                    
            # 찾아낸 진짜 줄을 기둥 이름(컬럼)으로 만들고, 그 윗줄들은 날려버립니다.
            df.columns = df.iloc[header_idx]
            df = df[header_idx + 1:].reset_index(drop=True)
            
            # 이름에 묻어있는 '[merged] ' 글자와 양옆 공백을 깔끔하게 제거합니다.
            df.columns = [str(col).replace('[merged] ', '').strip() for col in df.columns]
            
            # 4. DB와 대조하여 새 주식 찾기
            buys_df = df[df['거래유형'] == '매수'].drop_duplicates(subset=['고유코드'], keep='first')
            
            for index, row in buys_df.iterrows():
                uid = str(row['고유코드'])
                if uid not in db:
                    unregistered_stocks.append({
                        'uid': uid,
                        'date': row['실거래일자'],
                        'name': row['종목명'],
                        'qty': row['수량'],
                        'total_price': row.get('거래금액', row.get('정산금액', 0))
                    })
                    
    except KeyError as e:
        st.error(f"엑셀 파일에서 {e} 기둥을 찾을 수 없습니다.")
        st.warning(f"현재 파이썬이 읽어낸 기둥 이름들: {df.columns.tolist()}")
    except Exception as e:
        st.error(f"파일을 분석하는 중 에러가 발생했습니다: {e}")
        
# 5. UI: 새 주식 입양소 (이름 지어주기)
if uploaded_file is not None:
    if unregistered_stocks:
        st.subheader("💌 새로운 반려주식이 도착했어요!")
        for stock in unregistered_stocks:
            with st.expander(f"✨ {stock['name']} {stock['qty']}주 ({stock['date']})"):
                with st.form(key=f"form_{stock['uid']}"):
                    title = st.text_input("이 주식의 이름을 지어주세요 (예: 첫 월급 기념)")
                    memo = st.text_area("어떤 다짐이나 추억으로 샀나요?")
                    emoji = st.selectbox("오늘의 기분", ["😎", "🥳", "🥺", "🔥", "💸", "🌱"])
                    
                    submit = st.form_submit_button("도장 찍고 다이어리에 넣기")
                    if submit and title:
                        db[stock['uid']] = {
                            "date": stock['date'],
                            "name": stock['name'],
                            "qty": stock['qty'],
                            "title": title,
                            "memo": memo,
                            "emoji": emoji
                        }
                        save_db(db)
                        st.success("저장되었습니다! 새로고침을 눌러주세요.")
                        st.rerun()
    else:
        st.info("새로 이름 지어줄 주식이 없습니다. 앨범을 확인해보세요!")

st.divider()

# 6. UI: 나의 반려주식 도감 뷰 (종목별 그룹화)
st.subheader("📖 나의 반려주식 도감")

if not db:
    st.write("아직 다이어리에 기록된 주식이 없어요. 파일을 업로드하고 이름을 지어주세요!")
else:
    # 1. DB의 데이터를 '종목명' 기준으로 하나로 묶습니다.
    portfolio = {}
    for uid, data in db.items():
        name = data['name']
        qty = float(data.get('qty', 0))
        # 금액 데이터에 콤마가 있을 경우를 대비한 안전한 정수 변환
        total_price = float(str(data.get('total_price', 0)).replace(',', ''))
        
        if name not in portfolio:
            portfolio[name] = {'total_qty': 0, 'total_invested': 0, 'memories': []}
            
        portfolio[name]['total_qty'] += qty
        portfolio[name]['total_invested'] += total_price
        portfolio[name]['memories'].append(data)
        
    # 2. 묶인 종목들을 화면에 예쁘게 출력합니다.
    for name, info in portfolio.items():
        # 평단가 계산 (총 투자금액 / 총 수량)
        avg_price = info['total_invested'] / info['total_qty'] if info['total_qty'] > 0 else 0
        
        # 💡 [핵심] 현재가와 등락률 (현재는 UI 시연을 위해 임시 계산식을 넣습니다)
        current_price = avg_price * 1.05 # 임시로 5% 성장했다고 가정
        return_rate = ((current_price - avg_price) / avg_price) * 100
        
        # 카드 디자인 렌더링
        st.markdown(f"""
        <div style="background-color:#ffffff; padding:20px; border-radius:15px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="margin-top:0px; color:#1E1E1E;">🌱 {name}</h3>
            <p style="font-size:16px; color:#555;">
                <b>보유 수량:</b> {info['total_qty']:,.2f}주 &nbsp;|&nbsp; 
                <b>평단가:</b> {avg_price:,.0f}원 &nbsp;|&nbsp; 
                <b>현재 수익률:</b> <span style="color:#FF4B4B; font-weight:bold;">+{return_rate:.1f}%</span>
            </p>
            <hr style="border:1px solid #EAEAEA;">
            <p style="font-size:14px; color:#888; margin-bottom:5px;">나의 입양 기록 📝</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 해당 종목에 달아둔 매수 메모들을 시간순으로 보여줍니다.
        for mem in info['memories']:
            st.info(f"{mem['emoji']} **{mem['title']}** ({mem['date']})\n\n\"{mem['memo']}\"")
