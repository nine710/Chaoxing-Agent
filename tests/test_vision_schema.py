"""vision_schema 的回归测试。"""

import pytest
from pydantic import ValidationError

from schemas.vision_schema import VisionResult


def _valid_raw(**overrides):
    raw = {
        "page_state": "question",
        "question_type": "single_choice",
        "question_text": "示例题",
        "options": [],
        "buttons": {
            "previous": {"visible": False, "text": None, "box": None},
            "next": {"visible": True, "text": "下一题", "box": [0, 800, 381, 850]},
            "submit": {"visible": False, "text": None, "box": None},
        },
        "popup": {"visible": False, "text": None, "buttons": []},
        "confidence": {"text": 0.9, "layout": 0.9},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(raw.get(k), dict):
            raw[k].update(v)
        else:
            raw[k] = v
    return raw


def test_submit_text_none_normalizes_to_empty_string():
    """Gemini 在按钮不可见时把 text 序列化成 null，必须归一为 ''。"""
    r = VisionResult.model_validate(_valid_raw())
    assert r.buttons.submit.text == ""
    assert r.buttons.previous.text == ""
    assert r.popup.text == ""


def test_submit_text_explicit_string_preserved():
    r = VisionResult.model_validate(
        _valid_raw(
            buttons={
                "previous": {"visible": False, "text": None, "box": None},
                "next": {"visible": False, "text": None, "box": None},
                "submit": {"visible": True, "text": "交卷", "box": [0, 900, 381, 950]},
            },
            page_state="submit",
            question_type="unknown",
        )
    )
    assert r.buttons.submit.text == "交卷"
    assert r.buttons.next.text == ""


def test_button_text_field_omitted_uses_default():
    r = VisionResult.model_validate(
        _valid_raw(
            buttons={
                "previous": {"visible": False},
                "next": {"visible": True, "text": "下一题", "box": [0, 800, 381, 850]},
                "submit": {"visible": False},
            }
        )
    )
    assert r.buttons.submit.text == ""
    assert r.buttons.previous.text == ""


def test_invalid_page_state_rejected():
    with pytest.raises(ValidationError):
        VisionResult.model_validate(_valid_raw(page_state="not_a_state"))


def test_options_with_box_parsed():
    raw = _valid_raw()
    raw["options"] = [
        {"key": "A", "text": "选项A", "box": [0, 100, 381, 150]},
        {"key": "B", "text": "选项B", "box": [0, 200, 381, 250]},
    ]
    r = VisionResult.model_validate(raw)
    assert len(r.options) == 2
    assert r.options[0].key == "A"
    assert r.options[1].box == [0, 200, 381, 250]
