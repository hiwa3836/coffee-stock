import streamlit as st
from supabase import create_client
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# =========================
# 1. システム設定 (CONFIG)
# =========================
st.set_page_config(page_title="RCS 在庫管理システム", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #ff4b4b; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_db():
    return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

db = init_db()

# =========================
# 2. データエンジン (ENGINE)
# =========================
@st.cache_data(ttl=10)
def get_inventory():
    res = db.table("inventory").select("*").order("category").order("item_name").execute()
    return pd.DataFrame(res.data)

def get_recent_logs():
    last_week = (datetime.now() - timedelta(days=7)).isoformat()
    res = db.table("logs").select("*").filter("created_at", "gte", last_week).execute()
    return pd.DataFrame(res.data)

def push_discord(msg):
    try: requests.post(st.secrets["discord_webhook_url"], json={"content": msg}, timeout=2)
    except: pass

# =========================
# 3. サイド바 (FILTERS)
# =========================
with st.sidebar:
    st.title("⚙️ 操作パネル")
    raw_df = get_inventory()
    
    if "category" in raw_df.columns:
        categories = ["すべて"] + sorted(raw_df["category"].unique().tolist())
        selected_cat = st.selectbox("カテゴリ選択", categories)
        df = raw_df if selected_cat == "すべて" else raw_df[raw_df["category"] == selected_cat]
    else:
        df = raw_df

    st.divider()
    user_name = st.text_input("担当者名", value="管理者")
    
    if st.button("🔄 データを更新"):
        st.cache_data.clear()
        st.rerun()

# =========================
# 4. ダッシュボード (ANALYTICS)
# =========================
shortage_items = raw_df[raw_df["current_stock"] <= raw_df["min_stock"]]

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    st.metric("在庫不足品目", f"{len(shortage_items)} 件")
with col2:
    st.metric("管理品目数", f"{len(raw_df)} 種")
with col3:
    if not shortage_items.empty:
        items_str = ", ".join(shortage_items["item_name"].tolist())
        st.error(f"**補充が必要です:** {items_str}")
    else:
        st.success("✅ 在庫は十分に確保されています。")

st.divider()

# =========================
# 5. 在庫管理エディタ (EDITOR)
# =========================
st.subheader("📦 消耗品在庫状況")

edited_df = st.data_editor(
    df,
    column_config={
        "id": None,
        "category": st.column_config.TextColumn("カテゴリ", disabled=True),
        "item_name": st.column_config.TextColumn("品目名", disabled=True),
        "current_stock": st.column_config.NumberColumn("現在の在庫", format="%d"),
        "unit": st.column_config.TextColumn("単位", disabled=True),
        "min_stock": st.column_config.NumberColumn("最低基準", disabled=True),
        "last_editor": None, "updated_at": None
    },
    hide_index=True,
    use_container_width=True,
    key="ops_editor"
)

if st.button("💾 変更内容を保存", use_container_width=True, type="primary"):
    diff = df[df["current_stock"] != edited_df["current_stock"]]
    
    if not diff.empty:
        updates, logs, alerts = [], [], []
        for _, row in diff.iterrows():
            new_val_raw = edited_df.loc[edited_df["id"] == row["id"], "current_stock"].values[0]
            
            clean_id = int(row["id"])
            clean_new_stock = int(new_val_raw)
            clean_old_stock = int(row["current_stock"])
            clean_user = str(user_name)
            clean_item = str(row["item_name"])

            updates.append({"id": clean_id, "current_stock": clean_new_stock, "last_editor": clean_user})
            logs.append({"user_name": clean_user, "item_name": clean_item, "old_stock": clean_old_stock, "new_stock": clean_new_stock})
            
            if clean_new_stock <= row["min_stock"] and clean_new_stock < clean_old_stock:
                alerts.append(f"🚨 **[在庫アラート] {clean_item}** : 残り{clean_new_stock}{row['unit']}")

        try:
            for u in updates:
                db.table("inventory").update({"current_stock": u["current_stock"], "last_editor": u["last_editor"]}).eq("id", u["id"]).execute()
            if logs:
                db.table("logs").insert(logs).execute()
            for msg in alerts:
                push_discord(msg)
                
            st.success(f"{len(updates)}件の更新が完了しました。")
            time.sleep(1)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"保存エラー: {e}")

# =========================
# 6. 最近の履歴 (HISTORY)
# =========================
st.divider()
c_log, c_trend = st.columns([1, 1])

with c_log:
    st.subheader("🕒 最近の変更履歴")
    history = get_recent_logs()
    if not history.empty:
        history["created_at_dt"] = pd.to_datetime(history["created_at"], errors='coerce')
        history = history.dropna(subset=["created_at_dt"])
        if not history.empty:
            history["display_time"] = history["created_at_dt"].dt.strftime("%m/%d %H:%M")
            st.dataframe(
                history[["display_time", "user_name", "item_name", "new_stock"]].head(10), 
                use_container_width=True,
                column_config={"display_time": "日時", "user_name": "担当者", "item_name": "品目", "new_stock": "在庫数"}
            )

with c_trend:
    st.subheader("📈 在庫消費トレンド (7日間)")
    if not history.empty:
        history["date"] = history["created_at_dt"].dt.date
        trend_data = history.groupby("date").size()
        st.line_chart(trend_data)
