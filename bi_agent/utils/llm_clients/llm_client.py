"""LLM 客户端抽象基类"""

from abc import ABC, abstractmethod

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse


class LLMClient(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    async def chat(self, messages: list[LLMMessage], tools: list | None = None) -> LLMResponse:
        """发送聊天消息并获取响应

        Args:
            messages: 消息列表
            tools: 可用工具列表（可选）

        Returns:
            LLM 响应
        """
        pass

