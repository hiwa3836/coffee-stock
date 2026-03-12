import streamlit as st
from streamlit_gsheets import GSheetsConnection

# 페이지 설정
st.set_page_config(page_title="在庫管理", layout="centered")
st.title("☕ コーヒーサークル 在庫管理")

# 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 불러오기
# (여기서 시트 URL은 굳이 안넣어도 설정 파일에서 관리할 수 있습니다)
try:
    df = conn.read()
    
    st.subheader("📊 現在の在庫状況")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("📦 在庫を調整する")
    
    selected_item = st.selectbox("品目を選択", df.iloc[:, 0].tolist())
    current_qty = df[df.iloc[:, 0] == selected_item].iloc[0, 1]

    st.info(f"現在の **{selected_item}** の在庫: **{current_qty}**")

    adjustment = st.number_input("変更量 (+入, -出)", step=1, value=0)

    if st.button("適用 (시트에 저장)"):
        # 계산
        new_qty = current_qty + adjustment
        
        # 데이터 업데이트
        df.loc[df.iloc[:, 0] == selected_item, df.columns[1]] = new_qty
        
        # 실제 구글 시트에 업데이트
        conn.update(data=df)
        
        st.success(f"✅ {selected_item} 가 {new_qty}로 변경되어 저장되었습니다!")
        st.balloons()

except Exception as e:
    st.error("연결 설정이 필요합니다. 아래 '통행증' 단계를 진행해주세요!")
