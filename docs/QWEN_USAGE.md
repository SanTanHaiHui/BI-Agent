# Qwen (通义千问) 使用指南

BI-Agent 支持使用阿里云 DashScope 的 Qwen (通义千问) 模型进行数据分析任务。

## 前置要求

1. **安装依赖**：确保已安装 `openai` 包
   ```bash
   pip install openai
   ```

2. **获取 API Key**：
   - 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/apiKey)
   - 创建并获取 API Key
   - 将 API Key 保存到环境变量或配置文件中

## 配置 API Key

### 方法 1：环境变量（推荐）

```bash
export QWEN_API_KEY=sk-your-api-key-here
export QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 可选
```

### 方法 2：命令行参数

```bash
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen \
    --model qwen-plus \
    --api-key sk-your-api-key-here
```

## 使用方法

### 命令行使用

```bash
# 使用默认模型 (qwen-plus)
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen

# 指定模型
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen \
    --model qwen-max

# 使用环境变量中的 API Key
export QWEN_API_KEY=sk-your-api-key-here
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen
```

### Python 代码使用

```python
import asyncio
from bi_agent.agent.agent import Agent
from bi_agent.utils.llm_clients.qwen_client import QwenClient

# 创建 Qwen 客户端
qwen_client = QwenClient(
    api_key="sk-your-api-key-here",  # 或使用 os.getenv("QWEN_API_KEY")
    model="qwen-plus",  # 可选：qwen-plus, qwen-max, qwen-turbo
    base_url=None,  # 可选，None 时会从环境变量 QWEN_BASE_URL 读取，或使用默认值
)

# 创建 Agent
agent = Agent(
    llm_client=qwen_client,
    data_dir="./data",
    output_dir="./output",
)

# 运行任务
async def main():
    execution = await agent.run("分析销售数据的月度趋势")
    print(f"任务完成: {execution.success}")
    print(f"结果: {execution.final_result}")

asyncio.run(main())
```

## 可用模型

Qwen 客户端支持以下模型（通过 `--model` 参数指定）：

| 模型名称 | 说明 | 适用场景 |
|---------|------|---------|
| `qwen-plus` | 通义千问 Plus（默认） | 通用场景，平衡性能和成本 |
| `qwen-max` | 通义千问 Max | 复杂任务，需要更强推理能力 |
| `qwen-turbo` | 通义千问 Turbo | 快速响应，简单任务 |

更多模型信息请参考：[阿里云模型列表](https://help.aliyun.com/zh/model-studio/getting-started/models)

## 配置说明

### Base URL

默认 Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`

可以通过以下方式配置 Base URL：

**方法 1：环境变量（推荐）**

在 `.env` 文件中配置：
```bash
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

或通过命令行设置：
```bash
export QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**方法 2：命令行参数**

```bash
python -m bi_agent.cli run "分析数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen \
    --base-url https://your-custom-url.com/v1
```

**方法 3：Python 代码**

```python
qwen_client = QwenClient(
    api_key=os.getenv("QWEN_API_KEY"),
    model="qwen-plus",
    base_url=os.getenv("QWEN_BASE_URL"),  # 如果为 None，会使用默认值
)
```

**优先级**：命令行参数 > Python 代码参数 > 环境变量 `QWEN_BASE_URL` > 默认值

### 模型选择

根据任务复杂度选择合适的模型：

- **简单数据分析**：使用 `qwen-turbo`（快速、经济）
- **常规数据分析**：使用 `qwen-plus`（平衡）
- **复杂分析任务**：使用 `qwen-max`（最强能力）

## 示例

### 示例 1：基本数据分析

```bash
export QWEN_API_KEY=sk-your-api-key-here

python -m bi_agent.cli run "分析销售数据的月度趋势并生成可视化图表" \
    --data-dir ./data \
    --output-dir ./output \
    --provider qwen \
    --model qwen-plus \
    --verbose
```

### 示例 2：使用 Python API

```python
import asyncio
import os
from bi_agent.agent.agent import Agent
from bi_agent.utils.llm_clients.qwen_client import QwenClient

# 从环境变量获取 API Key 和 Base URL
api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise ValueError("请设置 QWEN_API_KEY 环境变量")

# base_url 可以从环境变量读取，如果为 None 会使用默认值
base_url = os.getenv("QWEN_BASE_URL")  # 可选

# 创建客户端
qwen_client = QwenClient(
    api_key=api_key,
    model="qwen-plus",
    base_url=base_url,  # 如果为 None，会自动从环境变量读取或使用默认值
)

# 创建 Agent
agent = Agent(
    llm_client=qwen_client,
    data_dir="./data",
    output_dir="./output",
    verbose=True,
)

# 运行任务
async def main():
    execution = await agent.run(
        "分析学生贷款数据，生成分类统计报告",
        extra_args={"focus": "还款状态分析"},
    )
    
    if execution.success:
        print("✓ 任务完成")
        print(f"结果: {execution.final_result}")
    else:
        print("✗ 任务失败")
        print(f"错误: {execution.final_result}")

asyncio.run(main())
```

## 故障排除

### 问题 1：API Key 错误

**错误信息**：
```
Error code: 401 - AuthenticationError
```

**解决方法**：
1. 检查 API Key 是否正确
2. 确认环境变量 `QWEN_API_KEY` 已设置
3. 验证 API Key 是否有效（访问 DashScope 控制台）

### 问题 2：模型不存在

**错误信息**：
```
Error code: 400 - Invalid model
```

**解决方法**：
1. 检查模型名称是否正确
2. 确认账户有权限使用该模型
3. 参考[模型列表](https://help.aliyun.com/zh/model-studio/getting-started/models)选择可用模型

### 问题 3：请求超时

**解决方法**：
1. 检查网络连接
2. 尝试使用 `qwen-turbo` 模型（响应更快）
3. 减少任务复杂度

### 问题 4：工具调用不支持

**说明**：Qwen 模型支持工具调用（Function Calling），但某些模型版本可能有差异。

**解决方法**：
1. 使用 `qwen-plus` 或 `qwen-max` 模型
2. 检查工具定义格式是否正确
3. 查看 DashScope 文档确认模型版本支持情况

## 参考资源

- [DashScope 官方文档](https://help.aliyun.com/zh/model-studio/)
- [Qwen 模型列表](https://help.aliyun.com/zh/model-studio/getting-started/models)
- [API Key 管理](https://dashscope.console.aliyun.com/apiKey)
- [OpenAI 兼容模式文档](https://help.aliyun.com/zh/model-studio/developer-reference/api-details-9)

## 注意事项

1. **API Key 安全**：不要将 API Key 提交到代码仓库，使用环境变量或配置文件
2. **费用说明**：使用 Qwen 模型会产生费用，请查看 [DashScope 定价](https://help.aliyun.com/zh/model-studio/product-overview/billing)
3. **速率限制**：注意 API 调用频率限制，避免超出配额
4. **模型选择**：根据任务需求选择合适的模型，平衡性能和成本

