# 대본 생성 모듈의 길이·형식 검증 로직을 테스트
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


def test_validate_accepts_narration_at_exact_upper_boundary():
    # 220 * 1.15 == 252.99999999999997 in float arithmetic, not 253.0 —
    # this boundary value must not be rejected by the tolerance check.
    validate_script(_valid(253), seconds=40, cpm=330)
