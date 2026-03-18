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
    try:
        requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
    except Exception:
        pass

# ==========================================
# 1. UI 디자인 최적화 (회색 탭 & 레이아웃)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* 상단 탭 디자인: 회색 배경에 흰색 글씨 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #f1f5f9;
            padding: 8px;
            border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: #64748b !important; /* 회색 배경 */
            color: white !important; /* 흰색 글씨 */
            border-radius: 8px !important;
            padding: 0 20px !important;
            font-weight: bold !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1e293b !important; /* 선택 시 더 진한 회색 */
            border: 2px solid #94a3b8 !important;
        }
        
        /* 모바일 대응 및 여백 조절 */
        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-top: 1rem !important; }
        input[type="number"] { text-align: center; font-size: 1.1rem; }
        
        /* 하단 바 제거 (요청에 따라 상단으로 이동) */
        .sticky-bottom-bar { display: none; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 데이터 초기화
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

# ==========================================
# 3. 메인 기능 함수
# ==========================================
def save_changes():
    """변경사항을 DB와 디코에 저장하는 함수"""
    if not st.session_state.edits:
        st.warning("変更사항이 없습니다.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discord_msg = f"📦 **[在庫更新通知]** ({now})\n"
    
    for i_id, n_val in st.session_state.edits.items():
        item = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
        diff = int(n_val) - int(item["current_stock"])
        
        if diff != 0:
            supabase.table("inventory").update({"current_stock": int(n_val)}).eq("id", i_id).execute()
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
    if "inventory_df" in st.session_state: del st.session_state.inventory_df
    if "logs_df" in st.session_state: del st.session_state.logs_df
    st.success("保存完了！")
    time.sleep(1)
    st.rerun()

# ==========================================
# 4. 메인 화면 UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCSシステム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    # --- TAB 1: 在庫更新 (카테고리와 저장 버튼 병렬 배치) ---
    with tab1:
        # 상단 조작부: 카테고리 선택(50%) | 저장 버튼(50%)
        ctrl_col1, ctrl_col2 = st.columns([5, 5], vertical_alignment="bottom")
        
        categories = ["すべて"] + sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["すべて"]
        selected_cat = ctrl_col1.selectbox("カテゴリ表示:", options=categories)
        
        if ctrl_col2.button("✅ 変更を確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<br>", unsafe_allow_html=True)
        
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        if df.empty:
            st.info("アイテムがありません。")
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
                st.markdown("<hr style='margin:0; opacity:0.2;'>", unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 変動履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty:
            st.info("履歴がありません。")
        else:
            PER_PAGE = 15
            MAX_PAGES = 5
            display_total_pages = min(MAX_PAGES, (len(logs) - 1) // PER_PAGE + 1)
            
            start_idx = (st.session_state.log_page - 1) * PER_PAGE
            paged_logs = logs.iloc[start_idx : start_idx + PER_PAGE]

            for _, row in paged_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{row['item_name']}**<br><small>{row['created_at']}</small>", unsafe_allow_html=True)
                diff = row['diff_qty']
                color = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{row['before_qty']} → {row['after_qty']}</small><br><b style='color:{color};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

            p1, p2, p3 = st.columns([1,1,1])
            if p1.button("⬅️ 前へ", disabled=st.session_state.log_page == 1):
                st.session_state.log_page -= 1
                st.rerun()
            p2.markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.log_page} / {display_total_pages}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️", disabled=st.session_state.log_page >= display_total_pages):
                st.session_state.log_page += 1
                st.rerun()

    # --- TAB 3: 管理設定 (카테고리 관리 기능 복구) ---
    with tab3:
        st.subheader("⚙️ マスタ管理")
        
        # 1. 신규 아이템 등록
        with st.expander("➕ 新規アイテム登録", expanded=False):
            new_name = st.text_input("商品名")
            # 기존 카테고리 목록 불러오기
            exist_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["コーヒー豆", "消耗品"]
            new_cat = st.selectbox("カテゴリ選択", options=exist_cats + ["(新規作成)"])
            
            # 신규 카테고리 입력창 (신규 선택 시만 표시)
            final_cat = new_cat
            if new_cat == "(新規作成)":
                final_cat = st.text_input("新しいカテゴリ名を入力")
                
            col_a, col_b = st.columns(2)
            new_min = col_a.number_input("発注目安", min_value=0)
            new_unit = col_b.text_input("単位", value="個")
            
            if st.button("登録", type="primary", use_container_width=True):
                if new_name and final_cat:
                    supabase.table("inventory").insert({
                        "item_name": new_name, "category": final_cat, 
                        "min_stock": int(new_min), "unit": new_unit, "current_stock": 0
                    }).execute()
                    st.success("登録完了！")
                    if "inventory_df" in st.session_state: del st.session_state.inventory_df
                    time.sleep(0.5)
                    st.rerun()

        st.divider()
        
        # 2. 기존 아이템 수정/삭제 (카테고리별로 묶어서 표시)
        st.markdown("##### 既存アイテムの編集/削除")
        if not st.session_state.inventory_df.empty:
            for cat in sorted(st.session_state.inventory_df["category"].unique()):
                with st.expander(f"📂 {cat}"):
                    cat_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in cat_df.iterrows():
                        edit_col1, edit_col2, edit_col3 = st.columns([5, 3, 2])
                        edit_col1.text(row["item_name"])
                        if edit_col3.button("削除", key=f"del_{row['id']}", type="secondary"):
                            supabase.table("inventory").delete().eq("id", row["id"]).execute()
                            if "inventory_df" in st.session_state: del st.session_state.inventory_df
                            st.rerun()
        else:
            st.write("アイテムが登録されていません。")

if __name__ == "__main__":
    main()
