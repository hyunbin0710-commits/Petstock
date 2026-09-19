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

# 3. 데이터 업로드 및 파싱
uploaded_file = st.file_uploader("NH투자증권 거래내역 CSV(엑셀) 파일을 올려주세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # 💡 NameError 방지: 에러가 나더라도 밑에서 쓸 수 있게 빈 리스트를 맨 먼저 만듭니다.
    unregistered_stocks = []
    
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, header=0)
    else:
        df = pd.read_excel(uploaded_file, header=0)
    
    # 컬럼명에 있는 '[merged] ' 글자와 양옆 공백을 지워서 깔끔하게 만듭니다.
    df.columns = [str(col).replace('[merged] ', '').strip() for col in df.columns]
    
    try:
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
        st.info("💡 팁: 다운받으신 엑셀 파일(Petstock.xlsx)을 열어서 맨 위쪽에 있는 쓸데없는 설명(계좌번호, 기간 등) 행을 삭제하고, '실거래일자', '거래유형' 같은 표 머리글이 엑셀의 제일 첫 번째 줄(1행)에 오도록 저장한 뒤 다시 올려주세요!")

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

# 6. UI: 나의 다이어리 앨범 뷰
st.subheader("📖 나의 앨범")
if not db:
    st.write("아직 다이어리에 기록된 주식이 없어요. 파일을 업로드하고 이름을 지어주세요!")
else:
    for uid, data in reversed(list(db.items())):
        st.markdown(f"""
        <div style="background-color:#F9F9F7; padding:20px; border-radius:15px; margin-bottom:15px; border: 1px solid #EAEAEA;">
            <h3 style="margin-top:0px;">{data['emoji']} {data['title']}</h3>
            <p style="color:gray; font-size:14px;">{data['name']} {data['qty']}주 입양일: {data['date']}</p>
            <p style="font-size:16px;"><i>"{data['memo']}"</i></p>
        </div>
        """, unsafe_allow_html=True)
