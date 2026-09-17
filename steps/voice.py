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
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
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
