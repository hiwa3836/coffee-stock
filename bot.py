if __name__ == "__main__":
    # 1. Flask 서버 즉시 가동 (포트 방어)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(5)

    # 2. 메인 로직 전체를 무한 루프로 보호
    while True:
        try:
            if not TOKEN:
                logging.error("❌ TOKEN MISSING")
                break # 토큰 없으면 루프 탈출
            
            logging.info("🚀 Discord Connect Attempt...")
            bot.run(TOKEN)
            
        except Exception as e:
            logging.error(f"🚨 Main Loop Error: {e}")
            logging.info("⚠️ 15분 대기 후 프로세스를 유지합니다...")
            # 여기서 멈춰줘야 Render가 "프로그램이 종료되었다"고 판단하지 않음
            time.sleep(900) 
            # 15분 뒤에 다시 위로 올라가서 재시도(Retry)하거나 계속 대기
