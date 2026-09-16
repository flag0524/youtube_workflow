# 선정된 주제로 쇼츠 대본을 생성하고 길이·형식 제약을 검증하는 모듈
import json
from pathlib import Path

import anthropic

from config import load_config

MAX_TITLE = 60
MAX_HOOK = 12
MAX_CAPTION = 12
LENGTH_TOLERANCE = 0.15

SYSTEM_PROMPT = """너는 한국 직장인 대상 AI 유튜브 쇼츠 대본 작가다.

절대 규칙:
1. 겪지 않은 경험을 1인칭으로 서술하지 마라. "제가 해봤더니", "저는 이걸로 얼마 벌었습니다" 금지.
   대신 "공개된 자료에 따르면", "제조사 발표 기준" 같은 표현을 써라.
2. 주어진 자료에 없는 수치를 만들지 마라. 모든 수치와 인용은 sources 에 URL을 남겨라.
3. narration 은 귀로 듣는 문장, caption 은 눈으로 읽는 자막이다. 둘은 다르게 써라.
   caption 은 12자 이내로 끊어라.
4. 구어체 짧은 문장. 한 문장 20자 내외.
5. 개발자 전용 용어를 쓰지 마라. 사무직이 아는 말로 바꿔라.
6. JSON만 출력해라. 설명 문장을 붙이지 마라."""

USER_PROMPT = """주제: {title}
앵글: {angles}
출처: {source_url}
포맷: {format_name} ({seconds}초)

나레이션 전체 길이는 공백 포함 {target}자 ±15% 로 맞춰라.

JSON 스키마:
{{
  "title": "유튜브 제목, 60자 이내, 앞 25자에 검색 키워드",
  "hook": "첫 2초 화면 자막, 12자 이내",
  "segments": [{{"narration": "읽을 문장", "caption": "화면 자막 12자 이내"}}],
  "loop_line": "마지막 1.5초, 다시 보게 만드는 한 문장",
  "description": "설명란 3~5줄",
  "tags": ["최대 15개"],
  "sources": ["근거 URL 최소 1개"]
}}"""


def target_chars(seconds: int, cpm: int) -> int:
    return int(seconds * cpm / 60)


def validate_script(data: dict, *, seconds: int, cpm: int) -> None:
    for key in ("title", "hook", "segments", "loop_line", "description",
                "tags", "sources"):
        if key not in data:
            raise ValueError(f"필수 키 누락: {key}")

    if len(data["title"]) > MAX_TITLE:
        raise ValueError(f"title 이 {MAX_TITLE}자를 넘는다: {len(data['title'])}자")
    if len(data["hook"]) > MAX_HOOK:
        raise ValueError(f"hook 이 {MAX_HOOK}자를 넘는다: {len(data['hook'])}자")

    if not data["sources"]:
        raise ValueError("sources 가 비어 있다. 근거 URL이 최소 1개 필요하다")

    for i, seg in enumerate(data["segments"]):
        if len(seg["caption"]) > MAX_CAPTION:
            raise ValueError(
                f"segments[{i}].caption 이 {MAX_CAPTION}자를 넘는다: {len(seg['caption'])}자"
            )

    total = sum(len(s["narration"]) for s in data["segments"])
    goal = target_chars(seconds, cpm)
    lo, hi = goal * (1 - LENGTH_TOLERANCE), goal * (1 + LENGTH_TOLERANCE)
    if not lo <= total <= hi:
        raise ValueError(
            f"나레이션 길이가 범위를 벗어났다: {total}자 (목표 {goal}자, 허용 {lo:.0f}~{hi:.0f}자)"
        )


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    cfg = load_config()
    topics = json.loads((out_dir / "topics.json").read_text(encoding="utf-8"))
    chosen, fmt = topics["chosen"], topics["format"]
    cpm = cfg["llm"]["chars_per_minute"]

    client = anthropic.Anthropic(api_key=cfg["anthropic_api_key"])
    prompt = USER_PROMPT.format(
        title=chosen["title"], angles=", ".join(chosen["angles"]),
        source_url=chosen.get("source_url", ""), format_name=fmt["name"],
        seconds=fmt["seconds"], target=target_chars(fmt["seconds"], cpm),
    )

    last_error = None
    for attempt in range(2):
        resp = client.messages.create(
            model=cfg["llm"]["model"], max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].removeprefix("json").strip()
        data = json.loads(text)
        try:
            validate_script(data, seconds=fmt["seconds"], cpm=cpm)
            break
        except ValueError as exc:
            last_error = exc
            prompt += f"\n\n직전 시도가 다음 이유로 거부됐다. 고쳐서 다시 출력해라: {exc}"
    else:
        raise ValueError(f"대본이 2회 모두 검증을 통과하지 못했다: {last_error}")

    if not dry_run:
        (out_dir / "script.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return data
