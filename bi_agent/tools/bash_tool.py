"""Bash 命令执行工具"""

import asyncio
import os

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter


class _BashSession:
    """Bash shell 会话"""

    _started: bool
    _timed_out: bool

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # 秒
    _timeout: float = 120.0  # 秒
    _sentinel: str = ",,,,bash-command-exit-__ERROR_CODE__-banner,,,,"

    def __init__(self) -> None:
        self._started = False
        self._timed_out = False
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._started:
            return

        if os.name != "nt":  # Unix-like systems
            self._process = await asyncio.create_subprocess_shell(
                self.command,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid,
            )
        else:
            self._process = await asyncio.create_subprocess_shell(
                "cmd.exe /v:on",
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        self._started = True

    async def stop(self) -> None:
        """终止 bash shell"""
        if not self._started:
            raise ToolError("会话尚未启动")
        if self._process is None:
            return
        if self._process.returncode is not None:
            return
        try:
            self._process.terminate()
            stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            try:
                stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=2.0)
            except asyncio.TimeoutError:
                return None
        except Exception:
            return None

    async def run(self, command: str) -> ToolExecResult:
        """在 bash shell 中执行命令"""
        if not self._started or self._process is None:
            raise ToolError("会话尚未启动")
        if self._process.returncode is not None:
            return ToolExecResult(
                error=f"bash 已退出，返回码 {self._process.returncode}。工具必须重启。",
                error_code=-1,
            )
        if self._timed_out:
            raise ToolError(f"超时：bash 在 {self._timeout} 秒内未返回，必须重启")

        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        error_code = 0

        sentinel_before, pivot, sentinel_after = self._sentinel.partition("__ERROR_CODE__")
        assert pivot == "__ERROR_CODE__"

        errcode_retriever = "!errorlevel!" if os.name == "nt" else "$?"
        command_sep = "&" if os.name == "nt" else ";"

        self._process.stdin.write(
            b"(\n"
            + command.encode()
            + f"\n){command_sep} echo {self._sentinel.replace('__ERROR_CODE__', errcode_retriever)}\n".encode()
        )
        await self._process.stdin.drain()

        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    output: str = self._process.stdout._buffer.decode()  # type: ignore
                    if sentinel_before in output:
                        output, pivot, exit_banner = output.rpartition(sentinel_before)
                        assert pivot

                        error_code_str, pivot, _ = exit_banner.partition(sentinel_after)
                        if not pivot or not error_code_str.isdecimal():
                            continue

                        error_code = int(error_code_str)
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(f"超时：bash 在 {self._timeout} 秒内未返回，必须重启")

        if output.endswith("\n"):
            output = output[:-1]

        error: str = self._process.stderr._buffer.decode()  # type: ignore
        if error.endswith("\n"):
            error = error[:-1]

        self._process.stdout._buffer.clear()  # type: ignore
        self._process.stderr._buffer.clear()  # type: ignore

        return ToolExecResult(output=output, error=error, error_code=error_code)


class BashTool(Tool):
    """允许 Agent 运行 bash 命令的工具"""

    def __init__(self, model_provider: str | None = None, data_dir: str | None = None):
        super().__init__(model_provider)
        self._session: _BashSession | None = None
        self._data_dir = data_dir

    def set_data_dir(self, data_dir: str):
        """设置数据目录，用于在执行命令时自动切换到该目录"""
        self._data_dir = data_dir

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "bash"

    @override
    def get_description(self) -> str:
        desc = """在 bash shell 中运行命令
* 调用此工具时，"command" 参数的内容不需要进行 XML 转义
* 你可以通过 apt 和 pip 访问常见的 Linux 和 Python 包
* 状态在命令调用和与用户的讨论之间保持持久
* 要检查文件的特定行范围，例如第 10-25 行，请尝试 'sed -n 10,25p /path/to/the/file'
* 请避免可能产生大量输出的命令
* 请在后台运行长时间运行的命令，例如 'sleep 10 &' 或在后台启动服务器

**Python 代码编写注意事项**：
* 当使用 `python3 -c` 执行 Python 代码时，避免在 f-string 中直接使用字典访问（如 `f"值: {df['col']}"`），这会导致语法错误
* **正确做法**：先提取变量，再在 f-string 中使用，例如：
  - ❌ **错误**：`print(f'统计: {df['col'].describe()}')` 
  - ✅ **正确**：`stats = df['col'].describe(); print(f'统计: {stats}')` 或 `print('统计:'); print(df['col'].describe())`
* 对于 matplotlib 图表，建议使用以下代码设置中文字体（自动处理字体问题）：
  ```python
  import matplotlib.pyplot as plt
  import warnings
  warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
  plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
  plt.rcParams['axes.unicode_minus'] = False
  ```
"""
        if self._data_dir:
            desc += f"\n**重要约束**：所有文件操作必须在数据目录及其子目录下进行\n"
            desc += f"* 数据目录：{self._data_dir}\n"
            desc += f"* **必须使用绝对路径**，且路径必须在数据目录下\n"
            desc += f"* **正确示例**：\n"
            desc += f"  - `ls {self._data_dir}`\n"
            desc += f"  - `cat {self._data_dir}/README.md`\n"
            desc += f"  - `find {self._data_dir} -name '*.csv'`\n"
            desc += f"  - `ls {self._data_dir}/example`\n"
            desc += f"* **禁止**：不要执行 `ls`、`ls -la`、`pwd` 等不带路径的命令（会在当前目录执行）\n"
            desc += f"* **禁止**：不要使用数据目录外的路径\n"
        return desc

    @override
    def get_parameters(self) -> list[ToolParameter]:
        restart_required = self.model_provider == "openai"

        return [
            ToolParameter(
                name="command",
                type="string",
                description="要运行的 bash 命令",
                required=True,
            ),
            ToolParameter(
                name="restart",
                type="boolean",
                description="设置为 true 以重启 bash 会话",
                required=restart_required,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        if arguments.get("restart"):
            if self._session:
                await self._session.stop()
            self._session = _BashSession()
            await self._session.start()
            return ToolExecResult(output="工具已重启")

        if self._session is None:
            try:
                self._session = _BashSession()
                await self._session.start()
            except Exception as e:
                return ToolExecResult(error=f"启动 bash 会话时出错: {e}", error_code=-1)

        command = str(arguments["command"]) if "command" in arguments else None
        if command is None:
            return ToolExecResult(
                error=f"未为 {self.get_name()} 工具提供命令",
                error_code=-1,
            )
        
        # 如果设置了数据目录，检查命令是否在数据目录及其子目录下执行
        if self._data_dir:
            from pathlib import Path
            data_dir_path = Path(self._data_dir).resolve()
            
            # 检查是否是危险命令（可能访问文件系统的命令）
            dangerous_commands = ["ls", "cat", "find", "grep", "head", "tail", "less", "more", "cd", "pwd", "touch", "mkdir", "rm", "mv", "cp"]
            command_words = command.strip().split()
            
            if command_words and command_words[0] in dangerous_commands:
                # 检查命令中的所有路径参数
                paths_in_command = []
                for word in command_words[1:]:
                    # 跳过选项参数（以 - 开头）
                    if word.startswith("-"):
                        continue
                    # 检查是否是路径（包含 / 或 .）
                    if "/" in word or word.startswith(".") or word.endswith("/"):
                        paths_in_command.append(word)
                
                # 如果没有路径参数，说明是危险命令（如 ls、pwd）
                if not paths_in_command:
                    if command_words[0] in ["ls", "pwd", "cd"]:
                        return ToolExecResult(
                            error=f"错误：命令 '{command}' 没有指定数据目录路径。\n"
                            f"所有文件操作必须在数据目录及其子目录下进行：{self._data_dir}\n"
                            f"请使用绝对路径，例如：`ls {self._data_dir}` 或 `ls {self._data_dir}/example`",
                            error_code=-1,
                        )
                else:
                    # 检查所有路径是否在数据目录下
                    all_paths_valid = True
                    invalid_paths = []
                    
                    for path_str in paths_in_command:
                        # 解析路径
                        try:
                            # 如果是相对路径，先转换为绝对路径
                            if not Path(path_str).is_absolute():
                                # 相对路径需要结合当前工作目录，但我们不知道当前工作目录
                                # 所以要求必须使用绝对路径
                                all_paths_valid = False
                                invalid_paths.append(path_str)
                                continue
                            
                            path_obj = Path(path_str).resolve()
                            
                            # 检查路径是否在数据目录下
                            try:
                                # 使用 commonpath 检查路径是否在数据目录下
                                if not str(path_obj).startswith(str(data_dir_path)):
                                    all_paths_valid = False
                                    invalid_paths.append(path_str)
                            except ValueError:
                                # 路径不在同一驱动器上（Windows）
                                all_paths_valid = False
                                invalid_paths.append(path_str)
                        except Exception:
                            # 路径解析失败，可能是通配符等，跳过检查
                            pass
                    
                    if not all_paths_valid:
                        return ToolExecResult(
                            error=f"错误：命令 '{command}' 中的以下路径不在数据目录下：{', '.join(invalid_paths)}\n"
                            f"所有文件操作必须在数据目录及其子目录下进行：{self._data_dir}\n"
                            f"请使用数据目录下的绝对路径，例如：\n"
                            f"  - `ls {self._data_dir}`\n"
                            f"  - `cat {self._data_dir}/README.md`\n"
                            f"  - `find {self._data_dir} -name '*.csv'`\n"
                            f"  - `ls {self._data_dir}/example`",
                            error_code=-1,
                        )
        
        try:
            return await self._session.run(command)
        except Exception as e:
            return ToolExecResult(error=f"运行 bash 命令时出错: {e}", error_code=-1)

    @override
    async def close(self):
        """正确关闭进程"""
        if self._session:
            ret = await self._session.stop()
            self._session = None
            return ret

