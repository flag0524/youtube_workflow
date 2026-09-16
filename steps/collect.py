# 이슈를 수집해 바이럴 앵글로 변환하고 실측 점수로 오늘의 주제 1건을 선정하는 모듈
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from config import load_config, load_seeds
from steps.history import angle_used_this_week, load_history, published_count
from steps.scoring import score_candidate
from steps.sources import collect_raw_issues
from steps.ytmetrics import fetch_keyword_metrics

logger = logging.getLogger(__name__)

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

ANGLE_PROMPT = """너는 한국 직장인 대상 AI 유튜브 쇼츠 채널의 기획자다.

아래 원시 이슈 목록에서 오늘 쇼츠로 만들 후보 5건을 뽑아라.

오늘 포맷: {format_name} ({seconds}초)
타깃: AI를 업무에 쓰는 한국 직장인 (기획·마케팅·사무직)

사용 가능한 앵글:
- loss_aversion: 손해를 피하게 하는 정보 ("아직 유료로 쓰세요?")
- actionable: 지금 바로 따라할 수 있는 것
- korea_only: 한국에서만 해당되는 정보
- comparison: 두 도구를 실제 비교
- number_shock: 구체적 숫자의 충격
- myth_busting: 통념 뒤집기
- job_threat: 일자리·업무 소멸 경고

엄격한 규칙:
1. 겪지 않은 경험을 1인칭으로 쓰지 마라. "제가 해봤더니" 금지.
2. 원시 이슈에 없는 수치를 지어내지 마라.
3. title 은 60자 이내, 앞 25자에 사람들이 실제로 검색할 한국어 키워드를 넣어라.
4. keyword 는 유튜브에 그대로 검색할 짧은 한국어 구절이다 (2~4어절).
5. 개발자 전용 용어(LangGraph, MCP 등)는 직장인이 아는 말로 바꿔라.

원시 이슈:
{issues}

JSON만 출력해라:
{{"candidates": [{{"title": "...", "keyword": "...", "angles": ["actionable"], "source_url": "..."}}]}}
"""


def seed_ratio(published: int, cfg: dict) -> float:
    cs = cfg["cold_start"]
    if published < cs["threshold_videos"]:
        return cs["seed_ratio_before"]
    return cs["seed_ratio_after"]


def filter_capped_angles(candidates: list[dict], history: list[dict], *,
                         now: datetime, cfg: dict) -> list[dict]:
    """주간 상한에 걸린 앵글을 후보에서 제거한다. 남은 앵글이 없으면 후보 자체를 버린다.

    now 는 tz-aware(UTC)로 들어오지만 steps.history 의 날짜 비교는 naive 를
    가정한다 (Task 3, 이미 승인됨). score_candidate 와 같은 패턴으로 여기서도
    tzinfo 를 제거하고 넘긴다.
    """
    caps = cfg.get("angle_weekly_cap", {})
    naive_now = now.replace(tzinfo=None)
    kept = []
    for c in candidates:
        allowed = [
            a for a in c["angles"]
            if a not in caps
            or angle_used_this_week(a, history, now=naive_now) < caps[a]
        ]
        if allowed:
            kept.append({**c, "angles": allowed})
    return kept


def map_angles(issues: list[dict], fmt: dict, client, cfg: dict) -> list[dict]:
    issue_lines = "\n".join(
        f"- {i['title']} ({i['source']}, {i['url']})" for i in issues[:40]
    )
    prompt = ANGLE_PROMPT.format(
        format_name=fmt["name"], seconds=fmt["seconds"], issues=issue_lines
    )
    resp = client.messages.create(
        model=cfg["llm"]["model"],
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    data = json.loads(text)

    published_lookup = {i["title"]: i["published_at"] for i in issues}
    out = []
    for c in data["candidates"]:
        out.append({
            "title": c["title"],
            "keyword": c["keyword"],
            "angles": c["angles"],
            "source_url": c.get("source_url", ""),
            "published_at": published_lookup.get(c["title"],
                                                 datetime.now(timezone.utc)),
        })
    return out


def _seed_candidates(cfg: dict, count: int) -> list[dict]:
    seeds = load_seeds()
    picked = random.sample(seeds, min(count, len(seeds)))
    now = datetime.now(timezone.utc)
    return [{
        "title": s["keyword"],
        "keyword": s["keyword"],
        "angles": [s["angle"]],
        "source_url": "",
        "published_at": now,  # 에버그린은 신선도 만점으로 취급한다
    } for s in picked]


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    cfg = load_config()
    now = datetime.now(timezone.utc)
    date = datetime.strptime(date_str, "%Y-%m-%d")
    fmt = cfg["formats"][WEEKDAY_KEYS[date.weekday()]]

    history = load_history(cfg["root"] / "history.jsonl")
    ratio = seed_ratio(published_count(history), cfg)

    candidates = _seed_candidates(cfg, round(5 * ratio))

    issues = collect_raw_issues(now=now, logger=logger)
    if issues:
        client = anthropic.Anthropic(api_key=cfg["anthropic_api_key"])
        candidates += map_angles(issues, fmt, client, cfg)
    else:
        logger.warning("이슈 수집 0건. 시드 주제만 사용한다.")
        candidates = _seed_candidates(cfg, 5)

    candidates = filter_capped_angles(candidates, history, now=now, cfg=cfg)
    if not candidates:
        raise RuntimeError("앵글 상한 적용 후 남은 후보가 없다")

    from steps.upload import get_youtube_service
    youtube = get_youtube_service()
    for c in candidates:
        metrics = fetch_keyword_metrics(youtube, c["keyword"], now=now)
        c.update(metrics)
        c["score"] = score_candidate(c, now=now, history=history, cfg=cfg)

    candidates.sort(key=lambda c: c["score"], reverse=True)
    chosen = candidates[0]

    payload = {
        "date": date_str,
        "format": fmt,
        "chosen": chosen,
        "candidates": candidates,
    }
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "topics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return payload
