import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask, request
import threading
import logging
import asyncio
import os  # 추가: 환경 변수를 읽어오기 위함

# --- 로깅 및 기본 설정 ---
logging.basicConfig(level=logging.INFO)

# --- 1. 보안 설정 (환경 변수 사용) ---
# 코드에 직접 정보를 적지 않고, 서버 시스템에서 값을 가져옵니다.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")
# 채널 ID는 민감정보는 아니지만 관리 편의상 환경변수로 뺄 수 있습니다.
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1483110205184278679))

# DB 연결
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

app = Flask(__name__)

# --- 2. Flask 서버 (웹앱의 알림 수신) ---
@app.route('/send_alert', methods=['POST'])
def send_alert():
    data = request.json
    message = data.get('message')
    if message:
        # Flask 스레드에서 Discord 봇 스레드로 안전하게 전송
        asyncio.run_coroutine_threadsafe(
            bot.get_channel(CHANNEL_ID).send(message),
            bot.loop
        )
        return {"status": "success"}, 200
    return {"status": "failed"}, 400

def run_flask():
    # 포트 5000번에서 실행 (배포 환경에 따라 포트가 달라질 수 있음)
    app.run(host='0.0.0.0', port=5000)

# --- 3. Discord 봇 이벤트 및 명령어 ---
@bot.event
async def on_ready():
    print(f'✅ 봇 온라인: {bot.user}')
    print(f'📢 알림 채널 ID: {CHANNEL_ID}')

@bot.command(name='ヘルプ')
async def help_command(ctx):
    help_text = """
    🛠️ **在庫管理システム・ヘルプ** 🛠️
    ▶️ `!在庫` : 全アイテムの在庫確認
    ▶️ `!不足` : 在庫不足アイテムのみ確認
    """
    await ctx.send(help_text)

@bot.command(name='在庫')
async def check_inventory(ctx):
    res = supabase.table("inventory").select("*").order("id").execute()
    items = res.data
    if not items:
        await ctx.send("📦 登録されたアイテムがありません。")
        return
    
    msg = "📦 **現在の在庫状況**\n```diff\n"
    for i in items:
        status = "+" if i['current_stock'] > i['min_stock'] else "-"
        msg += f"{status} {i['item_name']}: {i['current_stock']} {i['unit']}\n"
    msg += "```"
    await ctx.send(msg)

@bot.command(name='不足')
async def check_shortage(ctx):
    res = supabase.table("inventory").select("*").execute()
    shortage = [i for i in res.data if i['current_stock'] <= i['min_stock']]
    if not shortage:
        await ctx.send("✅ 不足している在庫はありません。")
        return
        
    msg = "🚨 **在庫不足アラート**\n```arm\n"
    for i in shortage:
        msg += f"• {i['item_name']}: {i['current_stock']} (最小 {i['min_stock']})\n"
    msg += "```"
    await ctx.send(msg)

# --- 실행 ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ 에러: DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.")
    else:
        threading.Thread(target=run_flask, daemon=True).start()
        bot.run(TOKEN)
