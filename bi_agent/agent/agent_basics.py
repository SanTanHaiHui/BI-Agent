"""Agent 基础数据类型"""

from dataclasses import dataclass
from enum import Enum

from bi_agent.tools.base import ToolCall, ToolResult
from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse, LLMUsage


class AgentState(Enum):
    """Agent 状态"""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class AgentStepState(Enum):
    """Agent 步骤状态"""

    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    REFLECTING = "reflecting"
    ERROR = "error"


@dataclass
class AgentStep:
    """表示 Agent 执行过程中的单个步骤"""

    step_number: int
    state: AgentStepState
    thought: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_results: list[ToolResult] | None = None
    llm_response: LLMResponse | None = None
    reflection: str | None = None
    error: str | None = None
    extra: dict[str, object] | None = None
    llm_usage: LLMUsage | None = None

    def __repr__(self) -> str:
        return (
            f"<AgentStep #{self.step_number} "
            f"state={self.state.name} "
            f"thought={repr(self.thought)[:40] if self.thought else None}...>"
        )


@dataclass
class AgentExecution:
    """表示 Agent 的完整执行过程"""

    task: str
    steps: list[AgentStep]
    agent_state: AgentState = AgentState.IDLE
    success: bool = False
    final_result: str | None = None
    execution_time: float = 0.0

