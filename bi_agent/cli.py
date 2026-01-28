"""BI-Agent 命令行界面"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from bi_agent.agent.agent import Agent
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.llm_clients.openai_client import OpenAIClient
from bi_agent.utils.llm_clients.doubao_client import DoubaoClient
from bi_agent.utils.llm_clients.qwen_client import QwenClient

# 加载环境变量
_ = load_dotenv()

console = Console()


def generate_session_id() -> str:
    """生成唯一的会话 ID
    
    Returns:
        格式：session_YYYYMMDD_HHMMSS_<uuid4前8位>
        例如：session_20260108_143025_a1b2c3d4
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_short = str(uuid.uuid4())[:8]
    return f"session_{timestamp}_{uuid_short}"


def create_llm_client(provider: str, model: str, api_key: str, base_url: str | None = None) -> LLMClient:
    """创建 LLM 客户端

    Args:
        provider: LLM 提供商（openai, doubao, qwen）
        model: 模型名称
        api_key: API Key
        base_url: Base URL（可选）

    Returns:
        LLM 客户端实例
    """
    provider_lower = provider.lower()
    
    if provider_lower == "openai":
        return OpenAIClient(api_key=api_key, model=model, base_url=base_url)
    elif provider_lower == "doubao":
        # Doubao 默认 base_url
        if base_url is None:
            base_url = "https://ark.cn-beijing.volces.com/api/v3"
        # Doubao 默认 model（如果未指定）
        if model == "gpt-4" or model == "default":
            model = "doubao-seed-1-6-251015"
        return DoubaoClient(api_key=api_key, model=model, base_url=base_url)
    elif provider_lower == "qwen":
        # Qwen 默认 model（如果未指定）
        if model == "gpt-4" or model == "default":
            model = "qwen-plus"
        # base_url 如果未指定，QwenClient 会自动从环境变量 QWEN_BASE_URL 读取，或使用默认值
        return QwenClient(api_key=api_key, model=model, base_url=base_url)
    else:
        console.print(f"[yellow]警告：不支持的提供商 {provider}，使用 OpenAI 客户端[/yellow]")
        return OpenAIClient(api_key=api_key, model=model, base_url=base_url)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """BI-Agent: 数据分析智能代理"""
    pass


@cli.command()
@click.argument("query", required=True)
@click.option(
    "--data-dir",
    "-d",
    required=True,
    help="数据文件所在目录的路径",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--output-dir",
    "-o",
    default="./output",
    help="输出文件保存目录（默认: ./output）",
    type=click.Path(resolve_path=True),
)
@click.option(
    "--provider",
    "-p",
    default="openai",
    help="LLM 提供商（openai, doubao, qwen）",
)
@click.option(
    "--model",
    "-m",
    default="gpt-4",
    help="模型名称",
)
@click.option(
    "--api-key",
    "-k",
    help="API Key（或通过环境变量设置，doubao 使用 ARK_API_KEY，qwen 使用 QWEN_API_KEY）",
    envvar="OPENAI_API_KEY",
)
@click.option(
    "--base-url",
    help="API Base URL（可选）",
)
@click.option(
    "--max-steps",
    default=50,
    help="最大执行步数（默认: 50）",
    type=int,
)
@click.option(
    "--trajectory-file",
    "-t",
    help="轨迹文件保存路径（可选）",
)
@click.option(
    "--verbose/--no-verbose",
    default=True,
    help="是否显示详细的执行过程（默认: 显示）",
)
@click.option(
    "--clear-memory/--no-clear-memory",
    default=False,
    help="是否在执行任务前清空会话记忆（默认: 不清空）",
)
def run(
    query: str,
    data_dir: str,
    output_dir: str,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    max_steps: int,
    trajectory_file: str | None,
    verbose: bool,
    clear_memory: bool,
):
    """运行数据分析任务

    QUERY: 数据分析需求描述（例如："分析销售数据的月度趋势"）
    """
    # 根据提供商选择环境变量
    if not api_key:
        if provider.lower() == "doubao":
            api_key = os.getenv("ARK_API_KEY")
            if not api_key:
                console.print("[red]错误：必须提供 Doubao API Key[/red]")
                console.print("[yellow]提示：通过 --api-key 参数提供，或设置 ARK_API_KEY 环境变量[/yellow]")
                console.print("[yellow]示例：export ARK_API_KEY=your_api_key_here[/yellow]")
                sys.exit(1)
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                console.print("[red]错误：必须提供 OpenAI API Key[/red]")
                console.print("[yellow]提示：通过 --api-key 参数提供，或设置 OPENAI_API_KEY 环境变量[/yellow]")
                console.print("[yellow]示例：export OPENAI_API_KEY=your_api_key_here[/yellow]")
                sys.exit(1)
    
    # 验证 API Key 不为空
    if not api_key or api_key.strip() == "":
        console.print("[red]错误：API Key 不能为空[/red]")
        sys.exit(1)

    # 创建 LLM 客户端
    try:
        llm_client = create_llm_client(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        console.print(f"[red]错误：创建 LLM 客户端失败: {e}[/red]")
        console.print("[yellow]提示：请确保已安装 openai 包: pip install openai[/yellow]")
        sys.exit(1)

    # 生成新的 session_id（每次启动程序时生成新的会话 ID）
    session_id = generate_session_id()
    
    # 可选：从环境变量读取 user_id，如果没有则使用默认值
    user_id = os.getenv("BI_AGENT_USER_ID", "default_user")

    # 创建 Agent
    agent = Agent(
        llm_client=llm_client,
        data_dir=data_dir,
        output_dir=output_dir,
        trajectory_file=trajectory_file,
        max_steps=max_steps,
        verbose=verbose,
        user_id=user_id,
        session_id=session_id,
        clear_memory=clear_memory,
    )

    # 显示任务信息
    console.print(
        Panel(
            f"""[bold]任务信息[/bold]

查询: {query}
数据目录: {data_dir}
输出目录: {output_dir}
模型: {model} ({provider})
最大步数: {max_steps}
会话 ID: {session_id}
用户 ID: {user_id}
清空记忆: {'是' if clear_memory else '否'}
轨迹文件: {agent.trajectory_file}""",
            title="BI-Agent",
            border_style="blue",
        )
    )

    # 运行任务
    try:
        execution = asyncio.run(agent.run(query))
        if execution.success:
            console.print(f"\n[green]✓ 任务完成！[/green]")
            if execution.final_result:
                console.print(f"[green]结果: {execution.final_result}[/green]")
        else:
            console.print(f"\n[red]✗ 任务失败[/red]")
            if execution.final_result:
                console.print(f"[red]错误: {execution.final_result}[/red]")
            # 检查是否有步骤错误
            if execution.steps:
                last_step = execution.steps[-1]
                if last_step.error:
                    console.print(f"\n[red]详细错误信息:[/red]")
                    console.print(f"[red]{last_step.error}[/red]")
                    # 如果是认证错误，给出提示
                    if "401" in last_step.error or "Authentication" in last_step.error or "API key" in last_step.error.lower():
                        console.print("\n[yellow]认证错误提示：[/yellow]")
                        if provider.lower() == "doubao":
                            console.print("[yellow]1. 检查 ARK_API_KEY 环境变量是否正确设置[/yellow]")
                            console.print("[yellow]2. 确认 API Key 格式正确（不应包含多余空格或引号）[/yellow]")
                            console.print("[yellow]3. 使用 --api-key 参数直接提供 API Key：[/yellow]")
                            console.print("[yellow]   --api-key YOUR_ARK_API_KEY[/yellow]")
                            console.print("[yellow]4. 验证 API Key 是否有效（在 Doubao 控制台检查）[/yellow]")
                        else:
                            console.print("[yellow]1. 检查 OPENAI_API_KEY 环境变量是否正确设置[/yellow]")
                            console.print("[yellow]2. 确认 API Key 格式正确（不应包含多余空格或引号）[/yellow]")
                            console.print("[yellow]3. 使用 --api-key 参数直接提供 API Key：[/yellow]")
                            console.print("[yellow]   --api-key YOUR_OPENAI_API_KEY[/yellow]")
                            console.print("[yellow]4. 验证 API Key 是否有效（在 OpenAI 控制台检查）[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]任务执行被用户中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]执行出错: {e}[/red]")
        import traceback

        console.print(traceback.format_exc())
        sys.exit(1)


@cli.command()
def show_config():
    """显示当前配置"""
    openai_key = os.getenv("OPENAI_API_KEY")
    doubao_key = os.getenv("ARK_API_KEY")
    
    console.print(
        Panel(
            f"""[bold]配置信息[/bold]

OpenAI API Key: {'已设置' if openai_key else '未设置'}
Doubao API Key (ARK_API_KEY): {'已设置' if doubao_key else '未设置'}
默认模型: gpt-4 (openai) / doubao-seed-1-6-251015 (doubao)
默认提供商: openai

支持的提供商:
  - openai: 使用 OPENAI_API_KEY 环境变量
  - doubao: 使用 ARK_API_KEY 环境变量""",
            title="BI-Agent 配置",
            border_style="yellow",
        )
    )


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()

