import discord
from discord.ext import commands
from supabase import create_client, Client
from flask import Flask
import threading
import os
import logging

# --- 0. 로그 설정 (에러 원인을 한눈에 보기 위함) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. 보안 설정 ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("DISCORD_TOKEN")
# 채널 ID가 없을 경우를 대비해 기본값 설정 후 예외 처리
try:
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "1483110205184278679"))
except ValueError:
    CHANNEL_ID = 1483110205184278679

# DB 연결
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("✅ Supabase 클라이언트 준비 완료")
except Exception as e:
    logging.error(f"❌ Supabase 설정 에러 (키를 확인하세요): {e}")

# --- 2. Flask 서버 (Render 포트 체크 통과용) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # Render가 문을 두드릴 때 대답하는 곳
    return "Bot is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000)) 
    logging.info(f"🌐 Flask 포트 방어 서버 가동 준비 완료 (포트: {port})")
    # 🔥 최적화 핵심: 스레드 안에서 돌릴 때는 use_reloader=False를 꼭 써야 충돌이 안 납니다.
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- 3. Discord 봇 설정 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'🤖 디스코드 봇 정상 로그인 완료: {bot.user}')

# (주의: 여기에 !在庫, !不足 등 사용하시던 명령어 함수들을 꼭 그대로 붙여넣으셔야 합니다!)

# --- 4. 실행부 (가장 중요) ---
if __name__ == "__main__":
    if not TOKEN:
        logging.error("❌ DISCORD_TOKEN이 비어있습니다. Render [Environment]를 확인하세요!")
    else:
        # 1. Render가 포트 없다고 화내기 전에 Flask를 제일 먼저 켭니다.
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # 2. 그 다음 디스코드 봇 로그인을 시도합니다.
        logging.info("⏳ 디스코드 서버에 연결을 시도합니다...")
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            # 디코가 또 차단했을 때 뱉어내는 명확한 에러 메시지
            logging.error(f"🚨 디스코드 연결 차단됨 (1015 에러 등, 잠시 후 다시 시도하세요): {e}")
        except Exception as e:
            logging.error(f"❌ 알 수 없는 봇 실행 에러: {e}")
