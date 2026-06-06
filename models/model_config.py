"""模型配置 — 读取 model_services.json + 客户端工厂"""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelConfig:
    api_type: str      # "openai" | "google"
    base_url: str
    api_key: str       # 已从环境变量读取的实际值
    model_id: str


def _get_config_dir() -> Path:
    return Path(__file__).parent.parent / "config"


def load_model_services() -> dict:
    """读取 model_services.json"""
    path = _get_config_dir() / "model_services.json"
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_api_key(env_var: str) -> str:
    """从环境变量读取 API Key"""
    key = os.environ.get(env_var, "")
    if not key:
        raise RuntimeError(
            f"环境变量 {env_var} 未设置。请设置后重试。\n"
            f"示例: set {env_var}=your-api-key"
        )
    return key


def get_vision_config(services: dict) -> ModelConfig:
    """根据 selected.vision_model 获取视觉模型配置"""
    selected_key = services["selected"]["vision_model"]
    entry = services["model_services"]["vision"][selected_key]
    return ModelConfig(
        api_type=entry["api_type"],
        base_url=entry["base_url"],
        api_key=_get_api_key(entry["api_key_env"]),
        model_id=entry["model_id"],
    )


def get_solver_config(services: dict) -> ModelConfig:
    """根据 selected.solver_model 获取文本模型配置"""
    selected_key = services["selected"]["solver_model"]
    entry = services["model_services"]["solver"][selected_key]
    return ModelConfig(
        api_type=entry["api_type"],
        base_url=entry["base_url"],
        api_key=_get_api_key(entry["api_key_env"]),
        model_id=entry["model_id"],
    )
