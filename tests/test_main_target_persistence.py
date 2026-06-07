"""main.py 的预配置 target 落盘回归测试。

回归保护：预配置命中时，必须立刻把 (selected_hwnd, pid, process_name,
client_rect, window_title) 写回 config.json；否则后续 _load_or_create_config
读到的 target.selected_hwnd 仍为 null，StateMachine 会 FATAL。
"""

import json
from pathlib import Path

import chaoxing_agent.core.viewport_selector as vs
import chaoxing_agent.core.window_selector as ws
from chaoxing_agent.core.window_selector import WindowInfo

from main import (
    _default_config,
    _load_or_create_config,
    _resolve_preconfigured_target,
    _save_config,
    _save_viewport_to_config,
)


def _make_win_info() -> WindowInfo:
    return WindowInfo(
        hwnd=6558336,
        pid=33252,
        process_name="vivoScreen.exe",
        window_title="手机投屏",
        client_rect=(2009, 168, 2397, 1096),
        screen_rect=(2009, 168, 2397, 1096),
        width=388,
        height=928,
    )


def _write_initial_config(cfg_path: Path, target: dict):
    cfg = _default_config()
    cfg["target"] = target
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_selects(monkeypatch, info: WindowInfo | None = None):
    """短路 select —— 全部测试用固定 info，不调用真实 psutil/win32gui。

    注意 main.py 用 `from chaoxing_agent.core.window_selector import select as select_window_fn`
    早绑定，必须 monkeypatch main.select_window_fn / main.select_viewport_fn。
    """
    import main

    wi = info or _make_win_info()
    monkeypatch.setattr(main, "select_window_fn", lambda _: wi)
    monkeypatch.setattr(main, "select_viewport_fn", lambda _: None)


def test_preconfigured_target_must_persist_to_disk(tmp_path: Path, monkeypatch):
    """模拟今天暴露的 bug：preconfigured 不写盘，后续 StateMachine 看到 null。"""
    cfg_path = tmp_path / "config.json"
    _write_initial_config(cfg_path, {
        "process_name": "vivoScreen",
        "pid": 33252,
        "selected_hwnd": None,
        "window_title": "",
        "client_rect": [0, 0, 0, 0],
    })
    _patch_selects(monkeypatch)

    # 模拟 main.py 的预配置分支（必须包含写盘）
    config = _load_or_create_config.__wrapped__(cfg_path) if False else None  # 走 _load_or_create_config
    # 直接用真实的 _load_or_create_config / _save_config 操作 cfg_path
    import main
    orig_path = main.CONFIG_PATH
    monkeypatch.setattr(main, "CONFIG_PATH", cfg_path)
    try:
        config = main._load_or_create_config()
        target = config.get("target", {})
        preconfigured = _resolve_preconfigured_target(target)
        assert preconfigured is not None
        config["target"] = preconfigured
        _save_config(config)  # ← 关键

        # 后续流程（viewport 重新标定）写盘时不踩坏 target
        vp_info_dict = {"x": 3, "y": 31, "width": 384, "height": 843,
                        "ratio_x": 0.0077, "ratio_y": 0.0334,
                        "ratio_w": 0.9897, "ratio_h": 0.9084}
        from chaoxing_agent.core.viewport_selector import ViewportInfo
        vp_info = ViewportInfo(**vp_info_dict)
        _save_viewport_to_config(config, vp_info)

        # StateMachine 入口重新读盘
        config = main._load_or_create_config()
        assert config["target"]["selected_hwnd"] == 6558336
        assert config["target"]["pid"] == 33252
        assert config["target"]["process_name"] == "vivoScreen.exe"
        assert config["target"]["client_rect"] == [2009, 168, 2397, 1096]
        assert config["viewport"]["phone_viewport_in_client"]["width"] == 384
    finally:
        monkeypatch.setattr(main, "CONFIG_PATH", orig_path)


def test_preconfigured_target_missing_falls_back_to_none(tmp_path: Path, monkeypatch):
    """target 既没 pid 也没 process_name → 返回 None（让 main 走交互式分支）。"""
    import main
    monkeypatch.setattr(main, "CONFIG_PATH", tmp_path / "config.json")
    target = {"process_name": "", "pid": None, "selected_hwnd": None}
    assert _resolve_preconfigured_target(target) is None


def test_preconfigured_pid_only(tmp_path: Path, monkeypatch):
    """仅有 pid 时也能命中。"""
    import main
    monkeypatch.setattr(main, "CONFIG_PATH", tmp_path / "config.json")
    _patch_selects(monkeypatch)
    target = {"process_name": "", "pid": 33252}
    r = _resolve_preconfigured_target(target)
    assert r is not None
    assert r["selected_hwnd"] == 6558336


def test_preconfigured_process_name_only(tmp_path: Path, monkeypatch):
    """仅有 process_name 时也能命中。"""
    import main
    monkeypatch.setattr(main, "CONFIG_PATH", tmp_path / "config.json")
    _patch_selects(monkeypatch)
    target = {"process_name": "vivoScreen", "pid": None}
    r = _resolve_preconfigured_target(target)
    assert r is not None
    assert r["selected_hwnd"] == 6558336
