# 발행 이력 로드/저장과 주제 중복·앵글 빈도 판정을 검증하는 테스트
import json
from datetime import datetime, timedelta

from steps.history import (
    angle_used_this_week,
    append_record,
    extract_keywords,
    is_duplicate,
    jaccard,
    load_history,
    published_count,
)

NOW = datetime(2026, 9, 12, 8, 0, 0)


def test_extract_keywords_drops_particles_and_short_tokens():
    kws = extract_keywords("챗GPT로 보고서 10분 만에 쓰는 법")
    assert "챗GPT" in kws
    assert "보고서" in kws
    assert "법" not in kws  # 1글자 토큰 제외


def test_jaccard_identical_sets_is_one():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_is_duplicate_detects_near_identical_title():
    history = [{"date": "2026-09-10", "title": "챗GPT로 보고서 10분 만에 쓰는 법",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("챗GPT로 보고서 쓰는 법 10분", history,
                        now=NOW, window_days=30, threshold=0.4) is True


def test_is_duplicate_ignores_records_outside_window():
    history = [{"date": "2026-01-01", "title": "챗GPT로 보고서 10분 만에 쓰는 법",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("챗GPT로 보고서 쓰는 법 10분", history,
                        now=NOW, window_days=30, threshold=0.4) is False


def test_is_duplicate_allows_unrelated_title():
    history = [{"date": "2026-09-10", "title": "엑셀 함수 AI로 만들기",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("회의록 자동 정리하는 도구", history,
                        now=NOW, window_days=30, threshold=0.4) is False


def test_angle_used_this_week_counts_only_last_seven_days():
    history = [
        {"date": "2026-09-11", "title": "a", "angle": "job_threat", "video_id": "1"},
        {"date": "2026-08-01", "title": "b", "angle": "job_threat", "video_id": "2"},
    ]
    assert angle_used_this_week("job_threat", history, now=NOW) == 1


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "history.jsonl"
    append_record(p, {"date": "2026-09-12", "title": "제목", "angle": "actionable",
                      "video_id": "abc"})
    loaded = load_history(p)
    assert len(loaded) == 1
    assert loaded[0]["title"] == "제목"


def test_load_history_returns_empty_when_file_missing(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []


def test_published_count(tmp_path):
    assert published_count([{"date": "2026-09-12", "title": "t",
                             "angle": "a", "video_id": "v"}]) == 1
