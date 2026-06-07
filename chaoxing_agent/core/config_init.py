"""从 example 模板初始化真实的 config.json / model_services.json。

example 入库，真实文件由 `.gitignore` 排除。首次运行 `main.py` 时若真实
文件不存在，则从 `*.example` 复制；用户也可以显式调用
`uv run python main.py --init-config` 强制重新生成。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable


def _config_dir() -> Path:
    return Path(__file__).parent.parent / "config"


_PAIRS: list[tuple[str, str]] = [
    ("config.json.example", "config.json"),
    ("model_services.json.example", "model_services.json"),
    (".env.example", ".env"),
]


def init_config_files(force: bool = False) -> list[tuple[str, str]]:
    """把缺失的（默认）真实文件从 example 复制。返回 (src, dst) 列表。

    `force=True` 时即使真实文件已存在也会覆盖。
    """
    cfg_dir = _config_dir()
    out: list[tuple[str, str]] = []
    for example_name, real_name in _PAIRS:
        src = cfg_dir / example_name
        dst = cfg_dir / real_name
        if not src.exists():
            # example 必须存在
            raise FileNotFoundError(f"模板文件缺失: {src}")
        if dst.exists() and not force:
            continue
        shutil.copyfile(src, dst)
        out.append((str(src), str(dst)))
    return out


def ensure_config_files() -> list[tuple[str, str]]:
    """仅在缺失时复制。供 `main.py` 启动时调用。"""
    return init_config_files(force=False)


def init_env_example() -> Path:
    """刷新 .env.example 模板（不创建真实 .env）。"""
    from chaoxing_agent.core.env_settings import write_default_env
    return write_default_env()
