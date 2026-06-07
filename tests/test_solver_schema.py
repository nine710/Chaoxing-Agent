"""solver_schema 的回归测试。"""

import pytest
from pydantic import ValidationError

from schemas.solver_schema import SolverResult


def _valid_raw(**overrides):
    raw = {
        "question_type": "single_choice",
        "answer": ["B"],
        "confidence": 0.92,
        "reason": "分析：……",
    }
    raw.update(overrides)
    return raw


def test_reason_none_normalizes_to_empty_string():
    r = SolverResult.model_validate(_valid_raw(reason=None))
    assert r.reason == ""


def test_reason_explicit_string_preserved():
    r = SolverResult.model_validate(_valid_raw(reason="因为……"))
    assert r.reason == "因为……"


def test_answer_must_be_list_of_strings():
    with pytest.raises(ValidationError):
        SolverResult.model_validate(_valid_raw(answer="B"))


def test_confidence_out_of_range_still_parses():
    """confidence 不强制 0~1 范围，但要能解析。"""
    r = SolverResult.model_validate(_valid_raw(confidence=1.5))
    assert r.confidence == 1.5


def test_question_type_can_be_unknown():
    r = SolverResult.model_validate(_valid_raw(question_type="unknown"))
    assert r.question_type == "unknown"
