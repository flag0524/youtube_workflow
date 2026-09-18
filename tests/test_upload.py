# 예약 공개 업로드 요청 본문 생성 로직을 검증하는 테스트
import pytest

from steps.upload import build_request_body, publish_at_rfc3339

CFG = {
    "upload": {"publish_time_kst": "18:00", "category_id": "28",
               "timezone_offset_hours": 9},
    "brand": {"channel_name": "AI 일잘러"},
}

SCRIPT = {
    "title": "챗GPT로 보고서 10분 만에 끝내는 법",
    "description": "설명 본문",
    "tags": ["AI", "보고서"],
    "sources": ["https://example.com/a"],
}


def test_publish_at_converts_kst_to_utc():
    # 2026-09-12 18:00 KST = 2026-09-12 09:00 UTC
    assert publish_at_rfc3339("2026-09-12", "18:00", 9) == "2026-09-12T09:00:00Z"


def test_publish_at_rolls_back_a_day_when_needed():
    # 2026-09-12 06:00 KST = 2026-09-11 21:00 UTC
    assert publish_at_rfc3339("2026-09-12", "06:00", 9) == "2026-09-11T21:00:00Z"


def test_body_is_private_for_scheduled_publish():
    """publishAt 은 privacyStatus 가 private 일 때만 동작한다."""
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-09-12T09:00:00Z"


def test_body_declares_synthetic_content():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["containsSyntheticMedia"] is True


def test_body_is_not_made_for_kids():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_body_truncates_long_title():
    script = {**SCRIPT, "title": "가" * 120}
    body = build_request_body(script, "2026-09-12T09:00:00Z", CFG)
    assert len(body["snippet"]["title"]) <= 100


def test_body_caps_tags_at_fifteen():
    script = {**SCRIPT, "tags": [f"t{i}" for i in range(40)]}
    body = build_request_body(script, "2026-09-12T09:00:00Z", CFG)
    assert len(body["snippet"]["tags"]) == 15


def test_description_includes_sources():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert "https://example.com/a" in body["snippet"]["description"]


def test_description_includes_shorts_hashtag():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert "#Shorts" in body["snippet"]["description"]
