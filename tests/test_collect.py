# 콜드 스타트 시드 비율과 앵글 주간 상한 필터를 검증하는 테스트
from datetime import datetime, timedelta, timezone

from steps.collect import filter_capped_angles, seed_ratio

NOW = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
CFG = {
    "cold_start": {"threshold_videos": 30, "seed_ratio_before": 0.8,
                   "seed_ratio_after": 0.4},
    "angle_weekly_cap": {"job_threat": 1},
}


def test_seed_ratio_is_high_before_threshold():
    assert seed_ratio(0, CFG) == 0.8
    assert seed_ratio(29, CFG) == 0.8


def test_seed_ratio_drops_after_threshold():
    assert seed_ratio(30, CFG) == 0.4
    assert seed_ratio(100, CFG) == 0.4


def test_filter_drops_angle_that_hit_weekly_cap():
    history = [{"date": "2026-09-11", "title": "t", "angle": "job_threat",
                "video_id": "x"}]
    candidates = [
        {"title": "a", "angles": ["job_threat"]},
        {"title": "b", "angles": ["actionable"]},
    ]
    kept = filter_capped_angles(candidates, history, now=NOW, cfg=CFG)
    assert [c["title"] for c in kept] == ["b"]


def test_filter_keeps_angle_below_cap():
    candidates = [{"title": "a", "angles": ["job_threat"]}]
    kept = filter_capped_angles(candidates, [], now=NOW, cfg=CFG)
    assert len(kept) == 1


def test_filter_keeps_candidate_when_only_one_of_its_angles_is_capped():
    history = [{"date": "2026-09-11", "title": "t", "angle": "job_threat",
                "video_id": "x"}]
    candidates = [{"title": "a", "angles": ["job_threat", "actionable"]}]
    kept = filter_capped_angles(candidates, history, now=NOW, cfg=CFG)
    assert kept[0]["angles"] == ["actionable"]
