"""Channel 通用组件（用户管理器、任务处理器、消息队列等）"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread

from bi_agent.channel.channel import ApiClientBase, ReportReplyBase

logger = logging.getLogger(__name__)


@dataclass
class UserFileInfo:
    """用户文件信息"""
    file_key: str
    file_name: str
    file_type: str  # excel, csv, etc.
    upload_time: float
    message_id: Optional[str] = None
    downloaded: bool = False
    local_path: Optional[Path] = None
    robot_code: Optional[str] = None  # 钉钉需要，用于文件下载


class UserManager:
    """用户文件夹管理器

    为每个用户创建独立的文件夹，管理用户上传的文件。
    """

    def __init__(self, base_dir: Path):
        """初始化用户管理器

        Args:
            base_dir: 基础目录路径
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.user_files: Dict[str, List[UserFileInfo]] = {}  # user_id -> [UserFileInfo]
        logger.info(f"用户管理器已初始化，基础目录: {self.base_dir}")

    def get_user_dir(self, user_id: str) -> Path:
        """获取用户目录

        Args:
            user_id: 用户ID

        Returns:
            用户目录路径
        """
        user_dir = self.base_dir / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def get_user_data_dir(self, user_id: str) -> Path:
        """获取用户数据目录（用于存放上传的文件）

        Args:
            user_id: 用户ID

        Returns:
            用户数据目录路径
        """
        data_dir = self.get_user_dir(user_id) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_user_output_dir(self, user_id: str) -> Path:
        """获取用户输出目录（用于存放分析结果）

        Args:
            user_id: 用户ID

        Returns:
            用户输出目录路径
        """
        output_dir = self.get_user_dir(user_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def add_file(self, user_id: str, file_key: str, file_name: str, file_type: str, message_id: Optional[str] = None, robot_code: Optional[str] = None):
        """添加文件记录（延迟下载，先不下载）

        Args:
            user_id: 用户ID
            file_key: 文件 key
            file_name: 文件名
            file_type: 文件类型
            message_id: 消息 ID（用于下载文件）
            robot_code: 机器人 Code（钉钉需要，用于文件下载）
        """
        import time
        file_info = UserFileInfo(
            file_key=file_key,
            file_name=file_name,
            file_type=file_type,
            upload_time=time.time(),
            message_id=message_id,
            downloaded=False,
            robot_code=robot_code,
        )

        if user_id not in self.user_files:
            self.user_files[user_id] = []

        self.user_files[user_id].append(file_info)
        logger.info(f"用户 {user_id} 添加文件记录: {file_name} (key: {file_key}, message_id: {message_id})")

    def download_file(
        self,
        user_id: str,
        file_key: str,
        api_client: ApiClientBase,
        save_path: Optional[Path] = None,
        message_id: Optional[str] = None,
        resource_type: str = "file",
        robot_code: Optional[str] = None
    ) -> Path:
        """下载文件

        Args:
            user_id: 用户ID
            file_key: 文件 key
            api_client: API 客户端
            save_path: 保存路径（如果为 None，则使用默认路径）
            message_id: 消息 ID（如果提供，使用消息资源 API）
            resource_type: 资源类型（file, image 等，默认为 file）
            robot_code: 机器人 Code（钉钉需要）

        Returns:
            保存的文件路径
        """
        # 查找文件信息
        file_info = self._find_file(user_id, file_key)
        if not file_info:
            raise ValueError(f"未找到文件记录: {file_key}")

        # 如果已下载，直接返回
        if file_info.downloaded and file_info.local_path and file_info.local_path.exists():
            logger.info(f"文件已存在，跳过下载: {file_info.local_path}")
            return file_info.local_path

        # 确定保存路径
        if save_path is None:
            data_dir = self.get_user_data_dir(user_id)
            save_path = data_dir / file_info.file_name

        file_message_id = file_info.message_id or message_id
        resource_type_param = resource_type or "file"
        actual_robot_code = getattr(file_info, 'robot_code', None) or robot_code
        
        import inspect
        sig = inspect.signature(api_client.download_file)
        if 'robot_code' in sig.parameters:
            api_client.download_file(file_key, save_path, message_id=file_message_id, resource_type=resource_type_param, robot_code=actual_robot_code)
        else:
            api_client.download_file(file_key, save_path, message_id=file_message_id, resource_type=resource_type_param)

        # 更新文件信息
        file_info.downloaded = True
        file_info.local_path = save_path
        logger.info(f"文件已下载: {save_path}")

        return save_path

    def download_all_files(self, user_id: str, api_client: ApiClientBase, message_id: Optional[str] = None, robot_code: Optional[str] = None):
        """下载用户的所有文件

        Args:
            user_id: 用户ID
            api_client: API 客户端
            message_id: 消息 ID（如果提供，使用消息资源 API）
            robot_code: 机器人 Code（钉钉需要）
        """
        if user_id not in self.user_files:
            return

        for file_info in self.user_files[user_id]:
            if not file_info.downloaded:
                try:
                    file_message_id = file_info.message_id or message_id
                    file_robot_code = getattr(file_info, 'robot_code', None) or robot_code
                    self.download_file(user_id, file_info.file_key, api_client, message_id=file_message_id, robot_code=file_robot_code)
                except Exception as e:
                    logger.error(f"下载文件失败 {file_info.file_name}: {e}")

    def get_user_files(self, user_id: str) -> List[UserFileInfo]:
        """获取用户的所有文件

        Args:
            user_id: 用户ID

        Returns:
            文件信息列表
        """
        return self.user_files.get(user_id, [])

    def _find_file(self, user_id: str, file_key: str) -> Optional[UserFileInfo]:
        """查找文件信息

        Args:
            user_id: 用户ID
            file_key: 文件 key

        Returns:
            文件信息，如果不存在返回 None
        """
        if user_id not in self.user_files:
            return None

        for file_info in self.user_files[user_id]:
            if file_info.file_key == file_key:
                return file_info

        return None


@dataclass
class MessageTask:
    """消息任务"""
    message_id: str
    user_id: str
    open_id: str
    chat_id: Optional[str]
    message_type: str  # text, file
    content: Any
    handler: Callable  # 处理函数


class MessageQueue:
    """消息队列（生产者消费者模式）"""

    def __init__(self, num_workers: int = 3):
        """初始化消息队列

        Args:
            num_workers: 消费者线程数量
        """
        self.queue: Queue = Queue()
        self.num_workers = num_workers
        self.workers: list[Thread] = []
        self.running = False

    def start(self):
        """启动消费者线程"""
        if self.running:
            return

        self.running = True
        for i in range(self.num_workers):
            worker = Thread(target=self._worker, daemon=True, name=f"MessageWorker-{i}")
            worker.start()
            self.workers.append(worker)
        logger.info(f"消息队列已启动，工作线程数: {self.num_workers}")

    def stop(self):
        """停止消费者线程"""
        self.running = False
        # 等待所有任务完成
        self.queue.join()
        logger.info("消息队列已停止")

    def put(self, task: MessageTask):
        """添加任务到队列（生产者）

        Args:
            task: 消息任务
        """
        self.queue.put(task)

    def _worker(self):
        """工作线程（消费者）"""
        while self.running:
            try:
                task = self.queue.get(timeout=1)
                if task is None:
                    continue

                logger.info(f"开始处理任务: {task.message_id}")
                try:
                    # 执行处理函数
                    if asyncio.iscoroutinefunction(task.handler):
                        # 如果是异步函数，需要在新的事件循环中运行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(task.handler(task))
                        loop.close()
                    else:
                        task.handler(task)
                    logger.info(f"任务处理完成: {task.message_id}")
                except Exception as e:
                    logger.error(f"处理任务失败 {task.message_id}: {e}", exc_info=True)
                finally:
                    self.queue.task_done()
            except Empty:
                # 队列为空是正常情况，继续等待
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"工作线程错误: {e}", exc_info=True)


class TaskHandler:
    """任务处理器

    负责调用 BI-Agent 处理数据分析任务。
    """

    def __init__(
        self,
        llm_client,
        user_manager: UserManager,
        api_client: ApiClientBase,
        report_reply: ReportReplyBase,
        base_output_dir: Path,
        channel_name: str = "channel",
    ):
        """初始化任务处理器

        Args:
            llm_client: LLM 客户端
            user_manager: 用户管理器
            api_client: API 客户端
            report_reply: 报告回复工具
            base_output_dir: 基础输出目录
            channel_name: Channel 名称（用于 session_id）
        """
        self.llm_client = llm_client
        self.user_manager = user_manager
        self.api_client = api_client
        self.report_reply = report_reply
        self.base_output_dir = Path(base_output_dir)
        self.channel_name = channel_name

    async def handle_task(
        self,
        user_id: str,
        task: str,
        receive_id_type: str,
        receive_id: str,
        chat_id: Optional[str] = None,
        message_id: Optional[str] = None,
        session_webhook: Optional[str] = None,
    ):
        """处理任务

        Args:
            user_id: 用户ID
            task: 任务描述
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            chat_id: 群聊 ID（如果是群聊）
            message_id: 消息 ID（用于回复）
            session_webhook: 会话 webhook（Stream 模式使用）
        """
        from bi_agent.agent.agent import Agent
        
        try:
            # 判断是否为群聊
            is_group = chat_id is not None and chat_id != ""
            
            # 发送开始处理消息
            self.api_client.send_text_message(
                receive_id_type,
                receive_id,
                "正在处理您的数据分析任务，请稍候...",
                message_id=message_id,
                is_group=is_group,
                session_webhook=session_webhook,
            )

            # 获取用户目录
            data_dir = self.user_manager.get_user_data_dir(user_id)
            output_dir = self.user_manager.get_user_output_dir(user_id)

            # 下载用户的所有文件（延迟下载：现在才下载）
            logger.info(f"开始下载用户 {user_id} 的文件...")
            robot_code = getattr(self.api_client, '_robot_code', None)
            self.user_manager.download_all_files(user_id, self.api_client, robot_code=robot_code)

            data_files = [f for f in data_dir.glob("*") if f.is_file()]
            if not data_files:
                self.api_client.send_text_message(
                    receive_id_type,
                    receive_id,
                    "未找到数据文件，请先上传数据文件。",
                    message_id=message_id,
                    is_group=is_group,
                    session_webhook=session_webhook,
                )
                return

            agent = Agent(
                llm_client=self.llm_client,
                data_dir=str(data_dir),
                output_dir=str(output_dir),
                max_steps=50,
                verbose=False,
                user_id=user_id,
                session_id=f"{self.channel_name}_{user_id}_{chat_id or 'private'}",
            )

            # 执行任务
            logger.info(f"开始执行任务: {task}")
            execution = await agent.run(task)

            # 处理结果
            if execution.success:
                # 查找生成的报告文件
                report_files = list(output_dir.glob("*.md"))
                if report_files:
                    # 使用最新的报告文件
                    report_file = max(report_files, key=lambda p: p.stat().st_mtime)

                    # 发送报告（使用富文本格式）
                    await self.report_reply.send_report(
                        receive_id_type,
                        receive_id,
                        report_file,
                        message_id=message_id,
                        is_group=is_group,
                        session_webhook=session_webhook
                    )

                    logger.info(f"任务完成，报告已发送: {report_file}")
                else:
                    # 如果没有报告文件，发送执行结果
                    result_text = execution.final_result or "任务已完成"
                    self.api_client.send_text_message(
                        receive_id_type,
                        receive_id,
                        f"任务完成！\n\n{result_text}",
                        message_id=message_id,
                        is_group=is_group,
                        session_webhook=session_webhook,
                    )
            else:
                # 任务失败
                error_msg = execution.final_result or "任务执行失败"
                self.api_client.send_text_message(
                    receive_id_type,
                    receive_id,
                    f"任务执行失败：\n\n{error_msg}",
                    message_id=message_id,
                    is_group=is_group,
                    session_webhook=session_webhook,
                )
                logger.error(f"任务执行失败: {error_msg}")

        except Exception as e:
            logger.error(f"处理任务时出错: {e}", exc_info=True)
            is_group = chat_id is not None and chat_id != ""
            self.api_client.send_text_message(
                receive_id_type,
                receive_id,
                f"处理任务时出错：{str(e)}",
                message_id=message_id,
                is_group=is_group,
                session_webhook=session_webhook,
            )
