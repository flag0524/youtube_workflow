# 완성된 쇼츠를 YouTube 에 비공개로 올리고 지정 시각에 예약 공개하는 모듈
import json
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import YOUTUBE_SCOPES, load_config

MAX_TITLE = 100
MAX_TAGS = 15


def get_youtube_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secrets.json", YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)


def publish_at_rfc3339(date_str: str, time_kst: str, offset_hours: int) -> str:
    local = datetime.strptime(f"{date_str} {time_kst}", "%Y-%m-%d %H:%M")
    utc = local - timedelta(hours=offset_hours)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_request_body(script: dict, publish_at: str, cfg: dict) -> dict:
    sources = "\n".join(f"출처: {u}" for u in script.get("sources", []))
    description = (
        f"{script['description']}\n\n{sources}\n\n"
        f"{cfg['brand']['channel_name']}\n"
        "이 영상의 나레이션은 AI 음성으로 제작되었습니다.\n"
        "#Shorts #AI #업무자동화"
    )
    return {
        "snippet": {
            "title": script["title"][:MAX_TITLE],
            "description": description,
            "tags": script.get("tags", [])[:MAX_TAGS],
            "categoryId": cfg["upload"]["category_id"],
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            # publishAt 은 privacyStatus 가 private 일 때만 동작한다.
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    cfg = load_config()
    script = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
    video_path = out_dir / "short.mp4"

    publish_at = publish_at_rfc3339(
        date_str, cfg["upload"]["publish_time_kst"],
        cfg["upload"]["timezone_offset_hours"],
    )
    body = build_request_body(script, publish_at, cfg)

    if dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return {"dry_run": True, "body": body}

    youtube = get_youtube_service()
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True,
                            mimetype="video/*")
    response = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    ).execute()

    result = {
        "video_id": response["id"],
        "url": f"https://youtube.com/watch?v={response['id']}",
        "publish_at": publish_at,
        "privacy_status": response["status"]["privacyStatus"],
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
