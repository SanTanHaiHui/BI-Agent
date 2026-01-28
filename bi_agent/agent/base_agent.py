"""Agent 基类"""

import asyncio
from abc import ABC, abstractmethod
from typing import Union, Optional

from bi_agent.agent.agent_basics import AgentExecution, AgentState, AgentStep, AgentStepState
from bi_agent.tools.base import Tool, ToolCall, ToolExecutor, ToolResult
from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.trajectory_recorder import TrajectoryRecorder
from bi_agent.utils.console_output import ConsoleOutput
from bi_agent.utils.memory_manager import MemoryManager, MemoryConfig


class BaseAgent(ABC):
    """LLM-based Agent 的基类"""

    def __init__(
        self,
        llm_client: LLMClient,
        tools: list[Tool],
        max_steps: int = 50,
        console_output: Optional[ConsoleOutput] = None,
        memory_config: Optional[MemoryConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """初始化 Agent

        Args:
            llm_client: LLM 客户端
            tools: 可用工具列表
            max_steps: 最大执行步数
            console_output: 控制台输出器（可选）
            memory_config: 记忆配置（可选）
            user_id: 用户 ID（用于长期记忆）
            session_id: 会话 ID（用于短期记忆）
        """
        self._llm_client = llm_client
        self._tools = tools
        self._max_steps = max_steps
        self._tool_caller = ToolExecutor(self._tools)
        self._task: str = ""
        self._initial_messages: list[LLMMessage] = []
        self._trajectory_recorder: TrajectoryRecorder | None = None
        self._console_output = console_output
        
        # 初始化记忆管理器
        self._memory_manager = MemoryManager(
            config=memory_config,
            user_id=user_id,
            session_id=session_id,
        )

    @property
    def llm_client(self) -> LLMClient:
        return self._llm_client

    @property
    def tools(self) -> list[Tool]:
        return self._tools

    @property
    def task(self) -> str:
        return self._task

    @task.setter
    def task(self, value: str):
        self._task = value

    @property
    def trajectory_recorder(self) -> TrajectoryRecorder | None:
        return self._trajectory_recorder

    def set_trajectory_recorder(self, recorder: TrajectoryRecorder | None) -> None:
        self._trajectory_recorder = recorder

    @abstractmethod
    def new_task(self, task: str, extra_args: dict[str, str] | None = None):
        """创建新任务"""
        pass
    
    @property
    def memory_manager(self) -> MemoryManager:
        """获取记忆管理器"""
        return self._memory_manager

    async def execute_task(self) -> AgentExecution:
        """执行任务"""
        import time

        start_time = time.time()
        execution = AgentExecution(task=self._task, steps=[])
        step: AgentStep | None = None

        try:
            messages = self._initial_messages
            step_number = 1
            execution.agent_state = AgentState.RUNNING

            while step_number <= self._max_steps:
                step = AgentStep(step_number=step_number, state=AgentStepState.THINKING)
                
                # 显示步骤开始
                if self._console_output:
                    self._console_output.print_step_start(step_number, self._max_steps)
                
                try:
                    messages = await self._run_llm_step(step, messages, execution)
                    await self._finalize_step(step, messages, execution)
                    if execution.agent_state == AgentState.COMPLETED:
                        break
                    step_number += 1
                except Exception as error:
                    execution.agent_state = AgentState.ERROR
                    step.state = AgentStepState.ERROR
                    step.error = str(error)
                    await self._finalize_step(step, messages, execution)
                    break

            if step_number > self._max_steps and not execution.success:
                execution.final_result = "任务执行超过最大步数，未完成。"
                execution.agent_state = AgentState.ERROR

        except Exception as e:
            execution.final_result = f"Agent 执行失败: {str(e)}"
            execution.agent_state = AgentState.ERROR

        finally:
            await self._close_tools()

        execution.execution_time = time.time() - start_time
        return execution

    async def _run_llm_step(
        self, step: AgentStep, messages: list[LLMMessage], execution: AgentExecution
    ) -> list[LLMMessage]:
        """运行 LLM 步骤"""
        step.state = AgentStepState.THINKING
        step.thought = "正在思考..."

        # 获取相关记忆并添加到消息中
        memory_messages = []
        
        if self._task:
            # 基于任务查询相关记忆
            relevant_memories = self._memory_manager.get_relevant_memories(
                query=self._task,
                context="当前任务执行中",
            )
            if relevant_memories:
                memory_messages.extend(relevant_memories)
        
        # 获取最近的对话交互作为记忆消息
        # 包括：大模型响应、工具调用、工具结果
        # 排除系统消息、记忆消息和初始任务消息
        recent_interactions = []
        
        # 从后往前遍历消息，收集最近的交互
        for msg in reversed(messages):
            # 排除系统消息和记忆消息
            if msg.role == "system" and msg.content and msg.content.startswith("[记忆 -"):
                continue
            
            # 排除初始任务消息
            if msg.role == "user" and msg.content and msg.content.startswith("数据分析任务："):
                continue
            
            # 优先检查工具结果消息（role 是 "user" 但包含 tool_result）
            if msg.tool_result:
                tool_result = msg.tool_result
                result_parts = []
                
                result_parts.append(f"工具 {tool_result.name} 执行结果")
                if tool_result.success:
                    if tool_result.result:
                        result_preview = str(tool_result.result)
                        if len(result_preview) > 300:
                            result_preview = result_preview[:300] + "..."
                        result_parts.append(f"成功: {result_preview}")
                    else:
                        result_parts.append("成功（无返回内容）")
                else:
                    error_preview = str(tool_result.error) if tool_result.error else "未知错误"
                    if len(error_preview) > 300:
                        error_preview = error_preview[:300] + "..."
                    result_parts.append(f"失败: {error_preview}")
                
                recent_interactions.append({
                    "role": "tool_result",
                    "content": " | ".join(result_parts)
                })
            
            # 收集 assistant 消息（包含响应和工具调用）
            elif msg.role == "assistant":
                interaction_parts = []
                
                # 添加响应内容
                if msg.content:
                    content_preview = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                    interaction_parts.append(f"响应: {content_preview}")
                
                # 添加工具调用信息
                if msg.tool_calls:
                    tool_calls_info = []
                    for tool_call in msg.tool_calls:
                        tool_info = f"调用工具 {tool_call.name}"
                        if tool_call.arguments:
                            # 简化参数显示（只显示关键参数）
                            args_str = str(tool_call.arguments)
                            if len(args_str) > 200:
                                args_str = args_str[:200] + "..."
                            tool_info += f" (参数: {args_str})"
                        tool_calls_info.append(tool_info)
                    interaction_parts.append(f"工具调用: {'; '.join(tool_calls_info)}")
                elif msg.tool_call:  # 向后兼容
                    tool_info = f"调用工具 {msg.tool_call.name}"
                    if msg.tool_call.arguments:
                        args_str = str(msg.tool_call.arguments)
                        if len(args_str) > 200:
                            args_str = args_str[:200] + "..."
                        tool_info += f" (参数: {args_str})"
                    interaction_parts.append(f"工具调用: {tool_info}")
                
                if interaction_parts:
                    recent_interactions.append({
                        "role": "assistant",
                        "content": " | ".join(interaction_parts)
                    })
            
            # 收集用户消息（非初始任务，且不是工具结果消息）
            elif msg.role == "user" and msg.content and not msg.tool_result:
                content_preview = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                recent_interactions.append({
                    "role": "user",
                    "content": content_preview
                })
            
            # 收集足够的交互（最近的两条完整交互：assistant + tool_result，或 user + assistant）
            # 我们收集最近的 2-4 条消息，确保包含完整的交互循环
            if len(recent_interactions) >= 4:
                break
        
        # 反转列表，恢复时间顺序
        recent_interactions.reverse()
        
        # 将最近的交互转换为记忆消息
        if recent_interactions:
            # 只取最后两条交互（避免记忆过长）
            for interaction in recent_interactions[-2:]:
                memory_msg = LLMMessage(
                    role="system",
                    content=f"[记忆 - 最近对话]: {interaction['role']}: {interaction['content']}",
                )
                memory_messages.append(memory_msg)
        
        # 将记忆消息添加到消息列表中
        if memory_messages:
            # 先移除之前添加的记忆消息（避免重复累积）
            # 记忆消息的特征：role="system" 且 content 以 "[记忆 -" 开头
            messages = [
                msg for msg in messages 
                if not (msg.role == "system" and msg.content and msg.content.startswith("[记忆 -"))
            ]
            
            # 找到系统消息的位置
            system_idx = -1
            for i, msg in enumerate(messages):
                if msg.role == "system":
                    system_idx = i
                    break
            
            if system_idx >= 0:
                # 在系统消息后插入记忆消息
                messages = messages[:system_idx+1] + memory_messages + messages[system_idx+1:]
            else:
                # 如果没有系统消息，添加到开头
                messages = memory_messages + messages

        # 显示 LLM 输入
        if self._console_output:
            self._console_output.print_llm_input(messages, step.step_number)

        # 调用 LLM
        try:
            response: LLMResponse = await self._llm_client.chat(messages, tools=self._tools)
        except Exception as e:
            # 捕获 LLM 调用错误
            step.state = AgentStepState.ERROR
            step.error = f"LLM 调用失败: {str(e)}"
            execution.agent_state = AgentState.ERROR
            execution.final_result = f"LLM 调用失败: {str(e)}"
            if self._console_output:
                self._console_output.print_error(str(e), step.step_number)
            raise
        
        step.llm_response = response
        step.llm_usage = response.usage

        # 显示 LLM 输出
        if self._console_output:
            self._console_output.print_llm_output(response, step.step_number)

        # 将 assistant 的响应添加到消息历史（保留之前的消息）
        # 如果有工具调用，需要包含工具调用信息
        if response.tool_calls:
            # 创建包含所有工具调用的 assistant 消息
            assistant_message = LLMMessage(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,  # 保存所有工具调用
                tool_call=response.tool_calls[0] if len(response.tool_calls) == 1 else None  # 向后兼容
            )
            # 将 assistant 响应添加到消息历史（保留之前的消息）
            messages.append(assistant_message)
            # 添加到记忆管理器
            self._memory_manager.add_message(assistant_message)
            
            # 处理工具调用，获取工具结果
            tool_result_messages = await self._tool_call_handler(response.tool_calls, step)
            # 将工具结果添加到消息历史
            messages.extend(tool_result_messages)
            
            # 将工具结果添加到记忆管理器，并检查是否有 task_done 工具调用
            task_done_called = False
            task_done_summary = ""
            
            for tool_result_msg in tool_result_messages:
                self._memory_manager.add_message(tool_result_msg)
                # 如果工具执行成功，将结果添加到短期记忆
                if tool_result_msg.tool_result and tool_result_msg.tool_result.success:
                    tool_name = tool_result_msg.tool_result.name
                    tool_result = tool_result_msg.tool_result.result
                    
                    # 检查是否是 task_done 工具
                    if tool_name == "task_done":
                        task_done_called = True
                        # 提取任务完成总结
                        if tool_result:
                            task_done_summary = tool_result
                        # 从工具调用参数中提取 summary
                        for tool_call in response.tool_calls:
                            if tool_call.name == "task_done" and tool_call.arguments:
                                summary = tool_call.arguments.get("summary", "")
                                if summary:
                                    task_done_summary = str(summary)
                                    break
                    
                    self._memory_manager.add_memory(
                        content=f"工具 {tool_name} 执行结果: {tool_result}",
                        memory_type="session",
                        metadata={
                            "tool_name": tool_name,
                            "step_number": step.step_number,
                        },
                    )
            
            # 如果调用了 task_done 工具，标记任务完成
            if task_done_called:
                execution.agent_state = AgentState.COMPLETED
                execution.success = True
                execution.final_result = task_done_summary or "任务已完成"
                # 将任务完成信息添加到长期记忆
                self._memory_manager.add_memory(
                    content=f"任务完成: {self._task}\n总结: {task_done_summary}",
                    memory_type="user",
                    metadata={"task": self._task, "status": "completed"},
                )
        else:
            # 没有工具调用，添加 assistant 响应到消息历史（保留之前的消息）
            assistant_message = LLMMessage(role="assistant", content=response.content)
            messages.append(assistant_message)
            # 添加到记忆管理器
            self._memory_manager.add_message(assistant_message)
            
            # 检查是否完成任务
            if self._is_task_complete(response.content):
                execution.agent_state = AgentState.COMPLETED
                execution.success = True
                execution.final_result = response.content
                # 将任务完成信息添加到长期记忆
                self._memory_manager.add_memory(
                    content=f"任务完成: {self._task}\n结果: {response.content}",
                    memory_type="user",
                    metadata={"task": self._task, "status": "completed"},
                )

        return messages

    async def _tool_call_handler(
        self, tool_calls: list[ToolCall] | None, step: AgentStep
    ) -> list[LLMMessage]:
        """处理工具调用"""
        messages: list[LLMMessage] = []
        if not tool_calls or len(tool_calls) <= 0:
            messages = [
                LLMMessage(role="user", content="看起来你还没有完成任务。")
            ]
            return messages

        step.state = AgentStepState.CALLING_TOOL
        step.tool_calls = tool_calls

        # 执行工具调用（顺序执行）
        tool_results = await self._tool_caller.sequential_tool_call(tool_calls)
        step.tool_results = tool_results

        # 显示工具执行结果
        if self._console_output:
            self._console_output.print_tool_execution(tool_calls, tool_results)

        # 将工具结果添加到消息中
        for tool_result in tool_results:
            message = LLMMessage(role="user", tool_result=tool_result)
            messages.append(message)

        return messages

    def _is_task_complete(self, content: str | None) -> bool:
        """判断任务是否完成"""
        if not content:
            return False
        # 简单的完成判断逻辑，可以根据需要扩展
        completion_keywords = ["完成", "已完成", "任务完成", "分析完成", "报告已生成"]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in completion_keywords)

    async def _finalize_step(
        self, step: AgentStep, messages: list[LLMMessage], execution: AgentExecution
    ) -> None:
        """完成步骤，记录轨迹"""
        execution.steps.append(step)

        if self._trajectory_recorder:
            self._trajectory_recorder.record_agent_step(
                step_number=step.step_number,
                state=step.state.name,
                llm_messages=messages,
                llm_response=step.llm_response,
                tool_calls=step.tool_calls,
                tool_results=step.tool_results,
                reflection=step.reflection,
                error=step.error,
            )
        
        # 将步骤的关键信息添加到记忆
        if step.llm_response and step.llm_response.content:
            # 提取关键信息
            key_info = step.llm_response.content[:500]  # 前500字符
            self._memory_manager.add_memory(
                content=f"步骤 {step.step_number}: {key_info}",
                memory_type="session",
                metadata={
                    "step_number": step.step_number,
                    "state": step.state.name,
                },
            )

    async def _close_tools(self):
        """关闭工具"""
        await self._tool_caller.close_tools()

