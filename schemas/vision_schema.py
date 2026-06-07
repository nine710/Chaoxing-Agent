"""视觉模型输出 Pydantic 校验模型"""

from typing import Literal, Optional

import pydantic
from pydantic import BaseModel, Field


class VisionOption(BaseModel):
    key: str
    text: str
    box: list[int]  # [x1, y1, x2, y2] — 手机截图内像素坐标


class VisionButton(BaseModel):
    visible: bool
    text: Optional[str] = ""
    box: Optional[list[int]] = None

    @pydantic.field_validator("text", mode="before")
    @classmethod
    def _empty_text(cls, v):
        """LLM 经常把"无值"输出成 null，这里统一把 None 归一为 ""。"""
        return "" if v is None else v


class VisionButtons(BaseModel):
    previous: VisionButton
    next: VisionButton
    submit: VisionButton


class VisionPopup(BaseModel):
    visible: bool = False
    text: Optional[str] = ""
    buttons: list = Field(default_factory=list)

    @pydantic.field_validator("text", mode="before")
    @classmethod
    def _empty_text(cls, v):
        return "" if v is None else v


class VisionConfidence(BaseModel):
    text: float   # 文字识别置信度 0~1
    layout: float  # 布局识别置信度 0~1


class VisionResult(BaseModel):
    page_state: Literal["question", "submit", "popup", "loading", "finished", "unknown"]
    question_type: Literal["single_choice", "multiple_choice", "true_false", "fill_blank", "unknown"]
    question_text: str = ""
    options: list[VisionOption] = Field(default_factory=list)
    buttons: VisionButtons
    popup: VisionPopup = Field(default_factory=VisionPopup)
    confidence: VisionConfidence
