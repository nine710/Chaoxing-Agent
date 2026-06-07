"""文本模型输出 Pydantic 校验模型"""

from typing import Optional

import pydantic
from pydantic import BaseModel


class SolverResult(BaseModel):
    question_type: str
    answer: list[str]   # 必须是数组，单选如 ["B"]，多选如 ["A", "C"]
    confidence: float
    reason: Optional[str] = ""

    @pydantic.field_validator("reason", mode="before")
    @classmethod
    def _empty_reason(cls, v):
        """LLM 经常把"无值"输出成 null，这里统一把 None 归一为 ""。"""
        return "" if v is None else v
