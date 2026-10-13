# 모션 자막 props 생성, 키워드 선택 폴백, 렌더 실패 폴백을 Remotion 없이 검증하는 테스트
import json

import pytest

from steps import motion
from steps.motion import build_props, longest_word, pick_keyword

CFG = {
    "video": {"width": 1080, "height": 1920, "fps": 30,
              "caption_y": 960, "hook_y": 760},
    "brand": {"logo_text": "AI 일잘러"},
}
TIMINGS = {
    "duration": 9.0, "hook": "보고서 아직 손으로?", "loop_line": "다시 보기",
    "captions": [
        {"caption": "보고서 고민", "start": 0.0, "end": 3.0},
        {"caption": "AI가 초안 작성", "start": 3.0, "end": 6.0},
        {"caption": "지금 바로 시작", "start": 6.0, "end": 9.0},
    ],
}


def test_longest_word_picks_longest_token():
    assert longest_word("AI가 초안 작성") == "AI가"


def test_pick_keyword_single_word_needs_no_api():
    assert pick_keyword("시작", ask=lambda *_: pytest.fail("API 호출")) == "시작"


def test_pick_keyword_falls_back_when_api_fails():
    def boom(*_):
        raise RuntimeError("503")

    assert pick_keyword("보고서 고민 해결", ask=boom) == longest_word("보고서 고민 해결")


def test_pick_keyword_rejects_answer_outside_candidates():
    assert pick_keyword("보고서 고민", ask=lambda *_: "없는단어") == longest_word("보고서 고민")


def test_pick_keyword_uses_api_answer():
    assert pick_keyword("보고서 고민", ask=lambda *_: "고민") == "고민"


def test_build_props_pops_only_the_last_caption():
    props = build_props(TIMINGS, CFG, keywords=["보고서", "초안", "시작"])
    assert [c["style"] for c in props["captions"]] == ["fade", "fade", "pop"]
    assert props["captions"][1]["keyword"] == "초안"
    assert props["hook"] == {"text": "보고서 아직 손으로?", "end": 2.0, "y": 760}
    assert props["duration"] == 9.0 and props["captionY"] == 960


def test_run_dry_run_skips_everything(tmp_path):
    assert motion.run("2026-10-11", tmp_path, dry_run=True) == {"overlay": None}


def test_run_returns_no_overlay_when_remotion_fails(tmp_path, monkeypatch):
    (tmp_path / "timings.json").write_text(json.dumps(TIMINGS), encoding="utf-8")
    monkeypatch.setattr(motion, "load_config", lambda: {**CFG, "root": tmp_path})
    monkeypatch.setattr(motion, "_render_overlay",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("렌더 실패")))
    assert motion.run("2026-10-11", tmp_path) == {"overlay": None}
