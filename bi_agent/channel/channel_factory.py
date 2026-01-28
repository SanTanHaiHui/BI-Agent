"""Channel 工厂（创建不同平台的 Channel）"""

import logging
from pathlib import Path
from typing import Optional

from bi_agent.channel.channel import ChannelServerBase
from bi_agent.channel.feishu.server import FeishuServer
from bi_agent.channel.dingTalk.server import DingTalkServer

logger = logging.getLogger(__name__)


class ChannelFactory:
    """Channel 工厂类"""

    @staticmethod
    def create_channel(
        channel_type: str,
        base_dir: Path,
        llm_provider: str = "doubao",
        llm_model: Optional[str] = None,
        **kwargs
    ) -> ChannelServerBase:
        """创建 Channel 服务器

        Args:
            channel_type: Channel 类型（feishu, dingtalk）
            base_dir: 基础数据目录
            llm_provider: LLM 提供商
            llm_model: LLM 模型名称
            **kwargs: 其他参数（传递给具体的 Channel 服务器）

        Returns:
            Channel 服务器实例

        Raises:
            ValueError: 不支持的 Channel 类型
        """
        channel_type_lower = channel_type.lower()

        if channel_type_lower == "feishu":
            return FeishuServer(
                base_dir=base_dir,
                llm_provider=llm_provider,
                llm_model=llm_model,
                **kwargs
            )
        elif channel_type_lower == "dingtalk":
            return DingTalkServer(
                base_dir=base_dir,
                llm_provider=llm_provider,
                llm_model=llm_model,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的 Channel 类型: {channel_type}，支持的类型: feishu, dingtalk")
