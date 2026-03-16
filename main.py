import streamlit as st
from supabase import create_client
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# =========================
# 1. CONFIG & SYSTEM
# =========================
st.set_page_config(page_title="RCS OPS Center", layout="wide")

# CSS: 가독성 중심의 스타일링
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
# 2. DATA ENGINE
# =========================
@st.cache_data(ttl=10)
def get_inventory():
    res = db.table("inventory").select("*").order("item_name").execute()
    return pd.DataFrame(res.data)

def get_recent_logs():
    # 최근 7일간의 로그 분석용
    last_week = (datetime.now() - timedelta(days=7)).isoformat()
    res = db.table("logs").select("*").filter("created_at", "gte", last_week).execute()
    return pd.DataFrame(res.data)

def push_discord(msg):
    try: requests.post(st.secrets["discord_webhook_url"], json={"content": msg}, timeout=2)
    except: pass

# =========================
# 3. SIDEBAR (FILTERS)
# =========================
with st.sidebar:
    st.title("⚙️ OPS Filter")
    raw_df = get_inventory()
    
    # 카테고리 컬럼 유무 확인 및 처리
    if "category" in raw_df.columns:
        categories = ["전체"] + sorted(raw_df["category"].unique().tolist())
        selected_cat = st.selectbox("카테고리 선택", categories)
        df = raw_df if selected_cat == "전체" else raw_df[raw_df["category"] == selected_cat]
    else:
        st.warning("DB에 'category' 컬럼이 없습니다.")
        df = raw_df

    st.divider()
    user_name = st.text_input("담당자 성함", value="운영진")
    
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

# =========================
# 4. DASHBOARD (ANALYTICS)
# =========================
shortage_items = raw_df[raw_df["current_stock"] <= raw_df["min_stock"]]

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    st.metric("재고 부족 품목", f"{len(shortage_items)} 건")
with col2:
    st.metric("관리 품목 총계", f"{len(raw_df)} 종")
with col3:
    if not shortage_items.empty:
        items_str = ", ".join(shortage_items["item_name"].tolist())
        st.error(f"**즉시 확인 필요:** {items_str}")
    else:
        st.success("✅ 모든 소모품 재고가 충분합니다.")

st.divider()

# =========================
# 5. MAIN EDITOR
# =========================
st.subheader("📦 소모품 현황 관리")

edited_df = st.data_editor(
    df,
    column_config={
        "id": None,
        "category": st.column_config.TextColumn("분류", disabled=True),
        "item_name": st.column_config.TextColumn("품목명", disabled=True),
        "current_stock": st.column_config.NumberColumn("현재 수량", format="%d"),
        "unit": st.column_config.TextColumn("단위", disabled=True),
        "min_stock": st.column_config.NumberColumn("최저 기준", disabled=True),
        "last_editor": None, "updated_at": None
    },
    hide_index=True,
    use_container_width=True,
    key="ops_editor"
)

if st.button("💾 변경사항 일괄 저장", use_container_width=True, type="primary"):
    # 변경사항 추출
    diff = df[df["current_stock"] != edited_df["current_stock"]]
    
    if not diff.empty:
        updates, logs, alerts = [], [], []
        
        for _, row in diff.iterrows():
            new_val_raw = edited_df.loc[edited_df["id"] == row["id"], "current_stock"].values[0]
            
            # [해결] JSON TypeError 방지를 위해 순수 Python 타입으로 강제 변환
            clean_id = int(row["id"])
            clean_new_stock = int(new_val_raw)
            clean_old_stock = int(row["current_stock"])
            clean_user = str(user_name)
            clean_item = str(row["item_name"])

            updates.append({
                "id": clean_id, 
                "current_stock": clean_new_stock, 
                "last_editor": clean_user
            })
            
            logs.append({
                "user_name": clean_user, 
                "item_name": clean_item,
                "old_stock": clean_old_stock, 
                "new_stock": clean_new_stock
            })
            
            if clean_new_stock <= row["min_stock"] and clean_new_stock < clean_old_stock:
                alerts.append(f"🚨 **[재고경보] {clean_item}** : {clean_new_stock}{row['unit']}")

        try:
            # DB 업데이트 수행
            for u in updates:
                db.table("inventory").update({
                    "current_stock": u["current_stock"], 
                    "last_editor": u["last_editor"]
                }).eq("id", u["id"]).execute()
            
            if logs:
                db.table("logs").insert(logs).execute()
            
            for msg in alerts:
                push_discord(msg)
                
            st.success(f"{len(updates)}건 업데이트 완료!")
            time.sleep(1)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")
    else:
        st.info("변경사항이 없습니다.")

# =========================
# 6. RECENT ACTIVITY
# =========================
st.divider()
c_log, c_trend = st.columns([1, 1])

with c_log:
    st.subheader("🕒 최근 변경 이력")
    history = get_recent_logs()
    if not history.empty:
        # [해결] OutOfBoundsDatetime 에러 방지 (errors='coerce')
        history["created_at_dt"] = pd.to_datetime(history["created_at"], errors='coerce')
        history = history.dropna(subset=["created_at_dt"])
        
        if not history.empty:
            history["display_time"] = history["created_at_dt"].dt.strftime("%m/%d %H:%M")
            st.dataframe(
                history[["display_time", "user_name", "item_name", "new_stock"]].head(10), 
                use_container_width=True,
                column_config={"display_time": "일시", "user_name": "담당자", "item_name": "품목", "new_stock": "수량"}
            )
        else:
            st.info("유효한 로그 데이터가 없습니다.")

with c_trend:
    st.subheader("📈 소모품 소비 흐름 (7일)")
    if not history.empty and "created_at_dt" in history.columns:
        history["date"] = history["created_at_dt"].dt.date
        trend_data = history.groupby("date").size()
        
        if not trend_data.empty:
            st.line_chart(trend_data)
        else:
            st.info("데이터가 부족하여 차트를 그릴 수 없습니다.")
    else:
        st.info("표시할 데이터가 없습니다.")
