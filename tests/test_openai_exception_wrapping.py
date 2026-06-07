"""vision_parser / text_solver 的 OpenAI SDK 异常包装回归测试。"""

import io
import json
from unittest.mock import MagicMock

import pytest
from PIL import Image

from chaoxing_agent.core.errors import PauseRequiredError, RecoverableError
from models.model_config import ModelConfig
from models.text_solver import solve as text_solve
from models.vision_parser import parse as vision_parse


def _make_config():
    return ModelConfig(
        api_type="openai",
        base_url="https://x.example/v1",
        api_key="k",
        model_id="m1",
    )


def _img():
    return Image.new("RGB", (10, 10), (255, 255, 255))


def test_vision_parser_wraps_connection_error_as_recoverable(monkeypatch):
    """openai.APIConnectionError 应被包装为 RecoverableError（重试）。"""
    fake_client = MagicMock()
    from openai import APIConnectionError
    fake_client.chat.side_effect = APIConnectionError(request=MagicMock())

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(RecoverableError):
            vision_parse(_img(), _make_config())


def test_vision_parser_wraps_timeout_as_recoverable(monkeypatch):
    from openai import APITimeoutError
    fake_client = MagicMock()
    fake_client.chat.side_effect = APITimeoutError(request=MagicMock())

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(RecoverableError):
            vision_parse(_img(), _make_config())


def test_vision_parser_wraps_rate_limit_as_recoverable(monkeypatch):
    from openai import RateLimitError
    fake_response = MagicMock()
    fake_response.status_code = 429
    fake_response.headers = {}
    fake_client = MagicMock()
    fake_client.chat.side_effect = RateLimitError(
        message="rate limited", response=fake_response, body=None
    )

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(RecoverableError):
            vision_parse(_img(), _make_config())


def test_vision_parser_wraps_authentication_error_as_pause(monkeypatch):
    """401/403 是配置错误，重试无意义，应升级为 PauseRequiredError 让人介入。"""
    from openai import AuthenticationError
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.headers = {}
    fake_client = MagicMock()
    fake_client.chat.side_effect = AuthenticationError(
        message="bad key", response=fake_response, body=None
    )

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            vision_parse(_img(), _make_config())


def test_vision_parser_wraps_api_error_5xx_as_recoverable(monkeypatch):
    from openai import APIStatusError
    fake_response = MagicMock()
    fake_response.status_code = 503
    fake_response.headers = {}
    fake_client = MagicMock()
    fake_client.chat.side_effect = APIStatusError(
        message="server err", response=fake_response, body=None
    )

    from models.vision_parser import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.vision_parser.make_openai_client", lambda _: fake_client)
        with pytest.raises(RecoverableError):
            vision_parse(_img(), _make_config())


def test_text_solver_wraps_timeout_as_recoverable(monkeypatch):
    from openai import APITimeoutError
    fake_client = MagicMock()
    fake_client.chat.side_effect = APITimeoutError(request=MagicMock())

    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        with pytest.raises(RecoverableError):
            text_solve("single_choice", "?", {"A": "x", "B": "y"}, _make_config())


def test_text_solver_wraps_auth_error_as_pause(monkeypatch):
    from openai import AuthenticationError
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.headers = {}
    fake_client = MagicMock()
    fake_client.chat.side_effect = AuthenticationError(
        message="bad key", response=fake_response, body=None
    )

    from models.text_solver import make_openai_client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("models.text_solver.make_openai_client", lambda _: fake_client)
        with pytest.raises(PauseRequiredError):
            text_solve("single_choice", "?", {"A": "x", "B": "y"}, _make_config())
