# 음성 생성 모듈의 틱-초 변환과 자막 타이밍 배분 로직을 테스트
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
