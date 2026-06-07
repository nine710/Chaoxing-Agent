"""ConfigHolder 白名单热更测试。"""
import json
import pytest
from pathlib import Path

from chaoxing_agent.config_holder import ConfigHolder, HOT_FIELDS


@pytest.mark.asyncio
async def test_hot_field_updates(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = ConfigHolder(
        {"timing": {"a": 1}, "target": {"b": 2}},
        config_path=cfg_path,
    )
    hot = await cfg.update({"timing": {"a": 99}})
    assert hot == ["timing"]
    assert cfg.get("timing") == {"a": 99}
    # 已写盘
    on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert on_disk["timing"] == {"a": 99}


@pytest.mark.asyncio
async def test_cold_field_rejected(tmp_path: Path):
    cfg = ConfigHolder(
        {"target": {"hwnd": 0}},
        config_path=tmp_path / "config.json",
    )
    hot = await cfg.update({"target": {"hwnd": 999}})
    assert hot == []
    assert cfg.get("target") == {"hwnd": 0}


@pytest.mark.asyncio
async def test_mixed_patch(tmp_path: Path):
    cfg = ConfigHolder(
        {"timing": {"x": 1.0}, "target": {"hwnd": 0}, "thresholds": {"a": 0.5}},
        config_path=tmp_path / "config.json",
    )
    hot = await cfg.update(
        {"timing": {"x": 9.0}, "target": {"hwnd": 1}, "thresholds": {"a": 0.9}}
    )
    assert set(hot) == {"timing", "thresholds"}
    assert cfg.get("timing") == {"x": 9.0}
    assert cfg.get("thresholds") == {"a": 0.9}
    assert cfg.get("target") == {"hwnd": 0}  # 未变


@pytest.mark.asyncio
async def test_snapshot_independence(tmp_path: Path):
    cfg = ConfigHolder({"timing": {"x": 1.0}}, config_path=tmp_path / "config.json")
    snap = cfg.snapshot()
    snap["timing"]["x"] = 999
    assert cfg.get("timing") == {"x": 1.0}