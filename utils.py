import io
import pandas as pd
import requests
import threading

BOT_SERVER_URL = "https://coffee-stock.onrender.com/send_alert"

# 1. 디스코드 비동기 알림
def send_discord_message_async(content):
    def task():
        try:
            requests.post(BOT_SERVER_URL, json={"message": content}, timeout=3)
        except Exception: pass
    threading.Thread(target=task, daemon=True).start()

# 2. 숫자 포맷팅 (3.0 -> 3)
def fmt(val):
    v = float(val)
    return int(v) if v.is_integer() else v

# 3. 현재 재고 엑셀 생성기
def generate_current_stock_excel(df):
    buffer = io.BytesIO()
    export_df = df[['category', 'item_name', 'current_stock', 'min_stock', 'unit']].copy()
    export_df = export_df.rename(columns={
        'category': 'カテゴリ',
        'item_name': '商品名',
        'current_stock': '現在在庫',
        'min_stock': '目標値',
        'unit': '単位'
    })
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='現在在庫')
    return buffer.getvalue()

# 4. 변경 이력 엑셀 생성기
def generate_logs_excel(df):
    buffer = io.BytesIO()
    export_df = df.copy()
    export_df['created_at'] = pd.to_datetime(
        export_df['created_at'], errors='coerce', utc=True
    ).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    export_df = export_df.rename(columns={
        'created_at': '変更日時',
        'item_name': '商品名',
        'before_qty': '変更前',
        'after_qty': '変更後',
        'diff_qty': '変動量'
    })
    export_df = export_df[['変更日時', '商品名', '変更前', '変更後', '変動量']]
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='変更履歴')
    return buffer.getvalue()
