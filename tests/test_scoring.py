# 5축 점수화 함수와 중복 패널티 적용을 검증하는 테스트
from datetime import datetime, timedelta, timezone

import pytest

from steps.scoring import (
    angle_score,
    demand_score,
    freshness_score,
    gap_score,
    score_candidate,
    target_score,
)

NOW = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
CFG = {
    "target": {"keywords": ["보고서", "엑셀", "회의록", "업무"]},
    "scoring": {
        "duplicate_penalty": 40,
        "duplicate_jaccard_threshold": 0.4,
        "duplicate_window_days": 30,
    },
}


def test_demand_score_is_zero_for_no_demand():
    assert demand_score(0) == 0


def test_demand_score_caps_at_thirty():
    assert demand_score(50_000_000) == 30


def test_demand_score_is_monotonic():
    assert demand_score(1_000) < demand_score(100_000) < demand_score(5_000_000)


def test_gap_score_is_max_when_no_recent_competitor():
    assert gap_score(0.0) == 25


def test_gap_score_is_zero_when_all_competitors_are_recent():
    assert gap_score(1.0) == 0


def test_freshness_full_within_24h():
    assert freshness_score(NOW - timedelta(hours=5), NOW) == 20


def test_freshness_zero_after_seven_days():
    assert freshness_score(NOW - timedelta(days=8), NOW) == 0


def test_freshness_is_between_for_three_days():
    s = freshness_score(NOW - timedelta(days=3), NOW)
    assert 0 < s < 20


def test_angle_score_five_per_angle_capped_at_fifteen():
    assert angle_score([]) == 0
    assert angle_score(["actionable"]) == 5
    assert angle_score(["actionable", "loss_aversion", "korea_only", "comparison"]) == 15


def test_target_score_counts_matched_keywords():
    assert target_score("챗GPT로 보고서 쓰기", CFG["target"]["keywords"]) == 5
    assert target_score("보고서와 엑셀 업무", CFG["target"]["keywords"]) == 10
    assert target_score("전혀 상관없는 내용", CFG["target"]["keywords"]) == 0


def test_score_candidate_has_no_randomness():
    c = {
        "title": "챗GPT로 보고서 10분 만에",
        "angles": ["actionable"],
        "published_at": NOW - timedelta(hours=2),
        "median_views": 200_000,
        "recent_ratio": 0.2,
    }
    scores = {score_candidate(c, now=NOW, history=[], cfg=CFG) for _ in range(20)}
    assert len(scores) == 1, "점수는 결정적이어야 한다"


def test_score_candidate_applies_duplicate_penalty():
    c = {
        "title": "챗GPT로 보고서 10분 만에",
        "angles": ["actionable"],
        "published_at": NOW - timedelta(hours=2),
        "median_views": 200_000,
        "recent_ratio": 0.2,
    }
    history = [{"date": "2026-09-10", "title": "챗GPT로 보고서 10분 만에 쓰기",
                "angle": "actionable", "video_id": "x"}]
    clean = score_candidate(c, now=NOW, history=[], cfg=CFG)
    dupe = score_candidate(c, now=NOW, history=history, cfg=CFG)
    assert clean - dupe == pytest.approx(40)
