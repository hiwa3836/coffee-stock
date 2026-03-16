import streamlit as st
from supabase import create_client, Client
import pandas as pd
import requests
import time

# 1. 설정
st.set_page_config(page_title="RCS 재고 관리 시스템", layout="centered")

# 2. 정보 연결 및 세션 관리
try:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    webhook = st.secrets["discord_webhook_url"]
    pw = st.secrets["site_password"]
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Secrets 설정 오류: {e}")
    st.stop()

if "ok" not in st.session_state: st.session_state.ok = False
if "page" not in st.session_state: st.session_state.page = 0

# 3. 로그인 로직
if not st.session_state.ok:
    st.subheader("🔒 RCS 로그인")
    u_name = st.text_input("담당자 성함")
    u_pw = st.text_input("접속 비밀번호", type="password")
    if st.button("접속", use_container_width=True):
        if u_pw == pw and u_name.strip():
            st.session_state.ok = True
            st.session_state.u = u_name.strip()
            st.rerun()
        else:
            st.error("정보가 일치하지 않습니다.")
    st.stop()

# 4. 메인 화면 상단
st.title("☕ RCS 재고 관리")
with st.sidebar:
    st.write(f"👤 담당자: **{st.session_state.u}**")
    if st.button("로그아웃"):
        st.session_state.ok = False
        st.rerun()

try:
    # 데이터 읽기
    res_inv = supabase.table("inventory").select("*").order("item_name").execute()
    df_inv = pd.DataFrame(res_inv.data)

    # --- 재고 수정 섹션 ---
    st.subheader("📊 현재 재고 현황")
    edited_df = st.data_editor(
        df_inv,
        column_config={
            "id": None,
            "item_name": "품목명",
            "current_stock": st.column_config.NumberColumn("수량", format="%d"),
            "unit": "단위",
            "min_stock": None, "last_editor": None, "updated_at": None
        },
        hide_index=True,
        use_container_width=True,
        key="editor"
    )

    if st.button("💾 변경사항 저장하기", use_container_width=True):
        updated = False
        for i, row in edited_df.iterrows():
            old_val = df_inv.iloc[i]['current_stock']
            new_val = row['current_stock']
            
            if old_val != new_val:
                # 1) 재고 업데이트
                supabase.table("inventory").update({
                    "current_stock": new_val,
                    "last_editor": st.session_state.u
                }).eq("item_name", row['item_name']).execute()
                
                # 2) 로그 기록
                supabase.table("logs").insert({
                    "user_name": st.session_state.u,
                    "item_name": row['item_name'],
                    "old_stock": int(old_val),
                    "new_stock": int(new_val)
                }).execute()
                
                # 3) 디스코드 알림
                if new_val <= row['min_stock']:
                    msg = {"content": f"🚨 **{row['item_name']} - {new_val} - {row['unit']}** (부족!)"}
                    requests.post(webhook, json=msg)
                updated = True
        
        if updated:
            st.success("재고가 업데이트되고 로그가 기록되었습니다!")
            time.sleep(1)
            st.rerun()

    # --- 로그 히스토리 섹션 ---
    st.divider()
    st.subheader("🕒 최근 변경 기록")
    
    # 로그 데이터 가져오기 (최신순 75개 = 15개씩 5페이지분량)
    res_log = supabase.table("logs").select("*").order("created_at", desc=True).limit(75).execute()
    df_log = pd.DataFrame(res_log.data)

    if not df_log.empty:
        # 시간 형식 예쁘게 변환
        df_log['created_at'] = pd.to_datetime(df_log['created_at']).dt.strftime('%m-%d %H:%M')
        
        # 페이지네이션 로직 (15개씩 자르기)
        total_logs = len(df_log)
        items_per_page = 15
        max_page = (total_logs - 1) // items_per_page
        
        curr_page = st.session_state.page
        start_idx = curr_page * items_per_page
        end_idx = start_idx + items_per_page
        
        # 테이블 표시
        display_log = df_log.iloc[start_idx:end_idx][['created_at', 'user_name', 'item_name', 'new_stock', 'old_stock']]
        st.table(display_log.rename(columns={
            'created_at': '일시', 'user_name': '담당자', 'item_name': '품목', 
            'new_stock': '변경후', 'old_stock': '변경전'
        }))

        # 페이지 버튼
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ 이전", disabled=(curr_page == 0)):
                st.session_state.page -= 1
                st.rerun()
        with col2:
            st.write(f"Page {curr_page + 1} / {max_page + 1}")
        with col3:
            if st.button("다음 ➡️", disabled=(curr_page >= max_page)):
                st.session_state.page += 1
                st.rerun()
    else:
        st.info("아직 변경 기록이 없습니다.")

except Exception as e:
    st.error(f"오류 발생: {e}")
