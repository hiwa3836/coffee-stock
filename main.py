import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ システム設定 (Secretsから取得)
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

# ★ 숫자를 예쁘게 만들어주는 마법의 함수 (3.0 -> 3 / 3.5 -> 3.5)
def fmt(val):
    v = float(val)
    return int(v) if v.is_integer() else v

# ==========================================
# 1. UI デザイン (検索窓 & 折りたたみカテゴリ)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }

        .stTabs [data-baseweb="tab-list"] {
            gap: 5px; background-color: #1e293b !important; padding: 5px; border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 40px; background-color: #334155 !important; color: #94a3b8 !important;
            font-size: 0.85rem; padding: 0 12px !important; border-radius: 6px !important;
            font-weight: bold;
        }
        .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }

        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"]:has(.item-name) {
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                align-items: center !important;
            }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(1) {
                width: 55% !important; flex: 1 1 55% !important; min-width: 0 !important;
            }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(2) {
                width: 45% !important; flex: 1 1 45% !important; min-width: 120px !important;
            }
        }

        div[data-baseweb="input"] > div { background-color: #0f172a !important; }

        [data-testid="stExpander"] {
            background-color: #1e293b !important;
            border-radius: 10px !important;
            border: 1px solid #334155 !important;
            margin-bottom: 8px !important;
        }
        [data-testid="stExpander"] summary { padding: 10px 15px !important; }
        [data-testid="stExpander"] summary p {
            font-weight: bold !important; color: #60a5fa !important; font-size: 0.95rem !important;
        }
        [data-testid="stExpanderDetails"] { padding: 0 10px 10px 10px !important; }

        .item-name { font-size: 0.95rem; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .item-cap { font-size: 0.75rem; color: #94a3b8; }

        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; opacity: 0.5; }
        .block-container { padding: 1.5rem 0.6rem !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ロジック管理
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
    st.session_state.edits[item_id] = float(st.session_state[f"input_{item_id}"])

# 1. 원자적 업데이트를 위한 SQL RPC 호출 권장 (Supabase Function)
# DB 단에서 'current_stock = current_stock + diff' 처리가 필요하지만, 
# 우선 Python 단에서 최소한의 방어 로직 구현

def save_changes():
    if not st.session_state.edits: return
    
    success_count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for i_id, n_val in st.session_state.edits.items():
        item = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
        diff = float(n_val) - float(item["current_stock"])
        
        if diff != 0:
            # 개별 업데이트 시 에러 핸들링 추가
            try:
                # [개선] 절대값이 아닌 증감값(diff) 기반으로 DB 함수(RPC)를 호출하는 것이 정석
                supabase.table("inventory").update({"current_stock": float(n_val)}).eq("id", i_id).execute()
                
                # 로그 삽입
                log_entry = {
                    "item_name": str(item["item_name"]), 
                    "before_qty": float(item["current_stock"]),
                    "after_qty": float(n_val), 
                    "diff_qty": float(diff), 
                    "created_at": now
                }
                supabase.table("inventory_logs").insert(log_entry).execute()
                success_count += 1
            except Exception as e:
                st.error(f"Update failed for {item['item_name']}: {e}")

    if success_count > 0:
        # 비동기 처리를 흉내내기 위해 별도 스레드에서 실행하거나 최적화 고려
        # send_discord_message(discord_msg) 
        
        # 전체 삭제 대신 수정한 데이터만 부분 업데이트하는 로직으로 전환 권장
        st.session_state.edits = {}
        if "inventory_df" in st.session_state: del st.session_state.inventory_df
        st.success(f"{success_count}건의 변경사항이 반영되었습니다.")
        time.sleep(0.5)
        st.rerun()
            
            # ★ 디스코드 알림에서도 소수점 숨기기 적용
            diff_val = fmt(diff)
            diff_str = f"+{diff_val}" if diff_val > 0 else f"{diff_val}"
            discord_msg += f"> **{item['item_name']}**: {fmt(item['current_stock'])} → **{fmt(n_val)}** ({diff_str})\n"
    
    send_discord_message(discord_msg)
    st.session_state.edits = {}
    if "inventory_df" in st.session_state: del st.session_state.inventory_df
    if "logs_df" in st.session_state: del st.session_state.logs_df
    st.success("保存が完了しました！")
    time.sleep(1)
    st.rerun()

# ==========================================
# 3. メイン UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS在庫管理システム", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCSシステム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    # --- TAB 1: 在庫更新 ---
    with tab1:
        search_query = st.text_input("🔍 検索", placeholder="🔍 商品名・カテゴリで検索 (入力後Enter)...", label_visibility="collapsed")
        
        c1, c2 = st.columns([0.6, 0.4])
        all_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else []
        selected_cat = c1.selectbox("カテゴリ表示", options=["すべて"] + all_cats, label_visibility="collapsed")
        
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        st.markdown("<hr style='margin-top:10px; margin-bottom:15px;'>", unsafe_allow_html=True)
        
        df = st.session_state.inventory_df
        if selected_cat != "すべて":
            df = df[df["category"] == selected_cat]
            
        if search_query:
            df = df[df['item_name'].str.contains(search_query, case=False, na=False) | 
                    df['category'].str.contains(search_query, case=False, na=False)]

        cats_to_show = sorted(df["category"].unique().tolist())
        
        if df.empty:
            st.warning("該当するアイテムが見つかりません。")
            
        for cat in cats_to_show:
            is_expanded = True if search_query else False
            
            with st.expander(f"📂 {cat}", expanded=is_expanded):
                c_df = df[df["category"] == cat]
                for _, row in c_df.iterrows():
                    i_id = row["id"]
                    val = float(st.session_state.edits.get(i_id, row["current_stock"]))
                    icon = "🔴" if val <= float(row["min_stock"]) else "🟢"
                    
                    col_t, col_i = st.columns([6, 4])
                    with col_t:
                        st.markdown(f"<div class='item-name'>{icon} {row['item_name']}</div>", unsafe_allow_html=True)
                        # ★ 리스트에 표시될 때도 예쁜 숫자로 (fmt 적용)
                        st.markdown(f"<div class='item-cap'>現在:{fmt(row['current_stock'])} / 目標:{fmt(row['min_stock'])} {row['unit']}</div>", unsafe_allow_html=True)
                    with col_i:
                        st.number_input(
                            "数量", 
                            value=val, 
                            min_value=0.0, 
                            step=0.5,           
                            format="%g",        # ★ 핵심! 입력창 안의 숫자를 3.0이 아닌 3으로 보여주는 마법 (%g)
                            key=f"input_{i_id}", 
                            label_visibility="collapsed", 
                            on_change=on_stock_change, 
                            args=(i_id,)
                        )
                    st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 在庫変動履歴 (最新75件)")
        logs = st.session_state.logs_df
        if logs.empty: st.info("履歴がありません。")
        else:
            P_SIZE = 15
            total_p = min(5, (len(logs)-1)//P_SIZE + 1)
            start = (st.session_state.log_page - 1) * P_SIZE
            p_logs = logs.iloc[start : start + P_SIZE]
            for _, r in p_logs.iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                
                # ★ 히스토리에서도 예쁜 숫자로 보이게 적용
                diff_val = fmt(r['diff_qty'])
                clr = "#ef4444" if diff_val < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{fmt(r['before_qty'])} → {fmt(r['after_qty'])}</small><br><b style='color:{clr};'>{'+' if diff_val > 0 else ''}{diff_val}</b></div>", unsafe_allow_html=True)
                st.divider()

    # --- TAB 3: 管理設定 ---
    with tab3:
        st.subheader("⚙️ マスタ管理")
        with st.expander("➕ 新規アイテム登録"):
            n_name = st.text_input("商品名")
            ex_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["コーヒー"]
            n_cat_s = st.selectbox("カテゴリ選択", options=ex_cats + ["(新規作成)"])
            f_cat = n_cat_s if n_cat_s != "(新規作成)" else st.text_input("新規カテゴリ名を入力")
            ca, cb = st.columns(2)
            nm = ca.number_input("通知目安(目標値)", min_value=0.0, step=0.5, format="%g") # ★ 여기도 적용
            nu = cb.text_input("単位", value="個")
            
            if st.button("登録する", type="primary", use_container_width=True):
                if not n_name.strip():
                    st.error("⚠️ 商品名を入力してください。")
                else:
                    try:
                        supabase.table("inventory").insert({
                            "item_name": n_name, "category": f_cat, 
                            "min_stock": float(nm), "unit": nu, "current_stock": 0.0
                        }).execute()
                        del st.session_state.inventory_df; st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ 登録失敗: {e}")

        st.divider()
        if not st.session_state.inventory_df.empty:
            cur_cats = sorted(st.session_state.inventory_df["category"].unique().tolist())
            for cat in cur_cats:
                with st.expander(f"📂 {cat}"):
                    c_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in c_df.iterrows():
                        rid = row["id"]; ek = f"em_{rid}"
                        if ek not in st.session_state: st.session_state[ek] = False
                        
                        if not st.session_state[ek]:
                            cc1, cc2 = st.columns([7, 3])
                            cc1.markdown(f"**{row['item_name']}** <small>({fmt(row['min_stock'])}{row['unit']})</small>", unsafe_allow_html=True)
                            if cc2.button("編集", key=f"e_{rid}", use_container_width=True):
                                st.session_state[ek] = True; st.rerun()
                        else:
                            st.markdown("---")
                            en = st.text_input("商品名", value=row["item_name"], key=f"n_{rid}")
                            ec = st.selectbox("カテゴリ", options=cur_cats, index=cur_cats.index(row["category"]), key=f"c_{rid}")
                            col_s1, col_s2 = st.columns(2)
                            em = col_s1.number_input("目安", value=float(row["min_stock"]), step=0.5, format="%g", key=f"m_{rid}")
                            eu = col_s2.text_input("単位", value=row["unit"], key=f"u_{rid}")
                            
                            b1, b2, b3 = st.columns(3)
                            if b1.button("💾 保存", key=f"s_{rid}", type="primary", use_container_width=True):
                                supabase.table("inventory").update({
                                    "item_name": en, "category": ec, 
                                    "min_stock": float(em), "unit": eu
                                }).eq("id", rid).execute()
                                st.session_state[ek] = False; del st.session_state.inventory_df; st.rerun()
                            if b2.button("🚫 取消", key=f"b_{rid}", use_container_width=True):
                                st.session_state[ek] = False; st.rerun()
                            if b3.button("🗑️ 削除", key=f"d_{rid}", use_container_width=True):
                                supabase.table("inventory").delete().eq("id", rid).execute()
                                del st.session_state.inventory_df; st.rerun()
                        st.markdown("<hr style='margin:5px 0; opacity:0.1;'>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
