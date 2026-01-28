# Doubao (豆包) 客户端使用指南

## 简介

BI-Agent 现已支持 Doubao (豆包) 大模型客户端。Doubao 是字节跳动推出的 AI 大模型服务，通过 OpenAI 兼容的 API 接口提供服务。

## 配置

### 1. 获取 API Key

1. 访问 Doubao 控制台
2. 创建推理接入点
3. 获取 `ARK_API_KEY`

### 2. 设置环境变量

在 `.env` 文件中设置：

```bash
ARK_API_KEY=your_ark_api_key_here
```

或者通过命令行参数提供：

```bash
--api-key your_ark_api_key_here
```

### 3. 配置 Base URL（可选）

默认使用北京区域：
```
https://ark.cn-beijing.volces.com/api/v3
```

如需使用其他区域，可通过 `--base-url` 参数指定。

## 使用方法

### 基本用法

```bash
python -m bi_agent.cli run "分析销售数据的月度趋势" \
    --data-dir ./data/example \
    --output-dir ./output \
    --provider doubao \
    --api-key YOUR_ARK_API_KEY
```

### 指定模型

```bash
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data/example \
    --output-dir ./output \
    --provider doubao \
    --model doubao-seed-1-6-251015 \
    --api-key YOUR_ARK_API_KEY
```

### 使用环境变量

```bash
# 设置环境变量
export ARK_API_KEY=your_ark_api_key_here

# 运行（无需 --api-key 参数）
python -m bi_agent.cli run "分析销售数据" \
    --data-dir ./data/example \
    --output-dir ./output \
    --provider doubao
```

## 特性

### 推理过程支持

Doubao 客户端支持 `reasoning_content`（推理过程），如果模型返回推理内容，会自动添加到响应中：

```
[推理过程]
... 模型的推理过程 ...

[最终回答]
... 模型的最终回答 ...
```

### 工具调用

Doubao 完全兼容 OpenAI 的工具调用格式，支持所有 BI-Agent 的工具：
- `data_reader`: 数据读取
- `data_cleaner`: 数据清洗
- `visualization`: 数据可视化
- `report_generator`: 报告生成
- `search_knowledge`: 知识库搜索
- `bash`: Bash 命令执行

## 区域配置

Doubao 支持多个区域，可通过 `base_url` 配置：

- **北京**: `https://ark.cn-beijing.volces.com/api/v3` (默认)
- **上海**: `https://ark.cn-shanghai.volces.com/api/v3`
- **其他区域**: 请参考 Doubao 官方文档

示例：

```bash
python -m bi_agent.cli run "分析数据" \
    --data-dir ./data \
    --output-dir ./output \
    --provider doubao \
    --api-key YOUR_ARK_API_KEY \
    --base-url https://ark.cn-shanghai.volces.com/api/v3
```

## 与 OpenAI 对比

| 特性 | OpenAI | Doubao |
|------|--------|--------|
| API Key 环境变量 | `OPENAI_API_KEY` | `ARK_API_KEY` |
| 默认 Base URL | `https://api.openai.com/v1` | `https://ark.cn-beijing.volces.com/api/v3` |
| 工具调用 | ✅ | ✅ |
| 推理过程 | ❌ | ✅ (部分模型) |
| 流式响应 | ✅ | ✅ |

## 常见问题

### Q: 如何知道我的推理接入点 ID？

A: 推理接入点 ID 就是 `--model` 参数的值，在 Doubao 控制台中创建推理接入点后可以看到。

### Q: 支持哪些 Doubao 模型？

A: 支持所有通过 Doubao 控制台创建的推理接入点。默认使用 `doubao-seed-1-6-251015`，您可以根据实际情况修改。

### Q: 可以使用 reasoning_effort 参数吗？

A: 当前实现暂不支持 `reasoning_effort` 参数，但可以通过修改 `doubao_client.py` 添加此功能。

### Q: 如何切换区域？

A: 使用 `--base-url` 参数指定不同区域的 URL。

## 示例

### 完整示例

```bash
python -m bi_agent.cli run "分析销售数据，包括：1) 数据清洗 2) 月度趋势分析 3) 区域分布分析 4) 生成可视化图表 5) 输出完整报告" \
    --data-dir ./data/example \
    --output-dir ./output/doubao_analysis \
    --provider doubao \
    --model doubao-seed-1-6-251015 \
    --api-key YOUR_ARK_API_KEY \
    --max-steps 100 \
    --trajectory-file ./trajectories/doubao_task.json
```

## 技术支持

如有问题，请参考：
- [Doubao 官方文档](https://www.volcengine.com/docs/82379)
- BI-Agent GitHub Issues

