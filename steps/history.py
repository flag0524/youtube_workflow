# 발행 이력을 읽고 쓰며 주제 중복과 앵글 사용 빈도를 판정하는 모듈
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# 조사·어미로 끝나는 1글자 토큰은 의미가 없어 제외한다.
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")
_TRAILING_PARTICLES = set("은는이가을를도만과와의에로")


# 흔한 조사 1글자만 제거하는 휴리스틱. 다중 글자 조사(에서/부터 등)는 처리하지 않는다.
def extract_keywords(text: str) -> set[str]:
    keywords = set()
    for token in _TOKEN.findall(text):
        if len(token) >= 2 and token[-1] in _TRAILING_PARTICLES:
            token = token[:-1]
        if len(token) >= 2:
            keywords.add(token)
    return keywords


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_history(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def append_record(path: Path, record: dict) -> None:
    path = Path(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _within(record: dict, now: datetime, days: int) -> bool:
    d = datetime.strptime(record["date"], "%Y-%m-%d")
    return now - d <= timedelta(days=days)


def is_duplicate(title: str, history: list[dict], *, now: datetime,
                 window_days: int, threshold: float) -> bool:
    target = extract_keywords(title)
    for rec in history:
        if not _within(rec, now, window_days):
            continue
        if jaccard(target, extract_keywords(rec["title"])) > threshold:
            return True
    return False


def angle_used_this_week(angle: str, history: list[dict], *, now: datetime) -> int:
    return sum(1 for r in history
               if r.get("angle") == angle and _within(r, now, 7))


def published_count(history: list[dict]) -> int:
    return len(history)
