import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask
import threading
import os
import logging
import time  # 무한 루프 방지용 대기 모듈 추가 (無限ループ防止用)

# --- 0. ログ設定 (エラー原因をひと目で確認するため) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. セキュリティ設定 (環境変数) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")

# チャンネルIDが存在しない場合に備えてデフォルト値を設定し、例外処理を適用
try:
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))
except ValueError:
    CHANNEL_ID = 1483110205184278679

# DB接続
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("✅ Supabaseクライアントの準備完了")
except Exception as e:
    logging.error(f"❌ Supabase設定エラー（キーを確認してください）: {e}")

# --- 2. Flaskサーバー (Renderのポートチェック通過用) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # Renderがヘルスチェックを行う際に応答するエンドポイント
    return "Bot is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000)) 
    logging.info(f"🌐 Flaskポート監視サーバーの稼働準備完了 (ポート: {port})")
    # 🔥 最適化のポイント: スレッド内で実行する場合は use_reloader=False が必須（競合防止）
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 3. Discord Botの設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'🤖 Discord Botのログインに成功しました: {bot.user}')

# (注意: ここに !在庫, !不足 など、使用していたコマンド関数をそのまま貼り付けてください)


# --- 4. 実行部 (最重要) ---
if __name__ == "__main__":
    if not TOKEN:
        logging.error("❌ DISCORD_TOKENが空です。Renderの[Environment]を確認してください。")
    else:
        # 1. Renderにポートエラーを出される前に、Flaskを最優先で起動する
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # 2. その後、Discord Botのログインを試行する
        logging.info("⏳ Discordサーバーへの接続を試行しています...")
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            # Discord側のIPブロック（429/1015エラー）発生時の処理
            logging.error(f"🚨 Discordへの接続がブロックされました（1015エラー等）: {e}")
            logging.info("⚠️ Renderによる即時再起動（無限ループ）を防ぐため、15分間待機します...")
            time.sleep(900)  # 15분 대기 (차단 해제 유도 및 Render 강제 재시작 방지)
        except Exception as e:
            logging.error(f"❌ 不明なBot実行エラー: {e}")
            time.sleep(60)   # 기타 에러 시 1분 대기
