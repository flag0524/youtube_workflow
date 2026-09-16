# ytmetrics 모듈의 median/recent_ratio/fetch_keyword_metrics 테스트
from datetime import datetime, timedelta, timezone

from steps.ytmetrics import fetch_keyword_metrics, median, recent_ratio

NOW = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)


def test_median_odd_count():
    assert median([1, 5, 3]) == 3


def test_median_even_count():
    assert median([1, 3, 5, 7]) == 4


def test_median_empty_is_zero():
    assert median([]) == 0


def test_recent_ratio_all_recent():
    dates = [NOW - timedelta(days=d) for d in (1, 10, 30)]
    assert recent_ratio(dates, now=NOW) == 1.0


def test_recent_ratio_none_recent():
    dates = [NOW - timedelta(days=d) for d in (200, 400)]
    assert recent_ratio(dates, now=NOW) == 0.0


def test_recent_ratio_half():
    dates = [NOW - timedelta(days=10), NOW - timedelta(days=300)]
    assert recent_ratio(dates, now=NOW) == 0.5


def test_recent_ratio_empty_is_one():
    """결과가 없으면 경쟁 공백을 판단할 수 없다. 보수적으로 1.0(공백 없음)을 준다."""
    assert recent_ratio([], now=NOW) == 1.0


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeSearch:
    def list(self, **kwargs):
        return _FakeRequest({"items": [
            {"id": {"videoId": "v1"}},
            {"id": {"videoId": "v2"}},
        ]})


class _FakeVideos:
    def list(self, **kwargs):
        return _FakeRequest({"items": [
            {"statistics": {"viewCount": "100000"},
             "snippet": {"publishedAt": "2026-09-01T00:00:00Z"}},
            {"statistics": {"viewCount": "300000"},
             "snippet": {"publishedAt": "2024-01-01T00:00:00Z"}},
        ]})


class _FakeYouTube:
    def search(self):
        return _FakeSearch()

    def videos(self):
        return _FakeVideos()


def test_fetch_keyword_metrics_combines_search_and_stats():
    m = fetch_keyword_metrics(_FakeYouTube(), "챗GPT 보고서", now=NOW)
    assert m["median_views"] == 200000
    assert m["recent_ratio"] == 0.5
