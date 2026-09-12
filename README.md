# YouTube Shorts 매일 1개 자동화 - 개발자 타겟 A안 (조회수 폭발)

## 기능
- 매일 08:00 KST 바이럴 주제 1개 자동 선정 (개발자 가중치: automation 30%, comparison 25%, tips 25%)
- GPT-4o로 45초 대본 + 제목/설명/태그 자동 생성
- ElevenLabs Adam 남성 보이스
- MoviePy 1080x1920 영상 합성
- YouTube Data API 자동 업로드

## 설치
```bash
pip install -r requirements.txt
# .env 생성
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

## YouTube API 1회 설정
1. console.cloud.google.com -> 프로젝트 생성 -> YouTube Data API v3 활성화
2. OAuth 동의화면 -> OAuth 클라이언트 ID (데스크톱) -> client_secrets.json 다운로드
3. 로컬에서 python -c "from uploader import get_youtube_service; get_youtube_service()" 실행 후 브라우저 인증
4. token.pickle 생성됨
5. GitHub Secrets 등록:
   CLIENT_SECRETS_B64=$(base64 -w 0 client_secrets.json)
   YOUTUBE_TOKEN_B64=$(base64 -w 0 token.pickle)

## 실행
python main.py
```
조회수 폭발 주제 엔진 대시보드: ai_agentic_artifact_1_3eff70710f0a.html 참고
