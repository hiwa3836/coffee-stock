import threading
import os
import logging
import time
import asyncio
import discord
from discord.ext import commands
from flask import Flask, request, jsonify

# --- 0. ログ設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. セキュリティ設定 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
try:
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))
except (ValueError, TypeError):
    CHANNEL_ID = 1483110205184278679

# --- 2. Flaskサーバー (Webhook受信用) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot System is Online!", 200

@app.route('/send_alert', methods=['POST'])
def send_alert():
    data = request.json
    message = data.get("message", "")
    if message and bot.is_ready():
        asyncio.run_coroutine_threadsafe(send_discord_message(message), bot.loop)
        return jsonify({"status": "sent"}), 200
    return jsonify({"status": "failed"}), 400

async def send_discord_message(content):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(content)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🌐 Flaskサーバー起動 (Port: {port})")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 3. Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'🤖 Discord Bot ログイン成功: {bot.user}')

# --- 4. 実行部 ---
if __name__ == "__main__":
    # Flaskを最優先で開始
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(5)

    if not TOKEN:
        logging.error("❌ DISCORD_TOKENが見つかりません。")
        while True: time.sleep(60)
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"🚨 エラー発生: {e}")
            while True: time.sleep(60)
