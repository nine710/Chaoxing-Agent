"""文本模型输出 Pydantic 校验模型"""

from pydantic import BaseModel


class SolverResult(BaseModel):
    question_type: str
    answer: list[str]   # 必须是数组，单选如 ["B"]，多选如 ["A", "C"]
    confidence: float
    reason: str = ""
