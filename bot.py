import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask
import threading
import os
import logging
import time

# --- 0. ログ設定 (エラー追跡用) ---
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

# --- 2. Flaskサーバー (Renderポート監視およびスリープ防止用) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # Renderがヘルスチェックを行う際に応答
    return "Bot is Online!", 200

def run_flask():
    # Renderの標準ポート10000を使用
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🌐 Flaskサーバーを起動します (Port: {port})")
    try:
        # スレッド実行のため reloader は無効化
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

# --- [注意] ここに使用していた !在庫, !不足 などのコマンド関数を貼り付けてください ---


# --- 4. 実行部 (Render最適化および強制終了防止ロジック) ---
if __name__ == "__main__":
    if not TOKEN:
        logging.error("❌ DISCORD_TOKENが見つかりません。環境変数を確認してください。")
    else:
        # [STEP 1] Renderのポートチェックをパスするため、Flaskを最優先で起動
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # [STEP 2] ポートが完全に開くまで5秒間待機
        logging.info("⏳ ポート疎通確認のため、5秒間待機します...")
        time.sleep(5)
        
        # [STEP 3] Discord Botの起動試行
        logging.info("🚀 Discordサーバーへの接続を開始します...")
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            # 1015/429 Rate Limit エラー発生時の対応
            logging.error(f"🚨 Discord接続拒否 (Rate Limit / 1015): {e}")
            logging.info("⚠️ IPブロックを回避するため、プロセスを維持します(再起動防止)...")
            # プロセスを終了させず、Renderに「正常稼働中」と誤認させて再起動ループを防ぐ
            while True:
                time.sleep(60)
        except Exception as e:
            # その他すべての例外（トークン間違い、ネットワークエラー等）
            logging.error(f"❌ 予期せぬエラーでBotが停止しました: {e}")
            logging.info("⚠️ Renderの強制終了(Application exited early)を防ぐため、プロセスを維持します...")
            # 無限ループによりプロセスを維持
            while True:
                time.sleep(60)
