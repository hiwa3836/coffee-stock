import streamlit as st
import pandas as pd
import time
import requests
import threading
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ 시스템 설정
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

def send_discord_message_async(content):
    def task():
        try:
            requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
        except Exception: pass
    threading.Thread(target=task, daemon=True).start()

def fmt(val):
    v = float(val)
    return int(v) if v.is_integer() else v

# ==========================================
# 1. UI 디자인 (CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; background-color: #1e293b !important; padding: 5px; border-radius: 10px; }
        .stTabs [data-baseweb="tab"] { height: 40px; background-color: #334155 !important; color: #94a3b8 !important; font-size: 0.85rem; padding: 0 12px !important; border-radius: 6px !important; font-weight: bold; }
        .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"]:has(.item-name) { flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(1) { width: 55% !important; flex: 1 1 55% !important; min-width: 0 !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(2) { width: 45% !important; flex: 1 1 45% !important; min-width: 120px !important; }
        }
        div[data-baseweb="input"] > div { background-color: #0f172a !important; }
        [data-testid="stExpander"] { background-color: #1e293b !important; border-radius: 10px !important; border: 1px solid #334155 !important; margin-bottom: 8px !important; }
        [data-testid="stExpander"] summary p { font-weight: bold !important; color: #60a5fa !important; font-size: 0.95rem !important; }
        .item-name { font-size: 0.95rem; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .item-cap { font-size: 0.75rem; color: #94a3b8; }
        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; opacity: 0.5; }
        .block-container { padding: 1.5rem 0.6rem !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 로직 관리 (RPC 기반)
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        res = supabase.table("inventory").select("*").order("id").execute()
        st.session_state.inventory_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if "edits" not in st.session_state: st.session_state.edits = {}
    if "logs_df" not in st.session_state:
        res_logs = supabase.table("inventory_logs").select("*").order("created_at", desc=True).limit(75).execute()
        st.session_state.logs_df = pd.DataFrame(res_logs.data) if res_logs.data else pd.DataFrame()

def on_stock_change(item_id):
    st.session_state.edits[item_id] = float(st.session_state[f"input_{item_id}"])

def save_changes():
    if not st.session_state.edits: return
    
    success_count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discord_msg = f"📦 **[在庫更新通知]** ({now})\n"
    
    for i_id, n_val in st.session_state.edits.items():
        mask = st.session_state.inventory_df["id"] == i_id
        item = st.session_state.inventory_df[mask].iloc[0]
        diff = float(n_val) - float(item["current_stock"])
        
        if diff != 0:
            try:
                # [Vulnerability Fix] RPC 호출: 재고 업데이트와 로그 기록을 원자적으로 처리
                supabase.rpc("update_inventory_atomic", {
                    "p_id": int(i_id),
                    "p_new_stock": float(n_val),
                    "p_diff": float(diff),
                    "p_item_name": str(item["item_name"]),
                    "p_before_qty": float(item["current_stock"])
                }).execute()
                
                # 로컬 세션 상태만 즉시 업데이트 (전체 재조회 방지)
                st.session_state.inventory_df.loc[mask, "current_stock"] = float(n_val)
                
                diff_str = f"+{fmt(diff)}" if diff > 0 else f"{fmt(diff)}"
                discord_msg += f"> **{item['item_name']}**: {fmt(item['current_stock'])} → **{fmt(n_val)}** ({diff_str})\n"
                success_count += 1
            except Exception as e:
                st.error(f"⚠️ {item['item_name']} 保存失敗: {e}")

    if success_count > 0:
        send_discord_message_async(discord_msg)
        st.session_state.edits = {}
        if "logs_df" in st.session_state: del st.session_state.logs_df
        st.success(f"✅ {success_count}건 저장 완료!")
        time.sleep(0.5)
        st.rerun()

# ==========================================
# 3. 메인 UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCS 시스템")
    tab1, tab2, tab3 = st.tabs(["📝 재고 업데이트", "📜 변경 이력", "⚙️ 설정"])

    with tab1:
        search = st.text_input("🔍 검색", placeholder="검색어 입력...", label_visibility="collapsed")
        
        c1, c2 = st.columns([0.6, 0.4])
        all_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else []
        sel_cat = c1.selectbox("카테고리", options=["전체"] + all_cats, label_visibility="collapsed")
        
        if c2.button("✅ 저장", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        df = st.session_state.inventory_df
        if sel_cat != "전체": df = df[df["category"] == sel_cat]
        if search: df = df[df['item_name'].str.contains(search, case=False, na=False)]

        for cat in sorted(df["category"].unique().tolist()):
            with st.expander(f"📂 {cat}", expanded=bool(search)):
                c_df = df[df["category"] == cat]
                for _, row in c_df.iterrows():
                    i_id = row["id"]
                    val = float(st.session_state.edits.get(i_id, row["current_stock"]))
                    icon = "🔴" if val <= float(row["min_stock"]) else "🟢"
                    
                    t, i = st.columns([6, 4])
                    t.markdown(f"<div class='item-name'>{icon} {row['item_name']}</div><div class='item-cap'>현재:{fmt(row['current_stock'])} / 목표:{fmt(row['min_stock'])} {row['unit']}</div>", unsafe_allow_html=True)
                    i.number_input("수량", value=val, step=0.5, format="%g", key=f"input_{i_id}", label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
                    st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

    with tab2:
        st.subheader("📜 최근 변경 이력")
        logs = st.session_state.logs_df
        if logs.empty: st.info("이력이 없습니다.")
        else:
            for _, r in logs.head(15).iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                diff = fmt(r['diff_qty'])
                clr = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{fmt(r['before_qty'])} → {fmt(r['after_qty'])}</small><br><b style='color:{clr};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

    with tab3:
        st.subheader("⚙️ 마스터 관리")
        with st.expander("➕ 새 품목 등록"):
            n_name = st.text_input("품목명")
            ca, cb = st.columns(2)
            nm = ca.number_input("목표 재고", min_value=0.0, step=0.5, format="%g")
            nu = cb.text_input("단위", value="개")
            if st.button("등록", type="primary", use_container_width=True):
                if n_name:
                    supabase.table("inventory").insert({"item_name": n_name, "category": "기본", "min_stock": float(nm), "unit": nu, "current_stock": 0.0}).execute()
                    if "inventory_df" in st.session_state: del st.session_state.inventory_df
                    st.rerun()

if __name__ == "__main__":
    main()
