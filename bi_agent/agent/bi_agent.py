"""BI-Agent 实现"""

from pathlib import Path

from bi_agent.utils.typing_compat import override

from bi_agent.agent.base_agent import BaseAgent
from bi_agent.prompts.system_prompt import BI_AGENT_SYSTEM_PROMPT
from bi_agent.tools.base import Tool
from bi_agent.tools.bash_tool import BashTool
from bi_agent.tools.python_executor_tool import PythonExecutorTool
from bi_agent.tools.search_knowledge_tool import SearchKnowledgeTool
from bi_agent.tools.report_generator_tool import ReportGeneratorTool
from bi_agent.tools.task_done_tool import TaskDoneTool
from bi_agent.utils.llm_clients.llm_basics import LLMMessage
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.system_info import get_system_info


class BIAgent(BaseAgent):
    """BI-Agent：数据分析智能代理"""

    def __init__(
        self,
        llm_client: LLMClient,
        data_dir: str,
        output_dir: str,
        tools: list[Tool] | None = None,
        max_steps: int = 50,
        console_output=None,
        memory_config=None,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        """初始化 BI-Agent

        Args:
            llm_client: LLM 客户端
            data_dir: 数据目录路径
            output_dir: 输出目录路径
            tools: 工具列表（如果为 None，则使用默认工具）
            max_steps: 最大执行步数
            console_output: 控制台输出器（可选）
            memory_config: 记忆配置（可选）
            user_id: 用户 ID（用于长期记忆）
            session_id: 会话 ID（用于短期记忆）
        """
        # 确保目录存在
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self.data_dir = Path(data_dir).resolve()
        self.output_dir = Path(output_dir).resolve()

        # 创建默认工具
        if tools is None:
            bash_tool = BashTool()
            # 设置数据目录，使 bash 工具能够验证命令路径
            bash_tool.set_data_dir(str(self.data_dir))
            
            python_executor = PythonExecutorTool(
                data_dir=str(self.data_dir),
                output_dir=str(self.output_dir),
            )
            
            tools = [
                bash_tool,  # bash 工具（用于文件操作、系统命令等）
                python_executor,  # Python 代码执行工具（用于数据分析、可视化等）
                SearchKnowledgeTool(data_dir=str(self.data_dir)),  # 知识搜索工具
                ReportGeneratorTool(),  # 报告生成工具
                TaskDoneTool(),  # 任务完成工具
            ]

        super().__init__(
            llm_client,
            tools,
            max_steps,
            console_output=console_output,
            memory_config=memory_config,
            user_id=user_id,
            session_id=session_id,
        )

    @override
    def new_task(self, task: str, extra_args: dict[str, str] | None = None):
        """创建新任务"""
        self._task = task

        # 构建初始消息
        system_message = LLMMessage(role="system", content=BI_AGENT_SYSTEM_PROMPT)

        # 获取系统环境信息
        system_info = get_system_info()

        # 构建用户消息
        user_content = f"""数据分析任务：{task}

## 环境信息
{system_info}

## 工作目录
数据目录：{self.data_dir}
输出目录：{self.output_dir}

请按照以下步骤完成分析：
1. 首先使用 `bash` 工具执行 `ls {self.data_dir}` 命令，扫描数据目录，了解有哪些数据文件
2. 读取说明文件（如果有），理解数据结构和业务含义
3. 使用 `python_executor` 工具编写 Python 代码读取数据文件，了解数据基本信息
   - 数据目录路径：{self.data_dir}（在代码中使用 DATA_DIR 变量）
   - 输出目录路径：{self.output_dir}（在代码中使用 OUTPUT_DIR 变量）
   - 可以使用 pandas 读取 Excel/CSV：`pd.read_excel(f'{{DATA_DIR}}/文件名.xlsx')` 或 `pd.read_csv(f'{{DATA_DIR}}/文件名.csv')`
4. 根据需求使用 `python_executor` 工具编写代码进行数据清洗（处理缺失值、重复值、异常值等）
5. 使用 `python_executor` 工具编写代码进行数据分析和可视化
   - 可以使用 matplotlib 生成图表：`plt.figure()`, `plt.plot()`, `plt.bar()` 等
   - 图表保存到输出目录：`plt.savefig(f'{{OUTPUT_DIR}}/图表名称.png')`
6. 使用 `report_generator` 工具生成分析报告
7. **任务完成时，必须调用 `task_done` 工具**，在 summary 参数中提供任务完成总结

**重要约束 - 必须在数据目录及其子目录下操作：**
- **数据目录（所有操作必须在此目录及其子目录下）**：{self.data_dir}
- **输出目录**：{self.output_dir}
- **严禁修改或删除原始数据文件**
- **使用 bash 工具时**：
  - ✅ **正确**：
    - `ls {self.data_dir}` - 列出数据目录内容
    - `cat {self.data_dir}/README.md` - 读取数据目录下的文件
    - `find {self.data_dir} -name "*.csv"` - 在数据目录下查找文件
    - `ls {self.data_dir}/example` - 列出数据目录子目录内容
    - `cat {self.data_dir}/example/sales_data.csv` - 读取子目录下的文件
  - ❌ **错误**：`ls`、`ls -la`、`pwd`、`cat README.md`（这些会在当前工作目录执行，不是数据目录）
  - ❌ **禁止**：不要使用数据目录外的路径
- **所有文件路径必须使用绝对路径，且路径必须在数据目录或其子目录下**
- 如果文件不存在，工具会列出数据目录下可用的文件，请使用列出的文件路径
"""

        if extra_args:
            for key, value in extra_args.items():
                user_content += f"\n{key}: {value}"

        user_message = LLMMessage(role="user", content=user_content)

        self._initial_messages = [system_message, user_message]

