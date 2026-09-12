import os

def tts_elevenlabs(text, output_path="voice.mp3"):
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        audio = client.text_to_speech.convert(
            voice_id="pNInz6obpgDQGcFmaJgB",
            model_id="eleven_multilingual_v2",
            text=text,
            voice_settings={"stability": 0.5, "similarity_boost": 0.75}
        )
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        print(f"ElevenLabs 완료: {output_path}")
        return output_path
    except Exception as e:
        print(f"ElevenLabs 실패, gTTS fallback: {e}")
        return tts_gtts(text, output_path)

def tts_gtts(text, output_path="voice.mp3"):
    from gtts import gTTS
    tts = gTTS(text=text, lang="ko")
    tts.save(output_path)
    return output_path
