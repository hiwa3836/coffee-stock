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
# 1. UI 디자인 (모바일 1행 배치 + 딥 네이비)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }

        /* 탭 바 디자인 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px; background-color: #1e293b !important; padding: 12px;
            border-radius: 14px; border: 1px solid #334155; margin-bottom: 25px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 52px; background-color: #334155 !important; color: #94a3b8 !important;
            border-radius: 10px !important; border: 1px solid #475569 !important;
            padding: 0 15px !important; font-weight: 700 !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563eb !important; color: #ffffff !important;
            border: 2px solid #60a5fa !important;
        }

        /* ★모바일에서 한 줄로 정렬하기 위한 핵심 CSS★ */
        /* 컬럼 컨테이너의 줄바꿈을 방지 */
        [data-testid="column"] {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        /* 숫자 조절기를 오른쪽 끝으로 밀기 */
        div[data-testid="stNumberInput"] {
            width: 140px !important; /* 모바일 폭에 맞춰 살짝 조절 */
            float: right;
        }
        
        /* 버튼 크기 최적화 */
        div[data-testid="stNumberInput"] button {
            width: 40px !important;
            height: 40px !important;
            background-color: #334155 !important;
        }

        div[data-testid="stNumberInput"] input {
            font-size: 1.1rem !important;
        }

        .stCaption { color: #94a3b8 !important; line-height: 1.2; }
        hr { border-top: 1px solid #334155 !important; margin: 10px 0 !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 로직 (기본 로직 유지)
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
# 3. 메인 UI (모바일 가로 배치 적용)
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCSシステム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    with tab1:
        c1, c2 = st.columns([5, 5], vertical_alignment="bottom")
        cats = ["すべて"] + sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = c1.selectbox("カテゴリ:", options=cats)
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.divider()
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        for _, row in df.iterrows():
            i_id = row["id"]
            val = st.session_state.edits.get(i_id, row["current_stock"])
            icon = "🔴" if val <= row["min_stock"] else "🟢"
            
            # 컬럼 비율을 6:4로 설정하여 가로로 나열
            col_text, col_input = st.columns([6, 4])
            with col_text:
                st.markdown(f"**{icon} {row['item_name']}**")
                st.caption(f"{row['current_stock']} / 目安:{row['min_stock']}")
            with col_input:
                st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{i_id}", 
                                label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
            st.markdown("<hr>", unsafe_allow_html=True)

    # ... (tab2, tab3 로직은 이전과 동일하되 레이아웃만 유지) ...
    # (생략된 tab2, tab3 코드는 이전 버전의 코드를 그대로 사용하시면 됩니다.)

if __name__ == "__main__":
    main()
