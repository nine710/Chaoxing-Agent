"""model_config + openai_client 的回归测试。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.model_config import (
    ModelConfig,
    _build_config,
    _get_api_key,
    get_solver_config,
    get_vision_config,
    make_openai_client,
)
from models.openai_client import OpenAIClient


# ---------------------------------------------------------------------------
# _get_api_key
# ---------------------------------------------------------------------------


def test_get_api_key_raises_when_env_var_missing(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="环境变量 NONEXISTENT_API_KEY 未设置"):
        _get_api_key("NONEXISTENT_API_KEY")


def test_get_api_key_returns_value(monkeypatch):
    monkeypatch.setenv("X_KEY", "abc123")
    assert _get_api_key("X_KEY") == "abc123"


# ---------------------------------------------------------------------------
# _build_config
# ---------------------------------------------------------------------------


def _entry(**overrides):
    e = {
        "api_type": "openai",
        "base_url": "https://example.com/v1",
        "api_key_env": "EXAMPLE_KEY",
        "model_id": "m1",
    }
    e.update(overrides)
    return e


def test_build_config_minimal(monkeypatch):
    monkeypatch.setenv("EXAMPLE_KEY", "k1")
    c = _build_config(_entry())
    assert c.api_type == "openai"
    assert c.base_url == "https://example.com/v1"
    assert c.api_key == "k1"
    assert c.model_id == "m1"
    assert c.extra_body == {}
    assert c.reasoning_effort is None
    assert c.use_response_format is True


def test_build_config_rejects_non_openai(monkeypatch):
    monkeypatch.setenv("EXAMPLE_KEY", "k1")
    with pytest.raises(ValueError, match="不支持的 api_type"):
        _build_config(_entry(api_type="anthropic"))


def test_build_config_optional_fields(monkeypatch):
    monkeypatch.setenv("EXAMPLE_KEY", "k1")
    c = _build_config(_entry(
        extra_body={"thinking": {"type": "enabled"}},
        reasoning_effort="high",
        use_response_format=False,
        max_tokens=800,
        temperature=0.0,
        image_format="jpeg",
        image_jpeg_quality=65,
    ))
    assert c.extra_body == {"thinking": {"type": "enabled"}}
    assert c.reasoning_effort == "high"
    assert c.use_response_format is False
    assert c.max_tokens == 800
    assert c.temperature == 0.0
    assert c.image_format == "jpeg"
    assert c.image_jpeg_quality == 65


def test_build_config_extra_body_none_treated_as_empty(monkeypatch):
    monkeypatch.setenv("EXAMPLE_KEY", "k1")
    c = _build_config(_entry(extra_body=None))
    assert c.extra_body == {}


# ---------------------------------------------------------------------------
# get_vision / get_solver
# ---------------------------------------------------------------------------


def test_get_vision_and_solver(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gk")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    services = {
        "vision": _entry(api_key_env="GOOGLE_API_KEY", model_id="gemini-2.5-flash"),
        "solver": _entry(
            api_key_env="DEEPSEEK_API_KEY",
            model_id="deepseek-chat",
            base_url="https://api.deepseek.com",
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        ),
    }
    vc = get_vision_config(services)
    sc = get_solver_config(services)
    assert vc.model_id == "gemini-2.5-flash"
    assert sc.reasoning_effort == "high"
    assert sc.extra_body == {"thinking": {"type": "enabled"}}


def test_get_config_missing_section_raises(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gk")
    with pytest.raises(KeyError):
        get_vision_config({"solver": _entry()})


def test_get_config_supports_selected_provider_registry(monkeypatch):
    """model_services 多 provider 注册表应按 selected.<role>_model 解析实际 provider。"""
    monkeypatch.setenv("VISION_KEY", "vk")
    monkeypatch.setenv("SOLVER_KEY", "sk")
    services = {
        "selected": {"vision_model": "gemini", "solver_model": "deepseek"},
        "vision": {
            "gemini": _entry(api_key_env="VISION_KEY", model_id="gemini-2.5-flash"),
        },
        "solver": {
            "deepseek": _entry(api_key_env="SOLVER_KEY", model_id="deepseek-chat"),
        },
    }

    vc = get_vision_config(services)
    sc = get_solver_config(services)

    assert vc.model_id == "gemini-2.5-flash"
    assert vc.api_key == "vk"
    assert sc.model_id == "deepseek-chat"
    assert sc.api_key == "sk"


def test_get_config_supports_selected_role_fallback(monkeypatch):
    """兼容已写入 selected.vision / selected.solver 的旧 RPC 数据。"""
    monkeypatch.setenv("VISION_KEY", "vk")
    services = {
        "selected": {"vision": "gemini"},
        "vision": {"gemini": _entry(api_key_env="VISION_KEY", model_id="gemini-2.5-flash")},
    }

    vc = get_vision_config(services)

    assert vc.model_id == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# OpenAIClient
# ---------------------------------------------------------------------------


def _make_config(**overrides):
    defaults = dict(
        api_type="openai",
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model_id="deepseek-chat",
        extra_body={},
        reasoning_effort=None,
        use_response_format=True,
        max_tokens=None,
        temperature=None,
        image_format="png",
        image_jpeg_quality=65,
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)


def test_openai_client_passes_basic_kwargs(monkeypatch):
    """base_url、api_key、timeout 必须传给 OpenAI()。"""
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = MagicMock()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config()
    OpenAIClient(cfg)

    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://api.deepseek.com"
    assert "timeout" in captured


def test_openai_client_strips_trailing_slash(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(base_url="https://api.deepseek.com/")
    OpenAIClient(cfg)
    assert captured["base_url"] == "https://api.deepseek.com"


def test_openai_client_normalizes_full_chat_completions_url(monkeypatch):
    """OpenAI SDK 需要 base_url 根路径，不能传完整 /chat/completions 端点。"""
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(base_url="https://apihub.agnes-ai.com/v1/chat/completions")
    OpenAIClient(cfg)
    assert captured["base_url"] == "https://apihub.agnes-ai.com/v1"


def test_chat_passes_model_messages_and_json_response(monkeypatch):
    """chat() 至少要带 model/messages/response_format={'type':'json_object'}/stream=False。"""
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config()
    client = OpenAIClient(cfg)
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert captured_kwargs["model"] == "deepseek-chat"
    assert captured_kwargs["response_format"] == {"type": "json_object"}
    assert captured_kwargs["stream"] is False
    assert captured_kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert "reasoning_effort" not in captured_kwargs
    assert "extra_body" not in captured_kwargs


def test_chat_passes_reasoning_effort_and_extra_body(monkeypatch):
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )
    # 必须显式把可选字段透传给 OpenAIClient.__init__
    client = OpenAIClient(
        cfg,
        extra=cfg.extra_body,
        reasoning_effort=cfg.reasoning_effort,
        use_response_format=cfg.use_response_format,
    )
    client.chat([{"role": "user", "content": "hi"}])
    assert captured_kwargs["reasoning_effort"] == "high"
    assert captured_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_chat_passes_max_tokens_and_temperature(monkeypatch):
    """vision/solver 可通过配置限制输出 token 和温度，减少无谓生成耗时。"""
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(max_tokens=900, temperature=0.0)
    client = OpenAIClient(cfg)
    client.chat([{"role": "user", "content": "hi"}])

    assert captured_kwargs["max_tokens"] == 900
    assert captured_kwargs["temperature"] == 0.0


def test_chat_merges_disable_thinking_into_extra_body(monkeypatch):
    """vision provider 配置 disable_thinking=True 时，请求中必须带 thinking 关闭字段。"""
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}})
    client = OpenAIClient(
        cfg,
        extra=cfg.extra_body,
        reasoning_effort=cfg.reasoning_effort,
        use_response_format=cfg.use_response_format,
    )
    client.chat([{"role": "user", "content": "hi"}])

    assert captured_kwargs["extra_body"] == {"enable_thinking": False, "thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in captured_kwargs


def test_chat_passes_low_reasoning_effort_with_thinking_enabled(monkeypatch):
    """solver 启用低深度思考时，reasoning_effort=low + extra_body enable_thinking=True 必须透传。"""
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(
        reasoning_effort="low",
        extra_body={"enable_thinking": True, "thinking": {"type": "low"}},
    )
    client = OpenAIClient(
        cfg,
        extra=cfg.extra_body,
        reasoning_effort=cfg.reasoning_effort,
        use_response_format=cfg.use_response_format,
    )
    client.chat([{"role": "user", "content": "hi"}])

    assert captured_kwargs["reasoning_effort"] == "low"
    assert captured_kwargs["extra_body"] == {"enable_thinking": True, "thinking": {"type": "low"}}


def test_chat_omits_response_format_when_disabled(monkeypatch):
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(use_response_format=False)
    client = OpenAIClient(
        cfg,
        extra=cfg.extra_body,
        reasoning_effort=cfg.reasoning_effort,
        use_response_format=cfg.use_response_format,
    )
    client.chat([{"role": "user", "content": "hi"}])
    assert "response_format" not in captured_kwargs


def test_chat_preserves_multimodal_content_list(monkeypatch):
    """vision 多模态 content 列表必须原样传给 SDK。"""
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                        model_id="gemini-2.5-flash")
    client = OpenAIClient(cfg)
    content = [
        {"type": "text", "text": "请解析"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]
    client.chat([{"role": "user", "content": content}])
    assert captured_kwargs["messages"][0]["content"] is content  # 原对象保留


# ---------------------------------------------------------------------------
# make_openai_client 工厂
# ---------------------------------------------------------------------------


def test_openai_client_reads_optional_fields_from_config():
    """直接传 ModelConfig 时，可选字段应自动从 config 透传 —— 不需要再传 extra/reasoning_effort。"""
    cfg = _make_config(
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        use_response_format=False,
    )
    # 只传 cfg 也能正确工作
    import models.openai_client as mod
    captured_kwargs: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].message.content = "ok"
            return m

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import unittest.mock as _um
    with _um.patch.object(mod, "OpenAI", FakeOpenAI):
        client = OpenAIClient(cfg)
        client.chat([{"role": "user", "content": "hi"}])
    assert captured_kwargs["reasoning_effort"] == "high"
    assert captured_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "response_format" not in captured_kwargs


def test_make_openai_client_passes_through_optional_fields(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import models.openai_client as mod
    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)

    cfg = _make_config(
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        use_response_format=False,
    )
    make_openai_client(cfg)
    # 构造时没动到 chat kwargs，只验证 SDK 初始化正常
    assert captured["api_key"] == "test-key"
