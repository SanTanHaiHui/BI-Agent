"""执行轨迹记录模块"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bi_agent.tools.base import ToolCall, ToolResult
from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse


class TrajectoryRecorder:
    """记录 Agent 执行轨迹和 LLM 交互"""

    def __init__(self, trajectory_path: Optional[str] = None):
        """初始化轨迹记录器

        Args:
            trajectory_path: 轨迹文件保存路径。如果为 None，则生成默认路径
        """
        if trajectory_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trajectory_path = f"trajectories/trajectory_{timestamp}.json"

        self.trajectory_path: Path = Path(trajectory_path).resolve()
        try:
            self.trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            print("错误：无法创建轨迹目录。轨迹可能无法正确保存。")

        self.trajectory_data: dict[str, Any] = {
            "task": "",
            "start_time": "",
            "end_time": "",
            "provider": "",
            "model": "",
            "max_steps": 0,
            "data_dir": "",
            "output_dir": "",
            "llm_interactions": [],
            "agent_steps": [],
            "success": False,
            "final_result": None,
            "execution_time": 0.0,
            "summary": "",
        }

    def start_recording(
        self,
        task: str,
        provider: str,
        model: str,
        max_steps: int,
        data_dir: str,
        output_dir: str,
    ) -> None:
        """开始记录轨迹

        Args:
            task: 任务描述
            provider: LLM 提供商
            model: 模型名称
            max_steps: 最大步数
            data_dir: 数据目录
            output_dir: 输出目录
        """
        self.trajectory_data["task"] = task
        self.trajectory_data["start_time"] = datetime.now().isoformat()
        self.trajectory_data["provider"] = provider
        self.trajectory_data["model"] = model
        self.trajectory_data["max_steps"] = max_steps
        self.trajectory_data["data_dir"] = data_dir
        self.trajectory_data["output_dir"] = output_dir
        self.save_trajectory()

    def end_recording(self, success: bool, final_result: Optional[str] = None, summary: Optional[str] = None) -> None:
        """结束记录轨迹

        Args:
            success: 是否成功
            final_result: 最终结果
            summary: 执行摘要
        """
        self.trajectory_data["end_time"] = datetime.now().isoformat()
        self.trajectory_data["success"] = success
        self.trajectory_data["final_result"] = final_result
        self.trajectory_data["summary"] = summary

        if self.trajectory_data["start_time"]:
            start = datetime.fromisoformat(self.trajectory_data["start_time"])
            end = datetime.fromisoformat(self.trajectory_data["end_time"])
            self.trajectory_data["execution_time"] = (end - start).total_seconds()

        self.save_trajectory()

    def record_llm_interaction(
        self,
        messages: list[LLMMessage],
        response: LLMResponse,
        provider: str,
        model: str,
        tools: Optional[list[Any]] = None,
    ) -> None:
        """记录 LLM 交互

        Args:
            messages: 发送给 LLM 的消息列表
            response: LLM 响应
            provider: LLM 提供商
            model: 模型名称
            tools: 可用工具列表（可选）
        """
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "messages": [self._serialize_message(msg) for msg in messages],
            "response": {
                "content": response.content,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens if response.usage else None,
                    "output_tokens": response.usage.output_tokens if response.usage else None,
                }
                if response.usage
                else None,
                "tool_calls": [self._serialize_tool_call(tc) for tc in response.tool_calls]
                if response.tool_calls
                else None,
            },
            "provider": provider,
            "model": model,
        }

        if tools:
            interaction["available_tools"] = [tool.name if hasattr(tool, "name") else str(tool) for tool in tools]

        self.trajectory_data["llm_interactions"].append(interaction)
        self.save_trajectory()

    def record_agent_step(
        self,
        step_number: int,
        state: str,
        llm_messages: Optional[list[LLMMessage]] = None,
        llm_response: Optional[LLMResponse] = None,
        tool_calls: Optional[list[ToolCall]] = None,
        tool_results: Optional[list[ToolResult]] = None,
        reflection: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录 Agent 执行步骤

        Args:
            step_number: 步骤编号
            state: 当前状态
            llm_messages: 发送给 LLM 的消息
            llm_response: LLM 响应
            tool_calls: 工具调用列表
            tool_results: 工具执行结果列表
            reflection: 反思内容
            error: 错误信息
        """
        step_data = {
            "step_number": step_number,
            "timestamp": datetime.now().isoformat(),
            "state": state,
            "llm_messages": [self._serialize_message(msg) for msg in llm_messages] if llm_messages else None,
            "llm_response": {
                "content": llm_response.content,
                "model": llm_response.model,
                "finish_reason": llm_response.finish_reason,
                "usage": {
                    "input_tokens": llm_response.usage.input_tokens if llm_response.usage else None,
                    "output_tokens": llm_response.usage.output_tokens if llm_response.usage else None,
                }
                if llm_response.usage
                else None,
                "tool_calls": [self._serialize_tool_call(tc) for tc in llm_response.tool_calls]
                if llm_response.tool_calls
                else None,
            }
            if llm_response
            else None,
            "tool_calls": [self._serialize_tool_call(tc) for tc in tool_calls] if tool_calls else None,
            "tool_results": [self._serialize_tool_result(tr) for tr in tool_results] if tool_results else None,
            "reflection": reflection,
            "error": error,
        }

        self.trajectory_data["agent_steps"].append(step_data)
        self.save_trajectory()

    def _serialize_message(self, message: LLMMessage) -> dict[str, Any]:
        """序列化消息对象"""
        result = {"role": message.role}
        if message.content:
            result["content"] = message.content
        if message.tool_result:
            result["tool_result"] = self._serialize_tool_result(message.tool_result)
        return result

    def _serialize_tool_call(self, tool_call: ToolCall) -> dict[str, Any]:
        """序列化工具调用对象"""
        return {
            "name": tool_call.name,
            "call_id": tool_call.call_id,
            "arguments": tool_call.arguments,
            "id": tool_call.id,
        }

    def _serialize_tool_result(self, tool_result: ToolResult) -> dict[str, Any]:
        """序列化工具结果对象"""
        return {
            "call_id": tool_result.call_id,
            "name": tool_result.name,
            "success": tool_result.success,
            "result": tool_result.result,
            "error": tool_result.error,
            "id": tool_result.id,
        }

    def save_trajectory(self) -> None:
        """保存轨迹到文件"""
        try:
            with open(self.trajectory_path, "w", encoding="utf-8") as f:
                json.dump(self.trajectory_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"错误：无法保存轨迹文件: {e}")

