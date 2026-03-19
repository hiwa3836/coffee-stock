import streamlit as st
import pandas as pd
import time
import requests
import threading
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# ⚙️ システム設定 (Secrets)
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

def send_discord_message_async(content):
    def task():
        try:
            requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
        except Exception: pass
    threading.Thread(target=task, daemon=True).start()

def fmt(val):
    v = float(val)
    return int(v) if v.is_integer() else v

# ==========================================
# 1. UI デザイン (CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0f172a !important; color: #f1f5f9 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; background-color: #1e293b !important; padding: 5px; border-radius: 10px; }
        .stTabs [data-baseweb="tab"] { height: 40px; background-color: #334155 !important; color: #94a3b8 !important; font-size: 0.85rem; padding: 0 12px !important; border-radius: 6px !important; font-weight: bold; }
        .stTabs [aria-selected="true"] { background-color: #2563eb !important; color: white !important; }
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"]:has(.item-name) { flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(1) { width: 55% !important; flex: 1 1 55% !important; min-width: 0 !important; }
            div[data-testid="stHorizontalBlock"]:has(.item-name) > div:nth-child(2) { width: 45% !important; flex: 1 1 45% !important; min-width: 120px !important; }
        }
        div[data-baseweb="input"] > div { background-color: #0f172a !important; }
        [data-testid="stExpander"] { background-color: #1e293b !important; border-radius: 10px !important; border: 1px solid #334155 !important; margin-bottom: 8px !important; }
        [data-testid="stExpander"] summary p { font-weight: bold !important; color: #60a5fa !important; font-size: 0.95rem !important; }
        .item-name { font-size: 0.95rem; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .item-cap { font-size: 0.75rem; color: #94a3b8; }
        hr { border-top: 1px solid #334155 !important; margin: 8px 0 !important; opacity: 0.5; }
        .block-container { padding: 1.5rem 0.6rem !important; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ロジック管理 (RPC)
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        res = supabase.table("inventory").select("*").order("id").execute()
        st.session_state.inventory_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if "edits" not in st.session_state: st.session_state.edits = {}
    if "logs_df" not in st.session_state:
        res_logs = supabase.table("inventory_logs").select("*").order("created_at", desc=True).limit(75).execute()
        st.session_state.logs_df = pd.DataFrame(res_logs.data) if res_logs.data else pd.DataFrame()

def on_stock_change(item_id):
    st.session_state.edits[item_id] = float(st.session_state[f"input_{item_id}"])

def save_changes():
    if not st.session_state.edits: return
    
    # [개선 1] 저장 직전, 변경하려는 아이템들의 '최신 재고'를 DB에서 실시간으로 다시 가져옴 (동시성 방어)
    edited_ids = list(st.session_state.edits.keys())
    try:
        latest_res = supabase.table("inventory").select("id, current_stock, item_name").in_("id", edited_ids).execute()
        latest_data = {row["id"]: row for row in latest_res.data}
    except Exception as e:
        st.error(f"⚠️ 最新データの取得に失敗しました: {e}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discord_lines = []
    
    # [개선 2] 매번 기록하지 않고 로그를 배열에 모아둠 (Bulk Insert용)
    logs_to_insert = []
    successful_ids = []

    for i_id, n_val in st.session_state.edits.items():
        latest_item = latest_data.get(i_id)
        if not latest_item: continue

        # 내 캐시가 아닌 DB의 '진짜 최신값' 기준으로 계산
        latest_stock = float(latest_item["current_stock"])
        diff = float(n_val) - latest_stock
        
        if diff != 0:
            try:
                # 1. 재고 업데이트 (원자적 트랜잭션 유지)
                supabase.rpc("update_inventory_atomic", {
                    "p_id": int(i_id),
                    "p_new_stock": float(n_val),
                    "p_diff": float(diff),
                    "p_item_name": str(latest_item["item_name"]),
                    "p_before_qty": latest_stock
                }).execute()
                
                # 2. 로그를 DB에 바로 안 넣고 배열에 모으기
                logs_to_insert.append({
                    "item_name": str(latest_item["item_name"]),
                    "before_qty": latest_stock,
                    "after_qty": float(n_val),
                    "diff_qty": float(diff),
                    "created_at": now
                })
                
                # 3. 디스코드 메시지 조합
                diff_str = f"+{fmt(diff)}" if diff > 0 else f"{fmt(diff)}"
                discord_lines.append(f"> **{latest_item['item_name']}**: {fmt(latest_stock)} → **{fmt(n_val)}** ({diff_str})")
                
                successful_ids.append(i_id)
            except Exception as e:
                st.error(f"⚠️ {latest_item['item_name']} の保存に失敗しました: {e}")
        else:
            # 수정한 줄 알았는데 최신 DB값과 똑같다면 성공 처리 (목록에서 비우기 위해)
            successful_ids.append(i_id)

    # [개선 2] 모아둔 로그를 한 번의 API 통신으로 통째로 저장 (병목 해결)
    if logs_to_insert:
        try:
            supabase.table("inventory_logs").insert(logs_to_insert).execute()
        except Exception as e:
            st.error(f"⚠️ 履歴の保存に失敗しました: {e}")

    # [개선 3] 전체 초기화가 아닌, '성공한 아이템'만 에디터에서 비우기 (부분 실패 복구)
    for s_id in successful_ids:
        st.session_state.edits.pop(s_id, None)

    # 마무리가 하나라도 되었다면 리프레시 및 알림 전송
    if successful_ids:
        if discord_lines:
            discord_msg = f"📦 **[在庫更新通知]** ({now})\n" + "\n".join(discord_lines)
            send_discord_message_async(discord_msg)
            
        if "inventory_df" in st.session_state: del st.session_state.inventory_df
        if "logs_df" in st.session_state: del st.session_state.logs_df
        
        # 아직 edits에 항목이 남아있다면(실패한 것), 경고 표시
        if not st.session_state.edits:
            st.success(f"✅ すべての在庫を更新しました！")
        else:
            st.warning(f"⚠️ 一部のアイテムが保存できませんでした。入力欄を確認して再試行してください。")
            
        time.sleep(1)
        st.rerun()

# ==========================================
# 3. メイン UI
# ==========================================
def main():
    st.set_page_config(page_title="RCS 在庫管理システム", layout="centered")
    inject_custom_css()
    init_state()

    st.title("📦 RCS 在庫管理システム")
    tab1, tab2, tab3 = st.tabs(["📝 在庫更新", "📜 変更履歴", "⚙️ 管理設定"])

    # --- TAB 1: 在庫更新 ---
    with tab1:
        search = st.text_input("🔍 検索", placeholder="商品名で検索...", label_visibility="collapsed")
        
        c1, c2 = st.columns([0.6, 0.4])
        all_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else []
        sel_cat = c1.selectbox("表示カテゴリ", options=["すべて"] + all_cats, label_visibility="collapsed")
        
        if c2.button("✅ 確定保存", type="primary", use_container_width=True, disabled=not st.session_state.edits):
            save_changes()

        df = st.session_state.inventory_df
        if sel_cat != "すべて": df = df[df["category"] == sel_cat]
        if search: df = df[df['item_name'].str.contains(search, case=False, na=False)]

        for cat in sorted(df["category"].unique().tolist()):
            with st.expander(f"📂 {cat}", expanded=bool(search)):
                c_df = df[df["category"] == cat]
                for _, row in c_df.iterrows():
                    i_id = row["id"]
                    val = float(st.session_state.edits.get(i_id, row["current_stock"]))
                    icon = "🔴" if val <= float(row["min_stock"]) else "🟢"
                    
                    t, i = st.columns([6, 4])
                    t.markdown(f"""
                        <div class='item-name'>{icon} {row['item_name']}</div>
                        <div class='item-cap'>現在: {fmt(row['current_stock'])} / 目標: {fmt(row['min_stock'])} {row['unit']}</div>
                    """, unsafe_allow_html=True)
                    i.number_input("数量", value=val, step=0.5, format="%g", key=f"input_{i_id}", label_visibility="collapsed", on_change=on_stock_change, args=(i_id,))
                    st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)

    # --- TAB 2: 変更履歴 ---
    with tab2:
        st.subheader("📜 直近の変更履歴 (最新15件)")
        logs = st.session_state.logs_df
        if logs.empty: st.info("表示可能な履歴がありません。")
        else:
            for _, r in logs.head(15).iterrows():
                l1, l2 = st.columns([6, 4])
                l1.markdown(f"**{r['item_name']}**<br><small>{r['created_at']}</small>", unsafe_allow_html=True)
                diff = fmt(r['diff_qty'])
                clr = "#ef4444" if diff < 0 else "#10b981"
                l2.markdown(f"<div style='text-align:right;'><small>{fmt(r['before_qty'])} → {fmt(r['after_qty'])}</small><br><b style='color:{clr};'>{'+' if diff > 0 else ''}{diff}</b></div>", unsafe_allow_html=True)
                st.divider()

    # --- TAB 3: 管理設定 ---
    with tab3:
        st.subheader("⚙️ マスタデータ管理")
        
        # 1. 신규 아이템 등록
        with st.expander("➕ 新規アイテムの登録"):
            n_name = st.text_input("商品名")
            ex_cats = sorted(st.session_state.inventory_df["category"].unique().tolist()) if not st.session_state.inventory_df.empty else ["コーヒー"]
            n_cat_s = st.selectbox("カテゴリ選択", options=ex_cats + ["(新規作成)"])
            f_cat = n_cat_s if n_cat_s != "(新規作成)" else st.text_input("新規カテゴリ名を入力")
            
            ca, cb = st.columns(2)
            nm = ca.number_input("通知ライン (目標値)", min_value=0.0, step=0.5, format="%g")
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
                        del st.session_state.inventory_df
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ 登録に失敗しました: {e}")

        st.divider()

        # 2. 기존 아이템 편집/삭제
        if not st.session_state.inventory_df.empty:
            cur_cats = sorted(st.session_state.inventory_df["category"].unique().tolist())
            for cat in cur_cats:
                with st.expander(f"📂 {cat}"):
                    c_df = st.session_state.inventory_df[st.session_state.inventory_df["category"] == cat]
                    for _, row in c_df.iterrows():
                        rid = row["id"]
                        ek = f"em_{rid}"
                        if ek not in st.session_state: st.session_state[ek] = False
                        
                        if not st.session_state[ek]:
                            cc1, cc2 = st.columns([7, 3])
                            cc1.markdown(f"**{row['item_name']}** <small>({fmt(row['min_stock'])}{row['unit']})</small>", unsafe_allow_html=True)
                            if cc2.button("編集", key=f"e_{rid}", use_container_width=True):
                                st.session_state[ek] = True
                                st.rerun()
                        else:
                            st.markdown("---")
                            en = st.text_input("商品名", value=row["item_name"], key=f"n_{rid}")
                            ec = st.selectbox("カテゴリ", options=cur_cats, index=cur_cats.index(row["category"]), key=f"c_{rid}")
                            col_s1, col_s2 = st.columns(2)
                            em = col_s1.number_input("目標値", value=float(row["min_stock"]), step=0.5, format="%g", key=f"m_{rid}")
                            eu = col_s2.text_input("単位", value=row["unit"], key=f"u_{rid}")
                            
                            b1, b2, b3 = st.columns(3)
                            if b1.button("💾 保存", key=f"s_{rid}", type="primary", use_container_width=True):
                                supabase.table("inventory").update({
                                    "item_name": en, "category": ec, 
                                    "min_stock": float(em), "unit": eu
                                }).eq("id", rid).execute()
                                st.session_state[ek] = False
                                del st.session_state.inventory_df
                                st.rerun()
                            if b2.button("🚫 取消", key=f"b_{rid}", use_container_width=True):
                                st.session_state[ek] = False
                                st.rerun()
                            if b3.button("🗑️ 削除", key=f"d_{rid}", use_container_width=True):
                                supabase.table("inventory").delete().eq("id", rid).execute()
                                del st.session_state.inventory_df
                                st.rerun()
                        st.markdown("<hr style='margin:5px 0; opacity:0.1;'>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
