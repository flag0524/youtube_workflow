# ffmpeg 렌더 커맨드 조립과 한글 폰트 해석을 검증하는 테스트
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
