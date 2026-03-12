import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ページの設定
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
if "updated_msg" not in st.session_state: # 갱신 메시지 상태 추가
    st.session_state.updated_msg = False

# --- 🔑 ログイン画面 ---
def login_screen():
    st.subheader("🔒 アクセス制限") 
    st.info("システムを利用するにはログインが必要です。")
    input_user = st.text_input("担当者名 (User Name)")
    input_password = st.text_input("パスワード (Password)", type="password")
    if st.button("ログイン"):
        if input_password == SITE_PASSWORD and input_user.strip() != "":
            st.session_state.logged_in = True
            st.session_state.user_name = input_user
            st.rerun()
        else:
            st.error("認証情報가 올바르지 않습니다.")

# --- 📦 メインコンテンツ ---
if not st.session_state.logged_in:
    login_screen()
else:
    with st.sidebar:
        st.write(f"👤 担当者: **{st.session_state.user_name}**")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.rerun()

    st.subheader("☕ RCS 在庫管理")

    try:
        # 데이터 읽기
        df = conn.read(worksheet="Inventory", ttl=60)
        df.columns = df.columns.str.strip()
        old_df = df.copy()

        st.write("") 
        st.subheader("📊 現在の在庫状況")
        
        # 💡 요청하신 부분: 갱신 성공 시 초록색 메시지 표시
        if st.session_state.updated_msg:
            st.success("✅ 在庫データが正常に更新されました。 (재고 데이터가 정상적으로 갱신되었습니다.)")
            st.session_state.updated_msg = False # 표시 후 초기화

        st.info("💡 「現在数量」のみ直接修正可能です。修正後、下の保存ボタンを押してください。")

        # 컬럼 설정 (수량만 편집 가능)
        config = {}
        for i, col in enumerate(df.columns):
            if i == 1: # 수량 컬럼
                config[col] = st.column_config.NumberColumn(format="%.1f", min_value=0.0)
            else:
                config[col] = st.column_config.Column(disabled=True)

        edited_df = st.data_editor(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config=config
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 変更を保存"):
                qty_col = df.columns[1]
                diff_mask = (old_df[qty_col] != edited_df[qty_col])
                changed_rows = edited_df[diff_mask]

                if not changed_rows.empty:
                    conn.update(worksheet="Inventory", data=edited_df)

                    # Log 기록
                    df_log = conn.read(worksheet="Log", ttl=0)
                    new_logs = []
                    for _, row in changed_rows.iterrows():
                        item_name = row[df.columns[0]]
                        new_qty = row[qty_col]
                        old_qty = old_df.loc[old_df[df.columns[0]] == item_name, qty_col].values[0]
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
                    st.session_state.updated_msg = True # 메시지 상태 활성화
                    st.rerun()
                else:
                    st.warning("変更された内容がありません。")
        
        with col2:
            if st.button("🔄 データを強制更新"):
                st.cache_data.clear()
                st.rerun()

        # 🕒 히스토리
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

            curr_page = st.session_state.current_page
            st.table(display_df.iloc[(curr_page - 1) * items_per_page : curr_page * items_per_page])
        else:
            st.write("履歴がありません。")

    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ API制限に達しました。1分ほど待ってから再試行してください。")
        else:
            st.error(f"システムエラー: {e}")
