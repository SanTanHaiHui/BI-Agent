"""Agent 工厂类"""

from bi_agent.agent.bi_agent import BIAgent
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.trajectory_recorder import TrajectoryRecorder
from bi_agent.utils.console_output import ConsoleOutput
from bi_agent.utils.memory_manager import MemoryConfig


class Agent:
    """Agent 工厂类，用于创建和管理 Agent 实例"""

    def __init__(
        self,
        llm_client: LLMClient,
        data_dir: str,
        output_dir: str,
        trajectory_file: str | None = None,
        max_steps: int = 50,
        verbose: bool = True,
        memory_config: MemoryConfig | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        clear_memory: bool = False,
    ):
        """初始化 Agent

        Args:
            llm_client: LLM 客户端
            data_dir: 数据目录路径
            output_dir: 输出目录路径
            trajectory_file: 轨迹文件路径（可选）
            max_steps: 最大执行步数
            verbose: 是否显示详细输出
            memory_config: 记忆配置（可选）
            user_id: 用户 ID（用于长期记忆）
            session_id: 会话 ID（用于短期记忆）
            clear_memory: 是否在执行任务前清空会话记忆
        """
        self.llm_client = llm_client
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.max_steps = max_steps
        self.clear_memory = clear_memory

        # 设置轨迹记录器
        if trajectory_file is not None:
            self.trajectory_file = trajectory_file
            self.trajectory_recorder = TrajectoryRecorder(trajectory_file)
        else:
            self.trajectory_recorder = TrajectoryRecorder()
            self.trajectory_file = str(self.trajectory_recorder.trajectory_path)

        # 创建控制台输出器
        self.console_output = ConsoleOutput(verbose=verbose)

        # 创建 BI-Agent（传入记忆配置）
        self.agent = BIAgent(
            llm_client=llm_client,
            data_dir=data_dir,
            output_dir=output_dir,
            max_steps=max_steps,
            console_output=self.console_output,
            memory_config=memory_config,
            user_id=user_id,
            session_id=session_id,
        )

        self.agent.set_trajectory_recorder(self.trajectory_recorder)

    async def run(self, task: str, extra_args: dict[str, str] | None = None):
        """运行任务

        Args:
            task: 任务描述
            extra_args: 额外参数
        """
        # 如果设置了清空记忆，在执行任务前清空会话记忆
        if self.clear_memory:
            if self.console_output:
                self.console_output.print_info("正在清空会话记忆...", step_number=0)
            try:
                self.agent.memory_manager.clear_session_memory()
                if self.console_output:
                    self.console_output.print_info("会话记忆已清空（内存中的消息历史已清空）", step_number=0)
            except Exception as e:
                # 即使 mem0 删除失败，内存中的消息历史也已经清空
                # 这是最重要的，所以这里只打印警告，不抛出异常
                if self.console_output:
                    self.console_output.print_info(
                        f"会话记忆已清空（内存中的消息历史已清空，mem0 删除可能失败但不影响使用）", 
                        step_number=0
                    )
        
        # 开始记录轨迹
        self.trajectory_recorder.start_recording(
            task=task,
            provider="unknown",  # 可以从 llm_client 获取
            model="unknown",  # 可以从 llm_client 获取
            max_steps=self.max_steps,
            data_dir=self.data_dir,
            output_dir=self.output_dir,
        )

        # 创建新任务
        self.agent.new_task(task, extra_args)

        # 执行任务
        execution = await self.agent.execute_task()

        # 结束记录轨迹
        self.trajectory_recorder.end_recording(
            success=execution.success,
            final_result=execution.final_result,
        )

        # 显示执行摘要
        if self.console_output:
            self.console_output.print_summary(execution)

        return execution

