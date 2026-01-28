"""OpenAI LLM 客户端实现"""

from bi_agent.utils.typing_compat import override

try:
    import openai
except ImportError:
    openai = None

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse, LLMUsage
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.tools.base import Tool, ToolCall


class OpenAIClient(LLMClient):
    """OpenAI LLM 客户端"""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str | None = None):
        """初始化 OpenAI 客户端

        Args:
            api_key: OpenAI API Key
            model: 模型名称
            base_url: API Base URL（可选，用于兼容其他 OpenAI 兼容的 API）
        """
        if openai is None:
            raise ImportError("请安装 openai 包: pip install openai")

        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @override
    async def chat(self, messages: list[LLMMessage], tools: list[Tool] | None = None) -> LLMResponse:
        """发送聊天消息"""
        import asyncio

        # 转换为 OpenAI 格式
        openai_messages = []
        for msg in messages:
            if msg.role == "system":
                openai_messages.append({"role": "system", "content": msg.content or ""})
            elif msg.role == "user":
                if msg.content:
                    openai_messages.append({"role": "user", "content": msg.content})
                elif msg.tool_result:
                    # 工具结果
                    openai_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": msg.tool_result.call_id,
                            "content": msg.tool_result.result or msg.tool_result.error or "",
                        }
                    )
            elif msg.role == "assistant":
                # 处理 assistant 消息，可能包含工具调用
                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                # 如果有工具调用信息，需要添加到消息中
                # 优先使用 tool_calls（多个工具调用），如果没有则使用 tool_call（单个工具调用）
                if msg.tool_calls:
                    import json
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                elif msg.tool_call:
                    import json
                    assistant_msg["tool_calls"] = [
                        {
                            "id": msg.tool_call.call_id,
                            "type": "function",
                            "function": {
                                "name": msg.tool_call.name,
                                "arguments": json.dumps(msg.tool_call.arguments),
                            },
                        }
                    ]
                openai_messages.append(assistant_msg)

        # 准备工具定义
        tool_definitions = None
        if tools:
            tool_definitions = [tool.json_definition() for tool in tools]

        # 调用 API（使用同步客户端，在异步环境中运行）
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    tools=tool_definitions,
                ),
            )
        except Exception as e:
            # 捕获并格式化错误信息
            error_msg = str(e)
            if hasattr(e, 'status_code'):
                error_msg = f"Error code: {e.status_code} - {error_msg}"
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    error_msg = f"Error code: {e.status_code} - {error_data}"
                except:
                    error_msg = f"Error code: {e.status_code} - {error_msg}"
            raise Exception(error_msg) from e

        # 解析响应
        choice = response.choices[0]
        content = choice.message.content or ""

        # 解析工具调用
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = []
            for tc in choice.message.tool_calls:
                import json

                try:
                    arguments = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    arguments = {}

                tool_calls.append(
                    ToolCall(
                        name=tc.function.name,
                        call_id=tc.id,
                        arguments=arguments,
                        id=tc.id,
                    )
                )

        # 解析使用量
        usage = None
        if response.usage:
            usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
            )

        return LLMResponse(
            content=content,
            usage=usage,
            model=self.model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

