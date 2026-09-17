# 단어 타이밍을 ffmpeg 가 번인할 수 있는 ASS 자막 문자열로 변환하는 순수 함수 모듈
HOOK_SECONDS = 2.0

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},78,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,60,1
Style: Hook,{font},104,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,2,5,60,60,60,1
Style: Logo,{font},34,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,7,50,50,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    centis = int(round((secs - int(secs)) * 100))
    if centis == 100:  # 반올림이 초를 넘기는 경우
        secs, centis = int(secs) + 1, 0
    return f"{int(hours)}:{int(minutes):02d}:{int(secs):02d}.{centis:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("\n", "\\N").replace("\r", "")


def _dialogue(start: float, end: float, style: str, override: str,
              text: str) -> str:
    return (f"Dialogue: 0,{format_time(start)},{format_time(end)},{style},,"
            f"0,0,0,,{override}{_escape(text)}")


def build_ass(timings: dict, cfg: dict) -> str:
    v = cfg["video"]
    cx = v["width"] // 2
    lines = [_HEADER.format(width=v["width"], height=v["height"],
                            font=v["font_family"])]

    lines.append(_dialogue(0.0, HOOK_SECONDS, "Hook",
                           f"{{\\pos({cx},{v['hook_y']})}}", timings["hook"]))

    for cap in timings["captions"]:
        lines.append(_dialogue(cap["start"], cap["end"], "Caption",
                               f"{{\\pos({cx},{v['caption_y']})}}",
                               cap["caption"]))

    lines.append(_dialogue(0.0, timings["duration"], "Logo", "",
                           cfg["brand"]["logo_text"]))

    return "\n".join(lines) + "\n"
