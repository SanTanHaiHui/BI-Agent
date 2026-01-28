# Channel 模块

Channel 模块提供了不同平台的消息处理通道，目前支持飞书（Feishu）和钉钉（DingTalk）。

## 架构设计

### 基础接口和抽象类

- **`ApiClientBase`**: API 客户端基类，定义了发送消息、下载文件、上传图片等接口
- **`ReportReplyBase`**: 报告回复基类，定义了将 Markdown 报告转换为平台特定格式的接口
- **`ChannelServerBase`**: Channel 服务器基类，定义了服务器运行接口

### 通用组件

- **`UserManager`**: 用户文件夹管理器，管理用户上传的文件和输出目录
- **`TaskHandler`**: 任务处理器，负责调用 BI-Agent 处理数据分析任务
- **`MessageQueue`**: 消息队列，实现生产者-消费者模式处理消息
- **`MessageTask`**: 消息任务数据类
- **`UserFileInfo`**: 用户文件信息数据类

### 平台特定实现

- **飞书（Feishu）**: `bi_agent.channel.feishu`
  - `FeishuApiClient`: 飞书 API 客户端
  - `FeishuServer`: 飞书服务器（基于 Flask）
  - `ReportReply`: 飞书报告回复工具

- **钉钉（DingTalk）**: `bi_agent.channel.dingTalk`
  - `DingTalkApiClient`: 钉钉 API 客户端
  - `DingTalkServer`: 钉钉服务器（基于流模式）
  - `DingTalkReportReply`: 钉钉报告回复工具

## 使用方式

### 工厂模式

使用 `ChannelFactory` 创建不同平台的 Channel：

```python
from pathlib import Path
from bi_agent.channel.channel_factory import ChannelFactory

# 创建飞书 Channel
feishu_server = ChannelFactory.create_channel(
    channel_type="feishu",
    base_dir=Path("./feishu_data"),
    llm_provider="doubao",
    llm_model="doubao-seed-1-6-251015",
)

# 创建钉钉 Channel
dingtalk_server = ChannelFactory.create_channel(
    channel_type="dingtalk",
    base_dir=Path("./dingtalk_data"),
    llm_provider="doubao",
    llm_model="doubao-seed-1-6-251015",
)

# 运行服务器
feishu_server.run(host="0.0.0.0", port=8000)
dingtalk_server.run()  # 钉钉使用流模式，不需要指定 host 和 port
```

### 直接使用

也可以直接实例化具体的 Channel 服务器：

```python
from pathlib import Path
from bi_agent.channel.feishu.server import FeishuServer
from bi_agent.channel.dingTalk.server import DingTalkServer

# 飞书服务器
feishu_server = FeishuServer(
    base_dir=Path("./feishu_data"),
    llm_provider="doubao",
)

# 钉钉服务器
dingtalk_server = DingTalkServer(
    base_dir=Path("./dingtalk_data"),
    llm_provider="doubao",
)
```

## 环境变量配置

### 飞书（Feishu）

```bash
# 飞书应用配置
APP_ID=your_app_id
APP_SECRET=your_app_secret
APP_VERIFICATION_TOKEN=your_verification_token
ENCRYPT_KEY=your_encrypt_key  # 可选

# LLM 配置（根据使用的提供商选择）
ARK_API_KEY=your_ark_api_key  # 豆包
OPENAI_API_KEY=your_openai_api_key  # OpenAI
QWEN_API_KEY=your_qwen_api_key  # 通义千问
```

### 钉钉（DingTalk）

```bash
# 钉钉应用配置
DINGTALK_CLIENT_ID=your_client_id
DINGTALK_CLIENT_SECRET=your_client_secret
DINGTALK_ROBOT_CODE=your_robot_code

# LLM 配置（根据使用的提供商选择）
ARK_API_KEY=your_ark_api_key  # 豆包
OPENAI_API_KEY=your_openai_api_key  # OpenAI
QWEN_API_KEY=your_qwen_api_key  # 通义千问
```

## 依赖安装

### 飞书依赖

```bash
pip install Flask>=2.0.0
pip install pycryptodome>=3.18.0
```

### 钉钉依赖

```bash
pip install dingtalk-stream
pip install alibabacloud-dingtalk
```

## 运行示例

### 飞书服务器

```bash
python -m bi_agent.channel.feishu.server \
    --host 0.0.0.0 \
    --port 8000 \
    --llm-provider doubao \
    --base-dir ./feishu_data
```

### 钉钉服务器

```bash
python -m bi_agent.channel.dingTalk.server \
    --llm-provider doubao \
    --base-dir ./dingtalk_data
```

## 扩展新的 Channel

要添加新的平台支持，需要：

1. 实现 `ApiClientBase` 接口
2. 实现 `ReportReplyBase` 接口
3. 实现 `ChannelServerBase` 接口
4. 在 `ChannelFactory` 中注册新的 Channel 类型

示例：

```python
# 1. 实现 API 客户端
class NewPlatformApiClient(ApiClientBase):
    def send_text_message(self, ...):
        # 实现发送文本消息
        pass
    
    # 实现其他抽象方法
    ...

# 2. 实现报告回复工具
class NewPlatformReportReply(ReportReplyBase):
    def parse_markdown(self, ...):
        # 实现 Markdown 解析
        pass
    
    # 实现其他抽象方法
    ...

# 3. 实现服务器
class NewPlatformServer(ChannelServerBase):
    def run(self, ...):
        # 实现服务器运行逻辑
        pass

# 4. 在工厂中注册
class ChannelFactory:
    @staticmethod
    def create_channel(channel_type, ...):
        if channel_type == "new_platform":
            return NewPlatformServer(...)
        ...
```

## 注意事项

1. **消息去重**: 所有 Channel 都使用 `MessageDeduplicator` 来避免重复处理消息（7.5小时过期）

2. **异步处理**: 消息处理使用消息队列异步处理，避免阻塞主线程

3. **文件下载**: 文件下载采用延迟下载策略，只有在用户发送任务时才下载文件，节省资源

4. **用户隔离**: 每个用户有独立的数据目录和输出目录，确保数据隔离

5. **错误处理**: 所有 Channel 都实现了统一的错误处理机制，确保错误不会导致服务器崩溃
