"""Google Gemini API 客户端"""

import requests

from models.base_client import BaseModelClient
from models.model_config import ModelConfig


class GoogleClient(BaseModelClient):
    def __init__(self, config: ModelConfig):
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.model_id = config.model_id

    def chat(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"

        contents = []
        for msg in messages:
            if msg.get("role") == "system":
                continue

            parts = []
            if isinstance(msg.get("content"), str):
                parts.append({"text": msg["content"]})
            elif isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "text":
                        parts.append({"text": item["text"]})
                    elif item.get("type") == "image_url":
                        data_url = item["image_url"]["url"]
                        header, b64 = data_url.split(",", 1)
                        mime = header.replace("data:", "").replace(";base64", "")
                        parts.append({"inline_data": {"mime_type": mime, "data": b64}})

            if parts:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({"role": role, "parts": parts})

        system_text = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
                break
        if system_text and contents:
            contents[0]["parts"].insert(
                0,
                {"text": f"[System Instruction]\n{system_text}\n\nPlease follow the system instruction above."},
            )

        body = {
            "contents": contents,
            "generationConfig": {"response_mime_type": "application/json"},
        }

        resp = requests.post(url, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        return parts[0]["text"] if parts else ""
