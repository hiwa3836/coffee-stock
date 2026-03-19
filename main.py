import streamlit as st
import pandas as pd
import time
from datetime import datetime

# 쪼개놓은 파일들에서 기능 가져오기
from database import supabase
from styles import inject_custom_css
from utils import fmt, send_discord_message_async, generate_current_stock_excel, generate_logs_excel

# ==========================================
# 1. ロジック管理 (상태 관리 및 저장 로직)
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
# 2. メイン UI (화면 구성)
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

    # --- TAB 2: 変更履歴 (Excel 버튼이 엄청나게 깔끔해짐!) ---
    with tab2:
        st.subheader("📜 直近の変更履歴 (最新15件)")
        
        col_dl1, col_dl2 = st.columns(2)
        
        # 1. 現在の在庫 DL 버튼
        if not st.session_state.inventory_df.empty:
            with col_dl1:
                st.download_button(
                    label="📦 現在の在庫データをDL",
                    data=generate_current_stock_excel(st.session_state.inventory_df), # utils.py의 함수 호출!
                    file_name=f"Current_Stock_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        # 2. 変更履歴 DL 버튼
        logs = st.session_state.logs_df
        if not logs.empty:
            with col_dl2:
                st.download_button(
                    label="📥 履歴データをDL",
                    data=generate_logs_excel(logs), # utils.py의 함수 호출!
                    file_name=f"Inventory_Logs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        st.markdown("<hr style='margin-top: 10px; margin-bottom: 15px;'>", unsafe_allow_html=True)

        if logs.empty:
            st.info("表示可能な履歴がありません。")
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
