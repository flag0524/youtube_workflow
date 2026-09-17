# timings.json 을 ASS 자막 문자열로 변환하는 순수 함수를 검증하는 테스트
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


def test_format_time_carries_seconds_into_minutes():
    # 59.996 is the actual float boundary that rounds up to 60.00 centiseconds
    # worth of seconds (59.995 looks like the boundary on paper, but
    # 59.995 - 59 == 0.9949999999999974 in binary float, which rounds down to
    # 99 centiseconds, not 100 — verified by direct execution). Must roll
    # into the minutes place, not emit an invalid "60.00" seconds value.
    assert format_time(59.996) == "0:01:00.00"


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
