import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# =========================
# 1. ページ設定
# =========================
st.set_page_config(page_title="RCS 在庫管理", layout="centered")

# =========================
# 2. Secrets / 接続
# =========================
try:
    SITE_PASSWORD = st.secrets["site_password"]
except Exception:
    st.error("Secretsに 'site_password' が設定されていません。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# =========================
# 3. セッション初期化
# =========================
def init_session():
    defaults = {
        "logged_in": False,
        "user_name": "",
        "current_page": 1,
        "updated_msg": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# =========================
# 4. 共通関数
# =========================
def read_sheet(sheet_name: str, ttl: int = 60) -> pd.DataFrame:
    df = conn.read(worksheet=sheet_name, ttl=ttl)
    if df is None:
        return pd.DataFrame()
    df.columns = df.columns.str.strip()
    return df

def logout():
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.current_page = 1
    st.session_state.updated_msg = False
    st.rerun()

def login_screen():
    st.subheader("🔒 アクセス制限")
    st.info("システムを利用するにはログインが必要です。")

    input_user = st.text_input("担当者名 (User Name)")
    input_password = st.text_input("パスワード (Password)", type="password")

    if st.button("ログイン", use_container_width=True):
        if input_password == SITE_PASSWORD and input_user.strip():
            st.session_state.logged_in = True
            st.session_state.user_name = input_user.strip()
            st.rerun()
        else:
            st.error("認証情報が正しくありません。")

def show_update_message():
    if st.session_state.updated_msg:
        placeholder = st.empty()
        placeholder.success("✅ 更新が完了しました！")
        time.sleep(1)  # 1秒だけ表示
        placeholder.empty()
        st.session_state.updated_msg = False
        st.rerun()

def build_log_rows(changed_rows: pd.DataFrame, old_df: pd.DataFrame, item_col: str, qty_col: str):
    new_logs = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for _, row in changed_rows.iterrows():
        item_name = row[item_col]
        new_qty = row[qty_col]
        old_qty = old_df.loc[old_df[item_col] == item_name, qty_col].values[0]

        new_logs.append({
            "日時": now_str,
            "担当者": st.session_state.user_name,
            "品目": item_name,
            "修正前": old_qty,
            "修正後": new_qty,
            "備考": "テーブル直接修正"
        })

    return pd.DataFrame(new_logs)

# =========================
# 5. ログイン画面
# =========================
if not st.session_state.logged_in:
    login_screen()
    st.stop()

# =========================
# 6. メイン画面
# =========================
with st.sidebar:
    st.write(f"👤 担当者: **{st.session_state.user_name}**")
    if st.button("ログアウト", use_container_width=True):
        logout()

st.subheader("☕ RCS 在庫管理")

try:
    df = read_sheet("Inventory", ttl=60)
    old_df = df.copy()

    if df.empty:
        st.warning("Inventory シートにデータがありません。")
        st.stop()

    item_col = df.columns[0]
    qty_col = df.columns[1]

    st.write("")
    st.subheader("📊 現在の在庫状況")

    # 1秒だけ表示
    show_update_message()

    st.info("💡 「現在数量」のみ直接修正可能です。修正後、下の保存ボタンを押してください。")

    # 列設定
    column_config = {}
    for i, col in enumerate(df.columns):
        if i == 1:
            column_config[col] = st.column_config.NumberColumn(
                format="%.1f",
                min_value=0.0
            )
        else:
            column_config[col] = st.column_config.Column(disabled=True)

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        key="inventory_editor"
    )

    col1, col2 = st.columns([1, 4])

    with col1:
        if st.button("💾 変更を保存", use_container_width=True):
            diff_mask = old_df[qty_col] != edited_df[qty_col]
            changed_rows = edited_df[diff_mask]

            if changed_rows.empty:
                st.warning("変更された内容がありません。")
            else:
                # Inventory 更新
                conn.update(worksheet="Inventory", data=edited_df)

                # Log 更新
                df_log = read_sheet("Log", ttl=0)
                new_log_df = build_log_rows(changed_rows, old_df, item_col, qty_col)

                if df_log.empty:
                    updated_log = new_log_df
                else:
                    updated_log = pd.concat([df_log, new_log_df], ignore_index=True)

                conn.update(worksheet="Log", data=updated_log)

                st.cache_data.clear()
                st.session_state.updated_msg = True
                st.rerun()

    with col2:
        if st.button("🔄 データを強制更新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # =========================
    # 7. 履歴表示
    # =========================
    st.divider()
    st.subheader("🕒 入出庫履歴")

    df_log_display = read_sheet("Log", ttl=60)

    if not df_log_display.empty:
        history_df = df_log_display.iloc[::-1].reset_index(drop=True)

        items_per_page = 15
        max_pages = 5
        total_limit = items_per_page * max_pages

        display_df = history_df.head(total_limit)
        actual_max_page = max(1, min(max_pages, (len(display_df) - 1) // items_per_page + 1))

        # 현재 페이지 보정
        if st.session_state.current_page > actual_max_page:
            st.session_state.current_page = actual_max_page
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1

        p_col_prev, p_col_page, p_col_next = st.columns([1, 2, 1])

        with p_col_prev:
            if st.button("⬅️ 前へ", use_container_width=True) and st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                st.rerun()

        with p_col_page:
            st.write(f"**{st.session_state.current_page} / {actual_max_page} ページ**")

        with p_col_next:
            if st.button("次へ ➡️", use_container_width=True) and st.session_state.current_page < actual_max_page:
                st.session_state.current_page += 1
                st.rerun()

        start_idx = (st.session_state.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page

        st.table(display_df.iloc[start_idx:end_idx])
    else:
        st.info("履歴データがありません。")

except Exception as e:
    if "429" in str(e):
        st.error("⚠️ API制限に達しました。1分ほど待ってから再試行してください。")
    else:
        st.error(f"システムエラー: {e}")
