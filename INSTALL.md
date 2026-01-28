# 安装指南

## 前置要求

- Python 3.10 或更高版本
- pip 包管理器

## 安装步骤

### 1. 克隆或下载项目

```bash
cd /path/to/BI-Agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

创建 `.env` 文件（可选）：

```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Doubao (豆包)
ARK_API_KEY=your_doubao_api_key_here
```

或者在使用时通过 `--api-key` 参数提供。

**支持的提供商：**
- **OpenAI**: 使用 `OPENAI_API_KEY` 环境变量
- **Doubao (豆包)**: 使用 `ARK_API_KEY` 环境变量

### 4. 生成示例数据（可选）

```bash
python scripts/generate_example_data.py
```

这将生成示例销售数据到 `data/example/` 目录。

## 验证安装

运行以下命令验证安装：

```bash
python -m bi_agent.cli show-config
```

如果看到配置信息，说明安装成功。

## 常见问题

### Q: 安装 pandas 失败？

A: 确保使用 Python 3.10+，并尝试使用 `pip install --upgrade pip` 升级 pip。

### Q: 找不到模块？

A: 确保在项目根目录下运行命令，或使用 `python -m bi_agent.cli` 而不是直接运行脚本。

### Q: API Key 错误？

A: 确保 API Key 正确，并且账户有足够的额度。

