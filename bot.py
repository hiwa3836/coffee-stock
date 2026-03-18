import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask, request
import threading
import logging
import asyncio
import os

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. 보안 설정 (환경 변수) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")
# 채널 ID가 없으면 기본값 사용, 있으면 환경변수 우선
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1483110205184278679))

# DB 연결
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    logger.error("❌ Supabase 설정이 누락되었습니다.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

app = Flask(__name__)

# --- 2. Flask 서버 (상태 확인 및 알림 수신) ---
@app.route('/')
def health_check():
    return "Bot is Running!", 200

@app.route('/send_alert', methods=['POST'])
def send_alert():
    data = request.json
    message = data.get('message')
    if message:
        asyncio.run_coroutine_threadsafe(
            bot.get_channel(CHANNEL_ID).send(message),
            bot.loop
        )
        return {"status": "success"}, 200
    return {"status": "failed"}, 400

def run_flask():
    # Render는 PORT 환경 변수를 자동으로 할당합니다. 이를 읽어와야 에러가 안 납니다.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- 3. Discord 봇 명령어 ---
@bot.event
async def on_ready():
    logger.info(f'✅ 봇 온라인: {bot.user}')

@bot.command(name='ヘル프')
async def help_command(ctx):
    help_text = "🛠️ **재고 관리 도움말**\n▶️ `!在庫`: 전체 확인\n▶️ `!不足`: 부족 확인"
    await ctx.send(help_text)

@bot.command(name='在庫')
async def check_inventory(ctx):
    try:
        res = supabase.table("inventory").select("*").order("id").execute()
        items = res.data
        if not items:
            await ctx.send("📦 등록된 아이템이 없습니다.")
            return
        
        msg = "📦 **현재 재고 상황**\n```diff\n"
        for i in items:
            status = "+" if i['current_stock'] > i['min_stock'] else "-"
            msg += f"{status} {i['item_name']}: {i['current_stock']} {i['unit']}\n"
        msg += "```"
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {e}")

@bot.command(name='不足')
async def check_shortage(ctx):
    try:
        res = supabase.table("inventory").select("*").execute()
        shortage = [i for i in res.data if i['current_stock'] <= i['min_stock']]
        if not shortage:
            await ctx.send("✅ 부족한 재고가 없습니다.")
            return
            
        msg = "🚨 **재고 부족 알림**\n```arm\n"
        for i in shortage:
            msg += f"• {i['item_name']}: {i['current_stock']} (최소 {i['min_stock']})\n"
        msg += "```"
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {e}")

# --- 실행 ---
if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN이 없습니다.")
    else:
        # Flask를 별도 스레드에서 실행
        threading.Thread(target=run_flask, daemon=True).start()
        # 디스코드 봇 실행
        bot.run(TOKEN)
