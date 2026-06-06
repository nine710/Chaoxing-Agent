"""视觉模型解析 — 截图 → VisionResult"""

import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

from core.errors import PauseRequiredError, RecoverableError
from models.google_client import GoogleClient
from models.model_config import ModelConfig
from models.openai_client import OpenAIClient
from schemas.vision_schema import VisionResult


def _load_prompt() -> str:
    """读取视觉模型提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "vision_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"视觉模型提示词文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _image_to_base64_url(image: Image.Image) -> str:
    """PIL Image → base64 data URL"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _extract_json(text: str) -> dict:
    """从模型返回文本中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    continue

    raise RecoverableError("无法从模型返回内容中提取 JSON")


def parse(image: Image.Image, config: ModelConfig) -> VisionResult:
    """发送手机截图到视觉模型，返回结构化 VisionResult"""
    prompt = _load_prompt()
    b64_url = _image_to_base64_url(image)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [
            {"type": "text", "text": f"图片尺寸: {image.width}x{image.height}，请解析页面结构。"},
            {"type": "image_url", "image_url": {"url": b64_url}},
        ]},
    ]

    if config.api_type == "openai":
        client = OpenAIClient(config)
    elif config.api_type == "google":
        client = GoogleClient(config)
    else:
        raise PauseRequiredError(f"不支持的 api_type: {config.api_type}")

    raw_text = client.chat(messages)
    raw_json = _extract_json(raw_text)

    try:
        return VisionResult.model_validate(raw_json)
    except Exception as e:
        raise PauseRequiredError(f"视觉模型返回 JSON 校验失败: {e}\n原始内容: {raw_text[:500]}") from e
