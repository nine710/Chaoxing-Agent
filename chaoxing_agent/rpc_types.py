"""NDJSON 协议类型定义 — RpcServer 通信用的 4 种消息 + parse helper。"""
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class RpcRequest:
    type: str = "request"
    id: int = 0
    method: str = ""
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class RpcResponse:
    type: str = "response"
    id: int = 0
    result: Any = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


@dataclass
class RpcEvent:
    type: str = "event"
    event: str = ""
    data: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


@dataclass
class RpcError:
    type: str = "error"
    id: int = 0
    error: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def parse_message(line: str) -> dict:
    """解析一行 NDJSON 消息。"""
    return json.loads(line)