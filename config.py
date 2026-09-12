import os
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

CHANNEL_CONFIG = {
    "language": "ko",
    "target": "developer",
    "voice_id": "pNInz6obpgDQGcFmaJgB",
    "video_width": 1080,
    "video_height": 1920,
    "duration_target": 45,
    "upload_time_kst": "08:00",
}

VIRAL_PILLARS_DEV = {
    "automation": 0.30,
    "comparison": 0.25,
    "tips": 0.25,
    "money": 0.10,
    "shock": 0.05,
    "controversy": 0.05,
}

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
