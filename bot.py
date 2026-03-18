import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask
import threading
import os
import asyncio

# --- 1. 보안 설정 ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1483110205184278679))

# DB 연결
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. Flask 서버 (Render 포트 체크 통과용) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # Render가 이 주소로 접속했을 때 200 OK를 던져줘야 'Live'가 됩니다.
    return "Bot is Online!", 200

def run_flask():
    # Render는 자동으로 PORT 환경 변수를 부여합니다.
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

# --- 3. Discord 봇 설정 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ 봇 온라인: {bot.user}')

# 여기에 !在庫, !不足 커맨드들은 그대로 두세요.

# --- 4. 실행부 (가장 중요) ---
if __name__ == "__main__":
    # Flask를 먼저 실행해서 Render의 포트 스캔을 통과시킵니다.
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # 그 다음 디스코드 봇 로그인
    if TOKEN:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ 봇 실행 에러: {e}")
    else:
        print("❌ DISCORD_TOKEN이 없습니다.")
