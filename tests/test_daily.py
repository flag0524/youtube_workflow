# 오케스트레이터의 재시도 로직과 단계 순서를 검증하는 테스트
import pytest

from daily import run_step


def test_run_step_returns_result_on_first_success(tmp_path):
    calls = []

    def fn(date_str, out_dir, dry_run=False):
        calls.append(1)
        return "ok"

    assert run_step("test", fn, "2026-09-12", tmp_path, dry_run=False) == "ok"
    assert len(calls) == 1


def test_run_step_retries_once_then_succeeds(tmp_path):
    calls = []

    def fn(date_str, out_dir, dry_run=False):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("일시적 실패")
        return "ok"

    assert run_step("test", fn, "2026-09-12", tmp_path, dry_run=False) == "ok"
    assert len(calls) == 2


def test_run_step_raises_after_retry_exhausted(tmp_path):
    def fn(date_str, out_dir, dry_run=False):
        raise RuntimeError("계속 실패")

    with pytest.raises(RuntimeError, match="계속 실패"):
        run_step("test", fn, "2026-09-12", tmp_path, dry_run=False)


def test_step_order_is_collect_script_voice_flow_render_upload():
    from daily import STEPS

    assert [name for name, _ in STEPS] == [
        "collect", "script", "voice", "flow", "render", "upload"
    ]
