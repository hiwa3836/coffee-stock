import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="在庫管理", layout="centered")
st.title("☕ コーヒーサークル 在庫管理")

# 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 데이터 읽기 (Secrets에 설정된 주소 사용)
    df = conn.read()
    
    # 공백 제거 및 첫 행 정리
    df.columns = df.columns.str.strip()
    
    st.subheader("📊 現在の在庫状況")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("📦 在庫を調整する")
    
    # 품목 선택 (첫 번째 열 사용)
    item_col = df.columns[0]
    qty_col = df.columns[1]
    
    items = df[item_col].tolist()
    selected_item = st.selectbox("品目を選択してください", items)

    # 현재 수량 찾기
    current_qty = df[df[item_col] == selected_item][qty_col].values[0]
    st.info(f"現在 **{selected_item}**の数量: **{current_qty}**")

    # 수량 변경
    diff = st.number_input("変更量 (+入, -出)", step=1, value=0)

    if st.button("適用 (시트에 저장)"):
        if diff != 0:
            # 값 변경
            df.loc[df[item_col] == selected_item, qty_col] = current_qty + diff
            # 시트 업데이트
            conn.update(data=df)
            st.success(f"✅ {selected_item} 저장 완료!")
            st.balloons()
            st.rerun() # 화면 새로고침
        else:
            st.warning("変更する数量を入力してください。")

except Exception as e:
    st.error("데이터를 불러올 수 없습니다. 시트가 '세로' 모양인지 확인해주세요!")
    st.write(e)
