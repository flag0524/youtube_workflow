# .env 와 config.yaml 을 병합해 전역 설정 딕셔너리를 제공하는 로더
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_config() -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
    cfg["root"] = ROOT
    return cfg


def load_seeds() -> list[dict]:
    data = yaml.safe_load((ROOT / "seeds.yaml").read_text(encoding="utf-8"))
    return data["seeds"]
