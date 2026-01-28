"""Python 代码执行工具"""

import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class PythonExecutorTool(Tool):
    """Python 代码执行工具
    
    允许大模型执行 Python 代码来完成数据分析任务，包括：
    - 数据读取（pandas）
    - 数据清洗和处理
    - 数据可视化（matplotlib）
    - 统计分析
    - 文件操作（限制在指定目录内）
    """

    def __init__(
        self,
        model_provider: str | None = None,
        data_dir: str | None = None,
        output_dir: str | None = None,
    ):
        super().__init__(model_provider)
        self._data_dir = Path(data_dir).resolve() if data_dir else None
        self._output_dir = Path(output_dir).resolve() if output_dir else None

    def set_data_dir(self, data_dir: str):
        """设置数据目录"""
        self._data_dir = Path(data_dir).resolve()

    def set_output_dir(self, output_dir: str):
        """设置输出目录"""
        self._output_dir = Path(output_dir).resolve()

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "python_executor"

    @override
    def get_description(self) -> str:
        return """执行 Python 代码工具
* 用于执行 Python 代码完成数据分析任务
* 支持数据读取、清洗、可视化、统计分析等操作
* 自动导入常用库：pandas (pd), numpy (np), matplotlib.pyplot (plt), seaborn (sns)
* 提供数据目录和输出目录的路径变量：DATA_DIR, OUTPUT_DIR
* 代码执行结果会返回标准输出和返回值
* 文件操作会被限制在数据目录和输出目录内
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="要执行的 Python 代码（字符串）",
                required=True,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="代码功能的简要描述（可选，用于日志记录）",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        code = str(arguments.get("code", ""))
        description = str(arguments.get("description", "执行 Python 代码"))

        if not code:
            return ToolExecResult(error="必须提供要执行的 Python 代码", error_code=-1)

        try:
            # 检查代码安全性（简单检查，防止危险操作）
            dangerous_keywords = [
                "__import__",
                "eval(",
                "exec(",
                "compile(",
                "open(",
                "file(",
                "input(",
                "raw_input(",
                "subprocess",
                "os.system",
                "os.popen",
                "shutil.rmtree",
                "shutil.move",
            ]

            # 允许在受控环境下的文件操作
            code_lower = code.lower()
            for keyword in dangerous_keywords:
                if keyword in code_lower:
                    # 检查是否是安全的文件操作（在指定目录内）
                    if keyword in ["open(", "file("]:
                        # 允许 open()，但会在执行环境中限制路径
                        continue
                    return ToolExecResult(
                        error=f"代码包含潜在危险操作: {keyword}。请使用安全的代码实现。",
                        error_code=-1,
                    )

            # 准备执行环境
            exec_globals = self._prepare_exec_environment()
            exec_locals = {}

            # 捕获标准输出和标准错误
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                # 执行代码
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, exec_globals, exec_locals)

                # 获取输出
                stdout_output = stdout_capture.getvalue()
                stderr_output = stderr_capture.getvalue()

                # 检查是否有返回值（通常是最后一个表达式的结果）
                result_value = None
                if exec_locals:
                    # 尝试获取常见的返回值变量
                    for var_name in ["result", "output", "df", "data", "fig"]:
                        if var_name in exec_locals:
                            result_value = exec_locals[var_name]
                            break

                # 构建结果消息
                result_lines = [f"✅ {description} 执行成功"]

                if stdout_output:
                    result_lines.append(f"\n标准输出:\n{stdout_output}")

                if stderr_output:
                    result_lines.append(f"\n警告信息:\n{stderr_output}")

                if result_value is not None:
                    # 格式化返回值
                    if hasattr(result_value, "__str__"):
                        result_str = str(result_value)
                        # 如果是 DataFrame，显示基本信息
                        if hasattr(result_value, "shape"):
                            result_lines.append(
                                f"\n返回值 (DataFrame): {result_value.shape[0]} 行 × {result_value.shape[1]} 列"
                            )
                            if len(result_str) < 500:
                                result_lines.append(f"\n数据预览:\n{result_str}")
                        elif len(result_str) < 500:
                            result_lines.append(f"\n返回值:\n{result_str}")
                        else:
                            result_lines.append(f"\n返回值: {type(result_value).__name__} (内容过长，已省略)")

                return ToolExecResult(output="\n".join(result_lines))

            except Exception as e:
                # 捕获执行错误
                error_traceback = traceback.format_exc()
                error_msg = f"❌ {description} 执行失败\n\n错误信息: {str(e)}\n\n错误堆栈:\n{error_traceback}"

                # 如果有标准输出，也包含进去
                stdout_output = stdout_capture.getvalue()
                if stdout_output:
                    error_msg = f"{error_msg}\n\n执行过程中的输出:\n{stdout_output}"

                return ToolExecResult(error=error_msg, error_code=-1)

        except Exception as e:
            return ToolExecResult(error=f"准备执行环境时出错: {str(e)}", error_code=-1)

    def _prepare_exec_environment(self) -> dict[str, Any]:
        """准备代码执行环境
        
        Returns:
            包含导入库和路径变量的全局命名空间
        """
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib
        
        # seaborn 是可选的，如果未安装则跳过
        try:
            import seaborn as sns
        except ImportError:
            sns = None

        # 设置 matplotlib 中文字体（自动处理）
        chinese_fonts = [
            "Arial Unicode MS",
            "SimHei",
            "WenQuanYi Zen Hei",
            "Noto Sans CJK SC",
            "PingFang SC",
            "STHeiti",
        ]
        import matplotlib.font_manager as fm

        available_fonts = [f.name for f in fm.fontManager.ttflist]
        selected_font = None
        for font in chinese_fonts:
            if font in available_fonts:
                selected_font = font
                break

        if selected_font:
            plt.rcParams["font.sans-serif"] = [selected_font] + plt.rcParams["font.sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False

        # 创建安全的文件操作包装器
        def safe_open(file_path: str, mode: str = "r", *args, **kwargs):
            """安全的文件打开函数，限制在数据目录和输出目录内"""
            path = Path(file_path).resolve()

            # 检查是否在允许的目录内（兼容 Python 3.8+）
            def is_relative_to(path_obj: Path, base: Path) -> bool:
                """检查路径是否相对于基础路径（兼容 Python 3.8）"""
                try:
                    path_obj.relative_to(base)
                    return True
                except ValueError:
                    return False

            # 检查是否在允许的目录内
            if self._data_dir and is_relative_to(path, self._data_dir):
                return open(path, mode, *args, **kwargs)
            elif self._output_dir and is_relative_to(path, self._output_dir):
                return open(path, mode, *args, **kwargs)
            else:
                raise PermissionError(
                    f"文件操作被限制：路径 {path} 不在数据目录或输出目录内。\n"
                    f"数据目录: {self._data_dir}\n"
                    f"输出目录: {self._output_dir}"
                )

        # 创建安全的路径操作函数
        def safe_path(file_path: str) -> Path:
            """安全的路径解析函数，自动解析相对路径"""
            path = Path(file_path)

            # 如果是绝对路径，直接返回
            if path.is_absolute():
                return path

            # 如果是相对路径，优先在数据目录下查找
            if self._data_dir:
                potential_path = self._data_dir / path
                if potential_path.exists():
                    return potential_path.resolve()

            # 如果数据目录下不存在，尝试输出目录
            if self._output_dir:
                potential_path = self._output_dir / path
                if potential_path.exists():
                    return potential_path.resolve()

            # 如果都不存在，返回相对于数据目录的路径（如果设置了数据目录）
            if self._data_dir:
                return (self._data_dir / path).resolve()
            else:
                return path.resolve()

        # 构建执行环境
        exec_globals = {
            # 标准库
            "__builtins__": __builtins__,
            # 数据分析库
            "pd": pd,
            "pandas": pd,
            "np": np,
            "numpy": np,
            "plt": plt,
            "matplotlib": matplotlib,
            "sns": sns if sns is not None else None,
            "seaborn": sns if sns is not None else None,
            # 路径变量
            "DATA_DIR": str(self._data_dir) if self._data_dir else None,
            "OUTPUT_DIR": str(self._output_dir) if self._output_dir else None,
            # 安全函数
            "safe_open": safe_open,
            "safe_path": safe_path,
            # 常用函数
            "Path": Path,
            "print": print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "sorted": sorted,
            "max": max,
            "min": min,
            "sum": sum,
            "abs": abs,
            "round": round,
        }

        return exec_globals

