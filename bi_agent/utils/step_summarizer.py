"""步骤摘要生成模块"""

from typing import Optional

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from bi_agent.utils.llm_clients.llm_client import LLMClient


class StepSummarizer:
    """生成执行步骤的文字摘要"""

    SUMMARY_PROMPT = """请根据以下 Agent 执行步骤，生成一段简洁的中文摘要，说明整个数据分析任务的执行过程。

要求：
1. 摘要应包含主要执行步骤（如数据读取、清洗、分析、可视化等）
2. 突出关键发现和结果
3. 语言简洁明了，控制在 200 字以内
4. 使用专业但易懂的语言

执行步骤信息：
{steps_info}

请直接输出摘要内容，不要包含其他说明文字。"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化步骤摘要生成器

        Args:
            llm_client: LLM 客户端（可选，如果不提供则返回简单摘要）
        """
        self.llm_client = llm_client

    async def generate_summary(self, agent_steps: list[dict]) -> str:
        """生成执行步骤摘要

        Args:
            agent_steps: Agent 执行步骤列表

        Returns:
            步骤摘要文本
        """
        if not agent_steps:
            return "未执行任何步骤。"

        # 提取步骤信息
        steps_info = []
        for step in agent_steps:
            step_desc = f"步骤 {step.get('step_number', '?')}: {step.get('state', 'unknown')}"
            if step.get("tool_calls"):
                tools = [tc.get("name", "unknown") for tc in step["tool_calls"]]
                step_desc += f" - 调用工具: {', '.join(tools)}"
            if step.get("reflection"):
                step_desc += f" - 反思: {step['reflection'][:100]}"
            steps_info.append(step_desc)

        steps_text = "\n".join(steps_info)

        # 如果有 LLM 客户端，使用 LLM 生成摘要
        if self.llm_client:
            try:
                prompt = self.SUMMARY_PROMPT.format(steps_info=steps_text)
                messages = [LLMMessage(role="user", content=prompt)]
                response: LLMResponse = await self.llm_client.chat(messages)
                return response.content.strip() if response.content else self._generate_simple_summary(agent_steps)
            except Exception:
                # 如果 LLM 调用失败，回退到简单摘要
                return self._generate_simple_summary(agent_steps)
        else:
            return self._generate_simple_summary(agent_steps)

    def _generate_simple_summary(self, agent_steps: list[dict]) -> str:
        """生成简单摘要（不使用 LLM）"""
        total_steps = len(agent_steps)
        tool_calls = []
        for step in agent_steps:
            if step.get("tool_calls"):
                for tc in step["tool_calls"]:
                    tool_name = tc.get("name", "unknown")
                    if tool_name not in tool_calls:
                        tool_calls.append(tool_name)

        summary = f"共执行 {total_steps} 个步骤"
        if tool_calls:
            summary += f"，使用了以下工具：{', '.join(tool_calls)}"
        summary += "。"

        return summary

