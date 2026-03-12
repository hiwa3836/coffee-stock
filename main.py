import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ページの設定
st.set_page_config(page_title="RCS 在庫管理システム v2", layout="centered")

# 2. Google Sheets 接続
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. セッション状態の初期化（ログイン管理用）
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""

# --- サイドバー：ユーザー認証 ---
with st.sidebar:
    st.header("🔐 ユーザー認証")
    if not st.session_state.logged_in:
        user_input = st.text_input("ユーザー名を入力してください")
        if st.button("ログイン"):
            if user_input.strip():
                st.session_state.logged_in = True
                st.session_state.user_name = user_input
                st.rerun()
            else:
                st.warning("名前を入力してください。")
    else:
        st.write(f"✅ ログイン中: **{st.session_state.user_name}** さん")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.session_state.user_name = ""
            st.rerun()

# --- メインロジック（ログイン時のみ表示） ---
if st.session_state.logged_in:
    st.title("☕ RCS 在庫管理システム")

    try:
        # データの読み込み（2つのワークシートを使用）
        # 1. 在庫状況シート (Inventory)
        df = conn.read(worksheet="Inventory", ttl=0) # リアルタイム性を高めるためttl=0
        df.columns = df.columns.str.strip()
        
        # 2. 履歴記録シート (Log)
        df_log = conn.read(worksheet="Log", ttl=0)

        # 現在の在庫状況を表示
        st.subheader("📊 現在の在庫状況")
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🔄 データを更新"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # 在庫調整セクション
        st.subheader("📦 在庫の調整と記録")
        
        item_col = df.columns[0] # 品目名の列
        qty_col = df.columns[1]  # 数量の列
        
        selected_item = st.selectbox("調整する品目を選択してください", df[item_col].tolist())
        
        # 現在の在庫数を取得
        raw_qty = df[df[item_col] == selected_item][qty_col].values[0]
        current_qty = int(raw_qty) if str(raw_qty).isdigit() else 0

        st.info(f"現在の **{selected_item}** の在庫数: **{current_qty}**")

        # 変更数量の入力（0やマイナスも入力可能に設定）
        diff = st.number_input("変更数量を入力 (+入庫, -出庫)", value=0, step=1)

        if st.button("💾 データを保存 (履歴に記録)"):
            # 在庫データの計算と更新
            new_qty = current_qty + diff
            df.loc[df[item_col] == selected_item, qty_col] = new_qty
            
            # 1. 在庫シートを更新
            conn.update(worksheet="Inventory", data=df)

            # 2. 履歴（ログ）データの作成と追加
            new_log = pd.DataFrame([{
                "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "担当者": st.session_state.user_name,
                "品目": selected_item,
                "変動": diff,
                "最終在庫": new_qty
            }])
            
            # 既存のログに新しいログを結合
            updated_log = pd.concat([df_log, new_log], ignore_index=True)
            
            # 2. 履歴シートを更新
            conn.update(worksheet="Log", data=updated_log)

            st.success(f"✅ {selected_item} の在庫が {new_qty} に更新され、履歴に記録されました！")
            st.balloons()
            st.rerun()

        # 直近の履歴を表示（任意）
        with st.expander("🕒 直近の入出庫履歴を表示"):
            if not df_log.empty:
                st.table(df_log.tail(10)) # 最新の10件を表示
            else:
                st.write("履歴はまだありません。")

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.info("Googleスプレッドシートに 'Inventory' と 'Log' という名前のシートがあるか確認してください。")

else:
    st.warning("左側のサイドバーからログインしてください。")
