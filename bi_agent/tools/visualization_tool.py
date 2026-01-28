"""数据可视化工具"""

from pathlib import Path

from bi_agent.utils.typing_compat import override

import matplotlib.pyplot as plt
import pandas as pd

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter
from bi_agent.tools.data_reader_tool import DataReaderTool

# 设置中文字体（自动检测可用字体）
import matplotlib.font_manager as fm
import warnings

# 尝试设置中文字体，按优先级顺序
chinese_fonts = ["Arial Unicode MS", "SimHei", "WenQuanYi Zen Hei", "Noto Sans CJK SC", "PingFang SC", "STHeiti"]
available_fonts = [f.name for f in fm.fontManager.ttflist]

# 找到第一个可用的中文字体
selected_font = None
for font in chinese_fonts:
    if font in available_fonts:
        selected_font = font
        break

if selected_font:
    plt.rcParams["font.sans-serif"] = [selected_font] + plt.rcParams["font.sans-serif"]
else:
    # 如果没有找到中文字体，使用默认字体，但抑制警告
    warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

plt.rcParams["axes.unicode_minus"] = False


class VisualizationTool(Tool):
    """数据可视化工具，生成各种图表"""

    def __init__(self, data_reader: DataReaderTool, model_provider: str | None = None):
        super().__init__(model_provider)
        self.data_reader = data_reader

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "visualization"

    @override
    def get_description(self) -> str:
        return """数据可视化工具
* 支持折线图、柱状图、散点图、饼图、箱线图等
* 支持多子图布局
* 图表会保存为 PNG 格式
* 自动设置中文标签和标题
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="数据文件的绝对路径",
                required=True,
            ),
            ToolParameter(
                name="chart_type",
                type="string",
                description="图表类型：line（折线图）、bar（柱状图）、scatter（散点图）、pie（饼图）、box（箱线图）、hist（直方图）",
                required=True,
                enum=["line", "bar", "scatter", "pie", "box", "hist"],
            ),
            ToolParameter(
                name="x_column",
                type="string",
                description="X 轴列名",
                required=False,
            ),
            ToolParameter(
                name="y_column",
                type="string",
                description="Y 轴列名（对于某些图表类型可能需要）",
                required=False,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="图表保存的绝对路径",
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="图表标题",
                required=False,
            ),
            ToolParameter(
                name="x_label",
                type="string",
                description="X 轴标签",
                required=False,
            ),
            ToolParameter(
                name="y_label",
                type="string",
                description="Y 轴标签",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        file_path = str(arguments.get("file_path", ""))
        chart_type = str(arguments.get("chart_type", ""))
        output_path = str(arguments.get("output_path", ""))

        if not file_path or not chart_type or not output_path:
            return ToolExecResult(error="必须提供文件路径、图表类型和输出路径", error_code=-1)

        try:
            # 读取数据
            df = self.data_reader.get_cached_data(file_path)
            if df is None:
                result = await self.data_reader.execute({"file_path": file_path})
                if result.error_code != 0:
                    return result
                df = self.data_reader.get_cached_data(file_path)

            if df is None:
                return ToolExecResult(error="无法读取数据文件", error_code=-1)

            # 创建图表
            fig, ax = plt.subplots(figsize=(10, 6))

            x_column = arguments.get("x_column")
            y_column = arguments.get("y_column")

            if chart_type == "line":
                if not x_column or not y_column:
                    return ToolExecResult(error="折线图需要 x_column 和 y_column", error_code=-1)
                ax.plot(df[x_column], df[y_column], marker="o")
            elif chart_type == "bar":
                if not x_column or not y_column:
                    return ToolExecResult(error="柱状图需要 x_column 和 y_column", error_code=-1)
                ax.bar(df[x_column], df[y_column])
            elif chart_type == "scatter":
                if not x_column or not y_column:
                    return ToolExecResult(error="散点图需要 x_column 和 y_column", error_code=-1)
                ax.scatter(df[x_column], df[y_column])
            elif chart_type == "pie":
                if not y_column:
                    return ToolExecResult(error="饼图需要 y_column", error_code=-1)
                if x_column:
                    ax.pie(df[y_column], labels=df[x_column], autopct="%1.1f%%")
                else:
                    ax.pie(df[y_column], autopct="%1.1f%%")
            elif chart_type == "box":
                if not y_column:
                    return ToolExecResult(error="箱线图需要 y_column", error_code=-1)
                ax.boxplot(df[y_column])
            elif chart_type == "hist":
                if not y_column:
                    return ToolExecResult(error="直方图需要 y_column", error_code=-1)
                ax.hist(df[y_column], bins=30)

            # 设置标签和标题
            title = arguments.get("title")
            if title:
                ax.set_title(title, fontsize=14, fontweight="bold")

            x_label = arguments.get("x_label") or x_column
            if x_label:
                ax.set_xlabel(x_label)

            y_label = arguments.get("y_label") or y_column
            if y_label:
                ax.set_ylabel(y_label)

            plt.tight_layout()

            # 保存图表
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            return ToolExecResult(
                output=f"图表已成功生成并保存到: {output_path}\n图表类型: {chart_type}\n数据文件: {file_path}"
            )

        except Exception as e:
            return ToolExecResult(error=f"生成图表时出错: {str(e)}", error_code=-1)

