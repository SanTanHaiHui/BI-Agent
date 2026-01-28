"""飞书服务器（主入口）- 使用长连接方式"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from bi_agent.channel.feishu.api_client import FeishuApiClient, FeishuApiException
from bi_agent.channel.common import MessageQueue, MessageTask, UserManager, TaskHandler
from bi_agent.channel.feishu.message_deduplicator import MessageDeduplicator
from bi_agent.channel.feishu.report_reply import ReportReply
from bi_agent.channel.channel import ChannelServerBase
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


class FeishuServer(ChannelServerBase):
    """飞书服务器（使用长连接方式）"""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        lark_host: str = "https://open.feishu.cn",
        base_dir: Path = Path("./feishu_data"),
        llm_provider: str = "doubao",
        llm_model: Optional[str] = None,
    ):
        """初始化飞书服务器

        Args:
            app_id: 应用 ID（从环境变量 APP_ID 读取）
            app_secret: 应用密钥（从环境变量 APP_SECRET 读取）
            lark_host: 飞书 API 主机地址
            base_dir: 基础数据目录
            llm_provider: LLM 提供商（openai, doubao, qwen）
            llm_model: LLM 模型名称
        """
        # 从环境变量读取配置
        self.app_id = app_id or os.getenv("APP_ID")
        self.app_secret = app_secret or os.getenv("APP_SECRET")

        if not self.app_id or not self.app_secret:
            raise ValueError("必须设置 APP_ID, APP_SECRET 环境变量")

        self.lark_host = lark_host
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.api_client = FeishuApiClient(self.app_id, self.app_secret, self.lark_host)
        self.message_queue = MessageQueue(num_workers=3)
        self.deduplicator = MessageDeduplicator(expire_hours=7.5)
        self.user_manager = UserManager(self.base_dir / "users")

        self.llm_client = self._create_llm_client(llm_provider, llm_model)
        report_reply = ReportReply(self.api_client, self.base_dir / "output")
        self.task_handler = TaskHandler(
            llm_client=self.llm_client,
            user_manager=self.user_manager,
            api_client=self.api_client,
            report_reply=report_reply,
            base_output_dir=self.base_dir / "output",
            channel_name="feishu",
        )

        self.client = lark.Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_p2_im_message_receive_v1)
            .build()
        )
        self.ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("飞书服务器已初始化（长连接模式）")

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

    def _handle_p2_im_message_receive_v1(self, data: P2ImMessageReceiveV1) -> None:
        """处理接收消息事件（长连接方式）

        Args:
            data: P2ImMessageReceiveV1 事件数据
        """
        try:
            logger.info("=" * 80)
            logger.info("收到飞书消息事件（长连接）")
            
            message = data.event.message
            message_id = message.message_id
            message_type = message.message_type
            chat_type = message.chat_type
            
            logger.info(f"消息ID: {message_id}")
            logger.info(f"消息类型: {message_type}")
            logger.info(f"聊天类型: {chat_type}")

            if self.deduplicator.is_processed(message_id):
                logger.info(f"消息已处理，跳过: {message_id}")
                return

            self.deduplicator.mark_processed(message_id)
            logger.info(f"消息已标记为已处理: {message_id}")

            sender = data.event.sender
            open_id = sender.sender_id.open_id if hasattr(sender.sender_id, "open_id") else None
            user_id = sender.sender_id.user_id if hasattr(sender.sender_id, "user_id") else open_id
            logger.info(f"用户ID: {user_id}, OpenID: {open_id}")

            chat_id = message.chat_id if hasattr(message, "chat_id") else None
            is_group = chat_type == "group"
            receive_id_type = "chat_id" if is_group else "open_id"
            receive_id = chat_id if is_group else open_id
            logger.info(f"消息类型: {'群聊' if is_group else '私聊'}, 接收者类型: {receive_id_type}, 接收者ID: {receive_id}")

            if message_type == "text":
                logger.info(f"处理文本消息，原始内容: {message.content}")
                content = json.loads(message.content) if isinstance(message.content, str) else message.content
                text = content.get("text", "").strip() if isinstance(content, dict) else str(content).strip()
                logger.info(f"提取的文本内容: {text}")

                if text:
                    logger.info(f"创建文本消息任务: {text[:50]}...")
                    task = MessageTask(
                        message_id=message_id,
                        user_id=user_id,
                        open_id=open_id,
                        chat_id=chat_id,
                        message_type="text",
                        content=text,
                        handler=self._handle_text_message,
                    )
                    self.message_queue.put(task)
                    logger.info(f"任务已添加到队列: {message_id}")
                else:
                    logger.warning("文本内容为空，跳过处理")

            elif message_type == "file":
                # 文件消息
                logger.info(f"处理文件消息，原始内容: {message.content}")
                content = json.loads(message.content) if isinstance(message.content, str) else message.content
                file_key = content.get("file_key", "") if isinstance(content, dict) else ""
                file_name = content.get("file_name", "") if isinstance(content, dict) else ""
                
                logger.info(f"文件信息 - Key: {file_key}, 文件名: {file_name}")

                if file_key:
                    file_ext = Path(file_name).suffix.lower()
                    file_type = "excel" if file_ext in [".xlsx", ".xls"] else "csv" if file_ext == ".csv" else "other"
                    logger.info(f"文件类型: {file_type}, 扩展名: {file_ext}")
                    self.user_manager.add_file(user_id, file_key, file_name, file_type, message_id=message_id)
                    logger.info(f"发送文件确认消息到 {receive_id_type}:{receive_id}")
                    self.api_client.send_text_message(
                        receive_id_type,
                        receive_id,
                        f"已收到文件：{file_name}\n请发送数据分析任务，我会在开始分析时下载文件。",
                        message_id=message_id,
                        is_group=is_group,
                    )
                else:
                    logger.warning("文件消息中缺少 file_key")

            else:
                logger.warning(f"未处理的消息类型: {message_type}")

            logger.info("消息处理完成")

        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)

    async def _handle_text_message(self, task: MessageTask):
        """处理文本消息（异步）"""
        task_content = task.content
        user_id = task.user_id
        open_id = task.open_id
        chat_id = task.chat_id
        message_id = task.message_id  # 用于回复消息

        # 判断是群聊还是私聊
        is_group = chat_id is not None and chat_id != ""
        receive_id_type = "chat_id" if is_group else "open_id"
        receive_id = chat_id if is_group else open_id

        # 调用任务处理器
        await self.task_handler.handle_task(
            user_id=user_id,
            task=task_content,
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            chat_id=chat_id,
            message_id=message_id,  # 传递 message_id 用于回复
        )

    def run(self):
        """运行服务器（启动长连接）"""
        # 启动消息队列
        self.message_queue.start()

        logger.info("启动飞书长连接服务器...")
        # 启动长连接
        self.ws_client.start()


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="飞书 BI-Agent 服务器（长连接模式）")
    parser.add_argument("--llm-provider", default="doubao", help="LLM 提供商")
    parser.add_argument("--llm-model", help="LLM 模型名称")
    parser.add_argument("--base-dir", default="./feishu_data", help="基础数据目录")

    args = parser.parse_args()

    # 创建服务器
    server = FeishuServer(
        base_dir=Path(args.base_dir),
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
    )

    # 运行服务器（启动长连接）
    server.run()


if __name__ == "__main__":
    main()
