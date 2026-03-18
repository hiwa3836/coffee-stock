import discord
from discord.ext import commands
import os
from flask import Flask
import threading

# 1. Flask 설정 (Render의 'Web Service' 체크 통과용)
app = Flask(__name__)

@app.route('/')
def home():
    return "I am Alive!", 200

def run_flask():
    # Render가 주는 포트를 최우선으로 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# 2. 디스코드 봇 설정
TOKEN = os.environ.get("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ 봇 온라인: {bot.user}')

# (기존 !在庫, !不足 커맨드들은 여기에 그대로 유지하세요)

# 3. 실행부 (순서 변경: Flask 먼저 실행)
if __name__ == "__main__":
    # Flask 서버를 백그라운드에서 먼저 실행 (Render 체크 통과용)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 그 다음 봇 실행
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN을 찾을 수 없습니다!")
