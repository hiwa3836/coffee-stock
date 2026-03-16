import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import time
import requests

# =========================
# 1. ページ設定
# =========================
st.set_page_config(page_title="RCS 在庫管理 (Supabase)", layout="centered")

# =========================
# 2. Secrets / 接続 (본인 정보로 수정 필요)
# =========================
# Streamlit Cloud의 Settings -> Secrets에 저장하거나 직접 입력하세요.
try:
    SUPABASE_URL = st.secrets["supabase_url"]
    SUPABASE_KEY = st.secrets["supabase_key"]
    DISCORD_WEBHOOK_URL = st.secrets["discord_webhook_url"]
    SITE_PASSWORD = st.secrets["site_password"]
except Exception:
    # 테스트를 위해 직접 입력 시 (보안 주의)
    SUPABASE_URL = "https://lrfkixsnphbumcwmthym.supabase.co"
    SUPABASE_KEY = "여기에_복사한_ANON_KEY_넣기"
    DISCORD_WEBHOOK_URL = "여기에_디스코드_웹훅_URL_넣기"
    SITE_PASSWORD = "여기에_접속_비밀번호_설정"

# Supabase 클라이언트 초기화
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 3. 세션 초기화
# =========================
def init_session():
    defaults = {
        "logged_in": False,
        "user_name": "",
        "current_page": 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# =========================
# 4. 共通関数 (Supabase 엔진으로 교체)
# =========================
def load_inventory():
    """Supabase에서 재고 목록 불러오기"""
    response = supabase.table("inventory").select("*").order("item_name").execute()
    return pd.DataFrame(response.data)

def send_discord_alert(item_name, qty, unit):
    """디스코드 알림 발송"""
    payload = {
        "embeds": [{
            "title": "🚨 재고 재입고 필요",
            "description": f"**{item_name}**의 재고가 **{qty}{unit}** 남았습니다!",
            "color": 15158332,
            "footer": {"text": f"확인자: {st.session_state.user_name} | Coffee Circle"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except:
        pass

def logout():
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.rerun()

# =========================
# 5. UI 화면 구성
# =========================
if not st.session_state.logged_in:
    st.subheader("🔒 RCS 시스템 로그인")
    input_user = st.text_input("담당자명")
    input_pass = st.text_input("패스워드", type="password")
    if st.button("로그인", use_container_width=True):
        if input_pass == SITE_PASSWORD and input_user.strip():
            st.session_state.logged_in = True
            st.session_state.user_name = input_user.strip()
            st.rerun()
        else:
            st.error("인증 정보가 틀립니다.")
    st.stop()

# 메인 화면
with st.sidebar:
    st.write(f"👤 담당자: **{st.session_state.user_name}**")
    if st.button("로그아웃"): logout()

st.subheader("☕ RCS 재고 관리 (Supabase Ver.)")

# 데이터 불러오기
df = load_inventory()

if not df.empty:
    # 데이터 에디터 설정
    edited_df = st.data_editor(
        df,
        column_config={
            "id": None, # ID는 숨김
            "item_name": st.column_config.Column("품목명", disabled=True),
            "current_stock": st.column_config.NumberColumn("현재 수량", format="%d"),
            "min_stock": st.column_config.NumberColumn("알림 기준", format="%d"),
            "unit": st.column_config.Column("단위", disabled=True),
            "last_editor": st.column_config.Column("최종 수정자", disabled=True),
            "updated_at": st.column_config.Column("최종 수정일시", disabled=True),
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 변경사항 저장", use_container_width=True):
        # 변경된 행 찾기 (단순화된 로직)
        for i, row in edited_df.iterrows():
            if row['current_stock'] != df.iloc[i]['current_stock']:
                # DB 업데이트
                supabase.table("inventory").update({
                    "current_stock": row['current_stock'],
                    "last_editor": st.session_state.user_name
                }).eq("item_name", row['item_name']).execute()
                
                # 재고 부족 시 디스코드 알림
                if row['current_stock'] <= row['min_stock']:
                    send_discord_alert(row['item_name'], row['current_stock'], row['unit'])
        
        st.success("성공적으로 저장되었습니다!")
        time.sleep(1)
        st.rerun()
else:
    st.info("데이터가 없습니다. Supabase 테이블을 확인하세요.")
    else:
        st.error(f"システムエラー: {e}")
