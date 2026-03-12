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
        "base_inventory_df": None,   # 사용자가 편집 시작한 기준 스냅샷
        "inventory_loaded": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# =========================
# 4. 共通関数
# =========================
def read_sheet(sheet_name: str, ttl: int = 30) -> pd.DataFrame:
    df = conn.read(worksheet=sheet_name, ttl=ttl)
    if df is None:
        return pd.DataFrame()
    df.columns = df.columns.str.strip()
    return df

def write_sheet(sheet_name: str, df: pd.DataFrame):
    conn.update(worksheet=sheet_name, data=df)

def logout():
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.current_page = 1
    st.session_state.base_inventory_df = None
    st.session_state.inventory_loaded = False
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

def ensure_inventory_loaded():
    """
    최초 진입/강제새로고침 시에만 기준 inventory를 세션에 적재
    """
    if (not st.session_state.inventory_loaded) or (st.session_state.base_inventory_df is None):
        df = read_sheet("Inventory", ttl=0)
        if df.empty:
            return pd.DataFrame()
        st.session_state.base_inventory_df = df.copy()
        st.session_state.inventory_loaded = True
    return st.session_state.base_inventory_df.copy()

def refresh_inventory():
    df = read_sheet("Inventory", ttl=0)
    st.session_state.base_inventory_df = df.copy() if not df.empty else pd.DataFrame()
    st.session_state.inventory_loaded = True

def validate_inventory_df(df: pd.DataFrame):
    if df.empty:
        return False, "Inventory シートにデータがありません。"

    if len(df.columns) < 2:
        return False, "Inventory シートの列数が不足しています。少なくとも2列必要です。"

    item_col = df.columns[0]
    qty_col = df.columns[1]

    if df[item_col].duplicated().any():
        dupes = df[df[item_col].duplicated()][item_col].astype(str).tolist()
        return False, f"品目名が重複しています: {', '.join(dupes[:5])}"

    return True, ""

def normalize_for_compare(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)

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

def save_inventory_safely(base_df: pd.DataFrame, edited_df: pd.DataFrame):
    """
    동시 수정 충돌을 회피하는 저장 로직

    흐름:
    1) 사용자가 처음 본 기준 데이터(base_df)와 edited_df 비교해서 내가 바꾼 행 파악
    2) 저장 직전에 최신 시트(latest_df) 재조회
    3) 내가 바꾸려는 행이 latest_df에서 이미 달라졌으면 충돌로 중단
    4) 충돌 없으면 latest_df에 내 변경만 반영 후 update
    """
    is_valid, msg = validate_inventory_df(base_df)
    if not is_valid:
        return False, msg

    is_valid, msg = validate_inventory_df(edited_df)
    if not is_valid:
        return False, msg

    item_col = base_df.columns[0]
    qty_col = base_df.columns[1]

    base_compare = normalize_for_compare(base_df[qty_col])
    edited_compare = normalize_for_compare(edited_df[qty_col])

    diff_mask = base_compare != edited_compare
    changed_rows = edited_df[diff_mask].copy()

    if changed_rows.empty:
        return False, "変更された内容がありません。"

    # 최신 시트 재조회
    latest_df = read_sheet("Inventory", ttl=0)
    if latest_df.empty:
        return False, "最新の Inventory を取得できませんでした。"

    is_valid, msg = validate_inventory_df(latest_df)
    if not is_valid:
        return False, msg

    latest_item_col = latest_df.columns[0]
    latest_qty_col = latest_df.columns[1]

    # 컬럼 구조 다르면 중단
    if item_col != latest_item_col or qty_col != latest_qty_col:
        return False, "保存中に Inventory シートの列構成が変更されました。再読み込みしてください。"

    # 품목 세트 동일 여부 확인
    base_items = set(base_df[item_col].astype(str))
    latest_items = set(latest_df[item_col].astype(str))
    if base_items != latest_items:
        return False, "保存中に品目一覧が変更されました。再読み込みしてください。"

    # index를 품목명 기준으로 맞춤
    base_indexed = base_df.set_index(item_col)
    latest_indexed = latest_df.set_index(item_col)
    changed_indexed = changed_rows.set_index(item_col)

    conflict_items = []

    for item_name in changed_indexed.index:
        base_qty = pd.to_numeric(base_indexed.at[item_name, qty_col], errors="coerce")
        latest_qty = pd.to_numeric(latest_indexed.at[item_name, qty_col], errors="coerce")

        # 내가 편집 시작한 뒤, 다른 사람이 이미 바꿈
        if pd.isna(base_qty):
            base_qty = 0
        if pd.isna(latest_qty):
            latest_qty = 0

        if float(base_qty) != float(latest_qty):
            conflict_items.append(str(item_name))

    if conflict_items:
        conflict_preview = "、".join(conflict_items[:5])
        return False, f"他のユーザーが先に更新しました。競合品目: {conflict_preview}。再読み込み後にやり直してください。"

    # 충돌 없으면 최신 시트에 내 변경만 merge
    merged_df = latest_df.copy().set_index(item_col)

    for item_name, row in changed_indexed.iterrows():
        merged_df.at[item_name, qty_col] = row[qty_col]

    merged_df = merged_df.reset_index()

    # Inventory 저장
    write_sheet("Inventory", merged_df)

    # Log 저장
    latest_log_df = read_sheet("Log", ttl=0)
    new_log_df = build_log_rows(changed_rows, base_df, item_col, qty_col)

    if latest_log_df.empty:
        updated_log = new_log_df
    else:
        updated_log = pd.concat([latest_log_df, new_log_df], ignore_index=True)

    write_sheet("Log", updated_log)

    # 저장 성공 후 세션 기준 데이터도 최신으로 갱신
    st.session_state.base_inventory_df = merged_df.copy()
    st.session_state.inventory_loaded = True

    return True, "✅ 更新が完了しました！"

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
    base_df = ensure_inventory_loaded()

    if base_df.empty:
        st.warning("Inventory シートにデータがありません。")
        st.stop()

    is_valid, msg = validate_inventory_df(base_df)
    if not is_valid:
        st.error(msg)
        st.stop()

    item_col = base_df.columns[0]
    qty_col = base_df.columns[1]

    st.subheader("📊 現在の在庫状況")

    guide_box = st.empty()
    guide_text = "💡 「現在数量」のみ直接修正可能です。修正後、保存ボタンを押してください。"
    guide_box.info(guide_text)

    # 列設定
    column_config = {}
    for i, col in enumerate(base_df.columns):
        if i == 1:
            column_config[col] = st.column_config.NumberColumn(
                format="%.1f",
                min_value=0.0
            )
        else:
            column_config[col] = st.column_config.Column(disabled=True)

    edited_df = st.data_editor(
        base_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        key="inventory_editor"
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("💾 変更を保存", use_container_width=True):
            ok, message = save_inventory_safely(
                st.session_state.base_inventory_df.copy(),
                edited_df.copy()
            )

            if ok:
                guide_box.success("✅ 更新が完了しました！")
                time.sleep(0.8)
                st.rerun()
            else:
                warning_box = guide_box.warning(message)
                time.sleep(5)
                warning_box.empty()
                guide_box.info(guide_text)

    with col2:
        if st.button("🔄 データを再読み込み", use_container_width=True):
            refresh_inventory()
            guide_box.success("🔄 最新データを再読み込みしました。")
            time.sleep(0.8)
            st.rerun()

    # =========================
    # 7. 履歴表示
    # =========================
    st.divider()
    st.subheader("🕒 入出庫履歴")

    df_log_display = read_sheet("Log", ttl=30)

    if not df_log_display.empty:
        history_df = df_log_display.iloc[::-1].reset_index(drop=True)

        items_per_page = 15
        max_pages = 5
        total_limit = items_per_page * max_pages

        display_df = history_df.head(total_limit)
        actual_max_page = max(1, min(max_pages, (len(display_df) - 1) // items_per_page + 1))

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
        st.error("⚠️ API制限に達しました。しばらく待ってから再試行してください。")
    else:
        st.error(f"システムエラー: {e}")
