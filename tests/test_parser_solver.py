"""vision_parser / text_solver 的回归测试。"""

import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from models.model_config import ModelConfig
from models.text_solver import solve as text_solve
from models.vision_parser import parse as vision_parse


def _make_config(model_id="m1", base_url="https://x.example/v1", api_key="k"):
    return ModelConfig(
        api_type="openai",
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
    )


# ---------------------------------------------------------------------------
# vision_parser
# ---------------------------------------------------------------------------


def test_vision_parser_returns_vision_result():
    img = Image.new("RGB", (400, 800), (255, 255, 255))
    raw_json = json.dumps({
        "page_state": "question",
        "question_type": "single_choice",
        "question_text": "1+1=?",
        "options": [{"key": "A", "text": "1", "box": [0, 100, 400, 150]}],
        "buttons": {
            "previous": {"visible": False, "text": None, "box": None},
            "next": {"visible": True, "text": "下一题", "box": [0, 700, 400, 750]},
            "submit": {"visible": False, "text": None, "box": None},
        },
        "popup": {"visible": False, "text": None, "buttons": []},
        "confidence": {"text": 0.9, "layout": 0.9},
    }, ensure_ascii=False)
    fake_client = MagicMock()
    fake_client.chat.return_value = raw_json

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        result = vision_parse(img, _make_config())

    assert result.page_state == "question"
    assert result.question_type == "single_choice"
    assert result.options[0].key == "A"
    assert result.buttons.next.text == "下一题"
    assert result.buttons.submit.text == ""  # None 已归一
    assert fake_client.chat.called


def test_vision_parser_json_in_markdown_fence():
    img = Image.new("RGB", (10, 10))
    raw = "```json\n" + json.dumps({
        "page_state": "question",
        "question_type": "true_false",
        "question_text": "Q",
        "options": [],
        "buttons": {
            "previous": {"visible": False},
            "next": {"visible": True, "text": "下一题", "box": [0, 0, 10, 10]},
            "submit": {"visible": False},
        },
        "confidence": {"text": 0.9, "layout": 0.9},
    }) + "\n```"
    fake_client = MagicMock()
    fake_client.chat.return_value = raw

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        result = vision_parse(img, _make_config())
    assert result.question_type == "true_false"


def test_vision_parser_can_send_jpeg_data_url_without_resizing():
    """vision 可用 JPEG 压缩降低传输体积，但用户文本仍报告原始尺寸，box 坐标不缩放。"""
    img = Image.new("RGB", (387, 861), (255, 255, 255))
    raw_json = json.dumps({
        "page_state": "question",
        "question_type": "single_choice",
        "question_text": "Q",
        "options": [{"key": "A", "text": "1", "box": [0, 100, 300, 150]}],
        "buttons": {
            "previous": {"visible": False},
            "next": {"visible": True, "text": "下一题", "box": [0, 700, 300, 750]},
            "submit": {"visible": False},
        },
        "confidence": {"text": 0.9, "layout": 0.9},
    }, ensure_ascii=False)
    fake_client = MagicMock()
    fake_client.chat.return_value = raw_json
    cfg = _make_config()
    cfg.image_format = "jpeg"
    cfg.image_jpeg_quality = 65

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        vision_parse(img, cfg)

    messages = fake_client.chat.call_args[0][0]
    assert "图片尺寸: 387x861" in messages[1]["content"][0]["text"]
    image_url = messages[1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_vision_parser_raises_pause_on_invalid_json():
    """无法从模型返回内容中提取任何 JSON → PauseRequiredError（让人介入或回退）。"""
    img = Image.new("RGB", (10, 10))
    fake_client = MagicMock()
    fake_client.chat.return_value = "not json at all"

    from models.vision_parser import make_openai_client
    from chaoxing_agent.core.errors import PauseRequiredError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            vision_parse(img, _make_config())


def test_vision_parser_raises_pause_on_schema_mismatch():
    img = Image.new("RGB", (10, 10))
    fake_client = MagicMock()
    fake_client.chat.return_value = json.dumps({
        "page_state": "BOGUS_STATE",  # 非法
        "question_type": "single_choice",
        "options": [],
        "buttons": {
            "previous": {"visible": False},
            "next": {"visible": True, "text": "下一题", "box": [0, 0, 10, 10]},
            "submit": {"visible": False},
        },
        "confidence": {"text": 0.9, "layout": 0.9},
    })
    from models.vision_parser import make_openai_client
    from chaoxing_agent.core.errors import PauseRequiredError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            vision_parse(img, _make_config())


def test_vision_parser_recovers_from_inner_json_object():
    """模型把单个选项 dict 当成顶层 JSON 输出（而非 schema）— 提取器应能找到正确 JSON。

    场景：模型先输出一段无关 JSON（如 "我看到的第一个选项"），然后再输出
    真正的结构化对象。提取器需要从所有候选对象中挑出能通过 schema 校验的那一个。
    """
    img = Image.new("RGB", (10, 10))
    inner_option = {"key": "A", "text": "191", "box": [33, 281, 967, 346]}
    real_payload = {
        "page_state": "question",
        "question_type": "single_choice",
        "question_text": "题干",
        "options": [{"key": "A", "text": "x", "box": [0, 0, 10, 10]}],
        "buttons": {
            "previous": {"visible": False},
            "next": {"visible": True, "text": "下一题", "box": [0, 0, 10, 10]},
            "submit": {"visible": False},
        },
        "confidence": {"text": 0.9, "layout": 0.9},
    }
    raw_text = (
        f"我看到的第一个选项是 {json.dumps(inner_option, ensure_ascii=False)}\n"
        f"完整解析:\n"
        f"{json.dumps(real_payload, ensure_ascii=False)}"
    )
    fake_client = MagicMock()
    fake_client.chat.return_value = raw_text

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        result = vision_parse(img, _make_config())
    assert result.page_state == "question"
    assert result.options[0].key == "A"


def test_vision_parser_no_valid_candidate_raises_pause():
    """当所有候选 JSON 都无法通过 schema 校验时，必须抛 PauseRequiredError（而非默默用错的对象）。"""
    img = Image.new("RGB", (10, 10))
    raw_text = "我看到的第一个选项是 " + json.dumps({
        "key": "A", "text": "191", "box": [33, 281, 967, 346]
    }, ensure_ascii=False)
    fake_client = MagicMock()
    fake_client.chat.return_value = raw_text

    from models.vision_parser import make_openai_client
    from chaoxing_agent.core.errors import PauseRequiredError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            vision_parse(img, _make_config())


# ---------------------------------------------------------------------------
# text_solver
# ---------------------------------------------------------------------------


def test_text_solver_returns_solver_result():
    raw = json.dumps({
        "question_type": "single_choice",
        "answer": ["B"],
        "confidence": 0.92,
        "reason": "因为……",
    })
    fake_client = MagicMock()
    fake_client.chat.return_value = raw

    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        result = text_solve("single_choice", "1+1=?", {"A": "1", "B": "2"}, _make_config())
    assert result.answer == ["B"]
    assert result.confidence == 0.92


def test_text_solver_normalizes_reason_none():
    raw = json.dumps({
        "question_type": "single_choice",
        "answer": ["A"],
        "confidence": 0.9,
        "reason": None,
    })
    fake_client = MagicMock()
    fake_client.chat.return_value = raw
    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        result = text_solve("single_choice", "?", {"A": "x", "B": "y"}, _make_config())
    assert result.reason == ""


def test_text_solver_multi_choice():
    raw = json.dumps({
        "question_type": "multiple_choice",
        "answer": ["A", "C"],
        "confidence": 0.85,
        "reason": "都对",
    })
    fake_client = MagicMock()
    fake_client.chat.return_value = raw
    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        result = text_solve("multiple_choice", "?", {"A": "a", "B": "b", "C": "c"}, _make_config())
    assert set(result.answer) == {"A", "C"}


def test_text_solver_raises_pause_on_bad_schema():
    raw = json.dumps({
        "question_type": "single_choice",
        "answer": "B",  # 应为 list
        "confidence": 0.9,
    })
    fake_client = MagicMock()
    fake_client.chat.return_value = raw
    from models.text_solver import make_openai_client
    from chaoxing_agent.core.errors import PauseRequiredError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            text_solve("single_choice", "?", {"A": "x", "B": "y"}, _make_config())


def test_text_solver_recovers_from_inner_json_object():
    """模型把单个 options 元素错当成顶层 JSON 输出 — 提取器应能挑出正确对象。"""
    inner_option = {"key": "B", "text": "2"}
    real_payload = {
        "question_type": "single_choice",
        "answer": ["A"],
        "confidence": 0.9,
        "reason": "OK",
    }
    raw_text = (
        f"我看到的选项 {json.dumps(inner_option, ensure_ascii=False)}\n"
        f"完整答案:\n"
        f"{json.dumps(real_payload, ensure_ascii=False)}"
    )
    fake_client = MagicMock()
    fake_client.chat.return_value = raw_text
    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        result = text_solve("single_choice", "1+1=?", {"A": "1", "B": "2"}, _make_config())
    assert result.answer == ["A"]
    assert result.confidence == 0.9
