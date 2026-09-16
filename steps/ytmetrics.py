# YouTube 검색 결과에서 키워드의 수요와 경쟁 공백을 실측하는 모듈
from datetime import datetime, timedelta, timezone


def median(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2


def recent_ratio(published_dates: list[datetime], *, now: datetime,
                 days: int = 90) -> float:
    if not published_dates:
        return 1.0
    cutoff = now - timedelta(days=days)
    return sum(1 for d in published_dates if d >= cutoff) / len(published_dates)


def fetch_keyword_metrics(youtube, keyword: str, *, now: datetime) -> dict:
    search = youtube.search().list(
        part="id", q=keyword, type="video", maxResults=10, order="relevance",
        regionCode="KR", relevanceLanguage="ko",
    ).execute()

    ids = [it["id"]["videoId"] for it in search.get("items", [])
           if it.get("id", {}).get("videoId")]
    if not ids:
        return {"median_views": 0.0, "recent_ratio": 1.0}

    detail = youtube.videos().list(
        part="statistics,snippet", id=",".join(ids)
    ).execute()

    views, dates = [], []
    for item in detail.get("items", []):
        views.append(int(item["statistics"].get("viewCount", 0)))
        dates.append(datetime.strptime(
            item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc))

    return {
        "median_views": median(views),
        "recent_ratio": recent_ratio(dates, now=now),
    }
