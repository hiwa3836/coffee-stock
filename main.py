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
# WEBHOOK ENGINE (Discord Embed)
# =========================

def send_discord_alert_embed(item_name, new_stock, min_stock, unit, retry=3):
    """在庫不足時のDiscord Embed通知"""
    payload = {
        "embeds": [{
            "title": "🚨 在庫補充の通知 (재고 보충 알림)",
            "color": 16711680,
            "fields": [
                {"name": "品目名", "value": item_name, "inline": False},
                {"name": "現在の在庫", "value": f"{new_stock}{unit}", "inline": True},
                {"name": "最小基準", "value": f"{min_stock}{unit}", "inline": True}
            ],
            "footer": {"text": "RCS 自動通知システム"},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    for i in range(retry):
        try:
            requests.post(
                st.secrets["discord_webhook_url"],
                json=payload,
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
        .order("created_at", desc=True)
        .execute()
    )
    return pd.DataFrame(res.data)

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

def add_new_item(category, item_name, current_stock, unit, min_stock, user):
    """新規品目の登録"""
    new_item = {
        "category": category,
        "item_name": item_name,
        "current_stock": current_stock,
        "unit": unit,
        "min_stock": min_stock,
        "last_editor": user,
        "updated_at": datetime.utcnow().isoformat()
    }
    db.table("inventory").insert(new_item).execute()
    
    log_entry = {
        "user_name": user,
        "item_name": f"[新規] {item_name}",
        "old_stock": 0,
        "new_stock": current_stock
    }
    db.table("logs").insert(log_entry).execute()

# =========================
# UPDATE ENGINE (Refactored for Absolute Values)
# =========================

def process_inventory_changes(changed_df, user):
    if changed_df.empty:
        return 0

    updates = []
    logs = []
    alerts = []

    for _, row in changed_df.iterrows():
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
            alerts.append({
                "item_name": row["item_name"],
                "new_stock": new_val,
                "min_stock": row["min_stock"],
                "unit": row["unit"]
            })

    # ---------- DB UPDATE ----------
    for u in updates:
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
    for alert in alerts:
        send_discord_alert_embed(
            alert["item_name"], 
            alert["new_stock"], 
            alert["min_stock"], 
            alert["unit"]
        )

    return len(updates)

# =========================
# SIDEBAR
# =========================

with st.sidebar:
    st.title("⚙️ RCS 管理")

    raw_df = get_inventory()

    if not raw_df.empty and "category" in raw_df.columns:
        categories = ["すべて"] + sorted(raw_df["category"].dropna().unique())
        selected = st.selectbox("カテゴリ", categories)
        df = raw_df if selected == "すべて" else raw_df[raw_df["category"] == selected]
    else:
        df = raw_df

    st.divider()

    user = st.text_input("担当者名", value="管理者")

    if st.button("🔄 データ更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    
    st.subheader("📥 レポートダウンロード")
    if not raw_df.empty:
        csv_data = convert_df_to_csv(raw_df)
        st.download_button(
            label="📊 現在の在庫状況 (CSV)",
            data=csv_data,
            file_name=f"RCS_Inventory_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# =========================
# DASHBOARD
# =========================

if not raw_df.empty:
    shortage = raw_df[raw_df["current_stock"] <= raw_df["min_stock"]]
else:
    shortage = pd.DataFrame()

c1, c2, c3 = st.columns([1,1,2])

with c1:
    st.metric("不足品目数", len(shortage))

with c2:
    st.metric("総管理品目数", len(raw_df))

with c3:
    if not shortage.empty:
        st.error(
            "補充必要: " + ", ".join(shortage["item_name"].tolist())
        )
    else:
        st.success("✅ 全在庫正常")

st.divider()

# =========================
# ADD NEW ITEM (Expander Form)
# =========================

with st.expander("➕ 新規品目の登録 (신규 품목 등록)"):
    with st.form("new_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_cat = st.text_input("カテゴリ (카테고리)", placeholder="例: 飲料, 文房具")
            new_name = st.text_input("品目名 (품목명)*")
        with col2:
            col2_1, col2_2, col2_3 = st.columns(3)
            with col2_1:
                new_stock = st.number_input("初期在庫", min_value=0, step=1)
            with col2_2:
                new_min = st.number_input("最小基準", min_value=0, step=1)
            with col2_3:
                new_unit = st.text_input("単位", value="個")
                
        submitted = st.form_submit_button("💾 登録する", use_container_width=True)
        if submitted:
            if not new_name.strip():
                st.error("品目名は必須です。 (품목명은 필수입니다.)")
            else:
                try:
                    add_new_item(new_cat, new_name, new_stock, new_unit, new_min, user)
                    st.success(f"「{new_name}」が登録されました！")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"登録エラー: {e}")

st.divider()

# =========================
# INVENTORY EDITOR (Absolute Input Mode)
# =========================

st.subheader("📦 在庫状況の更新 (재고 현황 갱신)")
st.caption("実際の在庫数を確認し、「現在の在庫」列の数字を直接書き換えてください。")

if not df.empty:
    edited_df = st.data_editor(
        df,
        column_config={
            "id": None,
            "category": st.column_config.TextColumn("カテゴリ", disabled=True),
            "item_name": st.column_config.TextColumn("品目名", disabled=True),
            # disabled=False로 변경하여 엑셀처럼 직접 수정 가능하게 오픈
            "current_stock": st.column_config.NumberColumn("現在の在庫", disabled=False, min_value=0, step=1),
            "unit": st.column_config.TextColumn("単位", disabled=True),
            "min_stock": st.column_config.NumberColumn("最小基準", disabled=True),
            "last_editor": None,
            "updated_at": None
        },
        hide_index=True,
        use_container_width=True
    )

    # 기존 데이터와 수정된 데이터를 ID 기준으로 병합(Merge)하여 변경점 추출
    merged = df.merge(
        edited_df[["id", "current_stock"]], 
        on="id", 
        suffixes=("_old", "_new")
    )
    changed_rows = merged[merged["current_stock_old"] != merged["current_stock_new"]].copy()

    if not changed_rows.empty:
        st.warning("⚠️ 以下の品目の変更内容を確認の上、最終承認してください。")
        
        # 변경 프리뷰 데이터프레임
        preview_df = changed_rows[["item_name", "current_stock_old", "current_stock_new", "unit"]].copy()
        preview_df["増減"] = preview_df["current_stock_new"] - preview_df["current_stock_old"]
        preview_df.rename(columns={
            "item_name": "品目名", 
            "current_stock_old": "変更前 (기존)", 
            "current_stock_new": "変更後 (최종)"
        }, inplace=True)
        
        # 보기 좋게 컬럼 순서 재배치
        st.dataframe(preview_df[["品目名", "変更前 (기존)", "増減", "変更後 (최종)", "unit"]], hide_index=True, use_container_width=True)

        if st.button("✅ 変更の最終承認とDB反映", type="primary", use_container_width=True):
            try:
                with st.spinner('データ更新中...'):
                    count = process_inventory_changes(changed_rows, user)
                    
                if count > 0:
                    st.success(f"{count}個の品目の在庫が正常に更新されました。")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                    
            except Exception as e:
                st.error(f"保存中にエラーが発生しました: {e}")
else:
    st.info("データがありません。新規品目を登録してください。")

# =========================
# HISTORY
# =========================

st.divider()

c1, c2 = st.columns(2)
history = get_logs()

with c1:
    st.subheader("🕒 最近の変動履歴")
    if not history.empty:
        history["created_at_dt"] = pd.to_datetime(
            history["created_at"],
            errors="coerce"
        )
        history = history.dropna(subset=["created_at_dt"])
        history["time"] = history["created_at_dt"].dt.strftime("%m/%d %H:%M")
        history["増減"] = history["new_stock"] - history["old_stock"]
        
        st.dataframe(
            history[["time", "user_name", "item_name", "増減", "new_stock"]].head(10),
            use_container_width=True,
            hide_index=True
        )

with c2:
    st.subheader("📈 日次処理件数")
    if not history.empty:
        history["date"] = history["created_at_dt"].dt.date
        trend = history.groupby("date").size()
        st.line_chart(trend)
