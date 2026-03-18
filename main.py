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
# 1. UI 디자인 (딥 네이비 + 버튼 너비 확장)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* 1. 전체 배경색 */
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }

        /* 2. 탭 바 디자인 및 하이라이트 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px; background-color: #1e293b !important; padding: 12px;
            border-radius: 14px; border: 1px solid #334155; margin-bottom: 25px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 52px; background-color: #334155 !important; color: #94a3b8 !important;
            border-radius: 10px !important; border: 1px solid #475569 !important;
            padding: 0 24px !important; font-weight: 700 !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563eb !important; color: #ffffff !important;
            border: 2px solid #60a5fa !important; box-shadow: 0px 0px 15px rgba(37, 99, 235, 0.4);
        }

        /* 3. ★버튼 너비 양옆으로 시원하게 확장★ */
        div[data-testid="stNumberInput"] {
            width: 180px !important; /* 전체 너비 확장 */
        }
        div[data-testid="stNumberInput"] button {
            width: 50px !important; /* -, + 버튼 가로 길이 대폭 확대 */
            height: 45px !important;
            background-color: #334155 !important;
            color: white !important;
        }
        div[data-testid="stNumberInput"] input {
            font-size: 1.4rem !important; /* 숫자 크기 확대 */
            font-weight: bold !important;
        }

        /* 4. 불필요한 하얀 박스 및 테두리 제거 */
        .stTabs, [data-baseweb="tabs"], [data-testid="stExpander"], div[data-testid="stVerticalBlock"] {
            background-color: transparent !important;
            border: none !important;
        }
        input, select { background-color: #1e293b !important; color: white !important; border: 1px solid #334155 !important; }
        hr { border-top: 1px solid #334155 !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 로직 및 데이터 관리
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
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    with tab1:
        c1, c2 = st.columns([5, 5], vertical_alignment="bottom")
        cats = ["すべて"] + sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = c1.selectbox("カテゴリ表示:", options=cats)
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<br>", unsafe_allow_html=True)
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        for _, row in df.iterrows():
            i_id = row["id"]
            val = st.session_state.edits.get(i_id, row["current_stock"])
            icon = "🔴" if val <= row["min_stock"] else "🟢"
            col1, col2 = st.columns([5, 5], vertical_alignment="center")
            with col1:
                st.markdown(f"**{icon} {row['item_name']}**")
                st.caption(f"現在: {row['current_stock']} / 目安: {row['min_stock']} {row['unit']}")
            with col2:
                st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{i_id}", label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
            st.markdown("<hr style='margin:0; opacity:0.1;'>", unsafe_allow_html=True)

    with tab2:
        st.subheader("📜 変動履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴がありません")
        else:
            P_SIZE, MAX_P = 15, 5
            total_p = min(MAX_P, (len(logs)-1)//P_SIZE + 1)
            start = (st.session_state.log_page - 1) * P_SIZE
            p_logs = logs.iloc[start : start + P_SIZE]
            for _, r in p_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                diff = r['diff_qty']; clr = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{r['before_qty']} → {r['after_qty']}</small><br><b style='color:{clr};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()
            p1, p2, p3 = st.columns([1,1,1])
            if p1.button("⬅️ 前へ"): st.session_state.log_page = max(1, st.session_state.log_page - 1); st.rerun()
            p2.markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.log_page} / {total_p}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️"): st.session_state.log_page = min(total_p, st.session_state.log_page + 1); st.rerun()

    with tab3:
        st.subheader("⚙️ 마스타 관리")
        with st.expander("➕ 新規アイテム登録"):
            n_name = st.text_input("商品名")
            ex_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["커피"]
            n_cat_s = st.selectbox("カテゴリ", options=ex_cats + ["(新規作成)"])
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
                            cc1, cc2, cc3 = st.columns([5, 3, 2])
                            cc1.markdown(f"**{row['item_name']}**\n<small>{row['min_stock']}{row['unit']}</small>", unsafe_allow_html=True)
                            if cc2.button("編集", key=f"e_{rid}"): st.session_state[ek] = True; st.rerun()
                            if cc3.button("削除", key=f"d_{rid}"): supabase.table("inventory").delete().eq("id", rid).execute(); del st.session_state.inventory_df; st.rerun()
                        else:
                            en = st.text_input("名", value=row["item_name"], key=f"n_{rid}")
                            ec = st.text_input("種", value=row["category"], key=f"c_{rid}")
                            if st.button("保存", key=f"s_{rid}", type="primary"):
                                supabase.table("inventory").update({"item_name": en, "category": ec}).eq("id", rid).execute()
                                st.session_state[ek] = False; del st.session_state.inventory_df; st.rerun()
                            if st.button("戻른", key=f"b_{rid}"): st.session_state[ek] = False; st.rerun()

if __name__ == "__main__":
    main()
