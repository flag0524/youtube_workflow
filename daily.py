# 하루 한 편의 쇼츠를 수집부터 예약 공개까지 순서대로 실행하는 오케스트레이터
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from config import load_config
from steps import collect, flow, motion, render, script, upload, voice
from steps.history import append_record

STEPS = [
    ("collect", collect.run),
    ("script", script.run),
    ("voice", voice.run),
    ("flow", flow.run),
    ("motion", motion.run),
    ("render", render.run),
    ("upload", upload.run),
]

logger = logging.getLogger("daily")


def run_step(name, fn, date_str, out_dir, *, dry_run, retries=1):
    """실패하면 지정 횟수만큼 재시도한다. 그래도 실패하면 예외를 올린다."""
    attempt = 0
    while True:
        try:
            logger.info("[%s] 시작", name)
            result = fn(date_str, out_dir, dry_run=dry_run)
            logger.info("[%s] 완료", name)
            return result
        except Exception as exc:
            attempt += 1
            if attempt > retries:
                logger.error("[%s] 실패: %s", name, exc)
                raise
            logger.warning("[%s] 실패, 재시도 %d회차: %s", name, attempt, exc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true",
                        help="업로드 없이 전 단계를 실행한다")
    parser.add_argument("--from-step", choices=[n for n, _ in STEPS],
                        help="지정한 단계부터 재실행한다")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("daily.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    cfg = load_config()
    out_dir = Path(cfg["root"]) / "out" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = STEPS
    if args.from_step:
        start = [n for n, _ in STEPS].index(args.from_step)
        steps = STEPS[start:]

    results = {}
    for name, fn in steps:
        try:
            results[name] = run_step(name, fn, args.date, out_dir,
                                     dry_run=args.dry_run)
        except Exception as exc:
            (out_dir / "result.json").write_text(
                json.dumps({"failed_step": name, "error": str(exc)},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.error("파이프라인 중단. 불완전한 영상은 올리지 않는다.")
            return 1

    if not args.dry_run and "upload" in results:
        topics = json.loads((out_dir / "topics.json").read_text(encoding="utf-8"))
        script_data = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
        append_record(Path(cfg["root"]) / "history.jsonl", {
            "date": args.date,
            "title": script_data["title"],
            "angle": topics["chosen"]["angles"][0],
            "video_id": results["upload"]["video_id"],
        })
        logger.info("완료: %s", results["upload"]["url"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
