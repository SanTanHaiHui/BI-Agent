"""MCP 工具包装器"""

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class MCPTool(Tool):
    """MCP 工具包装器"""

    def __init__(self, client, tool, model_provider: str | None = None):
        super().__init__(model_provider)
        self.client = client
        self.tool = tool

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return self.tool.name

    @override
    def get_description(self) -> str:
        return self.tool.description

    @override
    def get_parameters(self) -> list[ToolParameter]:
        def properties_to_parameter():
            parameters = []
            inputSchema = self.tool.inputSchema
            required = inputSchema.get("required", [])
            properties = inputSchema.get("properties", {})
            for name, prop in properties.items():
                tool_para = ToolParameter(
                    name=name,
                    type=prop["type"],
                    items=prop.get("items", None),
                    description=prop["description"],
                    required=name in required,
                )
                parameters.append(tool_para)
            return parameters

        return properties_to_parameter()

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        try:
            import mcp

            output = await self.client.call_tool(self.get_name(), arguments)
            if output.isError:
                return ToolExecResult(output=None, error=output.content[0].text)
            else:
                return ToolExecResult(output=output.content[0].text)

        except Exception as e:
            return ToolExecResult(error=f"运行 MCP 工具时出错: {e}", error_code=-1)

