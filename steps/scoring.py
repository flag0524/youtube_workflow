# 주제 후보를 측정 가능한 5개 축으로 점수화하는 순수 함수 모음 (네트워크·랜덤 없음)
import math
from datetime import datetime

from steps.history import is_duplicate

# 검색 수요를 로그 스케일로 정규화하는 구간. 조회수 100 이하는 0점, 1,000,000 이상은 만점.
_DEMAND_LO = 2.0   # log10(100)
_DEMAND_HI = 6.0   # log10(1_000_000)

_FRESH_FULL_HOURS = 24
_FRESH_ZERO_HOURS = 168  # 7일


def demand_score(median_views: float) -> float:
    if median_views <= 0:
        return 0.0
    scaled = (math.log10(median_views + 1) - _DEMAND_LO) / (_DEMAND_HI - _DEMAND_LO)
    return round(min(30.0, max(0.0, scaled * 30)), 2)


def gap_score(recent_ratio: float) -> float:
    """상위 결과 중 최근 90일 영상 비율. 낮을수록 뚫고 들어갈 틈이 크다."""
    return round(max(0.0, min(1.0, 1 - recent_ratio)) * 25, 2)


def freshness_score(published_at: datetime, now: datetime) -> float:
    hours = (now - published_at).total_seconds() / 3600
    if hours <= _FRESH_FULL_HOURS:
        return 20.0
    if hours >= _FRESH_ZERO_HOURS:
        return 0.0
    span = _FRESH_ZERO_HOURS - _FRESH_FULL_HOURS
    return round(20 * (1 - (hours - _FRESH_FULL_HOURS) / span), 2)


def angle_score(angles: list[str]) -> float:
    return float(min(15, len(angles) * 5))


def target_score(text: str, keywords: list[str]) -> float:
    matched = sum(1 for k in keywords if k in text)
    return float(min(10, matched * 5))


def score_candidate(candidate: dict, *, now: datetime, history: list[dict],
                    cfg: dict) -> float:
    total = (
        demand_score(candidate["median_views"])
        + gap_score(candidate["recent_ratio"])
        + freshness_score(candidate["published_at"], now)
        + angle_score(candidate["angles"])
        + target_score(candidate["title"], cfg["target"]["keywords"])
    )
    sc = cfg["scoring"]
    if is_duplicate(candidate["title"], history, now=now.replace(tzinfo=None),
                    window_days=sc["duplicate_window_days"],
                    threshold=sc["duplicate_jaccard_threshold"]):
        total -= sc["duplicate_penalty"]
    return round(total, 2)
