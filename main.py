import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ 시스템 설정
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

def send_discord_message(content):
    try:
        requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
    except Exception:
        pass

# ==========================================
# 1. UI 디자인 (좌우 5:5 배치 & 버튼 강제 표시)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }

        /* 탭 디자인 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px; background-color: #1e293b !important; padding: 5px; border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 36px; background-color: #334155 !important; color: #94a3b8 !important;
            font-size: 0.75rem; padding: 0 8px !important;
        }

        /* ★핵심: 좌우 5:5 강제 고정 및 한 줄 유지★ */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            width: 100% !important;
        }
        
        /* 왼쪽 텍스트 칸 (정확히 50%) */
        div[data-testid="column"]:nth-child(1) {
            flex: 0 0 50% !important;
            max-width: 50% !important;
            min-width: 0 !important;
        }

        /* 오른쪽 버튼 칸 (정확히 50%) */
        div[data-testid="column"]:nth-child(2) {
            flex: 0 0 50% !important;
            max-width: 50% !important;
            display: flex !important;
            justify-content: flex-end !important;
        }

        /* ★버튼 복구: Number Input 내부 요소 강제 조정★ */
        div[data-testid="stNumberInput"] {
            width: 100% !important;
            max-width: 130px !important; /* 버튼 뭉치 최대 너비 */
        }
        
        /* 버튼(-, +)이 숨겨지지 않도록 강제 노출 */
        div[data-testid="stNumberInput"] button {
            display: flex !important;
            width: 35px !important; 
            height: 35px !important; 
            background-color: #334155 !important;
            border: 1px solid #475569 !important;
            visibility: visible !important;
        }

        div[data-testid="stNumberInput"] input {
            font-size: 0.9rem !important;
            text-align: center !important;
        }

        /* 이름이 길면 줄임표(...) 처리 */
        .item-name { 
            font-size: 0.85rem; font-weight: bold; 
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; 
        }
        .item-cap { font-size: 0.7rem; color: #94a3b8; }

        .block-container { padding: 1rem 0.6rem !important; }
        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 로직 (기존과 동일)
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        res = supabase.table("inventory").select("*").order("id").execute()
        st.session_state.inventory_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if "edits" not in st.session_state: st.session_state.edits = {}
    if "logs_df" not in st.session_state:
        res_logs = supabase.table("inventory_logs").select("*").order("created_at", desc=True).limit(75).execute()
        st.session_state.logs_df = pd.DataFrame(res_logs.data) if res_logs.data else pd.DataFrame()
    if "log_page" not in st.session_state: st.session_state.log_page = 1

def on_stock_change(item_id):
    st.session_state.edits[item_id] = int(st.session_state[f"input_{item_id}"])

def save_changes():
    if not st.session_state.edits: return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discord_msg = f"📦 **[在庫更新通知]** ({now})\n"
    for i_id, n_val in st.session_state.edits.items():
        item = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
        diff = int(n_val) - int(item["current_stock"])
        if diff != 0:
            supabase.table("inventory").update({"current_stock": int(n_val)}).eq("id", i_id).execute()
            log_entry = {"item_name": str(item["item_name"]), "before_qty": int(item["current_stock"]),
                         "after_qty": int(n_val), "diff_qty": int(diff), "created_at": now}
            supabase.table("inventory_logs").insert(log_entry).execute()
            diff_str = f"+{diff}" if diff > 0 else f"{diff}"
            discord_msg += f"> **{item['item_name']}**: {item['current_stock']} → **{n_val}** ({diff_str})\n"
    send_discord_message(discord_msg)
    st.session_state.edits = {}
    if "inventory_df" in st.session_state: del st.session_state.inventory_df
    if "logs_df" in st.session_state: del st.session_state.logs_df
    st.success("保存完了！")
    time.sleep(1)
    st.rerun()

# ==========================================
# 3. 메인 화면 (5:5 컬럼 적용)
# ==========================================
def main():
    st.set_page_config(page_title="RCS", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCS")
    tab1, tab2, tab3 = st.tabs(["📝 更新", "📜 履歴", "⚙️ 設定"])

    with tab1:
        c1, c2 = st.columns([0.5, 0.5])
        all_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else []
        selected_cat = c1.selectbox("CAT", options=["すべて"] + all_cats, label_visibility="collapsed")
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        for _, row in df.iterrows():
            i_id = row["id"]
            val = st.session_state.edits.get(i_id, row["current_stock"])
            icon = "🔴" if val <= row["min_stock"] else "🟢"
            
            # 5:5 가로 배치
            col_t, col_i = st.columns([0.5, 0.5])
            with col_t:
                st.markdown(f"<div class='item-name'>{icon} {row['item_name']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='item-cap'>現:{row['current_stock']} / 目:{row['min_stock']}</div>", unsafe_allow_html=True)
            with col_i:
                st.number_input("QTY", value=int(val), min_value=0, step=1, key=f"input_{i_id}", 
                                label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
            st.markdown("<hr>", unsafe_allow_html=True)

    with tab2:
        st.subheader("📜 変動履歴")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴なし")
        else:
            P_SIZE = 15
            total_p = min(5, (len(logs)-1)//P_SIZE + 1)
            start = (st.session_state.log_page - 1) * P_SIZE
            p_logs = logs.iloc[start : start + P_SIZE]
            for _, r in p_logs.iterrows():
                l1, l2 = st.columns([0.6, 0.4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                diff = r['diff_qty']; clr = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{r['before_qty']}→{r['after_qty']}</small><br><b style='color:{clr};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

if __name__ == "__main__":
    main()
