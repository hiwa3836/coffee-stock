import streamlit as st
import pandas as pd

# 1. 여기에 본인의 구글 시트 ID를 입력하세요!
SHEET_ID = '1cRbwbRwkG6ssB8B1JSkRP7v6st5g8YYkFAnqw2X-tbo'
SHEET_NAME = 'Sheet1' 
url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}'

# 페이지 설정
st.set_page_config(page_title="Inventory Management", layout="centered")
st.title("☕ RCS 在庫管理")

# 데이터 불러오기
try:
    df = pd.read_csv(url)
    
    st.subheader("📊 現在の在庫状況 ")
    # 표 디자인 예쁘게 출력
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # 재고 조정 섹션
    st.subheader("📦 在庫を調整する ")
    
    # 품목 선택 박스
    items = df['品目名'].tolist()
    selected_item = st.selectbox("品目を選択してください", items)

    # 현재 해당 품목의 수량 가져오기
    current_qty = df[df['品目名'] == selected_item]['現在數量'].values[0]
    st.info(f"選択した **{selected_item}**の現在の数量は **{current_qty}**です。")

    # 조정 수량 입력
    adjustment = st.number_input("変更する数量 (입고는 +, 출고는 -)", step=1, value=0)
    
    if st.button("適用 "):
        # 실제 시트에 반영하는 코드는 API 연동 단계에서 추가됩니다.
        # 지금은 화면에서만 계산 결과가 나옵니다.
        new_qty = current_qty + adjustment
        st.success(f"✅ {selected_item}の数が {new_qty}で変更されました! (시뮬레이션)")
        st.balloons() # 축하 효과!

except Exception as e:
    st.error("⚠️ 오류 발생! 시트 ID를 확인하거나, 시트 공유 설정이 '편집자'인지 확인해주세요.")
    st.write(e)
