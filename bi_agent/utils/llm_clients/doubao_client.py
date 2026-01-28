"""Doubao (豆包) LLM 客户端实现"""

from bi_agent.utils.typing_compat import override

try:
    import openai
except ImportError:
    openai = None

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse, LLMUsage
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.tools.base import Tool, ToolCall


class DoubaoClient(LLMClient):
    """Doubao (豆包) LLM 客户端 - 基于 OpenAI 兼容 API"""

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-seed-1-6-251015",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    ):
        """初始化 Doubao 客户端

        Args:
            api_key: Doubao API Key (ARK_API_KEY)
            model: 模型名称（推理接入点 ID）
            base_url: API Base URL（默认：北京区域）
        """
        if openai is None:
            raise ImportError("请安装 openai 包: pip install openai")

        if not api_key:
            raise ValueError(
                "Doubao API Key 不能为空。\n"
                "请设置 ARK_API_KEY 环境变量，或在 .env 文件中配置：ARK_API_KEY=your_doubao_api_key"
            )

        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @override
    async def chat(self, messages: list[LLMMessage], tools: list[Tool] | None = None) -> LLMResponse:
        """发送聊天消息"""
        import asyncio
        import json

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
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                elif msg.tool_call:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": msg.tool_call.call_id,
                            "type": "function",
                            "function": {
                                "name": msg.tool_call.name,
                                "arguments": json.dumps(msg.tool_call.arguments) if isinstance(msg.tool_call.arguments, dict) else str(msg.tool_call.arguments),
                            },
                        }
                    ]
                openai_messages.append(assistant_msg)

        # 准备工具定义
        # Doubao API 需要 tools 格式为 [{"type": "function", "function": {...}}]
        tool_definitions = None
        if tools:
            tool_definitions = []
            for tool in tools:
                tool_json = tool.json_definition()
                # Doubao 需要包装在 function 字段中
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool_json["name"],
                        "description": tool_json["description"],
                        "parameters": tool_json["parameters"],
                    },
                }
                tool_definitions.append(tool_def)

        # 调用 API（使用同步客户端，在异步环境中运行）
        loop = asyncio.get_event_loop()
        try:
            # 构建 API 调用参数
            api_params = {
                "model": self.model,
                "messages": openai_messages,
                "reasoning_effort": "minimal",  # 关闭深度思考，设置为 minimal
            }
            # 只有当有工具时才添加 tools 参数
            if tool_definitions:
                api_params["tools"] = tool_definitions
            
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(**api_params),
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

        # 注意：已通过 reasoning_effort="minimal" 关闭深度思考，不再处理 reasoning_content
        # 如果需要启用思考过程，可以将 reasoning_effort 改为 "medium" 或 "high"，并取消下面的注释
        # if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
        #     # 将推理内容添加到响应内容前
        #     content = f"[推理过程]\n{choice.message.reasoning_content}\n\n[最终回答]\n{content}"

        # 解析工具调用
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = []
            for tc in choice.message.tool_calls:
                try:
                    # 处理 arguments，可能是字符串或字典
                    if isinstance(tc.function.arguments, str):
                        arguments = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    else:
                        arguments = tc.function.arguments or {}
                except (json.JSONDecodeError, AttributeError):
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

