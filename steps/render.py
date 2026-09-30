# 배경·자막·나레이션을 ffmpeg 로 합성해 쇼츠 mp4 를 만드는 모듈
import json
import shutil
import subprocess
from pathlib import Path

from fontTools.ttLib import TTFont

from config import load_config
from steps.flow import segment_durations
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


def build_flow_ffmpeg_command(clips: list[str], durations: list[float], mp3: str,
                              ass: str, out: str, cfg: dict) -> list[str]:
    """Flow 클립을 세그먼트 길이만큼 잘라 9:16 으로 맞춰 잇는다. Flow 오디오는 버린다."""
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    parts = [
        f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"fps={fps},setsar=1[v{i}]"
        for i, d in enumerate(durations)
    ]
    joined = "".join(f"[v{i}]" for i in range(len(clips)))
    graph = (";".join(parts) + f";{joined}concat=n={len(clips)}:v=1:a=0[cat];"
             f"[cat]subtitles={ass}:fontsdir=fonts[v]")
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", c]
    cmd += ["-i", mp3, "-filter_complex", graph,
            "-map", "[v]", "-map", f"{len(clips)}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    return cmd


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

    caps = timings["captions"]
    clips = [f"clips/clip_{i}.mp4" for i in range(len(caps))]
    if clips and all((out_dir / c).exists() for c in clips):
        cmd = build_flow_ffmpeg_command(
            clips, segment_durations(caps, timings["duration"]),
            "narration.mp3", "subs.ass", "short.mp4", cfg)
    else:  # Flow 클립이 없거나 모자라면 정적 배경으로 폴백한다.
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
