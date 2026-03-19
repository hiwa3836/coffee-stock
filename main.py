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
# 1. UI 디자인 (모바일 1행 강제 배치)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }

        /* 탭 디자인 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px; background-color: #1e293b !important; padding: 10px;
            border-radius: 14px; border: 1px solid #334155; margin-bottom: 20px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 48px; background-color: #334155 !important; color: #94a3b8 !important;
            border-radius: 8px !important; border: 1px solid #475569 !important;
            padding: 0 10px !important; font-size: 0.85rem;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563eb !important; color: #ffffff !important;
        }

        /* ★핵심: 모바일에서도 컬럼이 쌓이지 않고 가로로 유지되도록 강제★ */
        [data-testid="column"] {
            width: fit-content !important;
            min-width: 0px !important;
            flex-basis: auto !important;
        }
        
        /* 컬럼들을 감싸는 컨테이너를 가로 정렬(Flex)로 고정 */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important; /* 줄바꿈 절대 방지 */
            align-items: center !important;
            justify-content: space-between !important;
        }

        /* 수량 조절기 디자인 */
        div[data-testid="stNumberInput"] {
            width: 130px !important; /* 모바일용 최적 너비 */
        }
        
        div[data-testid="stNumberInput"] button {
            width: 35px !important;
            height: 35px !important;
            background-color: #334155 !important;
        }

        div[data-testid="stNumberInput"] input {
            font-size: 1rem !important;
            padding: 0px !important;
        }

        .stCaption { color: #94a3b8 !important; font-size: 0.8rem; white-space: nowrap; }
        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; }
        
        /* 불필요한 여백 제거 */
        .block-container { padding: 1rem 0.8rem !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 로직 (생략 없이 통합)
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
# 3. 메인 UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCSシステム")
    tab1, tab2, tab3 = st.tabs(["📝 更新", "📜 履歴", "⚙️ 設定"])

    with tab1:
        c1, c2 = st.columns([1, 1])
        cats = ["すべて"] + sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = c1.selectbox("카테고리", options=cats, label_visibility="collapsed")
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        for _, row in df.iterrows():
            i_id = row["id"]
            val = st.session_state.edits.get(i_id, row["current_stock"])
            icon = "🔴" if val <= row["min_stock"] else "🟢"
            
            # 컬럼 비율을 모바일 최적화로 설정 (텍스트가 넉넉하게)
            col_text, col_input = st.columns([0.65, 0.35])
            with col_text:
                st.markdown(f"**{icon} {row['item_name']}**")
                st.caption(f"現:{row['current_stock']} / 目:{row['min_stock']}")
            with col_input:
                st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{i_id}", 
                                label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
            st.markdown("<hr>", unsafe_allow_html=True)

    with tab2:
        st.subheader("📜 変動履歴")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴がありません")
        else:
            P_SIZE, MAX_P = 15, 5
            total_p = min(MAX_P, (len(logs)-1)//P_SIZE + 1)
            start = (st.session_state.log_page - 1) * P_SIZE
            p_logs = logs.iloc[start : start + P_SIZE]
            for _, r in p_logs.iterrows():
                l1, l2 = st.columns([0.6, 0.4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                diff = r['diff_qty']; clr = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{r['before_qty']}→{r['after_qty']}</small><br><b style='color:{clr};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()
            p1, p2, p3 = st.columns([1,1,1])
            if p1.button("⬅️"): st.session_state.log_page = max(1, st.session_state.log_page - 1); st.rerun()
            p2.markdown(f"<div style='text-align:center;'>{st.session_state.log_page}/{total_p}</div>", unsafe_allow_html=True)
            if p3.button("➡️"): st.session_state.log_page = min(total_p, st.session_state.log_page + 1); st.rerun()

    with tab3:
        st.subheader("⚙️ 設定")
        with st.expander("➕ 新規登録"):
            n_name = st.text_input("商品名")
            ex_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["커피"]
            n_cat_s = st.selectbox("카테고리", options=ex_cats + ["(新規作成)"])
            f_cat = n_cat_s if n_cat_s != "(新規作成)" else st.text_input("新規カテゴリ名")
            ca, cb = st.columns(2)
            nm = ca.number_input("目安", min_value=0); nu = cb.text_input("単位", value="個")
            if st.button("登録", type="primary", use_container_width=True):
                supabase.table("inventory").insert({"item_name": n_name, "category": f_cat, "min_stock": int(nm), "unit": nu, "current_stock": 0}).execute()
                del st.session_state.inventory_df; st.rerun()

        st.divider()
        if not st.session_state.inventory_df.empty:
            for cat in sorted(st.session_state.inventory_df["category"].unique()):
                with st.expander(f"📂 {cat}"):
                    c_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in c_df.iterrows():
                        rid = row["id"]; ek = f"em_{rid}"
                        if ek not in st.session_state: st.session_state[ek] = False
                        if not st.session_state[ek]:
                            cc1, cc2 = st.columns([0.7, 0.3])
                            cc1.markdown(f"**{row['item_name']}** ({row['min_stock']}{row['unit']})")
                            if cc2.button("Edit", key=f"e_{rid}"): st.session_state[ek] = True; st.rerun()
                        else:
                            en = st.text_input("名", value=row["item_name"], key=f"n_{rid}")
                            ec = st.text_input("種", value=row["category"], key=f"c_{rid}")
                            if st.button("Save", key=f"s_{rid}", type="primary"):
                                supabase.table("inventory").update({"item_name": en, "category": ec}).eq("id", rid).execute()
                                st.session_state[ek] = False; del st.session_state.inventory_df; st.rerun()
                            if st.button("Back", key=f"b_{rid}"): st.session_state[ek] = False; st.rerun()

if __name__ == "__main__":
    main()
