"""数据分析工具模块"""

from bi_agent.tools.base import Tool, ToolCall, ToolExecutor, ToolResult
from bi_agent.tools.bash_tool import BashTool
from bi_agent.tools.python_executor_tool import PythonExecutorTool
from bi_agent.tools.report_generator_tool import ReportGeneratorTool
from bi_agent.tools.search_knowledge_tool import SearchKnowledgeTool
from bi_agent.tools.task_done_tool import TaskDoneTool
from bi_agent.tools.mcp_tool import MCPTool

__all__ = [
    "Tool",
    "ToolResult",
    "ToolCall",
    "ToolExecutor",
    "BashTool",
    "PythonExecutorTool",
    "ReportGeneratorTool",
    "SearchKnowledgeTool",
    "TaskDoneTool",
    "MCPTool",
]

tools_registry: dict[str, type[Tool]] = {
    "bash": BashTool,
    "python_executor": PythonExecutorTool,
    "report_generator": ReportGeneratorTool,
    "search_knowledge": SearchKnowledgeTool,
    "task_done": TaskDoneTool,
}

