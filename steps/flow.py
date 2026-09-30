# Google Flow 웹 화면을 Playwright 로 조작해 세그먼트별 배경 영상 클립을 만드는 모듈
import json
import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path

import requests

from config import load_config

logger = logging.getLogger("flow")

FLOW_URL = "https://flow.google.com/"
SUPPORTED_SECONDS = (4, 6, 8, 10)
_THUMB = "생성된 동영상 썸네일"
_LAUNCH = dict(
    channel="chrome", headless=False, accept_downloads=True,
    ignore_default_args=["--enable-automation"],
    args=["--disable-blink-features=AutomationControlled"],
)


def pick_duration(seconds: float) -> int:
    """세그먼트를 덮는 가장 짧은 Flow 길이를 고른다. 크레딧은 길이에 비례한다."""
    for s in SUPPORTED_SECONDS:
        if seconds <= s + 1e-9:
            return s
    raise ValueError(f"Flow 는 10초를 넘는 클립을 만들 수 없다: {seconds:.1f}초")


def segment_durations(captions: list[dict], total: float) -> list[float]:
    """자막 경계로 세그먼트별 화면 길이를 구한다. 합이 나레이션 전체와 같다."""
    bounds = [0.0] + [c["start"] for c in captions[1:]] + [total]
    return [bounds[i + 1] - bounds[i] for i in range(len(captions))]


def build_prompt(seg: dict) -> str:
    # 자막은 ffmpeg 가 직접 얹으므로 화면 안 글자는 금지한다.
    return (f"세로형 9:16 시네마틱 B-roll 영상. 장면 주제: {seg['caption']}. "
            f"내용: {seg['narration']} "
            "화면에 글자, 자막, 로고, 워터마크를 넣지 마라. 인물이 말하지 않는다.")


def _popup(page):
    return page.locator("div:has-text('생성 시'):has-text('9:16')").last


def _open_settings(page):
    # 닫히는 중에 누른 클릭은 무시되므로 열린 것을 확인하며 다시 누른다.
    for _ in range(3):
        if _popup(page).is_visible():
            break
        page.get_by_label("설정 트리거").click()
        page.wait_for_timeout(800)
    _popup(page).wait_for(state="visible")
    return _popup(page)


def _apply_options(page, seconds: int, cfg: dict) -> int:
    """동영상·9:16·화질·길이·x1 을 매번 명시한다. 설정이 이전 값으로 남기 때문이다."""
    f = cfg["flow"]
    popup = _open_settings(page)
    for label in ("동영상", "9:16", f["resolution"], f"{seconds}초", "x1"):
        popup.get_by_text(label, exact=True).first.click()
    if f["model"] not in popup.inner_text():
        popup.locator("text=arrow_drop_down").first.click()
        page.get_by_text(f["model"], exact=True).last.click()
    m = re.search(r"(\d+)\s*크레딧", popup.inner_text())
    page.keyboard.press("Escape")
    popup.wait_for(state="hidden")
    return int(m.group(1)) if m else -1


def _submit(page, prompt: str) -> None:
    page.locator(".prosemirror-editor").first.click()
    page.keyboard.insert_text(prompt)
    page.wait_for_timeout(500)
    # 크레딧이 모자라면 제출 버튼이 "크레딧 부족 경고" 아이콘으로 바뀐다.
    if page.get_by_label("크레딧 부족 경고").count():
        raise RuntimeError("Flow 크레딧이 부족하다")
    page.get_by_text("arrow_forward").last.click()


def _wait_new_tile(page, before: int, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        page.wait_for_timeout(5000)
        done = page.get_by_alt_text(_THUMB).count() > before
        if done and not re.search(r"\b\d{1,3}%", page.inner_text("body")):
            return
    raise TimeoutError(f"Flow 생성이 {timeout}초 안에 끝나지 않았다")


def _save_original(page, dest: Path) -> None:
    """원본(720p)을 받는다. 클릭 시 Flow 가 서명된 mp4 주소를 요청하므로 그 주소를 잡아 직접 받는다.

    Playwright 다운로드 이벤트나 응답 본문에 기대면 다운로드 직후 Chrome 이 통째로
    종료돼 실패한다. 주소에 서명이 들어 있어 브라우저 없이도 받을 수 있다.
    """
    urls = []
    page.on("response", lambda r: urls.append(r.url)
            if "video/mp4" in r.headers.get("content-type", "") else None)
    page.get_by_text("download", exact=True).first.click()
    page.wait_for_timeout(1000)
    page.get_by_text("원본 크기").first.click()
    for _ in range(100):
        if urls:
            break
        page.wait_for_timeout(200)
    if not urls:
        raise RuntimeError("원본 mp4 주소를 받지 못했다")
    body = requests.get(urls[0], timeout=120).content
    if len(body) < 100_000 or body[4:8] != b"ftyp":
        raise RuntimeError(f"mp4 가 아닌 응답이다: {len(body)}바이트")
    dest.write_bytes(body)


def _open_clip(page, prompt: str) -> None:
    """프롬프트가 일치하는 타일의 편집 화면을 연다. 최신이 앞인지 뒤인지 몰라 양쪽을 본다."""
    page.wait_for_timeout(4000)
    n = page.get_by_alt_text(_THUMB).count()
    for idx in dict.fromkeys((0, n - 1)):
        page.get_by_alt_text(_THUMB).nth(idx).click()
        page.wait_for_url("**/edit/**", timeout=30000)
        page.wait_for_timeout(2000)
        if prompt[:40] in page.inner_text("body"):
            return
        page.get_by_text("arrow_back").first.click()
        page.wait_for_timeout(2000)
    raise RuntimeError("생성한 클립을 찾지 못했다: 프롬프트가 일치하는 타일이 없다")


@contextmanager
def _session(cfg: dict):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(Path(cfg["root"]) / cfg["flow"]["profile_dir"]), **_LAUNCH)
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            try:
                ctx.close()
            except Exception:  # 다운로드 후 Chrome 이 이미 종료됐을 수 있다
                pass


def _generate_one(job: dict, project_url: str | None, cfg: dict) -> str:
    """클립 1개를 만들어 Flow 프로젝트에 남긴다. 프로젝트 주소를 돌려준다."""
    with _session(cfg) as page:
        page.goto(project_url or FLOW_URL, wait_until="domcontentloaded")
        if project_url is None:
            page.get_by_text("새 프로젝트").first.click()
            page.wait_for_url("**/project/**", timeout=30000)
        page.wait_for_timeout(5000)
        project_url = page.url
        cost = _apply_options(page, job["duration"], cfg)
        logger.info("클립 %s 생성 요청 (%d초, %s크레딧)",
                    job["path"].name, job["duration"], cost)
        before = page.get_by_alt_text(_THUMB).count()
        _submit(page, job["prompt"])
        _wait_new_tile(page, before, cfg["flow"]["generate_timeout_sec"])
    return project_url


def _fetch_one(job: dict, project_url: str, tries: int = 3) -> None:
    """생성된 클립을 받는다. 무료이므로 브라우저를 새로 띄워 재시도해도 된다."""
    for attempt in range(1, tries + 1):
        try:
            with _session(job["cfg"]) as page:
                page.goto(project_url, wait_until="domcontentloaded")
                _open_clip(page, job["prompt"])
                _save_original(page, job["path"])
            return
        except Exception as exc:
            if attempt == tries:
                raise
            logger.warning("다운로드 실패, 재시도 %d/%d: %s", attempt, tries, exc)


def _generate_clips(jobs: list[dict], out_dir: Path, cfg: dict) -> None:
    project_url = None
    for job in jobs:
        if job["path"].exists():  # 중간 실패 후 재실행 시 크레딧을 또 쓰지 않는다
            continue
        project_url = _generate_one(job, project_url, cfg)
        _fetch_one({**job, "cfg": cfg}, project_url)


def run(date_str: str, out_dir: Path, *, dry_run: bool = False) -> dict:
    """클립 경로 목록을 돌려준다. 실패하면 예외 대신 빈 목록을 돌려줘 렌더가 정적 배경으로 폴백한다."""
    if dry_run:
        return {"clips": []}

    cfg = load_config()
    script = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
    timings = json.loads((out_dir / "timings.json").read_text(encoding="utf-8"))
    segments = script["segments"]

    clip_dir = out_dir / "clips"
    rel = [f"clips/clip_{i}.mp4" for i in range(len(segments))]
    if all((out_dir / r).exists() for r in rel):
        return {"clips": rel}

    try:
        cap = cfg["flow"]["max_clips_per_day"]
        if len(segments) > cap:
            raise ValueError(f"세그먼트 {len(segments)}개가 일일 상한 {cap}개를 넘는다")
        durs = segment_durations(timings["captions"], timings["duration"])
        clip_dir.mkdir(exist_ok=True)
        jobs = [{"prompt": build_prompt(seg), "duration": pick_duration(d),
                 "path": out_dir / r}
                for seg, d, r in zip(segments, durs, rel)]
        _generate_clips(jobs, out_dir, cfg)
        return {"clips": rel}
    except Exception as exc:
        logger.warning("Flow 단계 실패, 정적 배경으로 폴백: %s", exc)
        return {"clips": []}
