import streamlit as st
import pandas as pd

# 1. 본인의 구글 시트 ID를 입력하세요
SHEET_ID = '1cRbwbRwkG6ssB8B1JSkRP7v6st5g8YYkFAnqw2X-tbo'
SHEET_NAME = 'Sheet1' 
url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}'

# 페이지 설정 (웹 브라우저 탭에 표시될 이름)
st.set_page_config(page_title="在庫管理システム", layout="centered")

# 제목
st.title("☕ コーヒーサークル 在庫管理")

try:
    # 데이터 가져오기 및 공백 제거
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    
    # 현재 재고 현황판
    st.subheader("📊 現在の在庫状況")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # 재고 조정 섹션
    st.subheader("📦 在庫を調整する")
    
    # 첫 번째 열(품목명)과 두 번째 열(수량)을 자동으로 인식
    col_item = df.columns[0]
    col_qty = df.columns[1]

    # 품목 선택
    items = df[col_item].tolist()
    selected_item = st.selectbox("品目を選択してください", items)

    # 현재 수량 표시
    current_qty = df[df[col_item] == selected_item][col_qty].values[0]
    st.info(f"現在の **{selected_item}** の在庫は **{current_qty}** です。")

    # 수량 입력 (입고/출고)
    adjustment = st.number_input(" 변경할 수량을 입력하세요 (입고: +, 출고: -)", step=1, value=0)
    
    if st.button("適用 (적용하기)"):
        # 계산 결과 보여주기
        new_qty = current_qty + adjustment
        st.success(f"✅ {selected_item} の在庫が {new_qty} に更新されました！")
        st.balloons()
        st.warning("⚠️ 注意: 現在は表示のみ更新されています。Googleシートへの保存にはAPI設定が必要です。")

except Exception as e:
    st.error("⚠️ 에러가 발생했습니다! 시트 ID와 공유 설정을 다시 확인해주세요.")
    st.write("Error Detail:", e)
