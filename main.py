import streamlit as st
from supabase import create_client
import pandas as pd
import requests
import time

# =========================
# 1. CONFIG
# =========================
st.set_page_config(
    page_title="RCS Inventory System",
    layout="centered"
)

# =========================
# 2. CONNECT
# =========================
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

supabase = init_supabase()
webhook = st.secrets["discord_webhook_url"]

# =========================
# 3. CACHE DATA
# =========================
@st.cache_data(ttl=5) # 테스트를 위해 캐시 주기를 조금 줄였습니다
def load_inventory():
    res = supabase.table("inventory").select("*").order("item_name").execute()
    return pd.DataFrame(res.data)

@st.cache_data(ttl=5)
def load_logs():
    res = supabase.table("logs").select("*").order("created_at", desc=True).limit(75).execute()
    return pd.DataFrame(res.data)

# =========================
# 4. WEBHOOK (RETRY)
# =========================
def send_discord_alert(message, retry=3):
    for i in range(retry):
        try:
            res = requests.post(webhook, json={"content": message}, timeout=3)
            if res.status_code == 204: return # 성공 시 리턴
        except:
            time.sleep(1)

# =========================
# 5. INVENTORY UPDATE
# =========================
def update_inventory_batch(old_df, new_df, user):
    updates = []
    logs = []
    alerts = []

    for i, row in new_df.iterrows():
        # ID 기준으로 이전 데이터 매칭
        old_row = old_df[old_df["id"] == row["id"]].iloc[0]
        old_stock = int(old_row["current_stock"])
        new_stock = int(row["current_stock"])

        if old_stock == new_stock:
            continue

        # 1) Inventory Update List
        updates.append({
            "id": row["id"],
            "current_stock": new_stock,
            "last_editor": user
        })

        # 2) Logs List
        logs.append({
            "user_name": user,
            "item_name": row["item_name"],
            "old_stock": old_stock,
            "new_stock": new_stock
        })

        # 3) Alert List (요청 문구 적용)
        if new_stock <= row["min_stock"]:
            alerts.append(f"🚨 **{row['item_name']} 부족! 현재: {new_stock}{row['unit']} 변경 공지**")

    # DB 반영
    for u in updates:
        supabase.table("inventory").update({
            "current_stock": u["current_stock"],
            "last_editor": u["last_editor"]
        }).eq("id", u["id"]).execute()

    if logs:
        supabase.table("logs").insert(logs).execute()

    for msg in alerts:
        send_discord_alert(msg)

    return len(updates)

# =========================
# 6. SESSION
# =========================
if "user" not in st.session_state: st.session_state.user = "TestUser"
if "page" not in st.session_state: st.session_state.page = 0

# =========================
# 7. UI (상단)
# =========================
st.title("☕ RCS Inventory")
st.write(f"접속자: **{st.session_state.user}** (Test Mode)")

# =========================
# 8. LOAD & SHOW
# =========================
try:
    df_inventory = load_inventory()

    # --- 재고 수정 테이블 ---
    edited_df = st.data_editor(
        df_inventory,
        column_config={
            "id": None,
            "item_name": "품목명",
            "current_stock": st.column_config.NumberColumn("현재 수량", format="%d"),
            "unit": "단위",
            "min_stock": None, "last_editor": None, "updated_at": None
        },
        hide_index=True,
        use_container_width=True,
        key="inventory_editor"
    )

    if st.button("💾 변경사항 저장", use_container_width=True):
        count = update_inventory_batch(df_inventory, edited_df, st.session_state.user)
        if count > 0:
            st.success(f"{count}개 항목 업데이트 완료!")
            st.cache_data.clear() # 캐시 강제 초기화
            time.sleep(1)
            st.rerun()
        else:
            st.info("변경사항이 없습니다.")

    # --- 로그 섹션 ---
    st.divider()
    st.subheader("🕒 최근 변경 기록")
    df_logs = load_logs()

    if not df_logs.empty:
        df_logs["created_at"] = pd.to_datetime(df_logs["created_at"]).dt.strftime("%m-%d %H:%M")
        
        per_page = 15
        total = len(df_logs)
        max_page = (total - 1) // per_page
        page = st.session_state.page

        start = page * per_page
        end = start + per_page
        display = df_logs.iloc[start:end][["created_at", "user_name", "item_name", "new_stock", "old_stock"]]

        st.table(display.rename(columns={
            "created_at": "일시", "user_name": "담당자", "item_name": "품목",
            "new_stock": "변경후", "old_stock": "변경전"
        }))

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("Prev", disabled=(page == 0)):
                st.session_state.page -= 1
                st.rerun()
        with c2:
            st.write(f"Page {page+1} / {max_page+1}")
        with c3:
            if st.button("Next", disabled=(page >= max_page)):
                st.session_state.page += 1
                st.rerun()
except Exception as e:
    st.error(f"Error: {e}")
