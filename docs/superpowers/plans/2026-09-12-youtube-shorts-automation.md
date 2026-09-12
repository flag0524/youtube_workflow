# 유튜브 쇼츠 매일 1건 자동화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 관련 한국어 쇼츠를 매일 1편 무인 생성해 유튜브에 예약 공개한다.

**Architecture:** 단계별 독립 스크립트가 `out/YYYY-MM-DD/` 에 JSON·미디어 산출물을 남기고, 각 단계는 앞 단계의 파일만 읽는다. 단계 간 공유 상태가 없어 어느 단계든 단독 재실행할 수 있다. 순수 로직(점수화·자막 생성·중복 판정)은 I/O에서 분리해 네트워크 없이 테스트한다.

**Tech Stack:** Python 3.11, anthropic, edge-tts, ffmpeg(CLI), google-api-python-client, PyYAML, fontTools, pytest

## Global Constraints

- Python 3.11. 프로젝트 전용 `venv/` 를 쓴다. 전역 파이썬으로 실행하지 않는다.
- Windows 전용 환경이다. 경로 리터럴에 `/tmp`, `/usr/share` 등 POSIX 절대경로를 쓰지 않는다.
- 모든 진입 스크립트 첫 줄에 `sys.stdout.reconfigure(encoding="utf-8")` 를 넣는다. Windows 콘솔 기본 인코딩 cp949는 한글·이모지 출력에서 죽는다.
- 새로 만드는 모든 `.py` 파일 첫 줄은 역할을 설명하는 한 줄 한국어 주석이다 (`config.yaml` 등 설정 파일은 제외).
- 영상 규격은 1080×1920 / 30fps 고정이다.
- 대본 LLM 외 편당 비용 0원. 유료 TTS·유료 영상 API·유료 스톡을 도입하지 않는다.
- Anthropic 모델 ID는 `claude-sonnet-5` 를 쓴다.
- 예외를 `except: pass` 로 삼키지 않는다. 반드시 로그를 남기거나 다시 던진다.
- 커밋 메시지 마지막 줄은 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` 이다.
- 작업 브랜치는 `design/shorts-automation` 이다. `main` 에 직접 커밋하지 않는다.

## File Structure

| 파일 | 책임 |
|---|---|
| `config.yaml` | 요일 포맷, 점수 가중치, 브랜드, 업로드 시각 |
| `seeds.yaml` | 콜드 스타트용 에버그린 주제 풀 |
| `config.py` | `.env` + `config.yaml` 병합 로더 |
| `steps/history.py` | 발행 이력 읽기·쓰기, 키워드 추출, 중복 판정 |
| `steps/sources.py` | HN·RSS 수집 및 정규화 |
| `steps/scoring.py` | 5축 점수화 (순수 함수, 네트워크 없음) |
| `steps/ytmetrics.py` | YouTube 검색 수요·경쟁 공백 조회 |
| `steps/collect.py` | 수집·앵글 매핑·점수화 통합 → `topics.json` |
| `steps/script.py` | Anthropic 대본 생성 → `script.json` |
| `steps/voice.py` | edge-tts 음성 + 단어 타이밍 → `narration.mp3`, `timings.json` |
| `steps/subtitles.py` | 타이밍 → `.ass` 자막 (순수 함수) |
| `steps/render.py` | ffmpeg 합성 → `short.mp4` |
| `steps/upload.py` | 예약 공개 업로드 → `result.json` |
| `daily.py` | 오케스트레이터, 재시도, `--dry-run` |

`steps/scoring.py`, `steps/subtitles.py`, `steps/history.py` 는 순수 함수만 담는다. 기존 코드가 깨진 지점(랜덤 점수, 자막 동기화)이 정확히 여기라서 네트워크 없이 단위 테스트가 가능해야 한다.

---

### Task 1: 저장소 위생 — 노출된 자격증명 격리

`client_secrets.json` 이 커밋되어 GitHub 원격에 푸시된 상태다. 이후 모든 커밋이 안전하려면 먼저 추적을 끊는다.

> 원격 이력에서 지우는 것과 Google Cloud에서 클라이언트를 폐기·재발급하는 것은 사용자가 직접 결정할 사항이다. 이 태스크는 **추적 해제와 재발 방지**까지만 한다.

**Files:**
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: `.gitignore` 작성**

```gitignore
# 자격증명
client_secrets.json
token.pickle
.env

# 파이썬
venv/
__pycache__/
*.pyc

# 산출물
out/
history.jsonl
```

- [ ] **Step 2: 이미 추적 중인 파일의 추적 해제**

작업 트리의 파일은 남기고 인덱스에서만 뺀다. `--cached` 없이 실행하면 실제 자격증명 파일이 삭제되어 OAuth가 깨진다.

```bash
git rm --cached client_secrets.json
git rm --cached -r __pycache__
```

- [ ] **Step 3: 추적 해제 확인**

Run: `git ls-files`
Expected: 출력에 `client_secrets.json` 과 `__pycache__/` 가 **없어야** 한다. `config.py`, `main.py`, `README.md` 등은 남아 있다.

- [ ] **Step 4: 작업 트리에 자격증명이 살아 있는지 확인**

Run: `python -c "import json,pathlib; d=json.loads(pathlib.Path('client_secrets.json').read_text()); print('ok' if (d.get('installed') or d.get('web')) else 'broken')"`
Expected: `ok`

- [ ] **Step 5: `.env.example` 작성**

```dotenv
# Anthropic API 키 (대본 생성·앵글 매핑에 사용)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

- [ ] **Step 6: 커밋**

```bash
git add .gitignore .env.example
git commit -m "chore: 자격증명·캐시 파일 추적 해제

client_secrets.json 이 원격에 푸시된 상태였다. 추적을 끊고
.gitignore 로 재발을 막는다. 원격 이력 정리와 OAuth 클라이언트
재발급은 별도 조치가 필요하다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: 설정 로더와 의존성 교체

**Files:**
- Create: `config.yaml`
- Create: `seeds.yaml`
- Modify: `config.py` (전면 재작성)
- Modify: `requirements.txt` (전면 재작성)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.load_config() -> dict` — `config.yaml` 전체에 `anthropic_api_key` 키를 더한 딕셔너리를 반환한다. 이후 모든 태스크가 이 함수로 설정을 읽는다.

- [ ] **Step 1: venv 생성과 의존성 설치**

`requirements.txt` 를 전면 교체한다. `openai`, `elevenlabs`, `gTTS`, `moviepy`, `Pillow` 는 더 이상 쓰지 않는다.

```
anthropic>=0.40.0
edge-tts>=6.1.0
requests>=2.31.0
feedparser>=6.0.10
PyYAML>=6.0
python-dotenv>=1.0.0
fonttools>=4.50.0
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.2.0
pytest>=8.0.0
```

```bash
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

- [ ] **Step 2: ffmpeg 확인**

Run: `ffmpeg -version`
Expected: `ffmpeg version 8.1.2` 로 시작하는 출력. 실패하면 이후 렌더 태스크가 전부 막히므로 여기서 멈추고 설치한다.

- [ ] **Step 3: `config.yaml` 작성**

```yaml
brand:
  channel_name: "AI 일잘러"
  logo_text: "AI 일잘러"

target:
  audience: "office_worker"
  keywords:
    - 보고서
    - 엑셀
    - 회의록
    - 기획
    - 마케팅
    - 업무
    - 직장인
    - 자동화
    - 문서
    - 메일

formats:
  mon: { name: "AI 이슈 속보", seconds: 25, role: "reach" }
  tue: { name: "바로 쓰는 AI 업무 꿀팁", seconds: 40, role: "reach" }
  wed: { name: "AI 이슈 속보", seconds: 25, role: "reach" }
  thu: { name: "바로 쓰는 AI 업무 꿀팁", seconds: 40, role: "reach" }
  fri: { name: "AI 이슈 속보", seconds: 25, role: "reach" }
  sat: { name: "업무 자동화 사례", seconds: 45, role: "convert" }
  sun: { name: "업무 자동화 사례", seconds: 45, role: "convert" }

angles:
  - loss_aversion
  - actionable
  - korea_only
  - comparison
  - number_shock
  - myth_busting
  - job_threat

# 주 1회 상한. 반복하면 채널이 공포 소구로 굳어 구독 전환이 떨어진다.
angle_weekly_cap:
  job_threat: 1

scoring:
  duplicate_penalty: 40
  duplicate_jaccard_threshold: 0.4
  duplicate_window_days: 30

cold_start:
  threshold_videos: 30
  seed_ratio_before: 0.8
  seed_ratio_after: 0.4

voice:
  name: "ko-KR-SunHiNeural"
  rate: "+12%"

video:
  width: 1080
  height: 1920
  fps: 30
  font_family: "Malgun Gothic"
  font_dir: "assets/fonts"
  caption_y: 960
  hook_y: 760

upload:
  publish_time_kst: "18:00"
  category_id: "28"
  timezone_offset_hours: 9

llm:
  model: "claude-sonnet-5"
  chars_per_minute: 330
```

- [ ] **Step 4: `seeds.yaml` 작성**

콜드 스타트용 에버그린 주제다. 신규 채널이 속보를 올려도 뜨지 않으므로 초기에는 검색 수요가 꾸준한 주제를 쓴다.

```yaml
seeds:
  - keyword: "챗GPT 보고서 작성"
    angle: actionable
    note: "직장인 검색 수요 상시"
  - keyword: "엑셀 함수 AI로 만들기"
    angle: actionable
    note: "사무직 진입 주제"
  - keyword: "회의록 자동 정리"
    angle: actionable
    note: "저장률 높음"
  - keyword: "무료로 쓰는 AI 도구"
    angle: loss_aversion
    note: "유료 결제 회피 심리"
  - keyword: "AI 번역 자연스럽게 쓰는 법"
    angle: actionable
  - keyword: "한국어로 쓰면 성능 떨어지는 이유"
    angle: korea_only
    note: "국내 채널의 해자"
  - keyword: "프롬프트 잘 쓰는 법"
    angle: actionable
  - keyword: "AI로 PPT 만들기"
    angle: actionable
  - keyword: "메일 답장 AI로 쓰기"
    angle: actionable
  - keyword: "AI 도구 유료 무료 차이"
    angle: number_shock
```

- [ ] **Step 5: 실패하는 테스트 작성**

```python
# tests/test_config.py
import os
from config import load_config


def test_load_config_merges_yaml_and_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = load_config()
    assert cfg["video"]["width"] == 1080
    assert cfg["video"]["fps"] == 30
    assert cfg["anthropic_api_key"] == "sk-ant-test"


def test_load_config_has_seven_day_formats():
    cfg = load_config()
    assert set(cfg["formats"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def test_reach_and_convert_split_is_five_two():
    cfg = load_config()
    roles = [f["role"] for f in cfg["formats"].values()]
    assert roles.count("reach") == 5
    assert roles.count("convert") == 2
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_config' from 'config'`

- [ ] **Step 7: `config.py` 전면 재작성**

```python
# .env 와 config.yaml 을 병합해 전역 설정 딕셔너리를 제공하는 로더
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_config() -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
    cfg["root"] = ROOT
    return cfg


def load_seeds() -> list[dict]:
    data = yaml.safe_load((ROOT / "seeds.yaml").read_text(encoding="utf-8"))
    return data["seeds"]
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 9: 커밋**

```bash
git add config.yaml seeds.yaml config.py requirements.txt tests/test_config.py
git commit -m "feat: 설정 로더와 의존성 교체

OpenAI·ElevenLabs·moviepy 의존성을 걷어내고 Anthropic·edge-tts·
ffmpeg 기반으로 바꾼다. 요일 포맷과 점수 가중치를 config.yaml 로
분리했다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 발행 이력과 중복 판정

**Files:**
- Create: `steps/__init__.py` (빈 파일)
- Create: `steps/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: `config.load_config()`
- Produces:
  - `extract_keywords(text: str) -> set[str]`
  - `jaccard(a: set[str], b: set[str]) -> float`
  - `load_history(path: Path) -> list[dict]` — 각 레코드는 `{"date": str, "title": str, "angle": str, "video_id": str}`
  - `append_record(path: Path, record: dict) -> None`
  - `is_duplicate(title: str, history: list[dict], *, now: datetime, window_days: int, threshold: float) -> bool`
  - `angle_used_this_week(angle: str, history: list[dict], *, now: datetime) -> int`
  - `published_count(history: list[dict]) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_history.py
import json
from datetime import datetime, timedelta

from steps.history import (
    angle_used_this_week,
    append_record,
    extract_keywords,
    is_duplicate,
    jaccard,
    load_history,
    published_count,
)

NOW = datetime(2026, 9, 12, 8, 0, 0)


def test_extract_keywords_drops_particles_and_short_tokens():
    kws = extract_keywords("챗GPT로 보고서 10분 만에 쓰는 법")
    assert "챗GPT" in kws
    assert "보고서" in kws
    assert "법" not in kws  # 1글자 토큰 제외


def test_jaccard_identical_sets_is_one():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_is_duplicate_detects_near_identical_title():
    history = [{"date": "2026-09-10", "title": "챗GPT로 보고서 10분 만에 쓰는 법",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("챗GPT로 보고서 쓰는 법 10분", history,
                        now=NOW, window_days=30, threshold=0.4) is True


def test_is_duplicate_ignores_records_outside_window():
    history = [{"date": "2026-01-01", "title": "챗GPT로 보고서 10분 만에 쓰는 법",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("챗GPT로 보고서 쓰는 법 10분", history,
                        now=NOW, window_days=30, threshold=0.4) is False


def test_is_duplicate_allows_unrelated_title():
    history = [{"date": "2026-09-10", "title": "엑셀 함수 AI로 만들기",
                "angle": "actionable", "video_id": "x"}]
    assert is_duplicate("회의록 자동 정리하는 도구", history,
                        now=NOW, window_days=30, threshold=0.4) is False


def test_angle_used_this_week_counts_only_last_seven_days():
    history = [
        {"date": "2026-09-11", "title": "a", "angle": "job_threat", "video_id": "1"},
        {"date": "2026-08-01", "title": "b", "angle": "job_threat", "video_id": "2"},
    ]
    assert angle_used_this_week("job_threat", history, now=NOW) == 1


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "history.jsonl"
    append_record(p, {"date": "2026-09-12", "title": "제목", "angle": "actionable",
                      "video_id": "abc"})
    loaded = load_history(p)
    assert len(loaded) == 1
    assert loaded[0]["title"] == "제목"


def test_load_history_returns_empty_when_file_missing(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []


def test_published_count(tmp_path):
    assert published_count([{"date": "2026-09-12", "title": "t",
                             "angle": "a", "video_id": "v"}]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps'`

- [ ] **Step 3: `steps/history.py` 구현**

```python
# 발행 이력을 읽고 쓰며 주제 중복과 앵글 사용 빈도를 판정하는 모듈
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# 조사·어미로 끝나는 1글자 토큰은 의미가 없어 제외한다.
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")


def extract_keywords(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text) if len(t) >= 2}


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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_history.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: 커밋**

```bash
git add steps/__init__.py steps/history.py tests/test_history.py
git commit -m "feat: 발행 이력과 주제 중복 판정 추가

기존 topic_generator 에는 이력 대조가 없어 같은 주제가 반복될 수
있었다. 자카드 유사도로 최근 30일 주제와 겹치는지 판정한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 이슈 수집 소스

기존 `topic_generator.py:9` 는 HN Algolia `search` 엔드포인트를 썼다. 이건 관련도순이라 수년 전 글이 올라온다. `search_by_date` 에 포인트·시간 필터를 건다. 그리고 `except: pass` 로 실패를 은폐하던 것을 로그로 바꾼다.

**Files:**
- Create: `steps/sources.py`
- Test: `tests/test_sources.py`
- Test: `tests/fixtures/hn_response.json`
- Test: `tests/fixtures/news_rss.xml`

**Interfaces:**
- Produces:
  - `parse_hn(payload: dict) -> list[dict]`
  - `parse_rss(xml_text: str, source_name: str) -> list[dict]`
  - `collect_raw_issues(*, now: datetime, logger) -> list[dict]`
  - 모든 이슈 레코드 형태는 `{"title": str, "url": str, "source": str, "published_at": datetime, "points": int}`

- [ ] **Step 1: 픽스처 작성**

```json
// tests/fixtures/hn_response.json
{
  "hits": [
    {
      "title": "OpenAI releases new agent framework",
      "url": "https://example.com/a",
      "points": 320,
      "created_at": "2026-09-11T22:00:00.000Z"
    },
    {
      "title": "Show HN: I built a spreadsheet copilot",
      "url": null,
      "objectID": "44444",
      "points": 88,
      "created_at": "2026-09-12T01:30:00.000Z"
    }
  ]
}
```

```xml
<!-- tests/fixtures/news_rss.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI 회의록 정리 서비스 국내 출시</title>
      <link>https://example.com/kr1</link>
      <pubDate>Fri, 11 Sep 2026 09:00:00 +0900</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_sources.py
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.sources'`

- [ ] **Step 4: `steps/sources.py` 구현**

```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_sources.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: 실제 네트워크로 한 번 확인**

Run: `./venv/Scripts/python.exe -c "import logging,sys; sys.stdout.reconfigure(encoding='utf-8'); from datetime import datetime,timezone; from steps.sources import collect_raw_issues; r=collect_raw_issues(now=datetime.now(timezone.utc), logger=logging.getLogger()); print(len(r)); [print(i['source'], i['title'][:50]) for i in r[:5]]"`
Expected: 10건 이상, 소스가 최소 2종 이상 섞여 나온다. 0건이면 필터가 너무 빡빡한 것이므로 `points>50` 을 `points>20` 으로 낮춘다.

- [ ] **Step 7: 커밋**

```bash
git add steps/sources.py tests/test_sources.py tests/fixtures/
git commit -m "feat: 이슈 수집 소스 교체

HN Algolia search(관련도순)를 search_by_date + 포인트·시간 필터로
바꿨다. 기존에는 수년 전 글이 올라왔다. except: pass 로 실패를
숨기던 것도 경고 로그로 바꿨다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: 점수화 엔진

기존 `topic_generator.py:44-46` 은 `80 + random.randint(0,15) + weight*30` 이었다. 랜덤 폭 15점이 필러 가중치 차이 7.5점을 압도해 사실상 제비뽑기였다. 랜덤을 완전히 제거하고 측정값만 쓴다.

**Files:**
- Create: `steps/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `demand_score(median_views: float) -> float` (0~30)
  - `gap_score(recent_ratio: float) -> float` (0~25)
  - `freshness_score(published_at: datetime, now: datetime) -> float` (0~20)
  - `angle_score(angles: list[str]) -> float` (0~15)
  - `target_score(text: str, keywords: list[str]) -> float` (0~10)
  - `score_candidate(candidate: dict, *, now, history, cfg) -> float`
  - candidate 형태는 `{"title": str, "angles": list[str], "published_at": datetime, "median_views": float, "recent_ratio": float}`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_scoring.py
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
    assert clean - dupe == 40
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.scoring'`

- [ ] **Step 3: `steps/scoring.py` 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_scoring.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add steps/scoring.py tests/test_scoring.py
git commit -m "feat: 실측 기반 점수화 엔진 추가

기존 viral_score 는 80 + random(0,15) 로 랜덤이 결과를 지배했다.
검색 수요·경쟁 공백·신선도·앵글·타깃 적합도 5축과 중복 패널티로
교체하고, 점수가 결정적임을 테스트로 고정했다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: YouTube 검색 지표 조회

점수화의 검색 수요·경쟁 공백 축에 넣을 실측값을 가져온다. `search.list` 는 호출당 100유닛, `videos.list` 는 1유닛이다. 후보 10건이면 1010유닛으로 일일 한도 10000 안에 들어간다.

**Files:**
- Create: `steps/ytmetrics.py`
- Modify: `uploader.py` → `steps/upload.py` 로 이동 (OAuth 함수 재사용을 위해 먼저 옮긴다)
- Test: `tests/test_ytmetrics.py`

**Interfaces:**
- Consumes: `steps.upload.get_youtube_service()` (이 태스크에서 파일만 이동, 내용 수정은 Task 12)
- Produces:
  - `median(values: list[int]) -> float`
  - `recent_ratio(published_dates: list[datetime], *, now: datetime, days: int = 90) -> float`
  - `fetch_keyword_metrics(youtube, keyword: str, *, now: datetime) -> dict` — `{"median_views": float, "recent_ratio": float}`

- [ ] **Step 1: `uploader.py` 를 `steps/upload.py` 로 이동**

이력을 남기기 위해 `git mv` 를 쓴다.

```bash
git mv uploader.py steps/upload.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_ytmetrics.py
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_ytmetrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.ytmetrics'`

- [ ] **Step 4: `steps/ytmetrics.py` 구현**

```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_ytmetrics.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: 커밋**

```bash
git add steps/ytmetrics.py steps/upload.py tests/test_ytmetrics.py
git commit -m "feat: YouTube 검색 수요·경쟁 공백 실측 추가

수요는 있는데 최근 영상이 없는 키워드가 신규 채널이 뚫을 수 있는
틈이다. 상위 10건의 조회수 중앙값과 최근 90일 비율로 측정한다.
uploader.py 를 steps/upload.py 로 이동했다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: 수집 통합 — 앵글 매핑과 주제 선정

기존 `topic_generator.py` 의 템플릿 문자열 조합을 폐기한다. `rivals` 딕셔너리에 없는 트렌드가 전부 `"Claude 4"` 로 폴백해 "Show HN: ... vs Claude 4" 같은 비문을 만들었다. 체험담 템플릿(`"$1,200 번 썰"`)도 제거한다. 겪지 않은 일을 1인칭으로 말하게 된다.

**Files:**
- Delete: `topic_generator.py` (`git rm`)
- Create: `steps/collect.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `steps.sources.collect_raw_issues`, `steps.scoring.score_candidate`, `steps.ytmetrics.fetch_keyword_metrics`, `steps.history.load_history`, `config.load_config`, `config.load_seeds`
- Produces:
  - `seed_ratio(published: int, cfg: dict) -> float`
  - `filter_capped_angles(candidates: list[dict], history: list[dict], *, now, cfg) -> list[dict]`
  - `map_angles(issues: list[dict], fmt: dict, client, cfg) -> list[dict]` — 후보 5건 반환, 각 후보는 `{"title", "angles", "keyword", "source_url", "published_at"}`
  - `run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict` — `topics.json` 을 쓰고 선정된 주제 딕셔너리를 반환

- [ ] **Step 1: 기존 파일 제거**

```bash
git rm topic_generator.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_collect.py
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.collect'`

- [ ] **Step 4: `steps/collect.py` 구현**

```python
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
    """주간 상한에 걸린 앵글을 후보에서 제거한다. 남은 앵글이 없으면 후보 자체를 버린다."""
    caps = cfg.get("angle_weekly_cap", {})
    kept = []
    for c in candidates:
        allowed = [
            a for a in c["angles"]
            if a not in caps
            or angle_used_this_week(a, history, now=now) < caps[a]
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_collect.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add steps/collect.py tests/test_collect.py
git rm --cached topic_generator.py 2>/dev/null; git add -A
git commit -m "feat: 주제 선정을 앵글 매핑 + 실측 점수로 교체

템플릿 문자열 조합을 폐기했다. rivals 딕셔너리 폴백 때문에
'Show HN: ... vs Claude 4' 같은 비문이 생성됐고, 체험담 템플릿은
겪지 않은 일을 1인칭으로 말하게 만들었다. 콜드 스타트 시드 비율과
앵글 주간 상한을 추가했다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: 대본 생성

**Files:**
- Delete: `script_writer.py` (`git rm`)
- Create: `steps/script.py`
- Test: `tests/test_script.py`

**Interfaces:**
- Consumes: `topics.json` (Task 7 산출)
- Produces:
  - `target_chars(seconds: int, cpm: int) -> int`
  - `validate_script(data: dict, *, seconds: int, cpm: int) -> None` — 위반 시 `ValueError`
  - `run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict` — `script.json` 기록
  - `script.json` 형태: `{"title", "hook", "segments": [{"narration", "caption"}], "loop_line", "description", "tags", "sources"}`

- [ ] **Step 1: 기존 파일 제거**

```bash
git rm script_writer.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_script.py
import pytest

from steps.script import target_chars, validate_script


def test_target_chars_for_forty_seconds():
    # 40초 × 330자/분 ÷ 60초 = 220자
    assert target_chars(40, 330) == 220


def test_target_chars_for_twentyfive_seconds():
    assert target_chars(25, 330) == 137


def _valid(n_chars=220):
    return {
        "title": "챗GPT로 보고서 10분 만에 끝내는 법",
        "hook": "보고서 아직 손으로?",
        "segments": [{"narration": "가" * n_chars, "caption": "짧은 자막"}],
        "loop_line": "다시 보기",
        "description": "설명",
        "tags": ["AI", "보고서"],
        "sources": ["https://example.com"],
    }


def test_validate_accepts_good_script():
    validate_script(_valid(), seconds=40, cpm=330)


def test_validate_rejects_missing_key():
    data = _valid()
    del data["hook"]
    with pytest.raises(ValueError, match="hook"):
        validate_script(data, seconds=40, cpm=330)


def test_validate_rejects_long_title():
    data = _valid()
    data["title"] = "가" * 61
    with pytest.raises(ValueError, match="title"):
        validate_script(data, seconds=40, cpm=330)


def test_validate_rejects_long_hook():
    data = _valid()
    data["hook"] = "가" * 13
    with pytest.raises(ValueError, match="hook"):
        validate_script(data, seconds=40, cpm=330)


def test_validate_rejects_long_caption():
    data = _valid()
    data["segments"][0]["caption"] = "가" * 13
    with pytest.raises(ValueError, match="caption"):
        validate_script(data, seconds=40, cpm=330)


def test_validate_rejects_narration_too_short():
    with pytest.raises(ValueError, match="나레이션"):
        validate_script(_valid(100), seconds=40, cpm=330)


def test_validate_rejects_narration_too_long():
    with pytest.raises(ValueError, match="나레이션"):
        validate_script(_valid(400), seconds=40, cpm=330)


def test_validate_rejects_empty_sources():
    data = _valid()
    data["sources"] = []
    with pytest.raises(ValueError, match="sources"):
        validate_script(data, seconds=40, cpm=330)
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_script.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.script'`

- [ ] **Step 4: `steps/script.py` 구현**

```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_script.py -v`
Expected: PASS (10 passed)

- [ ] **Step 6: 커밋**

```bash
git add steps/script.py tests/test_script.py
git add -A
git commit -m "feat: 대본 생성을 Anthropic 으로 교체하고 검증 추가

나레이션과 화면 자막을 분리하고, 길이·체험담 금지·출처 필수를
코드에서 검증한다. 검증 실패 시 이유를 붙여 1회 재요청한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: 음성 생성과 단어 타이밍

기존 `tts.py` 는 ElevenLabs(유료)에 gTTS 폴백이었다. gTTS는 단어 타이밍을 주지 않아 자막 동기화가 불가능하다. edge-tts 의 `WordBoundary` 이벤트를 쓴다.

**Files:**
- Delete: `tts.py` (`git rm`)
- Create: `steps/voice.py`
- Test: `tests/test_voice.py`

**Interfaces:**
- Consumes: `script.json`
- Produces:
  - `ticks_to_seconds(ticks: int) -> float` — edge-tts 오프셋은 100나노초 단위다
  - `assign_caption_times(segments: list[dict], words: list[dict]) -> list[dict]` — 각 항목 `{"caption": str, "start": float, "end": float}`
  - `run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict` — `narration.mp3`, `timings.json` 기록

- [ ] **Step 1: 기존 파일 제거**

```bash
git rm tts.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_voice.py
from steps.voice import assign_caption_times, ticks_to_seconds


def test_ticks_to_seconds():
    assert ticks_to_seconds(10_000_000) == 1.0
    assert ticks_to_seconds(5_000_000) == 0.5


def _words(specs):
    return [{"text": t, "start": s, "end": e} for t, s, e in specs]


def test_assign_caption_times_splits_by_narration_word_count():
    segments = [
        {"narration": "보고서 쓰기 힘들죠", "caption": "보고서 고민"},
        {"narration": "챗지피티 쓰면 됩니다", "caption": "AI가 해결"},
    ]
    words = _words([
        ("보고서", 0.0, 0.5), ("쓰기", 0.5, 1.0), ("힘들죠", 1.0, 1.6),
        ("챗지피티", 1.6, 2.2), ("쓰면", 2.2, 2.6), ("됩니다", 2.6, 3.2),
    ])
    result = assign_caption_times(segments, words)
    assert len(result) == 2
    assert result[0]["caption"] == "보고서 고민"
    assert result[0]["start"] == 0.0
    assert result[0]["end"] == 1.6
    assert result[1]["start"] == 1.6
    assert result[1]["end"] == 3.2


def test_assign_caption_times_is_gapless():
    segments = [
        {"narration": "한 둘", "caption": "A"},
        {"narration": "셋 넷", "caption": "B"},
    ]
    words = _words([("한", 0.0, 0.3), ("둘", 0.3, 0.7),
                    ("셋", 0.9, 1.2), ("넷", 1.2, 1.5)])
    result = assign_caption_times(segments, words)
    # 자막이 끊기면 화면이 비어 이탈한다. 다음 자막 시작까지 이어 붙인다.
    assert result[0]["end"] == result[1]["start"]


def test_assign_caption_times_handles_fewer_words_than_expected():
    segments = [
        {"narration": "한 둘 셋", "caption": "A"},
        {"narration": "넷 다섯 여섯", "caption": "B"},
    ]
    words = _words([("한", 0.0, 0.3), ("둘", 0.3, 0.6)])
    result = assign_caption_times(segments, words)
    assert len(result) == 2
    assert result[-1]["end"] >= result[-1]["start"]
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_voice.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.voice'`

- [ ] **Step 4: `steps/voice.py` 구현**

```python
# edge-tts 로 나레이션 음성을 만들고 단어 경계 타이밍으로 자막 구간을 산출하는 모듈
import asyncio
import json
from pathlib import Path

import edge_tts

from config import load_config

TICKS_PER_SECOND = 10_000_000


def ticks_to_seconds(ticks: int) -> float:
    return ticks / TICKS_PER_SECOND


async def _synthesize(text: str, voice: str, rate: str, mp3_path: Path) -> list[dict]:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    words: list[dict] = []
    with mp3_path.open("wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = ticks_to_seconds(chunk["offset"])
                words.append({
                    "text": chunk["text"],
                    "start": start,
                    "end": start + ticks_to_seconds(chunk["duration"]),
                })
    return words


def assign_caption_times(segments: list[dict], words: list[dict]) -> list[dict]:
    """나레이션의 어절 수 비율로 단어 타이밍을 세그먼트에 배분한다.

    edge-tts 의 단어 분절은 나레이션 어절과 1:1로 맞지 않을 수 있다.
    누적 어절 수로 경계를 잡고, 단어가 모자라면 마지막 타이밍으로 채운다.
    """
    if not words:
        return [{"caption": s["caption"], "start": 0.0, "end": 0.0}
                for s in segments]

    result, cursor = [], 0
    last_end = words[-1]["end"]
    for seg in segments:
        count = len(seg["narration"].split())
        chunk = words[cursor:cursor + count]
        if chunk:
            start, end = chunk[0]["start"], chunk[-1]["end"]
        else:
            start = end = last_end
        result.append({"caption": seg["caption"], "start": start, "end": end})
        cursor += count

    # 자막 사이에 빈 구간이 생기면 화면이 비어 이탈한다. 다음 시작까지 이어 붙인다.
    for i in range(len(result) - 1):
        result[i]["end"] = result[i + 1]["start"]
    result[-1]["end"] = max(result[-1]["end"], last_end)
    return result


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    cfg = load_config()
    script = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
    text = " ".join(s["narration"] for s in script["segments"])

    mp3_path = out_dir / "narration.mp3"
    words = asyncio.run(_synthesize(
        text, cfg["voice"]["name"], cfg["voice"]["rate"], mp3_path
    ))
    captions = assign_caption_times(script["segments"], words)

    payload = {
        "duration": words[-1]["end"] if words else 0.0,
        "words": words,
        "captions": captions,
        "hook": script["hook"],
        "loop_line": script["loop_line"],
    }
    if not dry_run:
        (out_dir / "timings.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return payload
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_voice.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: 실제 음성 1건 생성해 길이 확인**

```bash
./venv/Scripts/python.exe -c "import asyncio,sys; sys.stdout.reconfigure(encoding='utf-8'); from pathlib import Path; from steps.voice import _synthesize; w=asyncio.run(_synthesize('안녕하세요. 오늘은 챗지피티로 보고서 쓰는 법을 알려드립니다.','ko-KR-SunHiNeural','+12%',Path('test_voice.mp3'))); print('단어 수', len(w)); print('길이', w[-1]['end'])"
```

Expected: 단어 수가 10 내외, 길이가 4~6초. `test_voice.mp3` 를 재생해 한국어가 정상인지 듣는다. 확인 후 파일을 지운다.

- [ ] **Step 7: 커밋**

```bash
git add steps/voice.py tests/test_voice.py
git add -A
git commit -m "feat: 음성 생성을 edge-tts 로 교체하고 단어 타이밍 추출

ElevenLabs 유료 의존을 제거했다. gTTS 폴백은 단어 타이밍을 주지
않아 자막 동기화가 불가능했다. WordBoundary 이벤트로 세그먼트별
자막 구간을 산출한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: ASS 자막 생성

기존 `video_maker.py:43-53` 은 나레이션을 마침표로 쪼개 각 8초씩 고정 배정했다. 실제 음성 길이와 무관해 자막과 음성이 어긋났다. `timings.json` 을 근거로 삼는다.

**Files:**
- Create: `steps/subtitles.py`
- Test: `tests/test_subtitles.py`

**Interfaces:**
- Consumes: `timings.json` (Task 9 산출)
- Produces:
  - `format_time(seconds: float) -> str` — ASS 시간 형식 `H:MM:SS.cc`
  - `build_ass(timings: dict, cfg: dict) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_subtitles.py
from steps.subtitles import build_ass, format_time

CFG = {
    "video": {"width": 1080, "height": 1920, "font_family": "Malgun Gothic",
              "caption_y": 960, "hook_y": 760},
    "brand": {"logo_text": "AI 일잘러"},
}

TIMINGS = {
    "duration": 6.0,
    "hook": "보고서 아직 손으로?",
    "loop_line": "다시 보기",
    "captions": [
        {"caption": "보고서 고민", "start": 0.0, "end": 3.0},
        {"caption": "AI가 해결", "start": 3.0, "end": 6.0},
    ],
}


def test_format_time():
    assert format_time(0) == "0:00:00.00"
    assert format_time(65.25) == "0:01:05.25"
    assert format_time(3661.5) == "1:01:01.50"


def test_build_ass_has_required_sections():
    ass = build_ass(TIMINGS, CFG)
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass


def test_build_ass_uses_configured_resolution():
    ass = build_ass(TIMINGS, CFG)
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass


def test_build_ass_emits_one_dialogue_per_caption_plus_hook():
    ass = build_ass(TIMINGS, CFG)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    # 훅 1줄 + 자막 2줄 + 로고 1줄
    assert len(dialogues) == 4


def test_build_ass_places_captions_in_safe_area():
    """쇼츠 UI가 하단을 가린다. 자막 y 는 620~1250 안에 있어야 한다."""
    ass = build_ass(TIMINGS, CFG)
    assert "\\pos(540,960)" in ass
    assert "\\pos(540,760)" in ass


def test_build_ass_escapes_newlines_in_caption():
    timings = {**TIMINGS, "captions": [
        {"caption": "두 줄\n자막", "start": 0.0, "end": 1.0}]}
    ass = build_ass(timings, CFG)
    assert "두 줄\\N자막" in ass
    # 실제 개행이 Dialogue 줄을 깨뜨리면 안 된다
    for line in ass.splitlines():
        assert not line.startswith("자막")


def test_build_ass_hook_ends_at_two_seconds():
    ass = build_ass(TIMINGS, CFG)
    hook_line = [l for l in ass.splitlines()
                 if l.startswith("Dialogue:") and "보고서 아직 손으로?" in l][0]
    assert "0:00:00.00,0:00:02.00" in hook_line
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_subtitles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.subtitles'`

- [ ] **Step 3: `steps/subtitles.py` 구현**

```python
# 단어 타이밍을 ffmpeg 가 번인할 수 있는 ASS 자막 문자열로 변환하는 순수 함수 모듈
HOOK_SECONDS = 2.0

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},78,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,60,1
Style: Hook,{font},104,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,2,5,60,60,60,1
Style: Logo,{font},34,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,7,50,50,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    centis = int(round((secs - int(secs)) * 100))
    if centis == 100:  # 반올림이 초를 넘기는 경우
        secs, centis = int(secs) + 1, 0
    return f"{int(hours)}:{int(minutes):02d}:{int(secs):02d}.{centis:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("\n", "\\N").replace("\r", "")


def _dialogue(start: float, end: float, style: str, override: str,
              text: str) -> str:
    return (f"Dialogue: 0,{format_time(start)},{format_time(end)},{style},,"
            f"0,0,0,,{override}{_escape(text)}")


def build_ass(timings: dict, cfg: dict) -> str:
    v = cfg["video"]
    cx = v["width"] // 2
    lines = [_HEADER.format(width=v["width"], height=v["height"],
                            font=v["font_family"])]

    lines.append(_dialogue(0.0, HOOK_SECONDS, "Hook",
                           f"{{\\pos({cx},{v['hook_y']})}}", timings["hook"]))

    for cap in timings["captions"]:
        lines.append(_dialogue(cap["start"], cap["end"], "Caption",
                               f"{{\\pos({cx},{v['caption_y']})}}",
                               cap["caption"]))

    lines.append(_dialogue(0.0, timings["duration"], "Logo", "",
                           cfg["brand"]["logo_text"]))

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_subtitles.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add steps/subtitles.py tests/test_subtitles.py
git commit -m "feat: 실제 음성 타이밍 기반 ASS 자막 생성

기존에는 나레이션을 마침표로 쪼개 8초씩 고정 배정해 음성과 자막이
어긋났다. timings.json 의 단어 경계를 근거로 삼고, 자막을 쇼츠 UI가
가리지 않는 y 620~1250 안에 배치한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: 영상 렌더

기존 `video_maker.py:15` 는 폰트 경로가 `/usr/share/fonts/truetype/nanum/` 리눅스 전용이었다. Windows에서 항상 `except` 로 빠져 `load_default()` 를 써 한글이 전부 두부(□)로 나왔다. 폰트 해석을 명시적으로 검증하고, 실패하면 조용히 넘어가지 않고 중단한다.

**Files:**
- Delete: `video_maker.py` (`git rm`)
- Create: `steps/render.py`
- Create: `assets/bg/gradient.png` (스텝 중 생성)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `timings.json`, `narration.mp3`
- Produces:
  - `resolve_font(cfg: dict) -> Path` — 한글 글리프가 없으면 `RuntimeError`
  - `font_supports_korean(path: Path) -> bool`
  - `font_family_name(path: Path) -> str` — ASS `Fontname` 에 넣을 내부 패밀리명
  - `build_ffmpeg_command(bg, mp3, ass, out, cfg) -> list[str]`
  - `run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> Path` — `short.mp4` 기록

> **배경 줌 보류:** 스펙 §7.2는 "그라디언트에 느린 줌"이라고 적었으나 이 계획은 정적 배경으로 간다. `zoompan` 필터는 단일 이미지에 쓸 때 총 프레임 수를 정확히 넘겨야 하고 렌더 시간이 크게 는다. 자막이 2~3초마다 바뀌므로 화면 변화는 이미 있다. 완시청률이 낮게 나오면 그때 추가한다.

- [ ] **Step 1: 기존 파일 제거와 배경 생성**

```bash
git rm video_maker.py
mkdir -p assets/bg assets/fonts
```

배경은 ffmpeg 로 한 번만 만들어 재사용한다. 별도 이미지 라이브러리를 쓰지 않는다.

```bash
ffmpeg -y -f lavfi -i "gradients=s=1080x1920:c0=0x0B1020:c1=0x1B2A55:n=2:d=1" -frames:v 1 assets/bg/gradient.png
```

Run: `ffprobe -v error -show_entries stream=width,height -of csv=p=0 assets/bg/gradient.png`
Expected: `1080,1920`

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_render.py
from pathlib import Path

import pytest

from steps.render import (
    build_ffmpeg_command,
    font_family_name,
    font_supports_korean,
    resolve_font,
)

CFG = {
    "video": {"width": 1080, "height": 1920, "fps": 30,
              "font_family": "Malgun Gothic", "font_dir": "assets/fonts"},
    "root": Path("."),
}


def test_malgun_gothic_supports_korean():
    p = Path("C:/Windows/Fonts/malgunbd.ttf")
    if not p.exists():
        pytest.skip("맑은 고딕 없음")
    assert font_supports_korean(p) is True


def test_font_family_name_is_not_the_filename_stem():
    """ASS Fontname 은 파일명이 아니라 폰트 내부 패밀리명이어야 한다.

    malgunbd.ttf 의 stem 은 'malgunbd' 지만 패밀리명은 'Malgun Gothic' 이다.
    stem 을 넣으면 libass 가 매칭에 실패해 다시 두부가 찍힌다.
    """
    p = Path("C:/Windows/Fonts/malgunbd.ttf")
    if not p.exists():
        pytest.skip("맑은 고딕 없음")
    assert font_family_name(p) == "Malgun Gothic"


def test_resolve_font_raises_when_nothing_found(tmp_path, monkeypatch):
    # 폴백을 비우지 않으면 실제 설치된 맑은 고딕이 잡혀 예외가 나지 않는다.
    monkeypatch.setattr("steps.render._WINDOWS_FALLBACKS", [])
    cfg = {"video": {"font_dir": "missing", "font_family": "NoSuchFont"},
           "root": tmp_path}
    with pytest.raises(RuntimeError, match="한글"):
        resolve_font(cfg)


def test_build_ffmpeg_command_uses_relative_paths():
    """Windows 절대경로의 드라이브 콜론은 subtitles 필터 문법을 깨뜨린다."""
    cmd = build_ffmpeg_command("bg.png", "narration.mp3", "subs.ass",
                               "short.mp4", CFG)
    joined = " ".join(cmd)
    assert "subtitles=subs.ass" in joined
    assert ":\\" not in joined
    assert "D:" not in joined


def test_build_ffmpeg_command_sets_thirty_fps():
    cmd = build_ffmpeg_command("bg.png", "narration.mp3", "subs.ass",
                               "short.mp4", CFG)
    assert "-r" in cmd
    assert cmd[cmd.index("-r") + 1] == "30"


def test_build_ffmpeg_command_ends_with_audio():
    cmd = build_ffmpeg_command("bg.png", "narration.mp3", "subs.ass",
                               "short.mp4", CFG)
    assert "-shortest" in cmd


def test_build_ffmpeg_command_uses_yuv420p_for_compatibility():
    cmd = build_ffmpeg_command("bg.png", "narration.mp3", "subs.ass",
                               "short.mp4", CFG)
    assert "yuv420p" in cmd
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steps.render'`

- [ ] **Step 4: `steps/render.py` 구현**

```python
# 배경·자막·나레이션을 ffmpeg 로 합성해 쇼츠 mp4 를 만드는 모듈
import json
import shutil
import subprocess
from pathlib import Path

from fontTools.ttLib import TTFont

from config import load_config
from steps.subtitles import build_ass

# 이 글자들이 전부 있어야 한국어 자막이 두부(□)로 깨지지 않는다.
_KOREAN_PROBE = "가나다한글은는이"

_WINDOWS_FALLBACKS = [
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    Path("C:/Windows/Fonts/malgun.ttf"),
]


def font_supports_korean(path: Path) -> bool:
    try:
        cmap = TTFont(str(path), fontNumber=0, lazy=True).getBestCmap()
    except Exception:
        return False
    return all(ord(ch) in cmap for ch in _KOREAN_PROBE)


def font_family_name(path: Path) -> str:
    """ASS Fontname 에 넣을 패밀리명을 폰트 name 테이블에서 읽는다.

    파일명 stem 을 쓰면 안 된다. malgunbd.ttf 의 패밀리명은 'Malgun Gothic'
    이고, libass 는 패밀리명으로 매칭한다. stem 을 넣으면 매칭에 실패해
    한글이 다시 두부로 찍힌다.
    """
    font = TTFont(str(path), fontNumber=0, lazy=True)
    for record in font["name"].names:
        if record.nameID == 1:  # Font Family name
            return record.toUnicode()
    raise RuntimeError(f"폰트 패밀리명을 읽지 못했다: {path}")


def resolve_font(cfg: dict) -> Path:
    """동봉 폰트를 1순위, 맑은 고딕을 폴백으로 쓴다.

    기존 코드는 폰트 로드 실패를 조용히 삼키고 기본 폰트로 넘어가
    한글이 전부 두부로 찍힌 영상을 만들었다. 여기서는 중단한다.
    """
    font_dir = Path(cfg["root"]) / cfg["video"]["font_dir"]
    if font_dir.exists():
        for candidate in sorted(font_dir.glob("*.[ot]tf")):
            if font_supports_korean(candidate):
                return candidate

    for candidate in _WINDOWS_FALLBACKS:
        if candidate.exists() and font_supports_korean(candidate):
            return candidate

    raise RuntimeError(
        f"한글 글리프를 가진 폰트를 찾지 못했다. {font_dir} 에 한글 폰트를 넣어라."
    )


def build_ffmpeg_command(bg: str, mp3: str, ass: str, out: str,
                         cfg: dict) -> list[str]:
    """모든 인자는 작업 디렉터리 기준 상대 경로여야 한다.

    Windows 절대경로의 드라이브 콜론(D:)은 subtitles 필터 문법과 충돌한다.
    호출부에서 cwd 를 출력 폴더로 지정해 상대 경로만 넘긴다.
    """
    v = cfg["video"]
    return [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg,
        "-i", mp3,
        "-vf", f"subtitles={ass}:fontsdir=fonts",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", str(v["fps"]),
        "-s", f"{v['width']}x{v['height']}",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out,
    ]


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> Path:
    cfg = load_config()
    timings = json.loads((out_dir / "timings.json").read_text(encoding="utf-8"))

    font_path = resolve_font(cfg)
    cfg["video"]["font_family"] = font_family_name(font_path)

    (out_dir / "subs.ass").write_text(build_ass(timings, cfg), encoding="utf-8")

    # ffmpeg 를 out_dir 에서 실행하므로 필요한 자원을 상대 경로로 놓는다.
    local_fonts = out_dir / "fonts"
    local_fonts.mkdir(exist_ok=True)
    shutil.copy(font_path, local_fonts / font_path.name)
    shutil.copy(Path(cfg["root"]) / "assets/bg/gradient.png", out_dir / "bg.png")

    cmd = build_ffmpeg_command("bg.png", "narration.mp3", "subs.ass",
                               "short.mp4", cfg)
    if dry_run:
        print(" ".join(cmd))
        return out_dir / "short.mp4"

    result = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{result.stderr[-2000:]}")

    return out_dir / "short.mp4"
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_render.py -v`
Expected: PASS (6 passed, 맑은 고딕이 없으면 1 skipped)

- [ ] **Step 6: 실제 렌더 1건 검증**

Task 9에서 만든 음성과 임의 타이밍으로 한 편을 렌더해 규격을 확인한다.

Run: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,pix_fmt -of default=nw=1 out/2026-09-12/short.mp4`
Expected: `width=1080`, `height=1920`, `r_frame_rate=30/1`, `pix_fmt=yuv420p`

- [ ] **Step 7: 한글 렌더링 육안 확인**

자동 검증이 어려운 부분이다. 프레임 3장을 뽑아 직접 본다.

```bash
ffmpeg -y -i out/2026-09-12/short.mp4 -vf "select='eq(n\,30)+eq(n\,150)+eq(n\,300)'" -vsync 0 out/2026-09-12/frame_%02d.png
```

Expected: PNG 3장이 생기고, 열었을 때 자막이 **두부(□)가 아닌 한글**로 보인다. 두부가 보이면 `resolve_font` 가 고른 폰트를 확인한다.

- [ ] **Step 8: 커밋**

```bash
git add steps/render.py tests/test_render.py assets/bg/gradient.png
git add -A
git commit -m "feat: 렌더를 moviepy 에서 ffmpeg 로 교체

기존 폰트 경로가 리눅스 전용이라 Windows 에서 항상 기본 폰트로
폴백해 한글이 두부로 찍혔다. fontTools 로 한글 글리프 존재를
검증하고 없으면 중단한다. 드라이브 콜론이 subtitles 필터를 깨뜨리는
문제는 cwd 를 출력 폴더로 잡아 상대 경로만 쓰는 것으로 피했다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: 예약 공개 업로드

기존 `steps/upload.py:38` 은 `privacyStatus: "public"` 즉시 공개였고 `publishAt` 이 없었다. 예약 공개는 반드시 `private` 으로 올려야 동작한다.

**Files:**
- Modify: `steps/upload.py` (OAuth 함수는 유지, 업로드 본문 재작성)
- Test: `tests/test_upload.py`

**Interfaces:**
- Consumes: `script.json`, `short.mp4`
- Produces:
  - `get_youtube_service()` (기존 유지)
  - `publish_at_rfc3339(date_str: str, time_kst: str, offset_hours: int) -> str`
  - `build_request_body(script: dict, publish_at: str, cfg: dict) -> dict`
  - `run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict` — `result.json` 기록

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_upload.py
import pytest

from steps.upload import build_request_body, publish_at_rfc3339

CFG = {
    "upload": {"publish_time_kst": "18:00", "category_id": "28",
               "timezone_offset_hours": 9},
    "brand": {"channel_name": "AI 일잘러"},
}

SCRIPT = {
    "title": "챗GPT로 보고서 10분 만에 끝내는 법",
    "description": "설명 본문",
    "tags": ["AI", "보고서"],
    "sources": ["https://example.com/a"],
}


def test_publish_at_converts_kst_to_utc():
    # 2026-09-12 18:00 KST = 2026-09-12 09:00 UTC
    assert publish_at_rfc3339("2026-09-12", "18:00", 9) == "2026-09-12T09:00:00Z"


def test_publish_at_rolls_back_a_day_when_needed():
    # 2026-09-12 06:00 KST = 2026-09-11 21:00 UTC
    assert publish_at_rfc3339("2026-09-12", "06:00", 9) == "2026-09-11T21:00:00Z"


def test_body_is_private_for_scheduled_publish():
    """publishAt 은 privacyStatus 가 private 일 때만 동작한다."""
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-09-12T09:00:00Z"


def test_body_declares_synthetic_content():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["containsSyntheticMedia"] is True


def test_body_is_not_made_for_kids():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_body_truncates_long_title():
    script = {**SCRIPT, "title": "가" * 120}
    body = build_request_body(script, "2026-09-12T09:00:00Z", CFG)
    assert len(body["snippet"]["title"]) <= 100


def test_body_caps_tags_at_fifteen():
    script = {**SCRIPT, "tags": [f"t{i}" for i in range(40)]}
    body = build_request_body(script, "2026-09-12T09:00:00Z", CFG)
    assert len(body["snippet"]["tags"]) == 15


def test_description_includes_sources():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert "https://example.com/a" in body["snippet"]["description"]


def test_description_includes_shorts_hashtag():
    body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", CFG)
    assert "#Shorts" in body["snippet"]["description"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_upload.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_request_body'`

- [ ] **Step 3: `steps/upload.py` 재작성**

`get_youtube_service()` 의 토큰 처리는 정상 동작하므로 그대로 둔다.

```python
# 완성된 쇼츠를 YouTube 에 비공개로 올리고 지정 시각에 예약 공개하는 모듈
import json
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import YOUTUBE_SCOPES, load_config

MAX_TITLE = 100
MAX_TAGS = 15


def get_youtube_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secrets.json", YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)


def publish_at_rfc3339(date_str: str, time_kst: str, offset_hours: int) -> str:
    local = datetime.strptime(f"{date_str} {time_kst}", "%Y-%m-%d %H:%M")
    utc = local - timedelta(hours=offset_hours)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_request_body(script: dict, publish_at: str, cfg: dict) -> dict:
    sources = "\n".join(f"출처: {u}" for u in script.get("sources", []))
    description = (
        f"{script['description']}\n\n{sources}\n\n"
        f"{cfg['brand']['channel_name']}\n"
        "이 영상의 나레이션은 AI 음성으로 제작되었습니다.\n"
        "#Shorts #AI #업무자동화"
    )
    return {
        "snippet": {
            "title": script["title"][:MAX_TITLE],
            "description": description,
            "tags": script.get("tags", [])[:MAX_TAGS],
            "categoryId": cfg["upload"]["category_id"],
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            # publishAt 은 privacyStatus 가 private 일 때만 동작한다.
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    cfg = load_config()
    script = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
    video_path = out_dir / "short.mp4"

    publish_at = publish_at_rfc3339(
        date_str, cfg["upload"]["publish_time_kst"],
        cfg["upload"]["timezone_offset_hours"],
    )
    body = build_request_body(script, publish_at, cfg)

    if dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return {"dry_run": True, "body": body}

    youtube = get_youtube_service()
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True,
                            mimetype="video/*")
    response = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    ).execute()

    result = {
        "video_id": response["id"],
        "url": f"https://youtube.com/watch?v={response['id']}",
        "publish_at": publish_at,
        "privacy_status": response["status"]["privacyStatus"],
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_upload.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add steps/upload.py tests/test_upload.py
git commit -m "feat: 즉시 공개를 예약 공개로 교체하고 합성 콘텐츠 고지 추가

publishAt 은 privacyStatus 가 private 일 때만 동작한다. 개발자용
해시태그 하드코딩을 걷어내고 대본이 만든 태그와 출처를 쓴다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: 오케스트레이터

**Files:**
- Delete: `main.py` (`git rm`)
- Create: `daily.py`
- Test: `tests/test_daily.py`

**Interfaces:**
- Consumes: 모든 `steps.*` 모듈의 `run(date_str, out_dir, dry_run=...)`
- Produces:
  - `STEPS: list[tuple[str, callable]]`
  - `run_step(name, fn, date_str, out_dir, *, dry_run, retries=1) -> object`
  - `main(argv=None) -> int`

- [ ] **Step 1: 기존 파일 제거**

```bash
git rm main.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_daily.py
import pytest

from daily import run_step


def test_run_step_returns_result_on_first_success(tmp_path):
    calls = []

    def fn(date_str, out_dir, dry_run=False):
        calls.append(1)
        return "ok"

    assert run_step("test", fn, "2026-09-12", tmp_path, dry_run=False) == "ok"
    assert len(calls) == 1


def test_run_step_retries_once_then_succeeds(tmp_path):
    calls = []

    def fn(date_str, out_dir, dry_run=False):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("일시적 실패")
        return "ok"

    assert run_step("test", fn, "2026-09-12", tmp_path, dry_run=False) == "ok"
    assert len(calls) == 2


def test_run_step_raises_after_retry_exhausted(tmp_path):
    def fn(date_str, out_dir, dry_run=False):
        raise RuntimeError("계속 실패")

    with pytest.raises(RuntimeError, match="계속 실패"):
        run_step("test", fn, "2026-09-12", tmp_path, dry_run=False)


def test_step_order_is_collect_script_voice_render_upload():
    from daily import STEPS

    assert [name for name, _ in STEPS] == [
        "collect", "script", "voice", "render", "upload"
    ]
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_daily.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daily'`

- [ ] **Step 4: `daily.py` 구현**

```python
# 하루 한 편의 쇼츠를 수집부터 예약 공개까지 순서대로 실행하는 오케스트레이터
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from config import load_config
from steps import collect, render, script, upload, voice
from steps.history import append_record

STEPS = [
    ("collect", collect.run),
    ("script", script.run),
    ("voice", voice.run),
    ("render", render.run),
    ("upload", upload.run),
]

logger = logging.getLogger("daily")


def run_step(name, fn, date_str, out_dir, *, dry_run, retries=1):
    """실패하면 지정 횟수만큼 재시도한다. 그래도 실패하면 예외를 올린다."""
    attempt = 0
    while True:
        try:
            logger.info("[%s] 시작", name)
            result = fn(date_str, out_dir, dry_run=dry_run)
            logger.info("[%s] 완료", name)
            return result
        except Exception as exc:
            attempt += 1
            if attempt > retries:
                logger.error("[%s] 실패: %s", name, exc)
                raise
            logger.warning("[%s] 실패, 재시도 %d회차: %s", name, attempt, exc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true",
                        help="업로드 없이 전 단계를 실행한다")
    parser.add_argument("--from-step", choices=[n for n, _ in STEPS],
                        help="지정한 단계부터 재실행한다")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("daily.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    cfg = load_config()
    out_dir = Path(cfg["root"]) / "out" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = STEPS
    if args.from_step:
        start = [n for n, _ in STEPS].index(args.from_step)
        steps = STEPS[start:]

    results = {}
    for name, fn in steps:
        try:
            results[name] = run_step(name, fn, args.date, out_dir,
                                     dry_run=args.dry_run)
        except Exception as exc:
            (out_dir / "result.json").write_text(
                json.dumps({"failed_step": name, "error": str(exc)},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.error("파이프라인 중단. 불완전한 영상은 올리지 않는다.")
            return 1

    if not args.dry_run and "upload" in results:
        topics = json.loads((out_dir / "topics.json").read_text(encoding="utf-8"))
        script_data = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
        append_record(Path(cfg["root"]) / "history.jsonl", {
            "date": args.date,
            "title": script_data["title"],
            "angle": topics["chosen"]["angles"][0],
            "video_id": results["upload"]["video_id"],
        })
        logger.info("완료: %s", results["upload"]["url"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./venv/Scripts/python.exe -m pytest tests/test_daily.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: 전체 테스트 실행**

Run: `./venv/Scripts/python.exe -m pytest -v`
Expected: 전부 PASS. 실패하면 여기서 고친다.

- [ ] **Step 7: dry-run 전 구간 실행**

Run: `./venv/Scripts/python.exe daily.py --dry-run --date 2026-09-12`
Expected: 5단계가 모두 완료 로그를 남기고 종료 코드 0. `out/2026-09-12/` 에 `topics.json`, `script.json`, `narration.mp3`, `timings.json`, `subs.ass`, `short.mp4` 가 생긴다. 업로드는 요청 바디만 출력된다.

- [ ] **Step 8: 커밋**

```bash
git add daily.py tests/test_daily.py
git add -A
git commit -m "feat: 오케스트레이터 추가

단계별 1회 재시도, --from-step 재실행, --dry-run 을 지원한다.
실패하면 result.json 에 실패 단계를 남기고 중단한다. 불완전한
영상을 올리는 것보다 그날을 건너뛰는 편이 낫다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 14: 실업로드 검증과 스케줄 등록

스펙 §8.1의 미검증 항목을 여기서 확인한다. **감사를 받지 않은 Google Cloud 프로젝트는 업로드가 비공개로 잠길 수 있다.** 이게 사실이면 예약 공개 완전 자동화는 성립하지 않으므로 폴백으로 전환해야 한다.

**Files:**
- Create: `README.md` (전면 재작성)
- Create: `checklist.md`
- Create: `context-notes.md`

- [ ] **Step 1: 실제 업로드 1건 실행**

```bash
./venv/Scripts/python.exe daily.py --date 2026-09-12
```

처음 실행하면 브라우저가 열리며 OAuth 동의를 요구한다. 완료하면 `token.pickle` 이 생성된다.

Expected: 종료 코드 0, `out/2026-09-12/result.json` 에 `video_id` 기록.

- [ ] **Step 2: 예약 공개가 실제로 걸렸는지 확인**

```bash
./venv/Scripts/python.exe -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); import json; from steps.upload import get_youtube_service; vid=json.load(open('out/2026-09-12/result.json',encoding='utf-8'))['video_id']; r=get_youtube_service().videos().list(part='status',id=vid).execute(); print(json.dumps(r['items'][0]['status'], ensure_ascii=False, indent=2))"
```

Expected: `privacyStatus: "private"` 이고 `publishAt` 이 설정되어 있다.

**판정 분기:**
- `publishAt` 이 그대로 있으면 예약 공개가 동작한다. Step 3으로 진행한다.
- `publishAt` 이 사라졌거나 `uploadStatus` 가 `rejected`/`failed` 면 감사 제한에 걸린 것이다. Step 3 대신 아래를 수행한다.

  1. `context-notes.md` 에 확인된 증상과 응답 원문을 기록한다
  2. Google Cloud Console에서 YouTube Data API 감사를 신청한다
  3. `config.yaml` 의 `upload:` 블록에 한 줄을 추가한다

     ```yaml
       manual_publish: true   # 감사 승인 전까지 예약 공개를 끄고 수동 공개로 운영
     ```

  4. `steps/upload.py` 의 `build_request_body` 를 아래로 교체한다

     ```python
     def build_request_body(script: dict, publish_at: str, cfg: dict) -> dict:
         sources = "\n".join(f"출처: {u}" for u in script.get("sources", []))
         description = (
             f"{script['description']}\n\n{sources}\n\n"
             f"{cfg['brand']['channel_name']}\n"
             "이 영상의 나레이션은 AI 음성으로 제작되었습니다.\n"
             "#Shorts #AI #업무자동화"
         )
         status = {
             "privacyStatus": "private",
             "selfDeclaredMadeForKids": False,
             "containsSyntheticMedia": True,
         }
         # 감사 미승인 프로젝트는 publishAt 을 무시하거나 업로드를 거부한다.
         # 이 경우 비공개로만 올리고 공개는 사람이 스튜디오에서 누른다.
         if not cfg["upload"].get("manual_publish"):
             status["publishAt"] = publish_at
         return {
             "snippet": {
                 "title": script["title"][:MAX_TITLE],
                 "description": description,
                 "tags": script.get("tags", [])[:MAX_TAGS],
                 "categoryId": cfg["upload"]["category_id"],
                 "defaultLanguage": "ko",
                 "defaultAudioLanguage": "ko",
             },
             "status": status,
         }
     ```

  5. 이 분기를 덮는 테스트를 `tests/test_upload.py` 에 추가한다

     ```python
     def test_body_omits_publish_at_in_manual_mode():
         cfg = {**CFG, "upload": {**CFG["upload"], "manual_publish": True}}
         body = build_request_body(SCRIPT, "2026-09-12T09:00:00Z", cfg)
         assert "publishAt" not in body["status"]
         assert body["status"]["privacyStatus"] == "private"
     ```

     Run: `./venv/Scripts/python.exe -m pytest tests/test_upload.py -v`
     Expected: PASS (10 passed)

  6. `daily.py` 실행 후 사람이 공개를 눌러야 한다는 사실을 `README.md` 에 명시하고 Step 3으로 진행한다

- [ ] **Step 3: 합성 콘텐츠 고지가 반영됐는지 확인**

YouTube 스튜디오에서 해당 영상의 "변경된 콘텐츠 또는 합성 콘텐츠" 표시를 확인한다. API의 `containsSyntheticMedia` 가 반영되지 않았으면 스튜디오 → 설정 → 업로드 기본값에서 채널 기본값으로 켠다.

- [ ] **Step 4: 작업 스케줄러 등록**

```powershell
$py = (Resolve-Path ".\venv\Scripts\python.exe").Path
$wd = (Get-Location).Path
$action = New-ScheduledTaskAction -Execute $py -Argument "daily.py" -WorkingDirectory $wd
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName "YouTubeShortsDaily" -Action $action -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` 이 PC가 꺼져 있던 날의 누락 실행을 다음 부팅 때 보정한다.

- [ ] **Step 5: 스케줄 등록 확인과 수동 1회 실행**

```powershell
Get-ScheduledTask -TaskName "YouTubeShortsDaily" | Select-Object TaskName, State
Start-ScheduledTask -TaskName "YouTubeShortsDaily"
```

Expected: `State` 가 `Ready`. 실행 후 `daily.log` 에 5단계 완료 로그가 남는다.

- [ ] **Step 6: 문서 3종 작성**

`README.md` 에 설치·설정·실행·문제 해결을 적는다. 최소한 아래를 포함한다.

- venv 생성과 `pip install -r requirements.txt`
- `.env` 에 `ANTHROPIC_API_KEY` 설정
- Google Cloud 프로젝트 생성 → YouTube Data API 활성화 → OAuth 클라이언트(데스크톱 앱) 생성 → `client_secrets.json` 배치
- `daily.py --dry-run` 으로 먼저 확인하는 절차
- `--from-step` 으로 특정 단계부터 재실행하는 법
- 한글이 두부로 나올 때 `assets/fonts/` 에 폰트를 넣는 조치
- Step 2에서 확인된 API 감사 결과와 현재 운영 모드
- 수익화 정책상 주 1회 직접 검토를 권한다는 안내

`checklist.md` 에 이 계획의 태스크를 체크박스로 옮긴다.

`context-notes.md` 에 아래 결정과 근거를 적는다.

- 랜덤 점수를 실측 5축으로 바꾼 이유
- 폰트를 fontTools 로 검증하고 실패 시 중단하는 이유 (조용한 폴백이 두부 영상을 만들었다)
- ffmpeg 를 출력 폴더 cwd 에서 상대 경로로 실행하는 이유 (드라이브 콜론이 필터 문법과 충돌)
- Step 2의 API 감사 판정 결과
- 체험담 템플릿을 제거한 이유

- [ ] **Step 7: 커밋**

```bash
git add README.md checklist.md context-notes.md
git add -A
git commit -m "docs: 설치·운영 문서와 컨텍스트 노트 작성

API 감사 검증 결과와 운영 모드를 기록한다.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## 남은 결정 사항

계획 밖이지만 사용자 결정이 필요한 항목이다.

1. **노출된 OAuth 자격증명** — Task 1은 추적 해제까지만 한다. 원격 이력 정리(force push)와 Google Cloud 클라이언트 재발급은 결정이 필요하다.
2. **브랜치 병합** — `design/shorts-automation` 을 `main` 에 언제 병합할지.
3. **수익화 정책 리스크** — 무인 자동 발행은 대량 생산 콘텐츠 정책의 위험 구간에 있다. 설계로 제거할 수 없으며 감수 여부는 운영 판단이다.
