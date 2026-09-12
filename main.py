import os
from topic_generator import pick_today_topic
from tts import tts_elevenlabs
from video_maker import make_shorts_video

# script_writer는 선택적 - API 키 없으면 더미 사용
try:
    from script_writer import write_script
    HAS_OPENAI = True
except:
    HAS_OPENAI = False

def main():
    print("=== 1. 오늘의 바이럴 주제 선정 (개발자 타겟 A) ===")
    use_gpt = bool(os.getenv("OPENAI_API_KEY"))
    topic = pick_today_topic(use_gpt=use_gpt)
    print(f"선정: {topic}")

    print("\n=== 2. 대본 생성 ===")
    if use_gpt and HAS_OPENAI:
        script = write_script(topic)
    else:
        script = {
            "title": topic["topic"],
            "hook_text": topic["hook"],
            "narration": f"{topic['hook']}. {topic['topic']} 방법을 45초 안에 정리합니다. 첫째 MCP 서버 연결, 둘째 Cursor 설정, 셋째 n8n 자동화. 이 영상 저장하고 팀 슬랙에 공유하세요.",
            "description": f"{topic['topic']} - 개발자 70% 타겟 AI 쇼츠. 오늘의 바이럴 스코어 {topic['viral_score']}점",
            "tags": ["AI", "MCP", "Cursor", "n8n", "자동화", "개발자", "코딩", "LangGraph", "AI에이전트"]
        }
    print(script)

    print("\n=== 3. 음성 생성 ===")
    voice_path = tts_elevenlabs(script["narration"], "voice.mp3")

    print("\n=== 4. 영상 합성 ===")
    video_path = make_shorts_video(script, voice_path, "shorts_final.mp4")

    print("\n=== 5. 유튜브 업로드 ===")
    if os.path.exists("client_secrets.json") or os.path.exists("token.pickle"):
        from uploader import upload_shorts
        upload_shorts(video_path, script)
    else:
        print("YouTube API 키 없음 - 영상만 생성됨. client_secrets.json 넣고 다시 실행하면 업로드 됩니다.")
        print(f"영상 위치: {video_path}")

if __name__ == "__main__":
    main()
