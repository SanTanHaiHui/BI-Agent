"""Channel 基础接口和抽象类"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ApiClientBase(ABC):
    """API 客户端基类"""

    @abstractmethod
    def send_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: str,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None,
    ):
        """发送文本消息"""
        pass

    @abstractmethod
    def send_rich_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: Dict[str, Any],
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送富文本消息"""
        pass

    @abstractmethod
    def download_file(
        self,
        file_key: str,
        save_path: Path,
        message_id: Optional[str] = None,
        resource_type: str = "file"
    ) -> Path:
        """下载文件"""
        pass

    @abstractmethod
    def upload_image(self, image_path: Path) -> str:
        """上传图片并获取 image_key"""
        pass


class ReportReplyBase(ABC):
    """报告回复基类"""

    def __init__(self, api_client: ApiClientBase, output_dir: Path):
        """初始化报告回复工具

        Args:
            api_client: API 客户端
            output_dir: 输出目录（用于查找图片文件）
        """
        self.api_client = api_client
        self.output_dir = Path(output_dir)

    @abstractmethod
    def parse_markdown(self, md_path: Path) -> Dict[str, Any]:
        """解析 Markdown 文件"""
        pass

    @abstractmethod
    async def send_report(
        self,
        receive_id_type: str,
        receive_id: str,
        md_path: Path,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送报告"""
        pass

    @abstractmethod
    def _build_rich_text_content(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """构建富文本消息内容（平台特定格式）"""
        pass


class ChannelServerBase(ABC):
    """Channel 服务器基类"""

    def __init__(
        self,
        base_dir: Path,
        llm_provider: str = "doubao",
        llm_model: Optional[str] = None,
    ):
        """初始化 Channel 服务器

        Args:
            base_dir: 基础数据目录
            llm_provider: LLM 提供商
            llm_model: LLM 模型名称
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def run(self, host: str = "0.0.0.0", port: int = 3000, debug: bool = False):
        """运行服务器"""
        pass
