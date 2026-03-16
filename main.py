import streamlit as st
from supabase import create_client, Client
import pandas as pd
import requests

# 1. 설정
st.set_page_config(page_title="RCS", layout="centered")

# 2. 정보 연결
try:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    webhook = st.secrets["discord_webhook_url"]
    pw = st.secrets["site_password"]
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Secrets 설정 오류: {e}")
    st.stop()

# 3. 로그인 로직
if "ok" not in st.session_state: st.session_state.ok = False

if not st.session_state.ok:
    st.subheader("🔒 로그인")
    u_name = st.text_input("이름")
    u_pw = st.text_input("비번", type="password")
    if st.button("접속"):
        if u_pw == pw and u_name:
            st.session_state.ok = True
            st.session_state.u = u_name
            st.rerun()
    st.stop()

# 4. 메인 화면
st.title("☕ RCS 재고 관리")

try:
    # 데이터 읽기
    res = supabase.table("inventory").select("*").order("item_name").execute()
    df = pd.DataFrame(res.data)

    # 수정 화면
    edit_df = st.data_editor(
        df,
        column_config={
            "id": None, 
            "item_name": "품목명",
            "current_stock": st.column_config.NumberColumn("수량"),
            "unit": "단위"
        },
        hide_index=True
    )

    if st.button("저장하기"):
        for i, row in edit_df.iterrows():
            if row['current_stock'] != df.iloc[i]['current_stock']:
                # DB 업데이트
                supabase.table("inventory").update({
                    "current_stock": row['current_stock'],
                    "last_editor": st.session_state.u
                }).eq("item_name", row['item_name']).execute()
                
                # 알림 체크 (기준 이하면 전송)
                if row['current_stock'] <= row['min_stock']:
                    msg = {"content": f"🚨 **{row['item_name']}** 부족! 현재: {row['current_stock']}{row['unit']}"}
                    requests.post(webhook, json=msg)
        
        st.success("완료!")
        st.rerun()

except Exception as e:
    st.error(f"오류: {e}")
