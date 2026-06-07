"""从模型响应文本中提取 JSON 对象候选。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable


def _add_candidate(out: list[dict], seen: set[str], obj: object) -> None:
    if not isinstance(obj, dict):
        return
    key = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    if key in seen:
        return
    seen.add(key)
    out.append(obj)


def _fenced_json_chunks(text: str) -> Iterable[str]:
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
        yield match.group(1)


def _balanced_object_chunks(text: str) -> Iterable[str]:
    """按 JSON 字符串规则查找平衡的 {...} 片段。"""
    start: int | None = None
    depth = 0
    in_string = False
    escape = False

    for idx, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
            continue

        if ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start:idx + 1]
                start = None


def extract_all_json_objects(text: str) -> list[dict]:
    """返回文本中所有可解析为 dict 的 JSON 对象候选，去重并保序。"""
    candidates: list[dict] = []
    seen: set[str] = set()

    stripped = text.strip()
    if stripped:
        try:
            _add_candidate(candidates, seen, json.loads(stripped))
        except json.JSONDecodeError:
            pass

    for chunk in _fenced_json_chunks(text):
        try:
            _add_candidate(candidates, seen, json.loads(chunk.strip()))
        except json.JSONDecodeError:
            pass

    for chunk in _balanced_object_chunks(text):
        try:
            _add_candidate(candidates, seen, json.loads(chunk))
        except json.JSONDecodeError:
            pass

    return candidates


def extract_first_json_object(text: str) -> dict:
    """兼容旧调用：返回第一个 JSON dict，否则抛 JSONDecodeError。"""
    candidates = extract_all_json_objects(text)
    if candidates:
        return candidates[0]
    raise json.JSONDecodeError("No JSON object found", text, 0)
