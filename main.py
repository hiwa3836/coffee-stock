import streamlit as st
import pandas as pd
import time
import requests # <-- 이거 필수!
from datetime import datetime

# 발급받으신 디스코드 웹훅 URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1483110270963286100/9MGwwhiTZ-LR3Hk0GcezOwBskFrTV1dfcs9mONHJEzAF6RLBhdkj3e2bIGvljpDAfp-z"

def send_discord_message(content):
    """디스코드로 메시지를 쏘는 마법의 함수"""
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as e:
        print(f"Discord Webhook Error: {e}")

# ==========================================
# 1. モバイル最適化 CSS (모바일 최적화 CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        .sticky-bottom-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 12px 20px;
            box-shadow: 0px -4px 12px rgba(0, 0, 0, 0.05);
            z-index: 99999;
            border-top: 1px solid #e2e8f0;
        }
        #MainMenu, footer {visibility: hidden;}
        .block-container {
            padding-bottom: 120px !important;
            padding-top: 1rem !important;
        }
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {
            border-bottom: 1px solid #f1f5f9;
            padding: 10px 0;
        }
        input[type="number"] {
            text-align: center;
            font-size: 1.2rem;
            font-weight: bold;
        }
        button[title="Step up"], button[title="Step down"] {
            display: none; 
        }
        [data-testid="stExpander"] {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 状態管理 (상태 관리)
# ==========================================
def init_state():
    if "inventory_df" not in st.session_state:
        st.session_state.inventory_df = pd.DataFrame({
            "id": [1, 2, 3, 4],
            "category": ["コーヒー豆", "コーヒー豆", "消耗品", "衛生用品"],
            "item_name": ["エチオピア 1kg", "グアテマラ 1kg", "紙コップ(大)", "消毒液"],
            "current_stock": [5, 2, 100, 1],
            "min_stock": [3, 3, 50, 2],
            "unit": ["袋", "袋", "個", "本"]
        })
    if "edits" not in st.session_state:
        st.session_state.edits = {}
    
    # 💡 로그 데이터 구조 변경: 변경 전(before), 변경 후(after), 차이(diff)를 명시
    if "logs_df" not in st.session_state:
        mock_logs = []
        for i in range(1, 16):
            before = 10 + (i % 3)
            diff = -(i % 4) if i % 2 == 0 else (i % 2) + 1
            after = before + diff
            mock_logs.append({
                "id": i, 
                "date": f"2026-03-1{8-(i//5)} 21:0{i%10}", 
                "item": "エチオピア 1kg" if i%2==0 else "紙コップ(大)", 
                "before": before,
                "after": after,
                "diff": diff,
                "user": "管理者"
            })
        st.session_state.logs_df = pd.DataFrame(mock_logs)
    
    if "categories" not in st.session_state:
        st.session_state.categories = ["コーヒー豆", "消耗品", "衛生用品", "シロップ", "その他"]

    if "log_page" not in st.session_state: st.session_state.log_page = 1

# --- Callbacks ---
def on_stock_change(item_id):
    new_val = st.session_state[f"input_{item_id}"]
    st.session_state.edits[item_id] = new_val

def add_new_item(name, cat, min_stock, unit):
    if name.strip() == "": return
    new_id = int(st.session_state.inventory_df["id"].max() + 1) if not st.session_state.inventory_df.empty else 1
    new_row = pd.DataFrame([{
        "id": new_id, "category": cat, "item_name": name, 
        "current_stock": 0, "min_stock": min_stock, "unit": unit
    }])
    st.session_state.inventory_df = pd.concat([st.session_state.inventory_df, new_row], ignore_index=True)

def update_item(item_id, new_name, new_cat, new_min, new_unit):
    if new_name.strip() == "": return
    idx = st.session_state.inventory_df.index[st.session_state.inventory_df["id"] == item_id].tolist()[0]
    st.session_state.inventory_df.at[idx, "item_name"] = new_name
    st.session_state.inventory_df.at[idx, "category"] = new_cat
    st.session_state.inventory_df.at[idx, "min_stock"] = new_min
    st.session_state.inventory_df.at[idx, "unit"] = new_unit

def delete_item(item_id):
    st.session_state.inventory_df = st.session_state.inventory_df[st.session_state.inventory_df["id"] != item_id].reset_index(drop=True)
    if item_id in st.session_state.edits:
        del st.session_state.edits[item_id]

# ==========================================
# 3. メイン画面 (메인 화면)
# ==========================================
def main():
    st.set_page_config(page_title="在庫管理システム", layout="centered", initial_sidebar_state="collapsed")
    inject_custom_css()
    init_state()

    st.title("📦 現場在庫管理")
    
    tab1, tab2, tab3 = st.tabs(["📝 日次棚卸", "📋 変更履歴", "⚙️ アイテム管理"])

    # ----------------------------------------
    # TAB 1: 日次棚卸 (일일 실사)
    # ----------------------------------------
    with tab1:
        st.caption("退勤前に倉庫の実際の在庫数をタップして入力してください。")
        
        filter_options = ["すべて"] + st.session_state.categories
        f_col1, f_col2 = st.columns([4, 6], vertical_alignment="center")
        with f_col1:
            st.markdown("<span style='font-size: 0.9rem; color: gray;'>🔍 カテゴリ</span>", unsafe_allow_html=True)
        with f_col2:
            selected_cat = st.selectbox("カテゴリフィルター", options=filter_options, label_visibility="collapsed")
        st.markdown("<hr style='margin: 5px 0px 10px 0px; padding: 0;'/>", unsafe_allow_html=True)

        df = st.session_state.inventory_df
        if selected_cat != "すべて":
            df = df[df["category"] == selected_cat]
        
        if df.empty:
            st.info("このカテゴリにはアイテムがありません。")
        else:
            for _, row in df.iterrows():
                item_id = row["id"]
                current_display_val = st.session_state.edits.get(item_id, row["current_stock"])
                status = "🔴" if current_display_val <= row["min_stock"] else "🟢"

                col1, col2 = st.columns([6, 4], vertical_alignment="center")
                with col1:
                    st.markdown(f"**{status} {row['item_name']}**")
                    st.caption(f"{row['category']} | 最小: {row['min_stock']}{row['unit']}")
                with col2:
                    st.number_input(
                        label="数量", value=int(current_display_val), min_value=0, step=1,
                        key=f"input_{item_id}", label_visibility="collapsed",
                        on_change=on_stock_change, args=(item_id,)
                    )

        has_changes = len(st.session_state.edits) > 0
        st.markdown('<div class="sticky-bottom-bar">', unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        c1.markdown(f"**📝 {len(st.session_state.edits)}件の変更**")
        
        if c2.button("✅ 一括保存", type="primary", use_container_width=True, disabled=not has_changes):
            with st.spinner("データベースに保存中..."):
                time.sleep(0.5) 
                
                new_logs = []
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 디스코드 전송용 메시지 조립 시작
                discord_msg = f"📦 **[在庫の棚卸し完了]** ({now_str})\n"
                discord_msg += "🔄 **変更履歴:**\n"
                
                alert_items = [] # 재고 부족 품목 모아두기
                
                for i_id, new_val in st.session_state.edits.items():
                    item_row = st.session_state.inventory_df[st.session_state.inventory_df["id"] == i_id].iloc[0]
                    before_val = item_row["current_stock"]
                    min_val = item_row["min_stock"]
                    item_name = item_row["item_name"]
                    diff = new_val - before_val
                    
                    if diff != 0:
                        # 1. 앱 내부 로그용 데이터 저장
                        new_logs.append({
                            "id": int(time.time() * 1000) + i_id,
                            "date": now_str,
                            "item": item_name,
                            "before": before_val,
                            "after": new_val,
                            "diff": diff,
                            "user": "管理者"
                        })
                        
                        # 2. 디스코드 메시지에 변경 내역 한 줄씩 추가
                        sign = "+" if diff > 0 else ""
                        discord_msg += f"> {item_name}: {before_val} → **{new_val}** ({sign}{diff})\n"
                        
                    # 3. 변경 후 수량이 최소 재고보다 작거나 같으면 알람 목록에 추가
                    if new_val <= min_val:
                        alert_items.append(f"- **{item_name}** (現在: {new_val} / 最小: {min_val})")
                    
                    # 실제 재고 수치 업데이트 (앱 내부)
                    st.session_state.inventory_df.loc[st.session_state.inventory_df["id"] == i_id, "current_stock"] = new_val
                
                # 디스코드 발주 알람 텍스트 추가
                if alert_items:
                    discord_msg += "\n🚨 **[発注アラート] 在庫不足です！至急確認してください。**\n"
                    discord_msg += "\n".join(alert_items)
                
                # 🚀 디스코드로 빵야!
                send_discord_message(discord_msg)
                
                if new_logs:
                    st.session_state.logs_df = pd.concat([pd.DataFrame(new_logs), st.session_state.logs_df], ignore_index=True)

                st.session_state.edits = {} 
                st.success("在庫状況が保存され、Discordに通知されました！")
                time.sleep(1)
                st.rerun()
    # ----------------------------------------
    # TAB 2: 変更履歴 (변경 이력)
    # ----------------------------------------
    with tab2:
        st.subheader("📋 在庫変更履歴")
        logs = st.session_state.logs_df
        ITEMS_PER_PAGE = 10
        total_pages = max(1, (len(logs) - 1) // ITEMS_PER_PAGE + 1)
        
        if st.session_state.log_page > total_pages: st.session_state.log_page = total_pages
        start_idx = (st.session_state.log_page - 1) * ITEMS_PER_PAGE
        paged_logs = logs.iloc[start_idx : start_idx + ITEMS_PER_PAGE]

        for _, row in paged_logs.iterrows():
            with st.container():
                l_col1, l_col2 = st.columns([6, 4])
                
                # 왼쪽: 아이템명과 날짜 (흰색 글씨 기본 적용)
                l_col1.markdown(f"<span style='color:#ffffff; font-weight:bold;'>{row['item']}</span><br><small style='color:#94a3b8;'>{row['date']} | {row['user']}</small>", unsafe_allow_html=True)
                
                # 오른쪽: 증가/감소 수치 계산 및 컬러 지정
                diff = row['diff']
                diff_color = "#ef4444" if diff < 0 else "#10b981" # 감소는 빨간색, 증가는 초록색
                diff_sign = "+" if diff > 0 else ""
                
                # 다크모드에 최적화된 흰색 + 강조 색상 혼합 디자인
                change_html = f"""
                <div style='text-align:right;'>
                    <span style='font-size: 0.85rem; color: #a1a1aa;'>{row['before']} → {row['after']}</span><br>
                    <span style='font-size: 1.15rem; font-weight:bold; color: {diff_color};'>{diff_sign}{diff}</span> 
                    <span style='color: #ffffff; font-size: 0.9rem;'></span>
                </div>
                """
                l_col2.markdown(change_html, unsafe_allow_html=True)
                st.divider()

        p1, p2, p3 = st.columns(3)
        if p1.button("⬅️ 前へ", key="log_prev", disabled=st.session_state.log_page == 1):
            st.session_state.log_page -= 1; st.rerun()
        p2.markdown(f"<div style='text-align: center; margin-top: 5px; color:#ffffff;'><b>{st.session_state.log_page}</b> / {total_pages}</div>", unsafe_allow_html=True)
        if p3.button("次へ ➡️", key="log_next", disabled=st.session_state.log_page == total_pages):
            st.session_state.log_page += 1; st.rerun()

    # ----------------------------------------
    # TAB 3: アイテム管理 (품목 관리: 추가/수정/삭제)
    # ----------------------------------------
    with tab3:
        st.subheader("⚙️ アイテム設定")
        
        with st.expander("➕ 新しいアイテムを追加", expanded=False):
            n_name = st.text_input("アイテム名", placeholder="例: 牛乳 1L", key="new_name")
            n_cat = st.selectbox("カテゴリ", options=st.session_state.categories, key="new_cat")
            nc1, nc2 = st.columns(2)
            n_min = nc1.number_input("最小在庫数", min_value=0, value=0, step=1, key="new_min")
            n_unit = nc2.text_input("単位", placeholder="例: 本, 袋", key="new_unit")
            
            if st.button("追加", type="primary", use_container_width=True):
                add_new_item(n_name, n_cat, n_min, n_unit)
                st.success(f"{n_name} を追加しました！")
                time.sleep(0.5)
                st.rerun()
                
        st.divider()
        st.caption("👇 登録済みのアイテムをタップして編集・削除できます。")
        
        for _, row in st.session_state.inventory_df.iterrows():
            i_id = row['id']
            with st.expander(f"📦 {row['item_name']} ({row['category']})"):
                e_name = st.text_input("アイテム名", value=row['item_name'], key=f"e_name_{i_id}")
                cat_index = st.session_state.categories.index(row['category']) if row['category'] in st.session_state.categories else 0
                e_cat = st.selectbox("カテゴリ", options=st.session_state.categories, index=cat_index, key=f"e_cat_{i_id}")
                
                ec1, ec2 = st.columns(2)
                e_min = ec1.number_input("最小在庫数", value=int(row['min_stock']), min_value=0, step=1, key=f"e_min_{i_id}")
                e_unit = ec2.text_input("単位", value=row['unit'], key=f"e_unit_{i_id}")
                
                bc1, bc2 = st.columns(2)
                if bc1.button("✅ 保存", key=f"save_{i_id}", use_container_width=True):
                    update_item(i_id, e_name, e_cat, e_min, e_unit)
                    st.success("保存しました！")
                    time.sleep(0.5)
                    st.rerun()
                if bc2.button("❌ 削除", key=f"del_{i_id}", use_container_width=True):
                    delete_item(i_id)
                    st.warning("削除しました。")
                    time.sleep(0.5)
                    st.rerun()

if __name__ == "__main__":
    main()
