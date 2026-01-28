"""数据读取工具"""

import csv
import json
from pathlib import Path

from bi_agent.utils.typing_compat import override

import pandas as pd

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter
from bi_agent.utils.exceptions import DataFileError


class DataReaderTool(Tool):
    """读取数据文件的工具，支持 Excel 和 CSV 格式"""

    def __init__(self, model_provider: str | None = None, data_dir: str | None = None):
        super().__init__(model_provider)
        self._data_cache: dict[str, pd.DataFrame] = {}
        self._data_dir: Path | None = Path(data_dir).resolve() if data_dir else None

    def set_data_dir(self, data_dir: str):
        """设置数据目录，用于解析相对路径"""
        self._data_dir = Path(data_dir).resolve()

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "data_reader"

    @override
    def get_description(self) -> str:
        return """读取数据文件（Excel 或 CSV 格式）
* 支持 .xlsx、.xls、.csv 文件
* 自动检测文件编码（UTF-8、GBK 等）
* 读取的数据会被缓存，后续可直接使用
* 返回数据的基本信息（行数、列数、列名、数据类型、前几行数据等）
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="数据文件的绝对路径，或相对于数据目录的相对路径（如果设置了数据目录）",
                required=True,
            ),
            ToolParameter(
                name="sheet_name",
                type="string",
                description="Excel 文件的 sheet 名称（仅对 Excel 文件有效，可选，默认为第一个 sheet）",
                required=False,
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="CSV 文件的编码格式（可选，默认自动检测：UTF-8、GBK、GB2312）",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        file_path = str(arguments.get("file_path", ""))
        if not file_path:
            return ToolExecResult(error="未提供文件路径", error_code=-1)

        file_path_obj = Path(file_path)
        
        # 如果路径不是绝对路径，且设置了数据目录，则尝试相对于数据目录解析
        if not file_path_obj.is_absolute() and self._data_dir:
            file_path_obj = self._data_dir / file_path
        # 如果路径是绝对路径但不存在，且设置了数据目录，尝试在数据目录下查找
        elif file_path_obj.is_absolute() and not file_path_obj.exists() and self._data_dir:
            # 尝试提取文件名，在数据目录下查找
            file_name = file_path_obj.name
            potential_path = self._data_dir / file_name
            if potential_path.exists():
                file_path_obj = potential_path
        
        if not file_path_obj.exists():
            # 提供更详细的错误信息，包括数据目录信息
            error_msg = f"文件不存在: {file_path}"
            if self._data_dir:
                error_msg += f"\n数据目录: {self._data_dir}"
                # 列出数据目录下的文件，帮助用户找到正确的文件
                try:
                    data_files = list(self._data_dir.glob("**/*.xlsx")) + list(self._data_dir.glob("**/*.xls")) + list(self._data_dir.glob("**/*.csv"))
                    if data_files:
                        error_msg += f"\n数据目录下可用的数据文件："
                        for f in data_files[:10]:  # 最多显示10个文件
                            error_msg += f"\n  - {f}"
                        if len(data_files) > 10:
                            error_msg += f"\n  ... 还有 {len(data_files) - 10} 个文件"
                except Exception:
                    pass
            return ToolExecResult(error=error_msg, error_code=-1)
        
        # 更新 file_path 为解析后的绝对路径
        file_path = str(file_path_obj.resolve())

        # 检查缓存
        cache_key = f"{file_path}_{arguments.get('sheet_name', '')}"
        if cache_key in self._data_cache:
            df = self._data_cache[cache_key]
            return self._format_data_info(df, file_path)

        try:
            # 读取数据
            if file_path_obj.suffix.lower() in [".xlsx", ".xls"]:
                sheet_name = arguments.get("sheet_name")
                if sheet_name:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                else:
                    df = pd.read_excel(file_path)
            elif file_path_obj.suffix.lower() == ".csv":
                encoding = arguments.get("encoding")
                if encoding:
                    df = pd.read_csv(file_path, encoding=encoding)
                else:
                    # 尝试多种编码
                    for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                        try:
                            df = pd.read_csv(file_path, encoding=enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        return ToolExecResult(error=f"无法识别文件编码: {file_path}", error_code=-1)
            else:
                return ToolExecResult(error=f"不支持的文件格式: {file_path_obj.suffix}", error_code=-1)

            # 缓存数据
            self._data_cache[cache_key] = df

            return self._format_data_info(df, file_path)

        except Exception as e:
            return ToolExecResult(error=f"读取文件时出错: {str(e)}", error_code=-1)

    def _format_data_info(self, df: pd.DataFrame, file_path: str) -> ToolExecResult:
        """格式化数据信息"""
        info_lines = [
            f"文件路径: {file_path}",
            f"数据形状: {df.shape[0]} 行 × {df.shape[1]} 列",
            f"\n列名: {', '.join(df.columns.tolist())}",
            f"\n数据类型:",
        ]

        for col, dtype in df.dtypes.items():
            info_lines.append(f"  {col}: {dtype}")

        info_lines.append(f"\n缺失值统计:")
        missing = df.isnull().sum()
        for col, count in missing.items():
            if count > 0:
                info_lines.append(f"  {col}: {count} ({count/len(df)*100:.1f}%)")

        info_lines.append(f"\n前 5 行数据:")
        info_lines.append(df.head().to_string())

        if len(df) > 5:
            info_lines.append(f"\n... (共 {len(df)} 行)")

        return ToolExecResult(output="\n".join(info_lines))

    def get_cached_data(self, file_path: str, sheet_name: str | None = None) -> pd.DataFrame | None:
        """获取缓存的数据"""
        cache_key = f"{file_path}_{sheet_name or ''}"
        return self._data_cache.get(cache_key)

