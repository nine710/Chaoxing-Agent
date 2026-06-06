"""视觉模型输出 Pydantic 校验模型"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VisionOption(BaseModel):
    key: str
    text: str
    box: list[int]  # [x1, y1, x2, y2] — 手机截图内像素坐标


class VisionButton(BaseModel):
    visible: bool
    text: str = ""
    box: Optional[list[int]] = None


class VisionButtons(BaseModel):
    previous: VisionButton
    next: VisionButton
    submit: VisionButton


class VisionPopup(BaseModel):
    visible: bool = False
    text: str = ""
    buttons: list = Field(default_factory=list)


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
