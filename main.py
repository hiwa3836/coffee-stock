import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ 시스템 설정 (Supabase & Bot Server)
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

def send_discord_message(content):
    """Discord通知送信"""
    try:
        requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
    except Exception:
        pass

# ==========================================
# 1. UI 디자인 최적화 (회색 탭 & 모바일 대응)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* 상단 탭 디자인: 회색 배경에 흰색 글씨 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px; background-color: #f1f5f9; padding: 8px; border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px; background-color: #64748b !important;
            color: white !important; border-radius: 8px !important;
            padding: 0 20px !important; font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1e293b !important; border: 2px solid #94a3b8 !important;
        }
        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-top: 1rem !important; }
        input[type="number"] { text-align: center; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 데이터 초기화 및 관리
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
    """재고 변경사항 저장 및 알림"""
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
# 3. 메인 화면 UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCSシステム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    # --- TAB 1: 在庫更新 ---
    with tab1:
        ctrl_col1, ctrl_col2 = st.columns([5, 5], vertical_alignment="bottom")
        categories = ["すべて"] + sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = ctrl_col1.selectbox("カテゴリ表示:", options=categories)
        if ctrl_col2.button("✅ 変更を確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<br>", unsafe_allow_html=True)
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        if df.empty: st.info("アイテムがありません。")
        else:
            for _, row in df.iterrows():
                item_id = row["id"]
                val = st.session_state.edits.get(item_id, row["current_stock"])
                status_icon = "🔴" if val <= row["min_stock"] else "🟢"
                col1, col2 = st.columns([6, 4], vertical_alignment="center")
                with col1:
                    st.markdown(f"**{status_icon} {row['item_name']}**")
                    st.caption(f"現在: {row['current_stock']} / 目安: {row['min_stock']} {row['unit']}")
                with col2:
                    st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{item_id}", label_visibility="collapsed", on_change=on_stock_change, args=(item_id,))
                st.markdown("<hr style='margin:0; opacity:0.2;'>", unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 変動履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴がありません")
        else:
            PER_PAGE, MAX_PAGES = 15, 5
            display_total_pages = min(MAX_PAGES, (len(logs) - 1) // PER_PAGE + 1)
            start_idx = (st.session_state.log_page - 1) * PER_PAGE
            paged_logs = logs.iloc[start_idx : start_idx + PER_PAGE]
            for _, row in paged_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{row['item_name']}**<br><small>{row['created_at']}</small>", unsafe_allow_html=True)
                diff = row['diff_qty']; color = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{row['before_qty']} → {row['after_qty']}</small><br><b style='color:{color};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()
            p1, p2, p3 = st.columns([1,1,1])
            if p1.button("⬅️ 前へ", disabled=st.session_state.log_page == 1):
                st.session_state.log_page -= 1; st.rerun()
            p2.markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.log_page} / {display_total_pages}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️", disabled=st.session_state.log_page >= display_total_pages):
                st.session_state.log_page += 1; st.rerun()

    # --- TAB 3: 管理設定 ---
    with tab3:
        st.subheader("⚙️ マスタ管理")
        with st.expander("➕ 新規アイテム登録"):
            n_name = st.text_input("商品名", key="new_name")
            exist_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["コーヒー豆"]
            n_cat_sel = st.selectbox("カテゴリ選択", options=exist_cats + ["(新規作成)"], key="n_cat_sel")
            final_cat = n_cat_sel if n_cat_sel != "(新規作成)" else st.text_input("新規カテゴリ名", key="n_cat_new")
            col_a, col_b = st.columns(2)
            n_min = col_a.number_input("発注目安", min_value=0, key="n_min")
            n_unit = col_b.text_input("単位", value="個", key="n_unit")
            if st.button("登録", type="primary", use_container_width=True):
                if n_name and final_cat:
                    supabase.table("inventory").insert({"item_name": n_name, "category": final_cat, "min_stock": int(n_min), "unit": n_unit, "current_stock": 0}).execute()
                    st.success("登録完了！"); del st.session_state.inventory_df; time.sleep(0.5); st.rerun()

        st.divider()
        st.markdown("##### 📦 既存アイテムの編集/削除")
        if not st.session_state.inventory_df.empty:
            for cat in sorted(st.session_state.inventory_df["category"].unique()):
                with st.expander(f"📂 {cat}"):
                    cat_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in cat_df.iterrows():
                        i_id = row["id"]; edit_key = f"edit_mode_{i_id}"
                        if edit_key not in st.session_state: st.session_state[edit_key] = False
                        
                        if not st.session_state[edit_key]:
                            c1, c2, c3 = st.columns([5, 3, 2])
                            c1.markdown(f"**{row['item_name']}**\n<small>{row['min_stock']}{row['unit']} 目安</small>", unsafe_allow_html=True)
                            if c2.button("編集", key=f"ed_btn_{i_id}", use_container_width=True):
                                st.session_state[edit_key] = True; st.rerun()
                            if c3.button("削除", key=f"del_btn_{i_id}", type="secondary", use_container_width=True):
                                supabase.table("inventory").delete().eq("id", i_id).execute(); del st.session_state.inventory_df; st.rerun()
                        else:
                            st.markdown("---")
                            e_name = st.text_input("商品名", value=row["item_name"], key=f"en_{i_id}")
                            e_cat = st.text_input("カテゴリ", value=row["category"], key=f"ec_{i_id}")
                            col_e1, col_e2 = st.columns(2)
                            e_min = col_e1.number_input("発注目安", value=int(row["min_stock"]), key=f"em_{i_id}")
                            e_unit = col_e2.text_input("単位", value=row["unit"], key=f"eu_{i_id}")
                            bc1, bc2 = st.columns(2)
                            if bc1.button("保存", key=f"sv_{i_id}", type="primary", use_container_width=True):
                                supabase.table("inventory").update({"item_name": e_name, "category": e_cat, "min_stock": int(e_min), "unit": e_unit}).eq("id", i_id).execute()
                                st.session_state[edit_key] = False; del st.session_state.inventory_df; st.rerun()
                            if bc2.button("取消", key=f"cn_{i_id}", use_container_width=True):
                                st.session_state[edit_key] = False; st.rerun()
                        st.markdown("<hr style='margin:5px 0; opacity:0.1;'>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
