import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ページの設定
st.set_page_config(page_title="RCS 在庫管理システム v3", layout="centered")

# 패스워드 설정
try:
    SITE_PASSWORD = st.secrets["site_password"]
except:
    st.error("Secrets에 'site_password'가 설정되지 않았습니다.")
    st.stop()

# 2. Google Sheets 接続
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. セッション状態の初期化
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""

# --- 🔑 ログイン画面 ---
def login_screen():
    st.title("🔒 アクセス制限")
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

# --- 📦 メインコンテンツ ---
if not st.session_state.logged_in:
    login_screen()
else:
    with st.sidebar:
        st.write(f"👤 担当者: **{st.session_state.user_name}**")
        if st.button("ログアウト"):
            st.session_state.logged_in = False
            st.rerun()

    st.title("☕ RCS 在庫管理システム")

    try:
        # API 횟수 제한 방지를 위해 ttl을 300(5분)으로 설정 (수정 시에만 초기화됨)
        df = conn.read(worksheet="Inventory", ttl=300)
        df.columns = df.columns.str.strip()
        df_log = conn.read(worksheet="Log", ttl=300)

        # 📊 在庫状況
        st.subheader("📊 現在の在庫状況")
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🔄 データを強制更新"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # 📦 在庫調整
        st.subheader("📦 在庫の調整 (入出庫)")
        item_col = df.columns[0]
        qty_col = df.columns[1]
        
        selected_item = st.selectbox("品目を選択してください", df[item_col].tolist())
        
        # 소수점 지원을 위해 float으로 변환
        raw_val = df[df[item_col] == selected_item][qty_col].values[0]
        try:
            current_qty = float(raw_val)
        except (ValueError, TypeError):
            current_qty = 0.0

        st.info(f"現在の **{selected_item}** の在庫数: **{current_qty:.2f}**")
        
        # 입력창 소수점 지원 (step=0.1)
        diff = st.number_input("変更数量 (+入庫 / -出庫)", value=0.0, step=0.1, format="%.2f")

        if st.button("💾 変更を保存"):
            new_qty = round(current_qty + diff, 3)
            
            if new_qty < 0:
                st.error(f"❌ 在庫不足です。現在の在庫({current_qty})を超える出주는できません。")
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
                    "最終在庫": new_qty
                }])
                updated_log = pd.concat([df_log, new_log], ignore_index=True)
                conn.update(worksheet="Log", data=updated_log)

                # 저장 후 캐시 삭제 (중요: 그래야 다음 로딩 때 API에서 새 데이터를 가져옴)
                st.cache_data.clear()
                
                st.success(f"✅ 更新完了: {selected_item} → {new_qty:.2f}")
                st.balloons()
                st.rerun()

        # 🕒 履歴 (최신 순서로 정렬)
        with st.expander("🕒 入出庫履歴 (最新 10件)"):
            if not df_log.empty:
                # iloc[::-1]를 사용하여 역순 정렬
                st.table(df_log.iloc[::-1].head(10))

    except Exception as e:
        # Quota 에러 발생 시 안내
        if "429" in str(e):
            st.error("⚠️ API 호출 제한에 도달했습니다. 1분만 기다려 주세요.")
        else:
            st.error(f"システムエラー: {e}")
