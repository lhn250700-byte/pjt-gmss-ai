import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# bot_msg: cnsl_id당 1행, msg_data.content에 { speaker, text, type, timestamp } 배열
# summary: 요약 텍스트
