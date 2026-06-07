"""env_settings 的回归测试。"""

import os
from pathlib import Path

import pytest

from chaoxing_agent.core.env_settings import (
    _apply_section_overrides,
    _default_template,
    apply_overrides,
    list_supported_keys,
    load_env_file,
)


@pytest.fixture
def clean_env(monkeypatch):
    """测试期间清空相关环境变量。"""
    keys = [
        "VISION_API_KEY",
        "SOLVER_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "CHAOXING_VISION_BASE_URL",
        "CHAOXING_VISION_MODEL_ID",
        "CHAOXING_SOLVER_BASE_URL",
        "CHAOXING_SOLVER_MODEL_ID",
        "CHAOXING_VISION_API_TYPE",
        "CHAOXING_SOLVER_API_KEY_ENV",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_load_env_file_returns_loaded_keys(tmp_path: Path, clean_env):
    p = tmp_path / ".env"
    p.write_text("VISION_API_KEY=vk\nSOLVER_API_KEY=sk\n", encoding="utf-8")
    loaded = load_env_file(p)
    assert loaded == {"VISION_API_KEY": "vk", "SOLVER_API_KEY": "sk"}
    assert os.environ["VISION_API_KEY"] == "vk"


def test_load_env_file_missing_returns_empty(tmp_path: Path, clean_env):
    assert load_env_file(tmp_path / "nope.env") == {}


def test_load_env_file_does_not_overwrite_existing(tmp_path: Path, clean_env):
    clean_env.setenv("VISION_API_KEY", "pre-existing")
    p = tmp_path / ".env"
    p.write_text("VISION_API_KEY=from-file\n", encoding="utf-8")
    load_env_file(p)
    assert os.environ["VISION_API_KEY"] == "pre-existing"


def test_load_env_file_skips_blank_values(tmp_path: Path, clean_env):
    p = tmp_path / ".env"
    p.write_text("VISION_API_KEY=\n# comment\n", encoding="utf-8")
    loaded = load_env_file(p)
    assert "VISION_API_KEY" not in loaded
    assert "VISION_API_KEY" not in os.environ


def test_apply_section_overrides_writes_field(clean_env):
    clean_env.setenv("CHAOXING_VISION_BASE_URL", "https://new-vision.example/v1")
    section = {"api_type": "openai", "base_url": "https://old", "model_id": "m", "api_key_env": "X"}
    n = _apply_section_overrides("vision", section)
    assert n == 1
    assert section["base_url"] == "https://new-vision.example/v1"
    assert section["api_type"] == "openai"  # 未覆盖则保留


def test_apply_section_overrides_unknown_section_noop(clean_env):
    section = {"base_url": "x"}
    assert _apply_section_overrides("nonsense", section) == 0


def test_apply_overrides_returns_tuple(clean_env, tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("VISION_API_KEY=vk\n", encoding="utf-8")
    monkey = pytest.MonkeyPatch()
    monkey.setattr("chaoxing_agent.core.env_settings._get_config_dir", lambda: tmp_path)
    try:
        services = {"vision": {"base_url": "u1"}, "solver": {"base_url": "u2"}}
        n_env, n_overrides = apply_overrides(services)
        assert n_env == 1
        assert n_overrides == 0  # 没设 CHAOXING_*
    finally:
        monkey.undo()


def test_apply_overrides_modifies_services(clean_env, tmp_path: Path):
    monkey = pytest.MonkeyPatch()
    monkey.setattr("chaoxing_agent.core.env_settings._get_config_dir", lambda: tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    clean_env.setenv("CHAOXING_SOLVER_BASE_URL", "https://ds.example/v1")
    clean_env.setenv("CHAOXING_SOLVER_MODEL_ID", "deepseek-chat-v2")
    services = {
        "vision": {"base_url": "u1", "model_id": "m1"},
        "solver": {"base_url": "u2", "model_id": "m2"},
    }
    n_env, n_overrides = apply_overrides(services)
    assert n_overrides == 2
    assert services["solver"]["base_url"] == "https://ds.example/v1"
    assert services["solver"]["model_id"] == "deepseek-chat-v2"
    assert services["vision"] == {"base_url": "u1", "model_id": "m1"}  # 未被波及
    monkey.undo()


def test_default_template_only_contains_api_keys():
    t = _default_template()
    assert "VISION_API_KEY" in t
    assert "SOLVER_API_KEY" in t
    # 不应出现 CHAOXING_ 占位
    assert "CHAOXING_" not in t


def test_list_supported_keys_matches_actual_env_names():
    keys = list_supported_keys()
    assert "CHAOXING_VISION_BASE_URL" in keys
    assert "CHAOXING_VISION_MODEL_ID" in keys
    assert "CHAOXING_SOLVER_BASE_URL" in keys
    assert "CHAOXING_SOLVER_MODEL_ID" in keys
    assert "CHAOXING_SOLVER_API_KEY_ENV" in keys
    assert "CHAOXING_VISION_API_TYPE" in keys
    assert "CHAOXING_SOLVER_REASONING_EFFORT" not in keys  # 不在覆盖范围内
