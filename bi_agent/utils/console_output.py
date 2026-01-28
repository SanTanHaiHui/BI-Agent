"""控制台输出工具"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from bi_agent.tools.base import ToolCall, ToolResult


class ConsoleOutput:
    """控制台输出管理器"""

    def __init__(self, verbose: bool = True):
        """初始化控制台输出

        Args:
            verbose: 是否显示详细信息
        """
        self.console = Console()
        self.verbose = verbose

    def print_step_start(self, step_number: int, max_steps: int):
        """打印步骤开始"""
        self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        self.console.print(f"[bold cyan]步骤 {step_number}/{max_steps}[/bold cyan]")
        self.console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

    def print_llm_input(self, messages: list[LLMMessage], step_number: int):
        """打印 LLM 输入"""
        if not self.verbose:
            return

        self.console.print("[bold yellow]📤 LLM 输入:[/bold yellow]")
        
        for i, msg in enumerate(messages, 1):
            role_name = {
                "system": "系统",
                "user": "用户",
                "assistant": "助手",
                "tool": "工具",
            }.get(msg.role, msg.role)

            if msg.content:
                # 显示消息内容（截断过长的内容，显示开头和结尾）
                content = msg.content
                if len(content) > 1000:
                    head = content[:400]
                    tail = content[-400:]
                    content = f"{head}\n... (中间省略 {len(content) - 800} 个字符，完整内容请查看轨迹文件) ...\n{tail}"
                
                self.console.print(f"\n[dim]消息 {i} ({role_name}):[/dim]")
                # 使用 Markdown 渲染，如果是代码或结构化内容
                if "```" in content or content.startswith("#"):
                    try:
                        self.console.print(Markdown(content))
                    except:
                        self.console.print(Panel(content, border_style="yellow"))
                else:
                    self.console.print(Panel(content, border_style="yellow", title=role_name))
            
            if msg.tool_result:
                self.console.print(f"\n[dim]工具结果:[/dim]")
                result = msg.tool_result
                status = "✅" if result.success else "❌"
                self.console.print(f"{status} [bold]{result.name}[/bold]")
                if result.result:
                    result_text = result.result
                    if len(result_text) > 500:
                        head = result_text[:200]
                        tail = result_text[-200:]
                        result_text = f"{head}\n... (中间省略 {len(result_text) - 400} 个字符) ...\n{tail}"
                    self.console.print(Panel(result_text, border_style="green" if result.success else "red"))
                if result.error:
                    self.console.print(f"[red]错误: {result.error}[/red]")

    def print_llm_output(self, response: LLMResponse, step_number: int):
        """打印 LLM 输出"""
        self.console.print("\n[bold green]📥 LLM 输出:[/bold green]")
        
        if response.content:
            content = response.content
            if len(content) > 2000:
                head = content[:800]
                tail = content[-800:]
                content = f"{head}\n... (中间省略 {len(content) - 1600} 个字符，完整内容请查看轨迹文件) ...\n{tail}"
            
            # 尝试使用 Markdown 渲染
            if "```" in content or content.startswith("#"):
                try:
                    self.console.print(Markdown(content))
                except:
                    self.console.print(Panel(content, border_style="green"))
            else:
                self.console.print(Panel(content, border_style="green", title="助手回复"))

        if response.tool_calls:
            self.console.print(f"\n[bold blue]🔧 工具调用 ({len(response.tool_calls)} 个):[/bold blue]")
            for i, tool_call in enumerate(response.tool_calls, 1):
                self.console.print(f"\n[cyan]工具 {i}: {tool_call.name}[/cyan]")
                if tool_call.arguments:
                    # 格式化参数
                    import json
                    try:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False, indent=2)
                        if len(args_str) > 500:
                            head = args_str[:200]
                            tail = args_str[-200:]
                            args_str = f"{head}\n... (中间省略 {len(args_str) - 400} 个字符) ...\n{tail}"
                        self.console.print(Syntax(args_str, "json", theme="monokai", line_numbers=False))
                    except:
                        self.console.print(f"[dim]参数: {tool_call.arguments}[/dim]")

        if response.usage:
            self.console.print(
                f"\n[dim]Token 使用: 输入 {response.usage.input_tokens} / "
                f"输出 {response.usage.output_tokens} / "
                f"总计 {response.usage.input_tokens + response.usage.output_tokens}[/dim]"
            )

    def print_tool_execution(self, tool_calls: list[ToolCall], tool_results: list[ToolResult]):
        """打印工具执行结果"""
        if not tool_calls:
            return

        self.console.print(f"\n[bold magenta]⚙️  工具执行结果:[/bold magenta]")
        
        for i, (tool_call, tool_result) in enumerate(zip(tool_calls, tool_results), 1):
            status = "✅" if tool_result.success else "❌"
            self.console.print(f"\n{status} [bold]{tool_call.name}[/bold]")
            
            if tool_result.result:
                result_text = tool_result.result
                if len(result_text) > 800:
                    head = result_text[:300]
                    tail = result_text[-300:]
                    result_text = f"{head}\n... (中间省略 {len(result_text) - 600} 个字符) ...\n{tail}"
                self.console.print(Panel(result_text, border_style="green" if tool_result.success else "red"))
            
            if tool_result.error:
                self.console.print(f"[red]错误: {tool_result.error}[/red]")

    def print_info(self, message: str, step_number: int | None = None):
        """打印信息"""
        if step_number is not None:
            self.console.print(f"[bold blue]ℹ️  步骤 {step_number}: {message}[/bold blue]")
        else:
            self.console.print(f"[bold blue]ℹ️  {message}[/bold blue]")

    def print_error(self, error: str, step_number: int | None = None):
        """打印错误信息"""
        if step_number:
            self.console.print(f"\n[bold red]❌ 步骤 {step_number} 出错:[/bold red]")
        else:
            self.console.print(f"\n[bold red]❌ 错误:[/bold red]")
        self.console.print(Panel(error, border_style="red", title="错误详情"))

    def print_summary(self, execution):
        """打印执行摘要"""
        self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        self.console.print("[bold cyan]执行摘要[/bold cyan]")
        self.console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")
        
        self.console.print(f"总步数: {len(execution.steps)}")
        self.console.print(f"执行时间: {execution.execution_time:.2f} 秒")
        self.console.print(f"状态: {'✅ 成功' if execution.success else '❌ 失败'}")
        
        if execution.final_result:
            self.console.print(f"\n最终结果:")
            self.console.print(Panel(execution.final_result, border_style="green" if execution.success else "red"))

