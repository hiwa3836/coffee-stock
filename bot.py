import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import threading
import os
import logging
import time
import asyncio

# --- 0. ログ設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. セキュリティ設定 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
try:
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))
except ValueError:
    CHANNEL_ID = 1483110205184278679

# --- 2. Flaskサーバー (ポート10000 / Webhook受信用) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot System is Online!", 200

@app.route('/send_alert', methods=['POST'])
def send_alert():
    """Streamlitからの在庫通知を受信しDiscordへ送信"""
    data = request.json
    message = data.get("message", "")
    
    if message and bot.is_ready():
        # 非同期ループにタスクを投げる
        asyncio.run_coroutine_threadsafe(send_discord_message(message), bot.loop)
        return jsonify({"status": "sent"}), 200
    return jsonify({"status": "failed"}), 400

async def send_discord_message(content):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(content)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🌐 Flaskサーバーを起動しました (Port: {port})")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 3. Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'🤖 Discord Bot ログイン成功: {bot.user}')

# --- 4. 実行部 (再起動ロジック搭載) ---
if __name__ == "__main__":
    # Flaskスレッドを先に開始
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(5) # ポート開放待ち

    while True:
        if not TOKEN:
            logging.error("❌ DISCORD_TOKENが設定されていません。環境変数を確認してください。")
            time.sleep(3600) # 1時間待機してループ維持
            continue

        try:
            logging.info("🚀 Discordサーバーへの接続を試行します...")
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429 or e.status == 1015:
                logging.error(f"🚨 レート制限(1015/429)を検知しました。15分間待機します: {e}")
                time.sleep(900) # 15分待機
            else:
                logging.error(f"🚨 HTTPエラーが発生しました。1分後に再試行します: {e}")
                time.sleep(60)
        except Exception as e:
            logging.error(f"❌ 予期せぬエラーが発生しました。プロセスを維持します: {e}")
            time.sleep(60)
