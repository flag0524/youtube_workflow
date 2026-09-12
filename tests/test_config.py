# config.load_config 와 load_seeds 의 병합 동작을 검증하는 테스트
from config import load_config


def test_load_config_merges_yaml_and_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = load_config()
    assert cfg["video"]["width"] == 1080
    assert cfg["video"]["fps"] == 30
    assert cfg["anthropic_api_key"] == "sk-ant-test"


def test_load_config_has_seven_day_formats():
    cfg = load_config()
    assert set(cfg["formats"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def test_reach_and_convert_split_is_five_two():
    cfg = load_config()
    roles = [f["role"] for f in cfg["formats"].values()]
    assert roles.count("reach") == 5
    assert roles.count("convert") == 2
