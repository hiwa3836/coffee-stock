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
    st.error("Secretsに 'site_password' が設定されていません。")
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
    st.subheader("🔒 アクセス制限") # 타이틀 크기를 subheader로 통일
    st.info("システムを利用するにはログインが必要です。")
    
    input_user = st.text_input("担当者名 (User Name)")
    input_password = st.text_input("パスワード (Password)", type="password")
    
    if st.button("ログイン"):
        if input_password == SITE_PASSWORD and input_user.strip() != "":
            st.session_state.logged_in = True
            st.session_state.user_name = input_user
            st.rerun()
        else:
            st.error("認証情報に誤りがあります。")

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

    # ⭐ 타이틀 크기를 아래 '현재 재고 상황'과 똑같은 크기(subheader)로 맞춤
    st.subheader("☕ コーヒーサークル 在庫管理")

    try:
        # 데이터 읽기
        df = conn.read(worksheet="Inventory", ttl=60)
        df.columns = df.columns.str.strip()
        df_log = conn.read(worksheet="Log", ttl=60)

        # 📊 現在の在庫状況
        st.write("") # 간격 조절
        st.subheader("📊 現在の在庫状況")
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🔄 データを強制更新"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # 📦 在庫数量の修正 (직접 입력 방식)
        st.subheader("📦 在庫数量の修正")
        item_col = df.columns[0]
        qty_col = df.columns[1]
        
        selected_item = st.selectbox("品目を選択してください", df[item_col].tolist())
        
        # 현재 수량 추출
        raw_val = df[df[item_col] == selected_item][qty_col].values[0]
        try:
            current_qty = float(raw_val)
        except:
            current_qty = 0.0

        st.info(f"現在の **{selected_item}** の在庫数: **{current_qty:.1f}**")
        
        # 직접 입력창 (소수점 1자리)
        new_qty_input = st.number_input("修正後の在庫数を入力", value=current_qty, step=0.1, format="%.1f")

        if st.button("💾 変更を保存"):
            final_qty = round(float(new_qty_input), 1)
            
            if final_qty < 0:
                st.error("❌ 在庫数は0未満に設定できません。")
            else:
                # Inventory 업데이트
                df.loc[df[item_col] == selected_item, qty_col] = final_qty
                conn.update(worksheet="Inventory", data=df)

                # Log 업데이트
                new_log = pd.DataFrame([{
                    "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "担当者": st.session_state.user_name,
                    "品目": selected_item,
                    "修正前": current_qty,
                    "修正後": final_qty,
                    "備考": "直接修正"
                }])
                updated_log = pd.concat([df_log, new_log], ignore_index=True)
                conn.update(worksheet="Log", data=updated_log)

                st.cache_data.clear()
                st.success(f"✅ 更新完了: {selected_item} → {final_qty:.1f}")
                st.rerun()

        # 🕒 入出庫履歴 (페이지네이션: 15개씩 5페이지)
        st.divider()
        st.subheader("🕒 入出庫履歴")

        if not df_log.empty:
            history_df = df_log.iloc[::-1].reset_index(drop=True)
            items_per_page = 15
            max_pages = 5
            total_limit = items_per_page * max_pages
            display_df = history_df.head(total_limit)
            
            actual_max_page = min(max_pages, (len(display_df) - 1) // items_per_page + 1)

            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ 前へ") and st.session_state.current_page > 1:
                    st.session_state.current_page -= 1
                    st.rerun()
            with col_page:
                st.write(f"**{st.session_state.current_page} / {actual_max_page} ページ**")
            with col_next:
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
            st.error("⚠️ API制限です。1分後にまた試してください。)
        else:
            st.error(f"Error: {e}")
