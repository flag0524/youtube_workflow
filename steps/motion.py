# 자막 타이밍을 Remotion 으로 렌더해 투명 모션 자막 오버레이(webm)를 만드는 모듈
import json
import logging
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from config import load_config

logger = logging.getLogger("motion")

HOOK_SECONDS = 2.0  # steps.subtitles 의 훅 표시 시간과 같다
JEV_URL = "https://api.typesafe.ai/v1/systemone"
_FONT_FALLBACK = Path("C:/Windows/Fonts/malgunbd.ttf")
# Remotion 이 내려받는 전용 브라우저는 앱 제어 정책에 막혀 실행되지 않는다(EFTYPE). 설치된 Chrome 을 쓴다.
_CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def longest_word(text: str) -> str:
    return max(text.split(), key=len)


def _jev_choice(text: str, words: list[str]) -> str:
    r = requests.post(
        JEV_URL, timeout=30,
        headers={"Authorization": f"Bearer {os.environ['JEV_API_KEY']}"},
        json={"state": text, "model": "jev-latest", "questions": {"keyword": {
            "type": "choice",
            "instructions": "쇼츠 자막에서 시청자가 가장 먼저 기억해야 할 핵심 단어는 무엇인가?",
            "criteria": {w: None for w in words},
        }}})
    r.raise_for_status()
    return r.json()["answers"]["keyword"]["choice"]


def pick_keyword(text: str, ask=_jev_choice) -> str | None:
    """강조할 단어 하나를 고른다. Jev 가 실패하거나 후보 밖을 답하면 가장 긴 단어를 쓴다."""
    words = list(dict.fromkeys(text.split()))
    if not words:
        return None
    if len(words) == 1:
        return words[0]
    try:
        answer = ask(text, words)
        if answer in words:
            return answer
    except Exception as exc:
        logger.warning("Jev 키워드 선택 실패, 최장 단어로 대체: %s", exc)
    return longest_word(text)


def build_props(timings: dict, cfg: dict, keywords: list[str | None]) -> dict:
    """절제된 모션 규칙. 마지막 자막(행동 유도)만 pop, 나머지는 짧은 페이드."""
    v, caps = cfg["video"], timings["captions"]
    return {
        "width": v["width"], "height": v["height"], "fps": v["fps"],
        "duration": timings["duration"],
        "logo": cfg["brand"]["logo_text"], "fontFile": "font.ttf",
        "captionY": v["caption_y"],
        "hook": {"text": timings["hook"], "end": HOOK_SECONDS, "y": v["hook_y"]},
        "captions": [
            {"text": c["caption"], "start": c["start"], "end": c["end"],
             "keyword": k, "style": "pop" if i == len(caps) - 1 else "fade"}
            for i, (c, k) in enumerate(zip(caps, keywords))
        ],
    }


def _font(cfg: dict) -> Path:
    for f in sorted((Path(cfg["root"]) / cfg["video"]["font_dir"]).glob("*.[ot]tf")):
        return f
    if _FONT_FALLBACK.exists():
        return _FONT_FALLBACK
    raise RuntimeError("모션 자막용 한글 폰트를 찾지 못했다")


def _render_overlay(props: dict, out_dir: Path, cfg: dict) -> Path:
    project = Path(cfg["root"]) / "remotion"
    npx = shutil.which("npx")
    if not npx or not (project / "node_modules").exists():
        raise RuntimeError("remotion 이 설치되지 않았다. remotion/ 에서 npm install 을 실행하라")
    (project / "public").mkdir(exist_ok=True)
    shutil.copy(_font(cfg), project / "public" / "font.ttf")
    (out_dir / "motion_props.json").write_text(
        json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    out = (out_dir / "overlay.webm").resolve()
    result = subprocess.run(
        [npx, "remotion", "render", "src/index.ts", "Captions", str(out),
         f"--props={(out_dir / 'motion_props.json').resolve()}",
         "--codec=vp9", "--image-format=png", "--pixel-format=yuva420p",
         *([f"--browser-executable={_CHROME}"] if _CHROME.exists() else [])],
        cwd=project, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600)
    if result.returncode != 0 or not out.exists():
        raise RuntimeError(f"remotion 렌더 실패:\n{(result.stderr or result.stdout)[-1500:]}")
    return out


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    """오버레이 경로를 돌려준다. 실패하면 None 을 돌려줘 render 가 ASS 자막으로 폴백한다."""
    if dry_run:
        return {"overlay": None}
    (out_dir / "overlay.webm").unlink(missing_ok=True)  # 지난 실행의 오버레이가 남아 쓰이면 안 된다
    try:
        cfg = load_config()
        timings = json.loads((out_dir / "timings.json").read_text(encoding="utf-8"))
        with ThreadPoolExecutor(6) as ex:
            keywords = list(ex.map(pick_keyword, [c["caption"] for c in timings["captions"]]))
        _render_overlay(build_props(timings, cfg, keywords), out_dir, cfg)
        return {"overlay": "overlay.webm"}
    except Exception as exc:
        logger.warning("모션 자막 실패, ASS 자막으로 폴백: %s", exc)
        return {"overlay": None}
