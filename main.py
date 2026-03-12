import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ページの設定
st.set_page_config(page_title="RCS 在庫管理システム v3", layout="centered")

# 비밀번호 설정 (Streamlit Secrets)
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

# --- 🔑 ログイン画面 ---
def login_screen():
    st.title("🔒 アクセ스 제한 (Access Restricted)")
    st.info("システムを利用するにはログインが必要です。")
    
    with st.container():
        input_user = st.text_input("担当者名 (User Name)")
        input_password = st.text_input("パスワード (Password)", type="password")
        
        if st.button("ログイン"):
            if input_password == SITE_PASSWORD and input_user.strip() != "":
                st.session_state.logged_in = True
                st.session_state.user_name = input_user
                st.success("認証に成功しました！")
                st.rerun()
            elif input_password != SITE_PASSWORD:
                st.error("パスワードが正しくありません。")
            else:
                st.warning("担当者名を入力してください。")

# --- 📦 メ인 콘텐츠 ---
if not st.session_state.logged_in:
    login_screen()
else:
    # --- サイドバー ---
    with st.sidebar:
        st.write(f"👤 担当者: **{st.session_state.user_name}**")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.rerun()

    st.title("☕ RCS 在庫管理システム")

    try:
        # 데이터 읽기 (캐시 없이 최신 상태 유지)
        df = conn.read(worksheet="Inventory", ttl=0)
        df.columns = df.columns.str.strip()
        df_log = conn.read(worksheet="Log", ttl=0)

        # 📊 在庫状況
        st.subheader("📊 現在の在庫状況")
        # 데이터프레임 표시 (소수점 포함)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🔄 データを更新"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # 📦 在庫調整
        st.subheader("📦 在庫の調整 (入出庫)")
        item_col = df.columns[0]
        qty_col = df.columns[1]
        
        selected_item = st.selectbox("品目を選択してください", df[item_col].tolist())
        
        # --- 수정 포인트 1: 소수점 변환 (float) ---
        raw_val = df[df[item_col] == selected_item][qty_col].values[0]
        try:
            current_qty = float(raw_val)
        except:
            current_qty = 0.0

        st.info(f"現在の **{selected_item}** の在庫数: **{current_qty:.2f}**")
        
        # --- 수정 포인트 2: 입력창 소수점 지원 ---
        # value=0.0 (float), step=0.1 정도로 설정
        diff = st.number_input("変更数量を入力 (+入庫 / -出庫)", value=0.0, step=0.1, format="%.2f")

        if st.button("💾 変更を保存"):
            # 소수점 계산 오류 방지를 위해 round 처리
            new_qty = round(current_qty + diff, 3)
            
            if new_qty < 0:
                st.error(f"❌ 在庫不足です。現在の在庫({current_qty})を超える出庫는できません。")
            else:
                # 1. Inventory 업데이트
                df.loc[df[item_col] == selected_item, qty_col] = new_qty
                conn.update(worksheet="Inventory", data=df)

                # 2. Log 업데이트
                new_log = pd.DataFrame([{
                    "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "担当者": st.session_state.user_name,
                    "品目": selected_item,
                    "変動": diff,
                    "最終在庫": round(new_qty, 3)
                }])
                updated_log = pd.concat([df_log, new_log], ignore_index=True)
                conn.update(worksheet="Log", data=updated_log)

                st.success(f"✅ 更新が完了しました: {selected_item} → {new_qty:.2f}")
                st.balloons()
                st.rerun()

        # 🕒 履歴 (최신 10개만, 역순 정렬)
        with st.expander("🕒 直近の入出庫履歴 (最新10件)"):
            if not df_log.empty:
                # 최신 데이터가 위로 오게 정렬해서 표시
                st.table(df_log.iloc[::-1].head(10))

    except Exception as e:
        st.error(f"システムエラーが発生しました: {e}")
        st.info("スプレッドシートのシート名（Inventory, Log）が正しいか確認してください。")
