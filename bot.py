import threading
import os
import logging
import time
import asyncio
import discord
from discord.ext import commands
from flask import Flask, request, jsonify
from supabase import create_client, Client # 추가됨

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))

# Supabase 클라이언트 초기화 (봇에서 DB 읽기용)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

# Flask -> Discord 메시지 전송 큐
message_queue = asyncio.Queue()

@app.route('/send_alert', methods=['POST'])
def send_alert():
    data = request.json
    message = data.get("message", "")
    if message:
        # 큐에 메시지 넣기 (Thread-safe)
        bot.loop.call_soon_threadsafe(message_queue.put_nowait, message)
        return jsonify({"status": "queued"}), 200
    return jsonify({"status": "failed"}), 400

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 큐에 쌓인 메시지를 백그라운드에서 처리하는 태스크
async def process_message_queue():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    while not bot.is_closed():
        message = await message_queue.get()
        if channel:
            await channel.send(message)

@bot.event
async def on_ready():
    logging.info(f'🤖 Discord Bot ログイン成功: {bot.user}')
    bot.loop.create_task(process_message_queue())

# ⭐ 추가된 기능: 디스코드에서 "!재고" 입력 시 현재 재고 상태 확인
@bot.command(name="재고", aliases=["stock"])
async def check_stock(ctx):
    try:
        res = supabase.table("inventory").select("item_name, current_stock, min_stock, unit").execute()
        if not res.data:
            await ctx.send("📦 현재 등록된 재고가 없습니다.")
            return

        msg = "📊 **현재 재고 상태**\n"
        for item in res.data:
            status = "🔴 (부족)" if item['current_stock'] <= item['min_stock'] else "🟢"
            msg += f"{status} **{item['item_name']}**: {item['current_stock']}{item['unit']} (목표: {item['min_stock']})\n"
        
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"⚠️ 재고를 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    if TOKEN:
        bot.run(TOKEN)
    else:
        logging.error("❌ DISCORD_TOKENが見つかりません。")
