import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ページの設定
st.set_page_config(page_title="在庫管理システム", layout="centered")
st.title("☕ RCS 在庫管理")

# Google Sheets 接続
conn = st.connection("gsheets", type=GSheetsConnection)

# キャッシュを10分(600秒)に設定して、API制限を回避します。
try:
    # データの読み込み
    df = conn.read(ttl=60) 
    df.columns = df.columns.str.strip()
    
    st.subheader("📊 現在の在庫状況")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 最新データに更新するボタン
    if st.button("🔄 最新の情報に更新"):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.subheader("📦 在庫を調整する")
    
    # 列名の取得（1列目：品目名、2列目：現在数量）
    item_col = df.columns[0]
    qty_col = df.columns[1]
    
    # 品目の選択
    selected_item = st.selectbox("品目を選択してください", df[item_col].tolist())
    
    # 現在の在庫数を取得
    raw_qty = df[df[item_col] == selected_item][qty_col].values[0]
    current_qty = int(raw_qty) if str(raw_qty).isdigit() else 0

    st.info(f"現在の **{selected_item}** の在庫数: **{current_qty}**")
    
    # 変更数量の入力
    diff = st.number_input("変更数量を入力 (+入庫, -出庫)", step=1, value=0)

    if st.button("適用して保存"):
        if diff != 0:
            # データの計算と更新
            new_qty = current_qty + diff
            df.loc[df[item_col] == selected_item, qty_col] = new_qty
            
            # Google Sheets を更新
            conn.update(data=df)
            
            # 保存後はキャッシュをクリアして最新状態を表示
            st.cache_data.clear()
            st.success(f"✅ {selected_item} の在庫を {new_qty} に更新しました！")
            st.balloons()
            st.rerun()
        else:
            st.warning("変更する数量を入力してください。")

except Exception as e:
    st.error("しばらくしてから再試行してください（Google APIの制限）")
    st.write(f"エラー詳細: {e}")
