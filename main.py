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
    """新規品目の登録 (신규 품목 등록)"""
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
    
    db.table("logs").insert({
        "user_name": user,
        "item_name": f"[新規] {item_name}",
        "old_stock": 0,
        "new_stock": current_stock
    }).execute()

def delete_item(item_id, item_name, user):
    """品目の削除 (품목 삭제)"""
    db.table("inventory").delete().eq("id", item_id).execute()
    
    db.table("logs").insert({
        "user_name": user,
        "item_name": f"[削除] {item_name}",
        "old_stock": 0,
        "new_stock": 0
    }).execute()

# =========================
# UPDATE ENGINE
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

    if logs:
        db.table("logs").insert(logs).execute()

    for alert in alerts:
        send_discord_alert_embed(alert["item_name"], alert["new_stock"], alert["min_stock"], alert["unit"])

    return len(updates)

# =========================
# SIDEBAR
# =========================

with st.sidebar:
    st.title("⚙️ RCS 管理")

    raw_df = get_inventory()
    df = raw_df.copy() # 원본 보존

    st.divider()
    user = st.text_input("担当者名 (담당자명)", value="管理者")

    if st.button("🔄 データ更新 (새로고침)", use_container_width=True):
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
    st.metric("不足品目数 (부족 품목)", len(shortage))

with c2:
    st.metric("総管理品目数 (총 품목)", len(raw_df))

with c3:
    if not shortage.empty:
        st.error("🚨 補充必要: " + ", ".join(shortage["item_name"].tolist()))
    else:
        st.success("✅ 全在庫正常 (모든 재고 정상)")

st.divider()

# =========================
# ITEM MANAGEMENT (Add & Delete)
# =========================

col_add, col_del = st.columns(2)

with col_add:
    with st.expander("➕ 新規品目の登録 (신규 품목 등록)"):
        with st.form("new_item_form", clear_on_submit=True):
            new_cat = st.text_input("カテゴリ (카테고리)", placeholder="例: コーヒー豆, 消耗品")
            new_name = st.text_input("品目名 (품목명)*")
            
            c_a1, c_a2, c_a3 = st.columns(3)
            with c_a1: new_stock = st.number_input("初期在庫", min_value=0, step=1)
            with c_a2: new_min = st.number_input("最小基準", min_value=0, step=1)
            with c_a3: new_unit = st.text_input("単位 (단위)", value="個")
                    
            if st.form_submit_button("💾 登録する", use_container_width=True):
                if not new_name.strip() or not new_cat.strip():
                    st.error("カテゴリと品目名は必須です。")
                else:
                    try:
                        add_new_item(new_cat, new_name, new_stock, new_unit, new_min, user)
                        st.success(f"「{new_name}」登録完了！")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")

with col_del:
    with st.expander("🗑️ 品目の削除 (단종 품목 삭제)"):
        if not raw_df.empty:
            with st.form("delete_item_form"):
                del_cat = st.selectbox("カテゴリを選択", sorted(raw_df["category"].unique()))
                
                # 선택된 카테고리에 맞는 품목만 필터링
                filtered_items = raw_df[raw_df["category"] == del_cat]
                del_item_name = st.selectbox("削除する品目名", filtered_items["item_name"].tolist())
                
                # 선택된 품목의 ID 찾기
                del_item_id = filtered_items[filtered_items["item_name"] == del_item_name]["id"].values[0] if not filtered_items.empty else None
                
                st.warning("⚠️ 削除すると元に戻せません。(삭제 시 복구 불가)")
                if st.form_submit_button("🗑️ 完全に削除する", use_container_width=True) and del_item_id:
                    try:
                        delete_item(del_item_id, del_item_name, user)
                        st.success(f"「{del_item_name}」を削除しました。")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")
        else:
            st.info("データがありません。")

st.divider()

# =========================
# INVENTORY EDITOR (Smart Tabs & Visual UX)
# =========================

st.subheader("📦 在庫状況の更新 (재고 현황 갱신)")

show_shortage = st.checkbox("🚨 不足品目のみ表示 (부족 품목만 모아보기)", value=False)

if not df.empty:
    def get_status(row):
        if row["current_stock"] <= row["min_stock"]: return "🔴"
        elif row["current_stock"] <= row["min_stock"] + 2: return "🟡"
        else: return "🟢"

    display_df = df.copy()
    display_df["状態"] = display_df.apply(get_status, axis=1)
    
    if show_shortage:
        display_df = display_df[display_df["current_stock"] <= display_df["min_stock"]]

    if display_df.empty:
        st.success("素晴らしい！現在表示する品目はありません。(표시할 부족 품목이 없습니다.)")
    else:
        categories = sorted(display_df["category"].dropna().unique())
        tabs = st.tabs(["すべて (전체)"] + categories)

        tab_data = {"すべて (전체)": display_df}
        for cat in categories:
            tab_data[cat] = display_df[display_df["category"] == cat]

        # 💡 FIX: 전체 데이터 병합이 아닌, "변경된 로우(Rows)"만 담을 리스트
        all_changed_rows = []

        for i, tab in enumerate(tabs):
            with tab:
                tab_name = list(tab_data.keys())[i]
                current_tab_df = tab_data[tab_name]
                
                if current_tab_df.empty:
                    st.caption("該当する品目がありません。")
                    continue

                edited_tab_df = st.data_editor(
                    current_tab_df,
                    key=f"editor_{tab_name}",
                    column_config={
                        "id": None,
                        "状態": st.column_config.TextColumn("状態", disabled=True),
                        "category": None, 
                        "item_name": st.column_config.TextColumn("品目名", disabled=True),
                        "current_stock": st.column_config.NumberColumn("現在の在庫", disabled=False, min_value=0, step=1),
                        "min_stock": st.column_config.NumberColumn("最小", disabled=True),
                        "unit": st.column_config.TextColumn("単位", disabled=True),
                        "last_editor": None,
                        "updated_at": None
                    },
                    column_order=["状態", "item_name", "current_stock", "min_stock", "unit"], 
                    hide_index=True,
                    use_container_width=True
                )
                
                # 💡 FIX: 각 탭 내부에서 원본과 수정본을 즉시 비교하여 변경된 데이터만 추출
                merged_tab = current_tab_df.merge(
                    edited_tab_df[["id", "current_stock"]], 
                    on="id", 
                    suffixes=("_old", "_new")
                )
                tab_changes = merged_tab[merged_tab["current_stock_old"] != merged_tab["current_stock_new"]].copy()
                
                if not tab_changes.empty:
                    all_changed_rows.append(tab_changes)

        # 💡 FIX: 변경된 데이터가 하나라도 있으면 하나로 취합 (중복 편집 방어)
        if all_changed_rows:
            changed_rows = pd.concat(all_changed_rows).drop_duplicates(subset=['id'], keep='last')
            has_changes = not changed_rows.empty
        else:
            changed_rows = pd.DataFrame()
            has_changes = False

        # --- Safe Guard UI ---
        if has_changes:
            st.warning("⚠️ 以下の変更内容を確認の上、最終承認してください。 (아래 변경 사항을 확인 후 승인해 주세요.)")
            
            preview_df = changed_rows[["item_name", "current_stock_old", "current_stock_new", "unit"]].copy()
            preview_df["増減"] = preview_df["current_stock_new"] - preview_df["current_stock_old"]
            preview_df.rename(columns={
                "item_name": "品目名", 
                "current_stock_old": "変更前", 
                "current_stock_new": "変更後"
            }, inplace=True)
            
            st.dataframe(preview_df[["品目名", "変更前", "増減", "変更後", "unit"]], hide_index=True, use_container_width=True)

        # 저장 버튼
        if st.button("✅ 変更の最終承認とDB反映 (변경 승인 및 저장)", type="primary", use_container_width=True, disabled=not has_changes):
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
                
        if not has_changes:
            st.caption("※ 表の数字を変更すると、上の保存ボタンが押せるようになります。 (표의 숫자를 변경하면 저장 버튼이 활성화됩니다.)")

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
        history["created_at_dt"] = pd.to_datetime(history["created_at"], errors="coerce")
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
