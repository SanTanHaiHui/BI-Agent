"""LLM 基础数据类型"""

from dataclasses import dataclass

from bi_agent.tools.base import ToolCall, ToolResult


@dataclass
class LLMMessage:
    """标准消息格式"""

    role: str
    content: str | None = None
    tool_call: ToolCall | None = None  # 单个工具调用（用于向后兼容）
    tool_calls: list[ToolCall] | None = None  # 多个工具调用（用于 assistant 消息）
    tool_result: ToolResult | None = None


@dataclass
class LLMUsage:
    """LLM 使用量格式"""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    reasoning_tokens: int = 0

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )

    def __str__(self) -> str:
        return f"LLMUsage(input_tokens={self.input_tokens}, output_tokens={self.output_tokens}, cache_creation_input_tokens={self.cache_creation_input_tokens}, cache_read_input_tokens={self.cache_read_input_tokens}, reasoning_tokens={self.reasoning_tokens})"


@dataclass
class LLMResponse:
    """标准 LLM 响应格式"""

    content: str
    usage: LLMUsage | None = None
    model: str | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None

