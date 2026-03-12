import streamlit as st
import pandas as pd
from bksheets import update_sheet # 이 부분은 다음 단계에서 제가 설명드릴 비밀 도구입니다!

# 1. 시트 ID 입력
SHEET_ID = '1cRbwbRwkG6ssB8B1JSkRP7v6st5g8YYkFAnqw2X-tbo'

st.set_page_config(page_title="在庫管理システム", layout="centered")
st.title("☕ コーヒーサークル 在庫管理")

# --- 데이터 읽기 ---
url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv'
df = pd.read_csv(url)
df.columns = df.columns.str.strip()

# --- 화면 표시 ---
st.subheader("📊 現在の在庫状況")
st.table(df) # 표를 더 깔끔하게 보여줍니다

st.divider()

# --- 재고 조정 ---
st.subheader("📦 在庫を調整する")
selected_item = st.selectbox("品目を選択", df.iloc[:, 0].tolist())
current_qty = df[df.iloc[:, 0] == selected_item].iloc[0, 1]

st.info(f"現在の **{selected_item}** の在庫: **{current_qty}**")

adjustment = st.number_input("変更量 (+입고, -출고)", step=1, value=0)

if st.button("適用 (실제 시트에 저장)"):
    # 나중에 여기에 구글 연동 비번을 넣으면 실시간으로 바뀝니다!
    new_qty = current_qty + adjustment
    st.success(f"✅ {selected_item} 가 {new_qty}로 변경되었습니다!")
    st.balloons()
