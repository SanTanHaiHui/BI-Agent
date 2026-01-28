"""报告生成工具"""

import re
import logging
from pathlib import Path

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter

logger = logging.getLogger(__name__)


class ReportGeneratorTool(Tool):
    """生成数据分析报告的工具"""

    def __init__(self, model_provider: str | None = None):
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "report_generator"

    @override
    def get_description(self) -> str:
        return """生成数据分析报告
* 支持 Markdown 格式
* 自动整合分析结果、图表路径、关键发现等
* 报告会保存到输出目录
* **重要约束**：
  - 报告中只能包含图片文件（.png, .jpg, .jpeg, .gif, .bmp, .webp 等图片格式）
  - 不要包含任何非图片文件的链接或引用（如 .csv, .xlsx, .xls, .txt, .json, .pdf 等）
  - 如果需要展示数据，请直接在报告中以文本、表格或图表的形式展示，不要引用文件
  - 用户侧无法显示除图片之外的文件，所有数据和分析结果都应该直接展示在报告中
  - **图片位置**：图片应该直接放在相应的章节标题下，例如"## 4. 可视化分析"标题后立即插入图片，不要将图片放在报告末尾
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="output_path",
                type="string",
                description="报告保存的绝对路径",
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="报告标题",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="报告内容（Markdown 格式）",
                required=True,
            ),
            ToolParameter(
                name="chart_paths",
                type="array",
                description="图表文件路径列表（可选）",
                required=False,
                items={"type": "string"},
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        output_path = str(arguments.get("output_path", ""))
        title = str(arguments.get("title", ""))
        content = str(arguments.get("content", ""))

        if not output_path or not title or not content:
            return ToolExecResult(error="必须提供输出路径、标题和内容", error_code=-1)

        try:
            # 过滤内容中的非图片文件链接
            # 支持的图片格式
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}
            
            # 检测并移除非图片文件的链接
            # 格式: [链接文本](文件路径)
            file_link_pattern = r"\[([^\]]+)\]\(([^)]+\.(?:csv|xlsx|xls|txt|json|pdf|doc|docx|zip|rar))\)"
            
            def replace_file_link(match):
                link_text = match.group(1)
                file_path = match.group(2)
                file_name = Path(file_path).name
                logger.warning(f"检测到非图片文件链接，已移除: {file_name} (链接文本: {link_text})")
                # 如果是相对路径（不是 http/https），只显示文件名作为纯文本
                if not file_path.startswith(('http://', 'https://')):
                    if link_text == file_path or link_text == file_name:
                        return file_name
                    return f"{link_text}: {file_name}"
                # 如果是 HTTP/HTTPS 链接，保留原样（可能是外部资源）
                return match.group(0)
            
            # 移除非图片文件链接
            filtered_content = re.sub(file_link_pattern, replace_file_link, content, flags=re.IGNORECASE)
            
            # 检查内容中是否还有非图片文件的直接引用（不带链接格式）
            # 例如: "详细数据请查看 data.csv" 这种文本引用
            non_image_file_pattern = r'\b[\w\-_]+\.(?:csv|xlsx|xls|txt|json|pdf|doc|docx|zip|rar)\b'
            non_image_files = re.findall(non_image_file_pattern, filtered_content, re.IGNORECASE)
            if non_image_files:
                logger.warning(f"检测到内容中提及的非图片文件: {non_image_files}")
                # 可以选择移除或保留（这里保留，因为可能只是文本描述）
            
            # 构建报告内容
            report_lines = [
                f"# {title}",
                "",
                "---",
                "",
                filtered_content,
                "",
            ]

            # 不再自动添加可视化分析部分，完全由LLM在content中控制报告结构
            # chart_paths 参数保留用于工具描述，但不在代码中自动处理
            chart_paths = arguments.get("chart_paths")
            if chart_paths and isinstance(chart_paths, list):
                logger.info(f"收到 {len(chart_paths)} 个图表路径，但不再自动添加，LLM应在content中自行处理图表引用")

            # 保存报告
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path_obj, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))

            return ToolExecResult(output=f"报告已成功生成并保存到: {output_path}")

        except Exception as e:
            return ToolExecResult(error=f"生成报告时出错: {str(e)}", error_code=-1)

