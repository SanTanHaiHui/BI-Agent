"""任务完成工具"""

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class TaskDoneTool(Tool):
    """任务完成标记工具
    
    当 Agent 判断任务已完成时，应调用此工具来标记任务完成。
    调用此工具后，Agent 将停止执行并返回最终结果。
    """

    def __init__(self, model_provider: str | None = None):
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "task_done"

    @override
    def get_description(self) -> str:
        return """标记任务完成
* 当你确定已经完成用户的所有要求时，调用此工具
* 调用此工具后，Agent 将停止执行并返回最终结果
* 请在 summary 参数中提供任务完成的总结，包括：
  - 任务执行的主要步骤
  - 关键发现或结果
  - 输出文件的位置（如果有）
* 只有在真正完成任务时才调用此工具，不要过早调用
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="summary",
                type="string",
                description="任务完成总结，包括执行步骤、关键发现、输出文件位置等",
                required=True,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        """执行任务完成标记
        
        Args:
            arguments: 工具参数，包含 summary
            
        Returns:
            工具执行结果
        """
        summary = str(arguments.get("summary", ""))
        
        if not summary:
            return ToolExecResult(
                error="必须提供任务完成总结（summary 参数）",
                error_code=-1
            )
        
        # 任务完成工具只是标记，不需要实际执行操作
        # 返回成功结果，BaseAgent 会检测到此工具调用并标记任务完成
        return ToolExecResult(
            output=f"任务完成标记已设置。总结：{summary}"
        )

