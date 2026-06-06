"""OpenAI 兼容 API 客户端"""

import requests

from models.base_client import BaseModelClient
from models.model_config import ModelConfig


class OpenAIClient(BaseModelClient):
    def __init__(self, config: ModelConfig):
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.model_id = config.model_id

    def chat(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
