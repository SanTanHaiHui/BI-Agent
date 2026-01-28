"""数据清洗工具"""

from pathlib import Path

from bi_agent.utils.typing_compat import override

import pandas as pd

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter
from bi_agent.tools.data_reader_tool import DataReaderTool


class DataCleanerTool(Tool):
    """数据清洗工具，提供常见的数据清洗操作"""

    def __init__(self, data_reader: DataReaderTool, model_provider: str | None = None):
        super().__init__(model_provider)
        self.data_reader = data_reader

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "data_cleaner"

    @override
    def get_description(self) -> str:
        return """数据清洗工具
* 支持删除重复行
* 支持处理缺失值（删除、填充）
* 支持数据类型转换
* 支持删除异常值
* 清洗后的数据会保存到输出目录
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="原始数据文件的绝对路径",
                required=True,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="清洗后数据保存的绝对路径",
                required=True,
            ),
            ToolParameter(
                name="operations",
                type="string",
                description="清洗操作，JSON 格式字符串，例如：{\"remove_duplicates\": true, \"fill_missing\": \"mean\", \"remove_outliers\": true}",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        file_path = str(arguments.get("file_path", ""))
        output_path = str(arguments.get("output_path", ""))

        if not file_path or not output_path:
            return ToolExecResult(error="必须提供文件路径和输出路径", error_code=-1)

        try:
            # 读取数据
            df = self.data_reader.get_cached_data(file_path)
            if df is None:
                # 如果缓存中没有，尝试读取
                from bi_agent.tools.data_reader_tool import DataReaderTool

                reader = DataReaderTool()
                result = await reader.execute({"file_path": file_path})
                if result.error_code != 0:
                    return result
                df = reader.get_cached_data(file_path)

            if df is None:
                return ToolExecResult(error="无法读取数据文件", error_code=-1)

            original_shape = df.shape

            # 解析清洗操作
            operations = {}
            if arguments.get("operations"):
                import json

                try:
                    operations = json.loads(str(arguments["operations"]))
                except json.JSONDecodeError:
                    return ToolExecResult(error="清洗操作格式错误，应为 JSON 格式", error_code=-1)

            # 执行清洗操作
            operations_log = []

            # 删除重复行
            if operations.get("remove_duplicates", False):
                before = len(df)
                df = df.drop_duplicates()
                after = len(df)
                operations_log.append(f"删除重复行: {before} -> {after} (删除了 {before - after} 行)")

            # 处理缺失值
            fill_method = operations.get("fill_missing")
            if fill_method:
                if fill_method == "drop":
                    before = len(df)
                    df = df.dropna()
                    after = len(df)
                    operations_log.append(f"删除缺失值: {before} -> {after} (删除了 {before - after} 行)")
                elif fill_method == "mean":
                    numeric_cols = df.select_dtypes(include=["number"]).columns
                    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
                    operations_log.append(f"用均值填充数值列的缺失值")
                elif fill_method == "median":
                    numeric_cols = df.select_dtypes(include=["number"]).columns
                    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
                    operations_log.append(f"用中位数填充数值列的缺失值")
                elif fill_method == "mode":
                    for col in df.columns:
                        mode_value = df[col].mode()
                        if len(mode_value) > 0:
                            df[col] = df[col].fillna(mode_value[0])
                    operations_log.append(f"用众数填充缺失值")
                elif fill_method == "forward":
                    df = df.fillna(method="ffill")
                    operations_log.append(f"用前向填充处理缺失值")
                else:
                    df = df.fillna(fill_method)
                    operations_log.append(f"用 '{fill_method}' 填充缺失值")

            # 删除异常值（使用 IQR 方法）
            if operations.get("remove_outliers", False):
                numeric_cols = df.select_dtypes(include=["number"]).columns
                before = len(df)
                for col in numeric_cols:
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
                after = len(df)
                operations_log.append(f"删除异常值: {before} -> {after} (删除了 {before - after} 行)")

            # 保存清洗后的数据
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            if output_path_obj.suffix.lower() in [".xlsx", ".xls"]:
                df.to_excel(output_path, index=False)
            elif output_path_obj.suffix.lower() == ".csv":
                df.to_csv(output_path, index=False, encoding="utf-8-sig")
            else:
                return ToolExecResult(error=f"不支持的输出格式: {output_path_obj.suffix}", error_code=-1)

            result_lines = [
                f"数据清洗完成！",
                f"原始数据: {original_shape[0]} 行 × {original_shape[1]} 列",
                f"清洗后: {df.shape[0]} 行 × {df.shape[1]} 列",
                f"\n执行的清洗操作:",
            ]
            result_lines.extend([f"  - {log}" for log in operations_log])
            result_lines.append(f"\n清洗后的数据已保存到: {output_path}")

            return ToolExecResult(output="\n".join(result_lines))

        except Exception as e:
            return ToolExecResult(error=f"数据清洗时出错: {str(e)}", error_code=-1)

