import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ システム設定 (Supabase & Bot Server)
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

def send_discord_message(content):
    """Discordへの通知送信機能"""
    try:
        requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
    except Exception:
        st.toast("⚠️ Discord通知に失敗しました（サーバー応答なし）")
        pass

# ==========================================
# 1. UIデザインの最適化 (CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .sticky-bottom-bar {
            position: fixed; bottom: 0; left: 0; width: 100%;
            background-color: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(10px); padding: 15px 20px;
            box-shadow: 0px -5px 15px rgba(0, 0, 0, 0.1);
            z-index: 99999; border-top: 1px solid #e2e8f0;
        }
        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-bottom: 130px !important; padding-top: 1.5rem !important; }
        input[type="number"] { text-align: center; font-size: 1.2rem; font-weight: bold; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #f8fafc; border-radius: 5px 5px 0 0; padding: 10px 20px;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. データ初期化
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        res = supabase.table("inventory").select("*").order("id").execute()
        st.session_state.inventory_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    
    if "edits" not in st.session_state: st.session_state.edits = {}
    
    if "logs_df" not in st.session_state:
        # DBから最新75件取得
        res_logs = supabase.table("inventory_logs").select("*").order("created_at", desc=True).limit(75).execute()
        st.session_state.logs_df = pd.DataFrame(res_logs.data) if res_logs.data else pd.DataFrame()

    if "log_page" not in st.session_state: st.session_state.log_page = 1

def on_stock_change(item_id):
    # numpyの型が混入しないよう明示的にintに変換
    st.session_state.edits[item_id] = int(st.session_state[f"input_{item_id}"])

# ==========================================
# 3. メイン画面 UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理システム", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCS在庫管理システム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    # --- TAB 1: 在庫更新 ---
    with tab1:
        st.markdown("##### 現在の実在庫数を入力してください")
        categories = ["すべて"] + st.session_state.inventory_df["category"].unique().tolist() if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = st.selectbox("カテゴリ表示:", options=categories)
        st.divider()

        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        if df.empty:
            st.info("該当するアイテムがありません。")
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
                    st.number_input("数量", value=int(val), min_value=0, step=1, 
                                    key=f"input_{item_id}", label_visibility="collapsed", 
                                    on_change=on_stock_change, args=(item_id,))

        if st.session_state.edits:
            st.markdown('<div class="sticky-bottom-bar">', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2], vertical_alignment="center")
            c1.markdown(f"**📝 {len(st.session_state.edits)}件変更中**")
            if c2.button("✅ 変更を確定して保存", type="primary", use_container_width=True):
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                discord_msg = f"📦 **[在庫更新通知]** ({now})\n"
                
                for i_id, n_val in st.session_state.edits.items():
                    item = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
                    diff = int(n_val) - int(item["current_stock"])
                    
                    if diff != 0:
                        # 1. 在庫更新
                        supabase.table("inventory").update({"current_stock": int(n_val)}).eq("id", i_id).execute()
                        
                        # 2. 履歴記録 (✅ JSONエラー回避のため明示的にint型へ変換)
                        log_entry = {
                            "item_name": str(item["item_name"]),
                            "before_qty": int(item["current_stock"]),
                            "after_qty": int(n_val),
                            "diff_qty": int(diff),
                            "created_at": now
                        }
                        supabase.table("inventory_logs").insert(log_entry).execute()
                        
                        diff_str = f"+{diff}" if diff > 0 else f"{diff}"
                        discord_msg += f"> **{item['item_name']}**: {item['current_stock']} → **{n_val}** ({diff_str})\n"
                
                send_discord_message(discord_msg)
                st.session_state.edits = {}
                # データを再読み込みさせるために状態を削除
                if "inventory_df" in st.session_state: del st.session_state.inventory_df
                if "logs_df" in st.session_state: del st.session_state.logs_df
                
                st.success("データベースを更新しました。")
                time.sleep(1)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 在庫変動履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty:
            st.info("履歴データがありません。")
        else:
            PER_PAGE = 15
            MAX_PAGES = 5
            total_data = len(logs)
            display_total_pages = min(MAX_PAGES, (total_data - 1) // PER_PAGE + 1)
            
            start_idx = (st.session_state.log_page - 1) * PER_PAGE
            paged_logs = logs.iloc[start_idx : start_idx + PER_PAGE]

            for _, row in paged_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{row['item_name']}**<br><small style='color:gray;'>{row['created_at']}</small>", unsafe_allow_html=True)
                diff = row['diff_qty']
                color = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{row['before_qty']} → {row['after_qty']}</small><br><b style='color:{color}; font-size:1.1rem;'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

            p1, p2, p3 = st.columns([1, 1, 1])
            if p1.button("⬅️ 前へ", disabled=st.session_state.log_page == 1):
                st.session_state.log_page -= 1
                st.rerun()
            p2.markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.log_page} / {display_total_pages}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️", disabled=st.session_state.log_page >= display_total_pages):
                st.session_state.log_page += 1
                st.rerun()

    # --- TAB 3: 管理設定 ---
    with tab3:
        st.subheader("⚙️ マスタ管理")
        with st.expander("➕ 新規アイテムの登録"):
            new_name = st.text_input("商品名")
            new_cat = st.selectbox("カテゴリ", ["コーヒー豆", "消耗品", "シロップ", "その他"])
            new_min = st.number_input("発注目安", min_value=0)
            new_unit = st.text_input("単位", value="個")
            if st.button("登録を実行", type="primary"):
                supabase.table("inventory").insert({
                    "item_name": new_name, "category": new_cat, 
                    "min_stock": int(new_min), "unit": new_unit, "current_stock": 0
                }).execute()
                st.success("登録完了しました。")
                time.sleep(0.5)
                st.rerun()

if __name__ == "__main__":
    main()
