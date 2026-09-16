# HN·RSS 원시 이슈 파서를 검증하는 테스트
import json
from datetime import datetime, timezone
from pathlib import Path

from steps.sources import parse_hn, parse_rss

FIX = Path(__file__).parent / "fixtures"


def test_parse_hn_maps_fields():
    payload = json.loads((FIX / "hn_response.json").read_text(encoding="utf-8"))
    items = parse_hn(payload)
    assert len(items) == 2
    first = items[0]
    assert first["title"] == "OpenAI releases new agent framework"
    assert first["url"] == "https://example.com/a"
    assert first["points"] == 320
    assert first["source"] == "hackernews"
    assert first["published_at"] == datetime(2026, 9, 11, 22, 0, tzinfo=timezone.utc)


def test_parse_hn_falls_back_to_discussion_url_when_url_is_null():
    payload = json.loads((FIX / "hn_response.json").read_text(encoding="utf-8"))
    items = parse_hn(payload)
    assert items[1]["url"] == "https://news.ycombinator.com/item?id=44444"


def test_parse_rss_maps_fields():
    xml = (FIX / "news_rss.xml").read_text(encoding="utf-8")
    items = parse_rss(xml, "googlenews")
    assert len(items) == 1
    assert items[0]["title"] == "AI 회의록 정리 서비스 국내 출시"
    assert items[0]["source"] == "googlenews"
    assert items[0]["points"] == 0
    assert items[0]["published_at"].tzinfo is not None


def test_parse_rss_returns_empty_on_garbage():
    assert parse_rss("not xml at all", "googlenews") == []


def test_parse_hn_accepts_timestamp_without_milliseconds():
    payload = {"hits": [{
        "title": "Some story without millisecond timestamp",
        "url": "https://example.com/b",
        "points": 100,
        "created_at": "2026-09-16T02:25:18Z",
    }]}
    items = parse_hn(payload)
    assert len(items) == 1
    assert items[0]["published_at"] == datetime(2026, 9, 16, 2, 25, 18, tzinfo=timezone.utc)
