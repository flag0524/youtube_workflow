from moviepy.editor import ColorClip, CompositeVideoClip, AudioFileClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
import textwrap, os

W, H = 1080, 1920

def create_background(duration):
    bg = ColorClip(size=(W, H), color=(10, 12, 30), duration=duration)
    return bg

def create_text_clip(text, fontsize=80, color="white", stroke_color="black", stroke_width=4, duration=3, pos="center"):
    img = Image.new("RGBA", (W, 400), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", fontsize)
    except:
        font = ImageFont.load_default()
    lines = textwrap.wrap(text, width=16)
    y = 0
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        w = bbox[2]-bbox[0]
        x = (W - w)//2
        for dx in [-stroke_width, stroke_width]:
            for dy in [-stroke_width, stroke_width]:
                draw.text((x+dx, y+dy), line, font=font, fill=stroke_color)
        draw.text((x, y), line, font=font, fill=color)
        y += fontsize + 10
    tmp_path = f"/tmp/text_{abs(hash(text))}.png"
    img.save(tmp_path)
    clip = ImageClip(tmp_path, duration=duration).set_position(pos)
    return clip

def make_shorts_video(script, voice_path, output_path="shorts_final.mp4"):
    audio = AudioFileClip(voice_path)
    duration = audio.duration + 0.5
    bg = create_background(duration)
    progress = ColorClip(size=(int(W * 0.9), 8), color=(0, 200, 255), duration=duration).set_position(("center", 120))
    clips = [bg, progress]
    hook_clip = create_text_clip(script["hook_text"], fontsize=90, duration=min(3, duration)).set_start(0).set_position(("center", 600))
    clips.append(hook_clip)
    narration = script["narration"]
    sentences = narration.split(".")
    t = 3
    for sent in sentences[:4]:
        if not sent.strip():
            continue
        dur = min(8, duration - t)
        if dur <= 0:
            break
        txt_clip = create_text_clip(sent.strip(), fontsize=65, duration=dur).set_start(t).set_position(("center", 1100))
        clips.append(txt_clip)
        t += dur
    logo = create_text_clip("AI DEV SHORTS", fontsize=40, color="#00D1FF", duration=duration).set_position((50, 50))
    clips.append(logo)
    final = CompositeVideoClip(clips, size=(W, H)).set_audio(audio).set_duration(duration)
    final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    print(f"영상 생성 완료: {output_path}")
    return output_path
