"""文本模型作答 — 题干+选项 → SolverResult"""

import json
import re
from pathlib import Path

from core.errors import PauseRequiredError, RecoverableError
from models.google_client import GoogleClient
from models.model_config import ModelConfig
from models.openai_client import OpenAIClient
from schemas.solver_schema import SolverResult


def _load_prompt() -> str:
    """读取文本模型提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "solver_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"文本模型提示词文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


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


def solve(question_type: str, question_text: str, options: dict[str, str], config: ModelConfig) -> SolverResult:
    """发送题干+选项到文本模型，返回 SolverResult"""
    prompt = _load_prompt()
    input_obj = {
        "question_type": question_type,
        "question": question_text,
        "options": options,
    }

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(input_obj, ensure_ascii=False)},
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
        return SolverResult.model_validate(raw_json)
    except Exception as e:
        raise PauseRequiredError(f"文本模型返回 JSON 校验失败: {e}\n原始内容: {raw_text[:500]}") from e
