"""OpenAI SDK 客户端 — 兼容 Google Gemini 与 DeepSeek 的 OpenAI 兼容端点。

通过 model_services.json 的可选字段透传 SDK 专用参数：
  - extra_body:        传给 client.chat.completions.create 的 extra_body
                       (DeepSeek: {"thinking": {"type": "enabled"}};
                        Google:   {"google": {"thinking_config": {...}}})
  - reasoning_effort:  DeepSeek 专用 ("low"|"medium"|"high"|None)
  - response_format:   设为 false 可关闭 JSON 模式（默认开启 {"type":"json_object"}）

参考：
  - DeepSeek: https://api-docs.deepseek.com/zh-cn/
  - Google Gemini OpenAI 兼容: https://ai.google.dev/gemini-api/docs/openai
"""

from typing import Any

from openai import OpenAI

from models.base_client import BaseModelClient
from models.model_config import ModelConfig


_DEFAULT_TIMEOUT = 120.0


def _normalize_base_url(base_url: str) -> str:
    """规范化 OpenAI SDK base_url。

    SDK 的 base_url 应是 API 根路径；如果用户误填完整
    /chat/completions 端点，需要裁掉该后缀，否则 SDK 会重复拼接路径。
    """
    url = base_url.rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    return url


class OpenAIClient(BaseModelClient):
    def __init__(self, config: ModelConfig, extra: dict | None = None,
                 reasoning_effort: str | None = None,
                 use_response_format: bool | None = None):
        """构造 OpenAI 兼容客户端。

        `extra` / `reasoning_effort` / `use_response_format` 若未显式给出，
        会从 `config` 读取。这样直接 `OpenAIClient(cfg)` 也能保留所有可选字段。
        """
        self.base_url = _normalize_base_url(config.base_url)
        self.api_key = config.api_key
        self.model_id = config.model_id

        # OpenAI SDK >= 1.0 入口
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=_DEFAULT_TIMEOUT,
        )

        self._extra_body: dict = dict(extra if extra is not None else (config.extra_body or {}))
        self._reasoning_effort = reasoning_effort if reasoning_effort is not None else config.reasoning_effort
        self._use_response_format = (
            use_response_format if use_response_format is not None else config.use_response_format
        )
        self._max_tokens = config.max_tokens
        self._temperature = config.temperature

    def chat(self, messages: list[dict]) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
        }

        if self._use_response_format:
            kwargs["response_format"] = {"type": "json_object"}

        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort

        if self._extra_body:
            kwargs["extra_body"] = self._extra_body

        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens

        if self._temperature is not None:
            kwargs["temperature"] = self._temperature

        # DeepSeek 示例里显式 stream=False；非流式默认就是 False，写上明确语义
        kwargs["stream"] = False

        resp = self._client.chat.completions.create(**kwargs)
        # resp.choices[0].message.content 在非流式响应下是 str
        return resp.choices[0].message.content or ""
