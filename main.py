import streamlit as st
import pandas as pd
import time
import requests
import threading
import io  # 엑셀 다운로드를 위한 메모리 버퍼 용도
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
    
    edited_ids = list(st.session_state.edits.keys())
    try:
        latest_res = supabase.table("inventory").select("id, current_stock, item_name").in_("id", edited_ids).execute()
        latest_data = {row["id"]: row for row in latest_res.data}
    except Exception as e:
        st.error(f"⚠️ 最新データの取得に失敗しました: {e}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discord_lines = []
    
    logs_to_insert = []
    successful_ids = []

    for i_id, n_val in st.session_state.edits.items():
        latest_item = latest_data.get(i_id)
        if not latest_item: continue

        latest_stock = float(latest_item["current_stock"])
        diff = float(n_val) - latest_stock
        
        if diff != 0:
            try:
                supabase.rpc("update_inventory_atomic", {
                    "p_id": int(i_id),
                    "p_new_stock": float(n_val),
                    "p_diff": float(diff),
                    "p_item_name": str(latest_item["item_name"]),
                    "p_before_qty": latest_stock
                }).execute()
                
                logs_to_insert.append({
                    "item_name": str(latest_item["item_name"]),
                    "before_qty": latest_stock,
                    "after_qty": float(n_val),
                    "diff_qty": float(diff),
                    "created_at": now
                })
                
                diff_str = f"+{fmt(diff)}" if diff > 0 else f"{fmt(diff)}"
                discord_lines.append(f"> **{latest_item['item_name']}**: {fmt(latest_stock)} → **{fmt(n_val)}** ({diff_str})")
                
                successful_ids.append(i_id)
            except Exception as e:
                st.error(f"⚠️ {latest_item['item_name']} の保存に失敗しました: {e}")
        else:
            successful_ids.append(i_id)

    if logs_to_insert:
        try:
            supabase.table("inventory_logs").insert(logs_to_insert).execute()
        except Exception as e:
            st.error(f"⚠️ 履歴の保存に失敗しました: {e}")

    for s_id in successful_ids:
        st.session_state.edits.pop(s_id, None)

    if successful_ids:
        if discord_lines:
            discord_msg = f"📦 **[在庫更新通知]** ({now})\n" + "\n".join(discord_lines)
            send_discord_message_async(discord_msg)
            
        if "inventory_df" in st.session_state: del st.session_state.inventory_df
        if "logs_df" in st.session_state: del st.session_state.logs_df
        
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

    # --- TAB 2: 変更履歴 (Excel ダウンロード機能追加) ---
    with tab2:
        st.subheader("📜 直近の変更履歴 (最新15件)")
        logs = st.session_state.logs_df
        
        if logs.empty: 
            st.info("表示可能な履歴がありません。")
        else:
            # Excel ダウンロードボタンの配置
            buffer = io.BytesIO()
            export_df = logs.copy()
            
# 日付のフォーマット処理 (타임존 에러 방지 및 안전한 변환)
            export_df['created_at'] = pd.to_datetime(
                export_df['created_at'], 
                errors='coerce', # 포맷이 이상한 데이터가 있어도 앱이 죽지 않게 함
                utc=True         # Supabase의 UTC 시간 형식을 인식하게 함
            ).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # カラム명을 日本語로 변경 (이 부분은 기존과 동일)
            export_df = export_df.rename(columns={
                'created_at': '変更日時',
                'item_name': '商品명',
                'before_qty': '変更前',
                'after_qty': '変更後',
                'diff_qty': '変動量'
            })
            
            # 必要なカラムのみ抽出
            export_df = export_df[['変更日時', '商品名', '変更前', '変更後', '変動量']]
            
            # メモリバッファにExcelとして書き込み
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='変更履歴')
            
            # ダウンロードボタン
            st.download_button(
                label="📥 履歴データをExcelでダウンロード",
                data=buffer.getvalue(),
                file_name=f"Inventory_Logs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.markdown("<hr style='margin-top: 10px; margin-bottom: 15px;'>", unsafe_allow_html=True)

            # 画面には最新15件のみ表示
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
