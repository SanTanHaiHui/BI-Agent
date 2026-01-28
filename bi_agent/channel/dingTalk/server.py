"""钉钉服务器（主入口）- 基于 Stream 模式"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

try:
    import dingtalk_stream
    from dingtalk_stream import AckMessage
except ImportError:
    dingtalk_stream = None
    AckMessage = None

from bi_agent.channel.dingTalk.api_client import DingTalkApiClient, DingTalkApiException
from bi_agent.channel.common import MessageQueue, MessageTask, UserManager, TaskHandler
from bi_agent.channel.feishu.message_deduplicator import MessageDeduplicator
from bi_agent.channel.dingTalk.report_reply import DingTalkReportReply
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.llm_clients.openai_client import OpenAIClient
from bi_agent.utils.llm_clients.doubao_client import DoubaoClient
from bi_agent.utils.llm_clients.qwen_client import QwenClient

# 加载环境变量
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DingTalkServer:
    """钉钉服务器（基于 Stream 模式）"""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_dir: Path = Path("./dingtalk_data"),
        llm_provider: str = "doubao",
        llm_model: Optional[str] = None,
    ):
        """初始化钉钉服务器

        Args:
            client_id: 应用 Key（从环境变量 DINGTALK_CLIENT_ID 读取）
            client_secret: 应用 Secret（从环境变量 DINGTALK_CLIENT_SECRET 读取）
            base_dir: 基础数据目录
            llm_provider: LLM 提供商（openai, doubao, qwen）
            llm_model: LLM 模型名称
        """
        if dingtalk_stream is None:
            raise ImportError("dingtalk_stream 未安装，请运行: pip install dingtalk-stream")

        # 从环境变量读取配置
        self.client_id = client_id or os.getenv("DINGTALK_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("DINGTALK_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("必须设置 DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET 环境变量")

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.api_client = DingTalkApiClient(self.client_id, self.client_secret, self.client_id)
        self.message_queue = MessageQueue(num_workers=3)
        self.deduplicator = MessageDeduplicator(expire_hours=7.5)
        self.user_manager = UserManager(self.base_dir / "users")

        self.llm_client = self._create_llm_client(llm_provider, llm_model)

        # 创建报告回复工具
        report_reply = DingTalkReportReply(self.api_client, self.base_dir / "output")

        # 创建任务处理器
        self.task_handler = TaskHandler(
            llm_client=self.llm_client,
            user_manager=self.user_manager,
            api_client=self.api_client,
            report_reply=report_reply,
            base_output_dir=self.base_dir / "output",
            channel_name="dingtalk",
        )

        # 创建钉钉流客户端
        credential = dingtalk_stream.Credential(self.client_id, self.client_secret)
        self.stream_client = dingtalk_stream.DingTalkStreamClient(credential)
        
        # 注册消息处理器
        self.stream_client.register_callback_handler(
            dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
            DingTalkMessageHandler(
                logger=logger,
                api_client=self.api_client,
                message_queue=self.message_queue,
                deduplicator=self.deduplicator,
                user_manager=self.user_manager,
                task_handler=self.task_handler,
            )
        )

        logger.info("钉钉服务器已初始化（Stream 模式）")

    def _create_llm_client(self, provider: str, model: Optional[str]) -> LLMClient:
        """创建 LLM 客户端"""
        provider_lower = provider.lower()

        if provider_lower == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("需要设置 OPENAI_API_KEY 环境变量")
            base_url = os.getenv("OPENAI_BASE_URL")
            return OpenAIClient(api_key=api_key, model=model or "gpt-4", base_url=base_url)

        elif provider_lower == "doubao":
            api_key = os.getenv("ARK_API_KEY")
            if not api_key:
                raise ValueError("需要设置 ARK_API_KEY 环境变量")
            base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
            return DoubaoClient(
                api_key=api_key,
                model=model or "doubao-seed-1-6-251015",
                base_url=base_url,
            )

        elif provider_lower == "qwen":
            api_key = os.getenv("QWEN_API_KEY")
            if not api_key:
                raise ValueError("需要设置 QWEN_API_KEY 环境变量")
            base_url = os.getenv("QWEN_BASE_URL")
            return QwenClient(api_key=api_key, model=model or "qwen-plus", base_url=base_url)

        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    def run(self, host: str = "0.0.0.0", port: int = 3000, debug: bool = False):
        """运行服务器（Stream 模式）

        Args:
            host: 主机地址（Stream 模式不需要，保留以兼容接口）
            port: 端口号（Stream 模式不需要，保留以兼容接口）
            debug: 是否开启调试模式
        """
        # 启动消息队列
        self.message_queue.start()

        logger.info("钉钉服务器启动（Stream 模式）")
        # 钉钉使用流模式，使用 start_forever() 启动
        self.stream_client.start_forever()


class DingTalkMessageHandler(dingtalk_stream.ChatbotHandler):
    """钉钉消息处理器（基于 Stream 模式）"""

    def __init__(
        self,
        logger: logging.Logger,
        api_client: DingTalkApiClient,
        message_queue: MessageQueue,
        deduplicator: MessageDeduplicator,
        user_manager: UserManager,
        task_handler: TaskHandler,
    ):
        """初始化消息处理器

        Args:
            logger: 日志记录器
            api_client: API 客户端
            message_queue: 消息队列
            deduplicator: 消息去重器
            user_manager: 用户管理器
            task_handler: 任务处理器
        """
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.logger = logger
        self.api_client = api_client
        self.message_queue = message_queue
        self.deduplicator = deduplicator
        self.user_manager = user_manager
        self.task_handler = task_handler

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        """处理消息回调

        Args:
            callback: 回调消息对象

        Returns:
            (状态码, 响应消息)
        """
        try:
            # 解析消息
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            message_id = incoming_message.message_id
            if not message_id:
                self.logger.warning("消息缺少 message_id，跳过处理")
                return AckMessage.STATUS_OK, 'OK'

            if self.deduplicator.is_processed(message_id):
                self.logger.info(f"消息已处理，跳过: {message_id}")
                return AckMessage.STATUS_OK, 'OK'

            self.deduplicator.mark_processed(message_id)

            user_id = incoming_message.sender_staff_id or incoming_message.sender_id
            if not user_id:
                self.logger.warning("消息缺少用户ID，跳过处理")
                return AckMessage.STATUS_OK, 'OK'

            conversation_id = incoming_message.conversation_id
            conversation_type = incoming_message.conversation_type
            is_group = conversation_type == '2'

            message_type = incoming_message.message_type
            self.logger.info(f"收到消息 - 类型: {message_type}, 用户: {user_id}, 会话: {conversation_id}, 群聊: {is_group}")

            if message_type == 'text' and incoming_message.text:
                text_content = incoming_message.text.content.strip()
                if text_content:
                    self.logger.info(f"收到文本消息: {text_content[:50]}...")
                    task = MessageTask(
                        message_id=message_id,
                        user_id=user_id,
                        open_id=user_id,  # 钉钉中 user_id 和 open_id 可能相同
                        chat_id=conversation_id,
                        message_type="text",
                        content=text_content,
                        handler=self._handle_text_message,
                    )
                    task.session_webhook = incoming_message.session_webhook
                    self.message_queue.put(task)
                else:
                    self.logger.warning("文本消息内容为空")
            
            elif message_type == 'picture' and incoming_message.image_content:
                download_code = incoming_message.image_content.download_code
                self.logger.info(f"收到图片消息，download_code: {download_code}")
                self.reply_text("已收到图片文件。", incoming_message)
            
            elif message_type == 'file':
                file_info = None
                if hasattr(incoming_message, 'extensions') and incoming_message.extensions:
                    content_data = incoming_message.extensions.get('content', {})
                    if isinstance(content_data, dict):
                        file_info = content_data
                    elif isinstance(content_data, str):
                        try:
                            import json
                            file_info = json.loads(content_data)
                        except:
                            pass
                
                if not file_info:
                    try:
                        import json
                        raw_data = callback.data if hasattr(callback, 'data') else {}
                        if isinstance(raw_data, dict):
                            content_data = raw_data.get('content', {})
                            if isinstance(content_data, dict):
                                file_info = content_data
                    except:
                        pass
                
                if file_info:
                    download_code = file_info.get('downloadCode') or file_info.get('download_code')
                    file_name = file_info.get('fileName') or file_info.get('file_name') or file_info.get('name', 'unknown')
                    
                    if download_code:
                        self.logger.info(f"收到文件消息 - 文件名: {file_name}, download_code: {download_code}")
                        
                        file_ext = Path(file_name).suffix.lower()
                        file_type = "excel" if file_ext in [".xlsx", ".xls"] else "csv" if file_ext == ".csv" else "other"
                        robot_code = incoming_message.robot_code
                        self.user_manager.add_file(
                            user_id=user_id,
                            file_key=download_code,  # 使用 download_code 作为 file_key
                            file_name=file_name,
                            file_type=file_type,
                            message_id=message_id,
                            robot_code=robot_code
                        )
                        
                        self.reply_text(
                            f"已收到文件：{file_name}\n请发送数据分析任务，我会在开始分析时下载文件。",
                            incoming_message
                        )
                    else:
                        self.logger.warning(f"文件消息中缺少 downloadCode，文件信息: {file_info}")
                        self.reply_text("无法识别文件信息，请重新上传文件。", incoming_message)
                else:
                    self.logger.warning(f"无法解析文件消息内容，消息类型: {message_type}")
                    self.reply_text("无法识别文件消息格式，请重新上传文件。", incoming_message)
            
            else:
                self.logger.info(f"收到未处理的消息类型: {message_type}")

            return AckMessage.STATUS_OK, 'OK'

        except Exception as e:
            self.logger.error(f"处理消息失败: {e}", exc_info=True)
            return AckMessage.STATUS_OK, 'OK'

    async def _handle_text_message(self, task: MessageTask):
        """处理文本消息（异步）"""
        task_content = task.content
        user_id = task.user_id
        chat_id = task.chat_id
        message_id = task.message_id
        session_webhook = getattr(task, 'session_webhook', None)

        # 判断是群聊还是私聊
        is_group = chat_id is not None and chat_id != ""
        receive_id_type = "conversation_id" if is_group else "user_id"
        receive_id = chat_id if is_group else user_id

        # 调用任务处理器
        await self.task_handler.handle_task(
            user_id=user_id,
            task=task_content,
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            chat_id=chat_id,
            message_id=message_id,
            session_webhook=session_webhook,
        )


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="钉钉 BI-Agent 服务器（Stream 模式）")
    parser.add_argument("--host", default="0.0.0.0", help="主机地址（Stream 模式不需要）")
    parser.add_argument("--port", type=int, default=8000, help="端口号（Stream 模式不需要）")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--llm-provider", default="doubao", help="LLM 提供商")
    parser.add_argument("--llm-model", help="LLM 模型名称")
    parser.add_argument("--base-dir", default="./dingtalk_data", help="基础数据目录")

    args = parser.parse_args()

    # 创建服务器
    server = DingTalkServer(
        base_dir=Path(args.base_dir),
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
    )

    # 运行服务器
    server.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
