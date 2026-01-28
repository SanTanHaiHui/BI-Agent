# 飞书消息处理通道

飞书消息处理通道允许用户通过飞书与 BI-Agent 交互，上传数据文件并执行数据分析任务。

## 功能特性

- ✅ **接收文件**：支持所有文件类型
- ✅ **用户隔离**：为每个用户创建独立的文件夹
- ✅ **文件延迟下载**：用户发送文件后先不下载，等用户发送任务要求后再下载，节省资源
- ✅ **消息去重**：基于消息ID，7.5小时过期，避免重复处理
- ✅ **群聊支持**：允许所有群聊，私聊无需加前缀
- ✅ **异步处理**：采用消息队列（生产者消费者模式）异步处理任务
- ✅ **报告回复**：将 BI-Agent 生成的 Markdown 报告转换为飞书友好的格式，包括文字和图片

## 安装依赖

```bash
pip install Flask pycryptodome
```

## 配置

在 `.env` 文件中设置以下环境变量：

```bash
# 飞书应用配置
APP_ID=your_app_id
APP_SECRET=your_app_secret
APP_VERIFICATION_TOKEN=your_verification_token
ENCRYPT_KEY=your_encrypt_key  # 可选，如果启用加密则必须设置

# LLM 配置（选择一种）
# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选

# 豆包（推荐）
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3  # 可选

# 通义千问
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 可选
```

## 运行服务器

```bash
# 使用默认配置
python -m bi_agent.channel.feishu.server

# 或使用命令行参数
python -m bi_agent.channel.feishu.server \
    --host 0.0.0.0 \
    --port 3000 \
    --llm-provider doubao \
    --llm-model doubao-seed-1-6-251015 \
    --base-dir ./feishu_data
```

## 配置飞书应用

1. 在[飞书开发者后台](https://open.feishu.cn/app/)创建企业自建应用
2. 获取 `App ID`、`App Secret`、`Verification Token` 和 `Encrypt Key`
3. 在**事件订阅**页面配置请求网址 URL（需要公网可访问，可使用 ngrok 等工具进行内网穿透）
4. 订阅 `im.message.receive_v1` 事件
5. 在**权限管理**页面开通以下权限：
   - **必需权限（消息相关）**：
     - `im:message` - 获取与发送单聊、群组消息（或 `im:message:readonly` - 只读权限）
   - **必需权限（文件相关）**：
     - `im:resource` - 获取与发送单聊、群组消息中的资源文件（用于下载用户发送的文件）
   - **其他权限**：
     - 获取用户发给机器人的单聊消息
     - 上传图片或文件资源
   
   **注意**：使用消息资源 API 下载文件时，需要 `im:message` 或 `im:message:readonly` 权限。如果遇到权限错误，请确保已开通上述权限并重新发布应用。

## 使用流程

1. **上传文件**：用户在飞书中向机器人发送数据文件
2. **发送任务**：用户发送数据分析任务描述（例如："分析销售数据的月度趋势"）
3. **自动处理**：
   - 系统下载用户上传的文件
   - 调用 BI-Agent 执行数据分析任务
   - 生成分析报告（Markdown 格式，包含图表）
4. **查看结果**：BI-Agent 将分析报告以友好的格式发送回飞书，包括文字和图片

## 目录结构

```
feishu_data/
├── users/
│   ├── user_{user_id}/
│   │   ├── data/          # 用户上传的数据文件
│   │   └── output/        # 分析结果和报告
└── output/                # 全局输出目录
```

## 消息处理流程

1. **接收消息**：Flask 服务器接收飞书回调事件
2. **消息去重**：检查消息ID，避免重复处理
3. **消息分类**：
   - 文本消息 → 创建数据分析任务
   - 文件消息 → 记录文件信息（延迟下载）
4. **任务队列**：将任务添加到消息队列
5. **异步处理**：消费者线程从队列中取出任务并处理
6. **调用 BI-Agent**：执行数据分析任务
7. **发送结果**：将分析报告发送回飞书

## 注意事项

- 文件延迟下载：用户发送文件后，系统只记录文件信息，不立即下载。只有当用户发送任务要求时，才会下载文件。
- 消息去重：使用消息ID进行去重，消息记录保留 7.5 小时后自动过期。
- 群聊支持：所有群聊消息都会被处理，私聊消息无需加前缀即可触发。
- 文件类型：支持所有文件类型，不再限制为 Excel 或 CSV 文件。

## 故障排查

### 消息未处理

- 检查飞书应用的事件订阅配置是否正确
- 检查请求网址 URL 是否可访问
- 查看服务器日志了解详细错误信息

### 文件下载失败

- 检查飞书应用的权限配置
- 确认文件 key 是否正确
- 查看网络连接是否正常

### LLM 调用失败

- 检查 API Key 是否正确设置
- 确认 API 配额是否充足
- 查看 LLM 客户端的错误日志
