import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="在庫管理", layout="centered")
st.title("☕ コーヒーサークル 在庫管理")

# 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 데이터 읽기 (ttl=0으로 설정하면 실시간으로 새로고침됩니다)
    df = conn.read(ttl=0)
    
    # 공백 제거 및 정리
    df.columns = df.columns.str.strip()
    
    st.subheader("📊 現在の在庫状況")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("📦 在庫を調整する")
    
    item_col = df.columns[0] # 첫번째 열 (品目名)
    qty_col = df.columns[1]  # 두번째 열 (現在数量)
    
    items = df[item_col].tolist()
    selected_item = st.selectbox("品目を選択してください", items)

    # [핵심 수정] 가져온 수량을 강제로 숫자로 변환합니다!
    raw_qty = df[df[item_col] == selected_item][qty_col].values[0]
    
    try:
        current_qty = int(raw_qty) # 숫자로 변환 시도
    except:
        current_qty = 0 # 만약 시트가 비어있거나 글자라면 0으로 취급

    st.info(f"현재 **{selected_item}**의 수량: **{current_qty}**")

    # 수량 변경 입력
    diff = st.number_input("변경량 (입고 +, 출고 -)", step=1, value=0)

    if st.button("適用 (시트에 저장)"):
        if diff != 0:
            # 계산 후 저장 (숫자 + 숫자)
            new_qty = current_qty + diff
            df.loc[df[item_col] == selected_item, qty_col] = new_qty
            
            # 구글 시트 업데이트
            conn.update(data=df)
            
            st.success(f"✅ {selected_item} 가 {new_qty}로 업데이트 되었습니다!")
            st.balloons()
            # 2초 뒤 화면 새로고침
            st.rerun()
        else:
            st.warning("변경할 수량을 입력하세요.")

except Exception as e:
    st.error("오류가 발생했습니다!")
    st.write(f"상세 에러: {e}")
