"""包结构契约测试：保证从 chaoxing_agent.core.<submodule> import 工作。"""

import sys


def test_chaoxing_agent_core_submodule_imports_work():
    """外部代码应通过 from chaoxing_agent.core.<submodule> import X 拿到东西。

    注意：此测试**不**清空 sys.modules —— 清空会导致 chaoxing_agent.core
    在后续测试中被重新加载，使得其他测试中已经拿到的 class 对象
    （如 RecoverableError）变成"旧"对象，破坏 isinstance 检查。
    """
    from chaoxing_agent.core.config_init import ensure_config_files
    from chaoxing_agent.core.env_settings import apply_overrides
    from chaoxing_agent.core.errors import FatalStopError
    from chaoxing_agent.core.state_machine import StateMachine
    from chaoxing_agent.core.viewport_selector import select as select_viewport_fn
    from chaoxing_agent.core.window_selector import select as select_window_fn
    from chaoxing_agent.core.click_executor import click_at
    from chaoxing_agent.core.coordinate_mapper import CoordinateMapper
    from chaoxing_agent.core.page_change_detector import detect
    from chaoxing_agent.core.screen_capture import capture_phone_screen
    from chaoxing_agent.core.trace_logger import TraceLogger

    assert all([
        ensure_config_files, apply_overrides, FatalStopError, StateMachine,
        select_viewport_fn, select_window_fn, click_at, CoordinateMapper,
        detect, capture_phone_screen, TraceLogger,
    ])


def test_chaoxing_agent_core_does_not_use_self_import_in_init():
    """__init__.py 不应自引用自身（self-import 反模式会留下空属性）。"""
    init_path = "chaoxing_agent/core/__init__.py"
    from pathlib import Path
    import re
    src = Path(init_path).read_text(encoding="utf-8")

    # 排除 docstring 后再 grep
    cleaned = re.sub(r'"""[\s\S]*?"""', "", src)
    cleaned = re.sub(r"'''[\s\S]*?'''", "", cleaned)

    bad_patterns = [
        re.compile(r"^\s*from\s+chaoxing_agent\.core\s+import\b", re.MULTILINE),
        re.compile(r"^\s*from\s+\.core\s+import\b", re.MULTILINE),
    ]
    for pat in bad_patterns:
        assert not pat.search(cleaned), (
            f"chaoxing_agent/core/__init__.py 含自引用: pattern={pat.pattern!r}"
        )


def test_models_module_uses_package_paths_for_core():
    """models/* 应使用 chaoxing_agent.core.* 引用 errors，不应回退到顶层 core shim。"""
    from pathlib import Path
    for fname in ("text_solver.py", "vision_parser.py"):
        src = Path(f"models/{fname}").read_text(encoding="utf-8")
        assert "from chaoxing_agent.core.errors" in src, (
            f"models/{fname} 仍用顶层 core.errors: 包路径应统一"
        )
        # 严禁用 'from core.errors'（走顶层 shim）
        assert "from core.errors" not in src, (
            f"models/{fname} 用 from core.errors —— 顶层 shim 不可靠"
        )


def test_state_machine_uses_consistent_package_paths():
    """chaoxing_agent/core/state_machine.py 内部 import 一致性。"""
    from pathlib import Path
    src = Path("chaoxing_agent/core/state_machine.py").read_text(encoding="utf-8")
    assert "from chaoxing_agent.core" in src
    assert "from core." not in src
