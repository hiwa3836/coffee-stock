import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask
import threading
import os
import logging
import time

# --- 0. ログ設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. セキュリティ設定 (環境変数) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")

try:
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))
except ValueError:
    CHANNEL_ID = 1483110205184278679

# DB接続
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("✅ Supabaseクライアントの準備完了")
except Exception as e:
    logging.error(f"❌ Supabase設定エラー: {e}")

# --- 2. Flaskサーバー (Renderポート監視用) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Online!", 200

def run_flask():
    # Renderは環境変数 PORT (通常10000) を使用します
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🌐 Flaskサーバーを起動します (Port: {port})")
    try:
        # use_reloader=False はスレッド実行時に必須
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    except Exception as e:
        logging.error(f"❌ Flaskサーバー起動エラー: {e}")

# --- 3. Discord Botの設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'🤖 Discord Bot ログイン成功: {bot.user}')

# --- 4. 実行部 (Render最適化済み) ---
if __name__ == "__main__":
    if not TOKEN:
        logging.error("❌ DISCORD_TOKENが見つかりません。")
    else:
        # [STEP 1] Flaskを別スレッドで先に起動
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # [STEP 2] Renderがポートを認識するまで5秒待機 (重要)
        logging.info("⏳ ポートの疎通を確認するため、5秒間待機します...")
        time.sleep(5)
        
        # [STEP 3] Discord Botの起動を試行
        logging.info("🚀 Discordサーバーへの接続を開始します...")
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            # 1015エラー (Rate Limit) 発生時の無限再起動防止
            logging.error(f"🚨 Discord接続拒否 (Rate Limit / 1015): {e}")
            logging.info("⚠️ IP制限を回避するため、15分間待機してプロセスを維持します...")
            # プロセスを終了させず維持することで Render の強制再起動ループを防ぐ
            while True:
                time.sleep(60)
        except Exception as e:
            logging.error(f"❌ 予期せぬエラーが発生しました: {e}")
            time.sleep(60)
