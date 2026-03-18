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

BOT_SERVER_URL = "https://coffee-stock-n3qfj7sgpn2iemxvpegv4y.streamlit.app/send_alert"

def send_discord_message(content):
    """通知送信機能"""
    try:
        requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
    except Exception as e:
        # 봇 서버가 꺼져있을 경우 앱이 멈추지 않도록 조용히 넘김
        pass

# ==========================================
# 1. デザイン最適化 (モバイル・UX)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .sticky-bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 12px 20px;
            box-shadow: 0px -4px 12px rgba(0, 0, 0, 0.05);
            z-index: 99999;
            border-top: 1px solid #e2e8f0;
        }
        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-bottom: 120px !important; padding-top: 1rem !important; }
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {
            border-bottom: 1px solid #f1f5f9; padding: 10px 0;
        }
        input[type="number"] { text-align: center; font-size: 1.2rem; font-weight: bold; }
        [data-testid="stExpander"] {
            border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. データ管理 (DB連携・コールバック)
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        res = supabase.table("inventory").select("*").order("id").execute()
        st.session_state.inventory_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    
    if "edits" not in st.session_state: st.session_state.edits = {}
    
    if "logs_df" not in st.session_state:
        st.session_state.logs_df = pd.DataFrame(columns=["id", "date", "item", "before", "after", "diff", "user"])
    
    if "categories" not in st.session_state:
        db_cats = st.session_state.inventory_df["category"].unique().tolist() if not st.session_state.inventory_df.empty else []
        default_cats = ["コーヒー豆", "消耗品", "衛生用品", "シロップ", "その他"]
        st.session_state.categories = list(set(db_cats + default_cats))

    if "log_page" not in st.session_state: st.session_state.log_page = 1

def on_stock_change(item_id):
    st.session_state.edits[item_id] = st.session_state[f"input_{item_id}"]

def add_new_item(name, cat, min_stock, unit):
    if name.strip() == "": return
    res = supabase.table("inventory").insert({
        "category": cat, "item_name": name, "current_stock": 0, "min_stock": min_stock, "unit": unit
    }).execute()
    st.session_state.inventory_df = pd.concat([st.session_state.inventory_df, pd.DataFrame(res.data)], ignore_index=True)

def update_item(item_id, new_name, new_cat, new_min, new_unit):
    supabase.table("inventory").update({
        "item_name": new_name, "category": new_cat, "min_stock": new_min, "unit": new_unit
    }).eq("id", item_id).execute()
    st.rerun()

def delete_item(item_id):
    supabase.table("inventory").delete().eq("id", item_id).execute()
    st.session_state.inventory_df = st.session_state.inventory_df[st.session_state.inventory_df["id"] != item_id].reset_index(drop=True)
    if item_id in st.session_state.edits: del st.session_state.edits[item_id]
    st.rerun()

# ==========================================
# 3. メイン画面 (UI - 단일 함수로 정리됨)
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理システム", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCS在庫管理")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📋 変更履歴", "⚙️ 設定"])

    # --- TAB 1: 在庫更新 ---
    with tab1:
        st.caption("退勤前に現在の実在庫数を入力してください。")
        filter_options = ["すべて"] + st.session_state.categories
        selected_cat = st.selectbox("カテゴリで絞り込み", options=filter_options, label_visibility="collapsed")
        st.markdown("<hr style='margin: 5px 0px 10px 0px; padding: 0;'/>", unsafe_allow_html=True)

        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        if df.empty:
            st.info("このカテゴリにはアイテムがありません。")
        else:
            for _, row in df.iterrows():
                item_id = row["id"]
                val = st.session_state.edits.get(item_id, row["current_stock"])
                status = "🔴" if val <= row["min_stock"] else "🟢"
                col1, col2 = st.columns([6, 4], vertical_alignment="center")
                with col1:
                    st.markdown(f"**{status} {row['item_name']}**")
                    st.caption(f"{row['category']} | 発注目安: {row['min_stock']}{row['unit']}")
                with col2:
                    st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{item_id}", label_visibility="collapsed", on_change=on_stock_change, args=(item_id,))

        if st.session_state.edits:
            st.markdown('<div class="sticky-bottom-bar">', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2], vertical_alignment="center")
            c1.markdown(f"**📝 {len(st.session_state.edits)}件変更**")
            if c2.button("✅ 変更を保存", type="primary", use_container_width=True):
                now_str = datetime.now().strftime("%H:%M")
                discord_msg = f"📦 **[在庫の棚卸し完了]** ({now_str})\n🔄 **変更履歴:**\n"
                new_logs = []
                for i_id, n_val in st.session_state.edits.items():
                    item = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
                    diff = n_val - item["current_stock"]
                    if diff != 0:
                        new_logs.append({"id": int(time.time()*1000)+i_id, "date": now_str, "item": item["item_name"], "before": item["current_stock"], "after": n_val, "diff": diff, "user": "管理者"})
                        discord_msg += f"> {item['item_name']}: {item['current_stock']} → **{n_val}** ({'+' if diff > 0 else ''}{diff})\n"
                        supabase.table("inventory").update({"current_stock": n_val}).eq("id", i_id).execute()
                        st.session_state.inventory_df.loc[st.session_state.inventory_df["id"] == i_id, "current_stock"] = n_val
                
                if new_logs:
                    st.session_state.logs_df = pd.concat([pd.DataFrame(new_logs), st.session_state.logs_df], ignore_index=True)
                    send_discord_message(discord_msg)
                
                st.session_state.edits = {} 
                st.success("データベースを更新しました。")
                time.sleep(1)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📋 在庫変動履歴")
        logs = st.session_state.logs_df
        if logs.empty:
            st.info("変更履歴がありません。")
        else:
            ITEMS_PER_PAGE = 10
            total_pages = max(1, (len(logs) - 1) // ITEMS_PER_PAGE + 1)
            start_idx = (st.session_state.log_page - 1) * ITEMS_PER_PAGE
            paged_logs = logs.iloc[start_idx : start_idx + ITEMS_PER_PAGE]

            for _, row in paged_logs.iterrows():
                l_col1, l_col2 = st.columns([6, 4])
                l_col1.markdown(f"**{row['item']}**<br><small style='color:gray;'>{row['date']} | {row['user']}</small>", unsafe_allow_html=True)
                diff = row['diff']
                color = "#ef4444" if diff < 0 else "#10b981"
                l_col2.markdown(f"<div style='text-align:right;'><small>{row['before']} → {row['after']}</small><br><b style='color:{color}; font-size:1.1rem;'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

            p1, p2, p3 = st.columns(3)
            if p1.button("⬅️ 前へ", disabled=st.session_state.log_page == 1): st.session_state.log_page -= 1; st.rerun()
            p2.markdown(f"<div style='text-align:center;'>{st.session_state.log_page} / {total_pages}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️", disabled=st.session_state.log_page == total_pages): st.session_state.log_page += 1; st.rerun()

    # --- TAB 3: アイテム管理 ---
    with tab3:
        st.subheader("⚙️ アイテム設定")
        
        with st.expander("➕ 新規アイテムの追加", expanded=False):
            n_name = st.text_input("商品名")
            n_cat = st.selectbox("カテゴリ", options=st.session_state.categories)
            nc1, nc2 = st.columns(2)
            n_min = nc1.number_input("最低在庫数", min_value=0, key="new_item_min")
            n_unit = nc2.text_input("単位 (例: 袋, 個)")
            if st.button("アイテムを登録", use_container_width=True, type="primary"):
                add_new_item(n_name, n_cat, n_min, n_unit)
                st.success("登録完了")
                time.sleep(0.5)
                st.rerun()

        st.divider()

        df = st.session_state.inventory_df
        if df.empty:
            st.info("登録済みのアイテムがありません。")
        else:
            categories = df["category"].unique()
            for cat in categories:
                with st.expander(f"📂 {cat}", expanded=False):
                    cat_items = df[df["category"] == cat]
                    for _, row in cat_items.iterrows():
                        i_id = row['id']
                        r1_c1, r1_c2 = st.columns([7, 3])
                        with r1_c1:
                            e_name = st.text_input("商品名", value=row['item_name'], key=f"en_{i_id}", label_visibility="collapsed")
                        with r1_c2:
                            e_min = st.number_input("最低", value=int(row['min_stock']), key=f"em_{i_id}", label_visibility="collapsed")
                        
                        r2_c1, r2_c2 = st.columns(2)
                        if r2_c1.button("更新", key=f"up_{i_id}", use_container_width=True):
                            update_item(i_id, e_name, cat, e_min, row['unit'])
                            st.toast(f"{e_name} を更新しました")
                        if r2_c2.button("削除", key=f"dl_{i_id}", use_container_width=True):
                            delete_item(i_id)
                            st.toast("削除しました")
                        st.markdown("<div style='margin-bottom: 15px; border-bottom: 1px solid #f0f2f6;'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
