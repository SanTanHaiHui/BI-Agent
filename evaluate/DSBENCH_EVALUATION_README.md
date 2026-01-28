# DSBench 评估说明

本目录包含用于评估 BI-Agent 在 DSBench 数据集上表现的脚本。

## DSBench 简介

DSBench 是一个用于评估数据分析智能代理的基准数据集，包含：
- **数据分析任务** (data_analysis): 来自 ModelOff 竞赛的真实数据分析问题
- **数据建模任务** (data_modeling): 来自 Kaggle 竞赛的数据建模问题

每个任务包含：
- 问题描述（可能包含图片和表格）
- 数据文件
- 标准答案

## 使用方法

### 1. 准备环境

确保已安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 准备 DSBench 数据

**重要提示**：DSBench 数据集文件较大，**不会包含在 GitHub 仓库中**。您需要单独下载数据。

DSBench 数据应位于 `data/DSBench/` 目录下：

```
data/DSBench/
├── data_analysis/
│   ├── data.json          # 任务列表
│   └── data/              # 数据文件目录
│       ├── 00000001/
│       │   ├── question6.txt
│       │   └── ...
│       └── ...
└── data_modeling/
    ├── data.json
    └── data/
        └── ...
```

**下载数据**：

1. 访问 [DSBench 官方仓库](https://github.com/LiqiangJing/DSBench)
2. 按照官方说明下载数据集
3. 将数据解压到项目的 `data/DSBench/` 目录下

**注意**：`data/DSBench/` 目录已在 `.gitignore` 中被忽略，不会提交到版本控制。

### 3. 配置环境变量

在 `.env` 文件中设置必要的 API Key：

```bash
# 用于运行 BI-Agent 的 LLM（选择其中一个）
OPENAI_API_KEY=your_openai_key
# 或
ARK_API_KEY=your_doubao_key
# 或
QWEN_API_KEY=your_qwen_key

# 注意：答案评估会使用与 BI-Agent 相同的 LLM 提供商和模型
# 例如，如果使用豆包运行 BI-Agent，答案评估也会使用相同的豆包模型和 API Key
```

### 4. 运行评估

#### 基本用法

```bash
# 评估数据分析任务
python -m evaluate.evaluate_dsbench \
    --task-type data_analysis \
    --provider openai \
    --model gpt-4o-2024-05-13 \
    --output-dir ./dsbench_evaluation

# 评估数据建模任务
python -m evaluate.evaluate_dsbench \
    --task-type data_modeling \
    --provider openai \
    --model gpt-4o-2024-05-13 \
    --output-dir ./dsbench_evaluation
```

#### 使用其他 LLM 提供商

```bash
# 使用豆包
python -m evaluate.evaluate_dsbench \
    --task-type data_analysis \
    --provider doubao \
    --model doubao-seed-1-6-251015

# 使用通义千问
python -m evaluate.evaluate_dsbench \
    --task-type data_analysis \
    --provider qwen \
    --model qwen-plus
```

#### 测试模式（限制样本数量）

```bash
# 只评估前 3 个样本（用于测试）
python -m evaluate.evaluate_dsbench \
    --task-type data_analysis \
    --limit 3
```

#### 查看评估结果

```bash
python -m evaluate.evaluate_dsbench \
    --show-results \
    --task-type data_analysis \
    --model gpt-4o-2024-05-13
```

### 5. 命令行参数说明

- `--task-type`: 任务类型，可选 `data_analysis` 或 `data_modeling`（默认: `data_analysis`）
- `--provider`: LLM 提供商，可选 `openai`、`doubao`、`qwen`（默认: `openai`）
- `--model`: LLM 模型名称（默认: `gpt-4o-2024-05-13`）
- `--output-dir`: 输出目录（默认: `./dsbench_evaluation`）
- `--max-steps`: Agent 最大执行步数（默认: `50`）
- `--limit`: 限制评估的样本数量（用于测试，默认: 无限制）
- `--show-results`: 显示评估结果统计

## 输出结果

评估结果保存在 `{output_dir}/save_process_{task_type}/{model}/` 目录下：

```
dsbench_evaluation/
└── save_process_data_analysis/
    └── gpt-4o-2024-05-13/
        ├── 00000001.json              # 每个样本的所有预测
        ├── 00000001_question6.json   # 每个问题的详细预测
        ├── all_results.json           # 所有结果汇总
        ├── results.json               # 评估结果（True/False）
        └── results_process.json       # 详细评估过程
```

### 结果文件说明

- `{sample_id}.json`: 包含该样本所有问题的预测结果
- `{sample_id}_{question_name}.json`: 单个问题的详细预测结果，包含：
  - `response`: Agent 的完整响应
  - `answer`: 提取的答案
  - `cost`: 执行成本（如果支持）
  - `time`: 执行时间（秒）
  - `success`: 是否成功完成
  - `steps`: 执行步数
- `results.json`: 每个问题的评估结果（True/False）
- `results_process.json`: 详细的评估过程，包含问题、正确答案、预测答案、评估结果

## 评估指标

评估脚本会计算以下指标：

1. **总准确率**: 所有问题的正确率
2. **每个挑战的准确率**: 每个样本（挑战）的平均准确率
3. **平均挑战准确率**: 所有挑战的平均准确率
4. **总成本**: 执行所有任务的总成本（如果支持）
5. **总耗时**: 执行所有任务的总时间

## 注意事项

1. **答案提取**: 脚本会尝试从 Agent 的响应中提取答案。如果 Agent 使用了 `task_done` 工具，会从 `summary` 中提取答案。否则会尝试从响应文本中提取。

2. **答案评估**: 使用与 BI-Agent 相同的 LLM 模型来判断预测答案是否正确。这需要额外的 API 调用，会产生额外成本。例如，如果使用豆包运行 BI-Agent，答案评估也会使用相同的豆包模型。

3. **数据文件**: 确保 DSBench 数据文件已正确下载并放置在 `data/DSBench/` 目录下。

4. **执行时间**: 完整评估可能需要较长时间，建议先用 `--limit` 参数测试少量样本。

5. **API 成本**: 评估过程会产生 API 调用成本，包括：
   - BI-Agent 执行任务的成本
   - 答案评估的成本（使用 GPT-4o）

## 示例输出

```
开始评估 43 个样本...
任务类型: data_analysis
模型: gpt-4o-2024-05-13 (openai)
输出目录: ./dsbench_evaluation/save_process_data_analysis/gpt-4o-2024-05-13

评估样本: 100%|████████████| 43/43 [45:23<00:00, 63.33s/样本]
计算准确率: 100%|████████████| 43/43 [12:34<00:00, 17.52s/样本]

============================================================
评估结果统计
============================================================
总问题数: 523
总准确率: 0.7234 (378/523)
总成本: $12.3456
总耗时: 2734.56 秒 (45.58 分钟)

每个挑战的准确率: [0.85, 0.72, 0.91, ...]
平均挑战准确率: 0.7234
============================================================
```

## 故障排除

### 1. 找不到数据文件

确保 DSBench 数据已正确下载并解压到 `data/DSBench/` 目录。

### 2. API Key 错误

检查 `.env` 文件中的 API Key 是否正确设置。

### 3. 答案提取失败

如果答案提取不准确，可以查看 `{sample_id}_{question_name}.json` 文件中的 `response` 字段，手动检查 Agent 的输出。

### 4. 评估超时

如果某个问题执行时间过长，可以增加 `--max-steps` 参数，或者检查问题是否过于复杂。

## 参考

- [DSBench 官方仓库](https://github.com/LiqiangJing/DSBench)
- [DSBench 论文](https://arxiv.org/abs/2409.07703)

