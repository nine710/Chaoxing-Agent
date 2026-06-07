"""config_init 的回归测试。"""

import json
from pathlib import Path

from chaoxing_agent.core.config_init import ensure_config_files, init_config_files, init_env_example


def test_ensure_creates_only_missing(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.json.example").write_text('{"k":"v"}', encoding="utf-8")
    (cfg_dir / "model_services.json.example").write_text('{"vision":{}}', encoding="utf-8")
    (cfg_dir / ".env.example").write_text("VISION_API_KEY=\n", encoding="utf-8")

    monkeypatch.setattr("chaoxing_agent.core.config_init._config_dir", lambda: cfg_dir)

    out = ensure_config_files()
    names = [Path(d).name for _, d in out]
    assert set(names) == {"config.json", "model_services.json", ".env"}

    for src_name, dst_name in (
        ("config.json.example", "config.json"),
        ("model_services.json.example", "model_services.json"),
        (".env.example", ".env"),
    ):
        assert (cfg_dir / dst_name).exists()


def test_ensure_skips_existing(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.json.example").write_text('{"k":"NEW"}', encoding="utf-8")
    (cfg_dir / "config.json").write_text('{"k":"PRESERVE"}', encoding="utf-8")
    (cfg_dir / "model_services.json.example").write_text('{"vision":{}}', encoding="utf-8")
    (cfg_dir / ".env.example").write_text("VISION_API_KEY=\n", encoding="utf-8")

    monkeypatch.setattr("chaoxing_agent.core.config_init._config_dir", lambda: cfg_dir)

    ensure_config_files()
    assert json.loads((cfg_dir / "config.json").read_text(encoding="utf-8")) == {"k": "PRESERVE"}


def test_init_force_overwrites_existing(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.json.example").write_text('{"k":"NEW"}', encoding="utf-8")
    (cfg_dir / "config.json").write_text('{"k":"PRESERVE"}', encoding="utf-8")
    (cfg_dir / "model_services.json.example").write_text('{"vision":{}}', encoding="utf-8")
    (cfg_dir / ".env.example").write_text("VISION_API_KEY=\n", encoding="utf-8")

    monkeypatch.setattr("chaoxing_agent.core.config_init._config_dir", lambda: cfg_dir)

    init_config_files(force=True)
    assert json.loads((cfg_dir / "config.json").read_text(encoding="utf-8")) == {"k": "NEW"}


def test_init_raises_if_example_missing(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    monkeypatch.setattr("chaoxing_agent.core.config_init._config_dir", lambda: cfg_dir)

    import pytest
    with pytest.raises(FileNotFoundError):
        init_config_files()


def test_init_env_example_writes_only_template(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / ".env").write_text("SECRET=existing", encoding="utf-8")
    monkeypatch.setattr("chaoxing_agent.core.config_init._config_dir", lambda: cfg_dir)
    monkeypatch.setattr("chaoxing_agent.core.env_settings._get_config_dir", lambda: cfg_dir)

    out = init_env_example()
    assert out.name == ".env.example"
    assert (cfg_dir / ".env.example").exists()
    # 真实 .env 不应被覆盖
    assert (cfg_dir / ".env").read_text(encoding="utf-8") == "SECRET=existing"
