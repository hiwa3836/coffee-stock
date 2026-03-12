import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ページの設定 (브라우저 탭 설정)
st.set_page_config(page_title="RCS 在庫管理", layout="centered")

# 패스워드 설정
try:
    SITE_PASSWORD = st.secrets["site_password"]
except:
    st.error("Secretsに 'site_password' 가 설정되지 않았습니다.")
    st.stop()

# 2. Google Sheets 接続
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. セッション状態の初期化
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = 1

# --- 🔑 ログイン画面 ---
def login_screen():
    st.subheader("🔒 アクセ스 제한") 
    st.info("システムを利用するにはログインが必要です。")
    
    input_user = st.text_input("担当者名 (User Name)")
    input_password = st.text_input("パスワード (Password)", type="password")
    
    if st.button("ログイン"):
        if input_password == SITE_PASSWORD and input_user.strip() != "":
            st.session_state.logged_in = True
            st.session_state.user_name = input_user
            st.rerun()
        else:
            st.error("認証情報が正しくありません。")

# --- 📦 メインコンテンツ ---
if not st.session_state.logged_in:
    login_screen()
else:
    # 사이드바 설정
    with st.sidebar:
        st.write(f"👤 担当者: **{st.session_state.user_name}**")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.session_state.current_page = 1
            st.rerun()

    # 타이틀 설정 (subheader로 크기 통일)
    st.subheader("☕ RCS 在庫管理")

    try:
        # 데이터 읽기
        df = conn.read(worksheet="Inventory", ttl=60)
        df.columns = df.columns.str.strip()
        
        # 원본 데이터 보관 (변경점 비교용)
        old_df = df.copy()

        st.write("") 
        st.subheader("📊 在庫状況 (直接修正可能)")
        st.info("💡 表の中の数値を直接クリックして修正した後、下の「変更保存」ボタンを押してください。")

        # ⭐ 핵심: 표 안에서 직접 수정 (st.data_editor)
        edited_df = st.data_editor(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                df.columns[0]: st.column_config.TextColumn(disabled=True), # 품목명 수정 불가
                df.columns[1]: st.column_config.NumberColumn(format="%.1f") # 수량 소수점 1자리
            }
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 変更を保存"):
                # 변경된 행 추출
                diff_mask = (old_df.iloc[:, 1] != edited_df.iloc[:, 1])
                changed_rows = edited_df[diff_mask]

                if not changed_rows.empty:
                    # 1. Inventory 시트 업데이트
                    conn.update(worksheet="Inventory", data=edited_df)

                    # 2. Log 업데이트 (변경된 모든 항목 기록)
                    df_log = conn.read(worksheet="Log", ttl=0)
                    new_logs = []
                    for _, row in changed_rows.iterrows():
                        item_name = row[0]
                        new_qty = row[1]
                        old_qty = old_df.loc[old_df[df.columns[0]] == item_name, df.columns[1]].values[0]
                        
                        new_logs.append({
                            "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "担当者": st.session_state.user_name,
                            "品目": item_name,
                            "修正前": old_qty,
                            "修正後": new_qty,
                            "備考": "テーブル直接修正"
                        })
                    
                    new_log_df = pd.DataFrame(new_logs)
                    updated_log = pd.concat([df_log, new_log_df], ignore_index=True)
                    conn.update(worksheet="Log", data=updated_log)

                    st.cache_data.clear()
                    st.success("✅ 全ての変更が保存されました！")
                    st.rerun()
                else:
                    st.warning("変更された内容がありません。")
        
        with col2:
            if st.button("🔄 データを強制更新"):
                st.cache_data.clear()
                st.rerun()

        # 🕒 入出庫履歴 (15개씩 5페이지)
        st.divider()
        st.subheader("🕒 入出庫履歴")

        df_log_display = conn.read(worksheet="Log", ttl=60)
        if not df_log_display.empty:
            history_df = df_log_display.iloc[::-1].reset_index(drop=True)
            items_per_page = 15
            max_pages = 5
            total_limit = items_per_page * max_pages
            display_df = history_df.head(total_limit)
            
            actual_max_page = min(max_pages, (len(display_df) - 1) // items_per_page + 1)

            p_col_prev, p_col_page, p_col_next = st.columns([1, 2, 1])
            with p_col_prev:
                if st.button("⬅️ 前へ") and st.session_state.current_page > 1:
                    st.session_state.current_page -= 1
                    st.rerun()
            with p_col_page:
                st.write(f"**{st.session_state.current_page} / {actual_max_page} ページ**")
            with p_col_next:
                if st.button("次へ ➡️") and st.session_state.current_page < actual_max_page:
                    st.session_state.current_page += 1
                    st.rerun()

            start_idx = (st.session_state.current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            st.table(display_df.iloc[start_idx:end_idx])
        else:
            st.write("履歴がありません。")

    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ API制限に達しました。1分ほど待ってから再試행してください。")
        else:
            st.error(f"システムエラー: {e}")
