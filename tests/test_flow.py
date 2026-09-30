# Flow 클립 길이 선택·프롬프트·폴백 분기를 Flow 접속 없이 검증하는 테스트
import json

import pytest

from steps import flow
from steps.flow import build_prompt, pick_duration, segment_durations


def test_pick_duration_rounds_up_to_supported_length():
    assert pick_duration(3.2) == 4
    assert pick_duration(4.0) == 4
    assert pick_duration(4.6) == 6
    assert pick_duration(8.0) == 8
    assert pick_duration(9.1) == 10


def test_pick_duration_rejects_longer_than_ten_seconds():
    with pytest.raises(ValueError, match="10초"):
        pick_duration(10.5)


def test_segment_durations_cover_whole_narration():
    caps = [{"start": 0.09, "end": 4.6}, {"start": 4.6, "end": 9.0},
            {"start": 9.0, "end": 13.5}]
    d = segment_durations(caps, total=16.8)
    assert d == pytest.approx([4.6, 4.4, 7.8])
    assert sum(d) == pytest.approx(16.8)


def test_build_prompt_forbids_text_in_frame():
    p = build_prompt({"caption": "보고서 고민", "narration": "보고서 쓸 때마다 힘드시죠."})
    assert "보고서 고민" in p
    assert "글자" in p and "자막" in p


def _setup(tmp_path, n_segments=2, seconds=(4.0, 4.0)):
    (tmp_path / "script.json").write_text(json.dumps({
        "segments": [{"narration": f"문장{i}", "caption": f"캡션{i}"}
                     for i in range(n_segments)]}), encoding="utf-8")
    caps, t = [], 0.0
    for i in range(n_segments):
        caps.append({"caption": f"캡션{i}", "start": t, "end": t + seconds[i]})
        t += seconds[i]
    (tmp_path / "timings.json").write_text(
        json.dumps({"duration": t, "captions": caps}), encoding="utf-8")


def test_run_dry_run_never_touches_flow(tmp_path, monkeypatch):
    _setup(tmp_path)
    monkeypatch.setattr(flow, "_generate_clips",
                        lambda *a, **k: pytest.fail("dry-run 에서 Flow 호출"))
    assert flow.run("2026-09-30", tmp_path, dry_run=True) == {"clips": []}


def test_run_falls_back_when_flow_fails(tmp_path, monkeypatch):
    _setup(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("크레딧 소진")

    monkeypatch.setattr(flow, "_generate_clips", boom)
    assert flow.run("2026-09-30", tmp_path) == {"clips": []}


def test_run_skips_flow_when_segments_exceed_daily_cap(tmp_path, monkeypatch):
    _setup(tmp_path, n_segments=2)
    monkeypatch.setattr(flow, "load_config", lambda: {
        "flow": {"max_clips_per_day": 1}, "root": tmp_path})
    monkeypatch.setattr(flow, "_generate_clips",
                        lambda *a, **k: pytest.fail("상한 초과인데 Flow 호출"))
    assert flow.run("2026-09-30", tmp_path) == {"clips": []}


def test_run_returns_clip_paths_in_segment_order(tmp_path, monkeypatch):
    _setup(tmp_path)

    def fake(jobs, out_dir, cfg):
        assert [j["duration"] for j in jobs] == [4, 4]
        for j in jobs:
            j["path"].write_bytes(b"x")

    monkeypatch.setattr(flow, "_generate_clips", fake)
    result = flow.run("2026-09-30", tmp_path)
    assert result["clips"] == ["clips/clip_0.mp4", "clips/clip_1.mp4"]


def test_run_reuses_existing_clips_without_spending_credits(tmp_path, monkeypatch):
    _setup(tmp_path)
    (tmp_path / "clips").mkdir()
    for i in range(2):
        (tmp_path / "clips" / f"clip_{i}.mp4").write_bytes(b"x")
    monkeypatch.setattr(flow, "_generate_clips",
                        lambda *a, **k: pytest.fail("이미 있는 클립을 다시 생성"))
    assert len(flow.run("2026-09-30", tmp_path)["clips"]) == 2
