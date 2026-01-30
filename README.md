# BI-Agent

BI-Agent 是一款面向普通用户与数据分析从业者的**全自动/半自动数据分析智能代理**，通过自然语言理解用户需求，自动处理数据文件，完成数据读取、清洗、探索、可视化与报告生成。

## 🎬 演示（GIF 预览）

下面是 BI-Agent 的效果演示（GIF 预览）：

![BI-Agent 演示](./docs/demo/demo.gif)

## 项目特点

- 🤖 **智能理解**：通过自然语言理解用户分析需求
- 📊 **自动分析**：自动完成数据读取、清洗、分析、可视化全流程
- 🔍 **知识理解**：优先读取说明文件，理解字段含义和业务背景
- 📈 **丰富可视化**：支持多种图表类型（折线图、柱状图、散点图、饼图等）
- 📝 **报告生成**：自动生成结构化的 Markdown 分析报告
- 🔒 **数据安全**：只读原始数据，所有结果保存到独立输出目录

## 项目架构

项目采用模块化设计，包含四大核心模块：

```
bi_agent/
├── agent/          # 核心代理模块
│   ├── base_agent.py      # Agent 基类
│   ├── bi_agent.py        # BI-Agent 实现
│   └── agent.py           # Agent 工厂类
├── tools/          # 数据分析工具集
│   ├── data_reader_tool.py        # 数据读取工具
│   ├── data_cleaner_tool.py       # 数据清洗工具
│   ├── visualization_tool.py     # 可视化工具
│   ├── report_generator_tool.py  # 报告生成工具
│   ├── search_knowledge_tool.py  # 知识库搜索工具
│   └── bash_tool.py              # Bash 命令工具
├── prompts/        # 提示词管理
│   ├── system_prompt.py   # 系统提示词
│   └── task_prompts.py    # 任务分类提示词
└── utils/          # 通用辅助工具
    ├── logger.py              # 日志记录
    ├── trajectory_recorder.py # 轨迹记录
    ├── step_summarizer.py     # 步骤摘要
    └── exceptions.py          # 异常处理
```

## 安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd BI-Agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件（可选）：

```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Doubao (豆包)
ARK_API_KEY=your_doubao_api_key_here

# Qwen (通义千问)
QWEN_API_KEY=your_dashscope_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 可选

# Mem0 (记忆管理，可选)
MEM0_API_KEY=your_mem0_api_key_here
```

或者在使用时通过 `--api-key` 参数提供。

## 使用方法

### 基本用法

```bash
python -m bi_agent.cli run "分析销售数据的月度趋势" \
    --data-dir ./data \
    --output-dir ./output \
    --api-key your_api_key
```

### 完整参数示例

**使用 OpenAI:**
```bash
python -m bi_agent.cli run "分析销售数据的月度趋势并给出区域优化建议" \
    --data-dir /path/to/data \
    --output-dir /path/to/output \
    --provider openai \
    --model gpt-4 \
    --api-key your_openai_api_key \
    --max-steps 50 \
    --trajectory-file ./trajectories/task_001.json
```

**使用 Doubao (豆包):**
```bash
python -m bi_agent.cli run "分析销售数据的月度趋势并给出区域优化建议" \
    --data-dir /path/to/data \
    --output-dir /path/to/output \
    --provider doubao \
    --model doubao-seed-1-6-251015 \
    --api-key your_ark_api_key \
    --max-steps 50 \
    --trajectory-file ./trajectories/task_001.json
```

**使用 Qwen (通义千问):**
```bash
python -m bi_agent.cli run "分析销售数据的月度趋势并给出区域优化建议" \
    --data-dir /path/to/data \
    --output-dir /path/to/output \
    --provider qwen \
    --model qwen-plus \
    --api-key your_dashscope_api_key \
    --max-steps 50 \
    --trajectory-file ./trajectories/task_001.json
```

### 参数说明

- `query`: 数据分析需求描述（必需）
- `--data-dir, -d`: 数据文件所在目录（必需）
- `--output-dir, -o`: 输出文件保存目录（默认: ./output）
- `--provider, -p`: LLM 提供商（默认: openai，支持：openai, doubao, qwen）
- `--model, -m`: 模型名称（默认: gpt-4，doubao 默认: doubao-seed-1-6-251015，qwen 默认: qwen-plus）
- `--api-key, -k`: API Key（或通过环境变量设置：OPENAI_API_KEY 或 ARK_API_KEY）
- `--base-url`: API Base URL（可选）
- `--max-steps`: 最大执行步数（默认: 50）
- `--trajectory-file, -t`: 轨迹文件保存路径（可选）

## 数据格式支持

### 支持的数据文件

- **Excel**: `.xlsx`, `.xls`
- **CSV**: `.csv`（自动检测编码：UTF-8、GBK、GB2312）

### 说明文件

Agent 会优先读取以下说明文件，理解数据结构和业务含义：

- `README.txt`
- `README.md`
- `字段说明.txt`
- `字段说明.md`
- 其他 `.txt` 或 `.md` 文件

## 使用示例

**注意**：以下示例假设您已经：
1. 在 `.env` 文件中配置了 API Key，或通过环境变量设置了 `OPENAI_API_KEY`（或其他提供商的 Key）
2. 准备了相应的数据文件在指定目录中

### 示例 1：分析数据趋势

```bash
# 使用项目自带的学生贷款数据示例
python -m bi_agent.cli run "分析学生贷款数据，包括性别分布、失业率等关键指标的趋势" \
    --data-dir ./data/analysis_on_student_loan \
    --output-dir ./output/student_loan_analysis
```

### 示例 2：数据清洗和可视化

```bash
# 分析数据并生成可视化图表
python -m bi_agent.cli run "清洗数据并生成各维度的分布图表，包括性别分布、学校分布等" \
    --data-dir ./data/analysis_on_student_loan \
    --output-dir ./output/visualization
```

### 示例 3：完整分析报告

```bash
# 执行完整的数据分析流程
python -m bi_agent.cli run "对学生贷款数据进行完整分析，包括：1) 数据清洗 2) 关键指标分析 3) 生成可视化图表 4) 输出完整分析报告" \
    --data-dir ./data/analysis_on_student_loan \
    --output-dir ./output/full_analysis \
    --max-steps 100
```

### 示例 4：使用自定义数据

```bash
# 使用您自己的数据文件
python -m bi_agent.cli run "分析销售数据的月度趋势" \
    --data-dir /path/to/your/data \
    --output-dir ./output/sales_analysis \
    --provider openai \
    --model gpt-4 \
    --api-key your_api_key_here
```

## 输出文件

执行完成后，输出目录将包含：

- **清洗后的数据**: `cleaned_data.xlsx` 或 `cleaned_data.csv`
- **可视化图表**: `chart_*.png`
- **分析报告**: `analysis_report.md`
- **轨迹文件**: `trajectory_*.json`（如果指定）

## 项目结构

```
BI-Agent/
├── bi_agent/           # 主代码目录
│   ├── agent/          # Agent 模块
│   ├── tools/          # 工具模块
│   ├── prompts/        # 提示词模块
│   ├── utils/          # 工具模块
│   └── cli.py          # CLI 入口
├── data/               # 数据目录（示例）
├── output/             # 输出目录
├── trajectories/       # 轨迹文件目录
├── requirements.txt    # 依赖列表
├── pyproject.toml      # 项目配置
└── README.md           # 本文档
```

## 开发说明

### 扩展工具

要添加新的工具，请：

1. 在 `bi_agent/tools/` 目录下创建新工具类
2. 继承 `Tool` 基类
3. 实现 `get_name()`, `get_description()`, `get_parameters()`, `execute()` 方法
4. 在 `bi_agent/tools/__init__.py` 中注册工具

### 自定义提示词

修改 `bi_agent/prompts/system_prompt.py` 中的系统提示词，或使用 `task_prompts.py` 中的分类提示词。

## 常见问题

### Q: 如何指定不同的 LLM 提供商？

A: 使用 `--provider` 参数指定提供商，例如：
- OpenAI: `--provider openai --api-key YOUR_OPENAI_KEY`
- Doubao (豆包): `--provider doubao --api-key YOUR_ARK_KEY`
- Qwen (通义千问): `--provider qwen --api-key YOUR_QWEN_KEY`

注意：
- OpenAI 使用 `OPENAI_API_KEY` 环境变量
- Doubao 使用 `ARK_API_KEY` 环境变量
- Qwen 使用 `QWEN_API_KEY` 环境变量

### Q: 数据文件编码问题？

A: Agent 会自动检测常见编码（UTF-8、GBK、GB2312）。如果仍有问题，可以在代码中手动指定编码。

### Q: 如何查看执行轨迹？

A: 使用 `--trajectory-file` 参数指定轨迹文件路径，执行完成后可以查看 JSON 格式的轨迹文件。

### Q: 支持哪些图表类型？

A: 目前支持折线图、柱状图、散点图、饼图、箱线图、直方图。可以通过扩展 `visualization_tool.py` 添加更多类型。

## 通道支持

BI-Agent 支持多种消息通道，可以通过飞书或钉钉与企业协作平台集成：

- **飞书通道**：支持长连接方式接收消息，详见 [飞书通道文档](bi_agent/channel/feishu/README.md)
- **钉钉通道**：支持流模式接收消息，详见 [钉钉通道文档](bi_agent/channel/dingTalk/README.md)

## 贡献

我们欢迎所有形式的贡献！请查看 [贡献指南](CONTRIBUTING.md) 了解如何参与项目。

### 贡献方式

- 🐛 报告 Bug
- 💡 提出功能建议
- 📝 改进文档
- 🔧 提交代码修复或新功能

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 联系方式

如有问题或建议，请通过以下方式反馈：

- GitHub Issues
- Pull Requests

## 致谢

感谢所有为项目做出贡献的开发者！

