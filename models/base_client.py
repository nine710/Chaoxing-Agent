"""模型客户端抽象基类"""

from abc import ABC, abstractmethod


class BaseModelClient(ABC):
    """所有模型客户端的抽象基类"""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """发送请求，返回模型原始响应文本"""
        ...
