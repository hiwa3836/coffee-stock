import streamlit as st
from supabase import create_client
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# =========================
# CONFIG
# =========================

st.set_page_config(page_title="RCS 在庫管理システム", layout="wide")

@st.cache_resource
def init_db():
    return create_client(
        st.secrets["supabase_url"],
        st.secrets["supabase_key"]
    )

db = init_db()

# =========================
# WEBHOOK ENGINE
# =========================

def send_discord(msg, retry=3):

    for i in range(retry):
        try:
            requests.post(
                st.secrets["discord_webhook_url"],
                json={"content": msg},
                timeout=3
            )
            return True
        except Exception:
            time.sleep(1)

    return False


# =========================
# DATA ENGINE
# =========================

@st.cache_data(ttl=15)
def get_inventory():

    res = (
        db.table("inventory")
        .select("*")
        .order("category")
        .order("item_name")
        .execute()
    )

    return pd.DataFrame(res.data)


@st.cache_data(ttl=30)
def get_logs():

    last_week = (datetime.now() - timedelta(days=7)).isoformat()

    res = (
        db.table("logs")
        .select("*")
        .filter("created_at", "gte", last_week)
        .execute()
    )

    return pd.DataFrame(res.data)


# =========================
# UPDATE ENGINE
# =========================

def update_inventory(old_df, new_df, user):

    # merge to prevent index mismatch
    merged = old_df.merge(
        new_df[["id", "current_stock"]],
        on="id",
        suffixes=("_old", "_new")
    )

    changed = merged[
        merged["current_stock_old"] != merged["current_stock_new"]
    ]

    if changed.empty:
        return 0

    updates = []
    logs = []
    alerts = []

    for _, row in changed.iterrows():

        new_val = int(row["current_stock_new"])
        old_val = int(row["current_stock_old"])

        updates.append({
            "id": int(row["id"]),
            "stock": new_val,
            "editor": user
        })

        logs.append({
            "user_name": user,
            "item_name": row["item_name"],
            "old_stock": old_val,
            "new_stock": new_val
        })

        if new_val <= row["min_stock"]:
            alerts.append(
                f"🚨 **在庫不足** {row['item_name']} : {new_val}{row['unit']}"
            )

    # ---------- DB UPDATE ----------

    for u in updates:

        # optimistic concurrency control
        db.table("inventory")\
            .update({
                "current_stock": u["stock"],
                "last_editor": u["editor"],
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", u["id"])\
            .execute()

    # ---------- LOG INSERT ----------

    if logs:
        db.table("logs").insert(logs).execute()

    # ---------- ALERT ----------

    for msg in alerts:
        send_discord(msg)

    return len(updates)


# =========================
# SIDEBAR
# =========================

with st.sidebar:

    st.title("⚙️ RCS 管理")

    raw_df = get_inventory()

    if "category" in raw_df.columns:

        categories = ["すべて"] + sorted(
            raw_df["category"].dropna().unique()
        )

        selected = st.selectbox("カテゴリ", categories)

        df = raw_df if selected == "すべて" else raw_df[
            raw_df["category"] == selected
        ]

    else:
        df = raw_df

    st.divider()

    user = st.text_input("担当者名", value="管理者")

    if st.button("🔄 データ更新"):

        st.cache_data.clear()
        st.rerun()


# =========================
# DASHBOARD
# =========================

shortage = raw_df[
    raw_df["current_stock"] <= raw_df["min_stock"]
]

c1, c2, c3 = st.columns([1,1,2])

with c1:
    st.metric("不足品目", len(shortage))

with c2:
    st.metric("総品目数", len(raw_df))

with c3:

    if not shortage.empty:
        st.error(
            "補充必要: "
            + ", ".join(shortage["item_name"].tolist())
        )
    else:
        st.success("在庫正常")


st.divider()

# =========================
# INVENTORY EDITOR
# =========================

st.subheader("📦 在庫管理")

edited_df = st.data_editor(

    df,

    column_config={
        "id": None,
        "category": st.column_config.TextColumn("カテゴリ", disabled=True),
        "item_name": st.column_config.TextColumn("品目", disabled=True),
        "current_stock": st.column_config.NumberColumn("在庫"),
        "unit": st.column_config.TextColumn("単位", disabled=True),
        "min_stock": st.column_config.NumberColumn("最低", disabled=True),
        "last_editor": None,
        "updated_at": None
    },

    hide_index=True,
    use_container_width=True

)


if st.button("💾 保存", use_container_width=True):

    try:

        count = update_inventory(
            raw_df,
            edited_df,
            user
        )

        if count > 0:

            st.success(f"{count}件 更新")

            st.cache_data.clear()

            time.sleep(1)

            st.rerun()

        else:

            st.info("変更なし")

    except Exception as e:

        st.error(f"保存エラー: {e}")


# =========================
# HISTORY
# =========================

st.divider()

c1, c2 = st.columns(2)

history = get_logs()

with c1:

    st.subheader("🕒 最近履歴")

    if not history.empty:

        history["created_at_dt"] = pd.to_datetime(
            history["created_at"],
            errors="coerce"
        )

        history = history.dropna(subset=["created_at_dt"])

        history["time"] = history["created_at_dt"]\
            .dt.strftime("%m/%d %H:%M")

        st.dataframe(

            history[
                ["time","user_name","item_name","new_stock"]
            ].head(10),

            use_container_width=True
        )


with c2:

    st.subheader("📈 消費トレンド")

    if not history.empty:

        history["date"] = history["created_at_dt"].dt.date

        trend = history.groupby("date").size()

        st.line_chart(trend)
