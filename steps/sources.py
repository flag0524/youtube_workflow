# Hacker News 와 RSS 피드에서 AI 관련 원시 이슈를 수집하고 공통 형태로 정규화하는 모듈
import logging
from datetime import datetime, timedelta, timezone

import feedparser
import requests

HN_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"

RSS_FEEDS = [
    ("googlenews", "https://news.google.com/rss/search?q=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5&hl=ko&gl=KR&ceid=KR:ko"),
    ("googlenews", "https://news.google.com/rss/search?q=%EC%B1%97GPT&hl=ko&gl=KR&ceid=KR:ko"),
    ("zdnet_kr", "https://feeds.feedburner.com/zdkorea"),
    ("etnews", "https://rss.etnews.com/Section901.xml"),
]


def parse_hn(payload: dict) -> list[dict]:
    items = []
    for hit in payload.get("hits", []):
        title = hit.get("title")
        if not title:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        items.append({
            "title": title,
            "url": url,
            "source": "hackernews",
            "points": hit.get("points") or 0,
            "published_at": datetime.strptime(
                hit["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc),
        })
    return items


def parse_rss(xml_text: str, source_name: str) -> list[dict]:
    feed = feedparser.parse(xml_text)
    items = []
    for entry in feed.entries:
        if not getattr(entry, "title", None):
            continue
        parsed = getattr(entry, "published_parsed", None)
        published = (
            datetime(*parsed[:6], tzinfo=timezone.utc)
            if parsed
            else datetime.now(timezone.utc)
        )
        items.append({
            "title": entry.title,
            "url": getattr(entry, "link", ""),
            "source": source_name,
            "points": 0,
            "published_at": published,
        })
    return items


def collect_raw_issues(*, now: datetime, logger: logging.Logger) -> list[dict]:
    """한 소스가 실패해도 나머지로 진행한다. 전부 실패하면 빈 리스트를 반환한다."""
    issues: list[dict] = []

    since = int((now - timedelta(hours=48)).timestamp())
    try:
        resp = requests.get(
            HN_ENDPOINT,
            params={
                "query": "AI",
                "tags": "story",
                "numericFilters": f"points>50,created_at_i>{since}",
                "hitsPerPage": 30,
            },
            timeout=10,
        )
        resp.raise_for_status()
        issues += parse_hn(resp.json())
    except Exception as exc:
        logger.warning("HN 수집 실패: %s", exc)

    for name, url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            issues += parse_rss(resp.text, name)
        except Exception as exc:
            logger.warning("RSS 수집 실패 (%s): %s", name, exc)

    return issues
