"""工具基类"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import TypeAlias

ParamSchemaValue: TypeAlias = str | list[str] | bool | dict[str, object]
Property: TypeAlias = dict[str, ParamSchemaValue]


class ToolError(Exception):
    """工具错误基类"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message: str = message


@dataclass
class ToolExecResult:
    """工具执行中间结果"""

    output: str | None = None
    error: str | None = None
    error_code: int = 0


@dataclass
class ToolResult:
    """工具执行结果"""

    call_id: str
    name: str
    success: bool
    result: str | None = None
    error: str | None = None
    id: str | None = None


ToolCallArguments = dict[str, str | int | float | dict[str, object] | list[object] | None]


@dataclass
class ToolCall:
    """工具调用表示"""

    name: str
    call_id: str
    arguments: ToolCallArguments = field(default_factory=dict)
    id: str | None = None

    def __str__(self) -> str:
        return f"ToolCall(name={self.name}, arguments={self.arguments}, call_id={self.call_id}, id={self.id})"


@dataclass
class ToolParameter:
    """工具参数定义"""

    name: str
    type: str | list[str]
    description: str
    enum: list[str] | None = None
    items: dict[str, object] | None = None
    required: bool = True


class Tool(ABC):
    """工具基类"""

    def __init__(self, model_provider: str | None = None):
        self._model_provider = model_provider

    @cached_property
    def model_provider(self) -> str | None:
        return self.get_model_provider()

    @cached_property
    def name(self) -> str:
        return self.get_name()

    @cached_property
    def description(self) -> str:
        return self.get_description()

    @cached_property
    def parameters(self) -> list[ToolParameter]:
        return self.get_parameters()

    def get_model_provider(self) -> str | None:
        """获取模型提供商"""
        return self._model_provider

    @abstractmethod
    def get_name(self) -> str:
        """获取工具名称"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """获取工具描述"""
        pass

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        """获取工具参数"""
        pass

    @abstractmethod
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        """执行工具"""
        pass

    def json_definition(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_input_schema(),
        }

    def get_input_schema(self) -> dict[str, object]:
        """获取输入模式"""
        schema: dict[str, object] = {
            "type": "object",
        }

        properties: dict[str, Property] = {}
        required: list[str] = []

        for param in self.parameters:
            param_schema: Property = {
                "type": param.type,
                "description": param.description,
            }

            if self.model_provider == "openai":
                required.append(param.name)
                if not param.required:
                    current_type = param_schema["type"]
                    if isinstance(current_type, str):
                        param_schema["type"] = [current_type, "null"]
                    elif isinstance(current_type, list) and "null" not in current_type:
                        param_schema["type"] = list(current_type) + ["null"]
            elif param.required:
                required.append(param.name)

            if param.enum:
                param_schema["enum"] = param.enum

            if param.items:
                param_schema["items"] = param.items

            if self.model_provider == "openai" and param.type == "object":
                param_schema["additionalProperties"] = False

            properties[param.name] = param_schema

        schema["properties"] = properties
        if len(required) > 0:
            schema["required"] = required

        if self.model_provider == "openai":
            schema["additionalProperties"] = False

        return schema

    async def close(self):
        """确保工具资源正确释放"""
        return None


class ToolExecutor:
    """工具执行器"""

    def __init__(self, tools: list[Tool]):
        self._tools = tools
        self._tool_map: dict[str, Tool] | None = None

    async def close_tools(self):
        """确保所有工具资源正确释放"""
        tasks = [tool.close() for tool in self._tools if hasattr(tool, "close")]
        res = await asyncio.gather(*tasks)
        return res

    def _normalize_name(self, name: str) -> str:
        """规范化工具名称"""
        return name.lower().replace("_", "")

    @property
    def tools(self) -> dict[str, Tool]:
        if self._tool_map is None:
            self._tool_map = {self._normalize_name(tool.name): tool for tool in self._tools}
        return self._tool_map

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """执行工具调用"""
        normalized_name = self._normalize_name(tool_call.name)
        if normalized_name not in self.tools:
            return ToolResult(
                name=tool_call.name,
                success=False,
                error=f"工具 '{tool_call.name}' 未找到。可用工具: {[tool.name for tool in self._tools]}",
                call_id=tool_call.call_id,
                id=tool_call.id,
            )

        tool = self.tools[normalized_name]

        try:
            tool_exec_result = await tool.execute(tool_call.arguments)
            return ToolResult(
                name=tool_call.name,
                success=tool_exec_result.error_code == 0,
                result=tool_exec_result.output,
                error=tool_exec_result.error,
                call_id=tool_call.call_id,
                id=tool_call.id,
            )
        except Exception as e:
            return ToolResult(
                name=tool_call.name,
                success=False,
                error=f"执行工具 '{tool_call.name}' 时出错: {str(e)}",
                call_id=tool_call.call_id,
                id=tool_call.id,
            )

    async def parallel_tool_call(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """并行执行工具调用"""
        return await asyncio.gather(*[self.execute_tool_call(call) for call in tool_calls])

    async def sequential_tool_call(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """顺序执行工具调用"""
        return [await self.execute_tool_call(call) for call in tool_calls]

