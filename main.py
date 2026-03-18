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
# 1. UI 디자인 최적화 (★다크 모드 & 하이라이트 탭★)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* [전체 배경] 흰색을 완전히 날리고 어두운 회색으로 설정 */
        .stApp {
            background-color: #111827 !important; /* 지옥에서 온 다크 그레이 */
            color: #e5e7eb !important; /* 기본 글씨는 연회색 */
        }

        /* [상단 탭 바 컨테이너] */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #1f2937; /* 약간 더 밝은 어두운 회색 */
            padding: 10px;
            border-radius: 12px;
            border: 1px solid #374151; /* 어둠 속의 경계선 */
        }

        /* [기본 탭 버튼 스타일] */
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #374151 !important; /* 차분한 어두운 회색 배경 */
            color: #9ca3af !important; /* 글씨는 약간 흐리게 */
            border-radius: 8px !important;
            border: 1px solid #4b5563 !important; /* 탭 개별 테두리 */
            padding: 0 20px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease;
        }

        /* [마우스를 올렸을 때 (Hover)] */
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #4b5563 !important;
            color: #ffffff !important;
        }

        /* [★선택된 활성 탭 (Active)★] 외부를 하이라이트로 밝게 강조 */
        .stTabs [aria-selected="true"] {
            background-color: #3b82f6 !important; /* 선명한 파란색 포인트 */
            color: #ffffff !important; /* 글씨는 완전 흰색 */
            border: 2px solid #818cf8 !important; /* ★이게 요청하신 하이라이트 테두리★ */
            box-shadow: 0px 0px 15px rgba(129, 140, 248, 0.6); /* 빛나는 효과 추가 */
        }

        /* [콘텐츠 영역 내부 요소] 배경을 어둡게 맞춤 */
        [data-testid="stExpander"], .stTable, div[data-testid="stVerticalBlock"] {
            background-color: #1f2937; /* 콘텐츠 배경 */
            border-radius: 10px;
            padding: 5px;
            border: 1px solid #374151;
        }
        
        /* [글씨 색상 강제 조정] 어두운 배경에서도 잘 보이게 */
        .stCaption, p, li, span, label { color: #d1d5db !important; }
        h1, h2, h3, h4, h5, h6, strong { color: #ffffff !important; }
        
        /* [입력창 스타일] 다크 모드 맞춤 */
        input[type="number"], input[type="text"], select {
            background-color: #374151 !important;
            color: #ffffff !important;
            border: 1px solid #4b5563 !important;
        }

        /* [구분선] 어둡게 */
        hr { border-top: 1px solid #374151 !important; }

        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-top: 1.5rem !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 데이터 초기화 및 관리 (기존 로직 유지)
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
# 3. 메인 UI (변경된 '다크 모드' 디자인 반영)
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
        # 다크 모드에서 저장 버튼은 녹색으로 눈에 띄게
        if ctrl_col2.button("✅ 変更を確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<br>", unsafe_allow_html=True)
        df = st.session_state.inventory_df
        if selected_cat != "すべて": df = df[df["category"] == selected_cat]
        
        if df.empty: st.info("アイテムがありません")
        else:
            for _, row in df.iterrows():
                i_id = row["id"]
                val = st.session_state.edits.get(i_id, row["current_stock"])
                status_icon = "🔴" if val <= row["min_stock"] else "🟢"
                col1, col2 = st.columns([6, 4], vertical_alignment="center")
                with col1:
                    st.markdown(f"**{status_icon} {row['item_name']}**")
                    st.caption(f"現在: {row['current_stock']} / 目安: {row['min_stock']} {row['unit']}")
                with col2:
                    st.number_input("数量", value=int(val), min_value=0, step=1, key=f"input_{i_id}", label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
                st.markdown("<hr style='margin:0; opacity:0.1;'>", unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 変동履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴가 없습니다")
        else:
            PER_PAGE, MAX_PAGES = 15, 5
            display_total_pages = min(MAX_PAGES, (len(logs) - 1) // PER_PAGE + 1)
            start_idx = (st.session_state.log_page - 1) * PER_PAGE
            paged_logs = logs.iloc[start_idx : start_idx + PER_PAGE]
            for _, row in paged_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{row['item_name']}**<br><small>{row['created_at']}</small>", unsafe_allow_html=True)
                diff = row['diff_qty']; color = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{row['before_qty']} → {row['after_qty']}</small><br><b style='color:{color}; font-size:1.1rem;'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()
            p1, p2, p3 = st.columns([1,1,1])
            if p1.button("⬅️ 前へ", key="prev_log"): st.session_state.log_page = max(1, st.session_state.log_page - 1); st.rerun()
            p2.markdown(f"<div style='text-align:center; padding-top:10px;'>{st.session_state.log_page} / {display_total_pages}</div>", unsafe_allow_html=True)
            if p3.button("次へ ➡️", key="next_log"): st.session_state.log_page = min(display_total_pages, st.session_state.log_page + 1); st.rerun()

    # --- TAB 3: 管理設定 ---
    with tab3:
        st.subheader("⚙️ マスタ管理")
        with st.expander("➕ 新規アイテム登録", expanded=False):
            n_name = st.text_input("商品名", key="new_name")
            exist_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["커피"]
            n_cat_sel = st.selectbox("カテゴリ選択", options=exist_cats + ["(新規作成)"], key="n_cat_sel")
            final_cat = n_cat_sel if n_cat_sel != "(新規作成)" else st.text_input("新規カテゴリ名", key="n_cat_new")
            col_a, col_b = st.columns(2)
            n_min = col_a.number_input("発注目安", min_value=0, key="n_min")
            n_unit = col_b.text_input("単位", value="個", key="n_unit")
            if st.button("商品を登録", type="primary"):
                supabase.table("inventory").insert({"item_name": n_name, "category": final_cat, "min_stock": int(n_min), "unit": n_unit, "current_stock": 0}).execute()
                del st.session_state.inventory_df; st.rerun()

        st.divider()
        st.markdown("##### 📦 既存アイテムの編集/削除")
        if not st.session_state.inventory_df.empty:
            for cat in sorted(st.session_state.inventory_df["category"].unique()):
                with st.expander(f"📂 {cat}"):
                    cat_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in cat_df.iterrows():
                        i_id = row["id"]; ed_key = f"ed_m_{i_id}"
                        if ed_key not in st.session_state: st.session_state[ed_key] = False
                        if not st.session_state[ed_key]:
                            c1, c2, c3 = st.columns([5, 3, 2])
                            c1.markdown(f"**{row['item_name']}**\n<small>{row['min_stock']}{row['unit']} 目安</small>", unsafe_allow_html=True)
                            if c2.button("編集", key=f"eb_{i_id}"): st.session_state[ed_key] = True; st.rerun()
                            if c3.button("削除", key=f"db_{i_id}", type="secondary"): supabase.table("inventory").delete().eq("id", i_id).execute(); del st.session_state.inventory_df; st.rerun()
                        else:
                            st.markdown("---")
                            en = st.text_input("商品名", value=row["item_name"], key=f"en_{i_id}")
                            ec = st.text_input("カテゴリ", value=row["category"], key=f"ec_{i_id}")
                            col_e1, col_e2 = st.columns(2)
                            em = col_e1.number_input("発注目安", value=int(row["min_stock"]), key=f"em_{i_id}")
                            eu = col_e2.text_input("単位", value=row["unit"], key=f"eu_{i_id}")
                            bc1, bc2 = st.columns(2)
                            if bc1.button("保存", key=f"sb_{i_id}", type="primary", use_container_width=True):
                                supabase.table("inventory").update({"item_name": en, "category": ec, "min_stock": int(em), "unit": eu}).eq("id", i_id).execute()
                                st.session_state[ed_key] = False; del st.session_state.inventory_df; st.rerun()
                            if bc2.button("取消", key=f"cb_{i_id}", use_container_width=True):
                                st.session_state[ed_key] = False; st.rerun()
                        st.markdown("<hr style='margin:5px 0; opacity:0.1;'>", unsafe_allow_html=True)
        else:
            st.write("アイテムが登録されていません")

if __name__ == "__main__":
    main()
