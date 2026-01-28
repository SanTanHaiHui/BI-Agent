"""消息去重器（基于消息ID，7.5小时过期）"""

import time
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MessageDeduplicator:
    """消息去重器

    使用消息ID存储已处理的消息，避免重复处理。
    消息过期时间：7.5小时
    """

    def __init__(self, expire_hours: float = 7.5):
        """初始化消息去重器

        Args:
            expire_hours: 消息过期时间（小时），默认 7.5 小时
        """
        self.expire_hours = expire_hours
        self.processed_messages: Dict[str, float] = {}  # message_id -> timestamp
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # 每小时清理一次过期消息

    def is_processed(self, message_id: str) -> bool:
        """检查消息是否已处理

        Args:
            message_id: 消息ID

        Returns:
            如果已处理返回 True，否则返回 False
        """
        # 定期清理过期消息
        self._cleanup_expired()

        if message_id in self.processed_messages:
            timestamp = self.processed_messages[message_id]
            # 检查是否过期
            if time.time() - timestamp < self.expire_hours * 3600:
                return True
            else:
                # 已过期，删除记录
                del self.processed_messages[message_id]

        return False

    def mark_processed(self, message_id: str):
        """标记消息为已处理

        Args:
            message_id: 消息ID
        """
        self.processed_messages[message_id] = time.time()

    def _cleanup_expired(self):
        """清理过期的消息记录"""
        current_time = time.time()
        # 每小时清理一次
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = current_time
        expire_seconds = self.expire_hours * 3600
        expired_ids = [
            msg_id for msg_id, timestamp in self.processed_messages.items()
            if current_time - timestamp >= expire_seconds
        ]

        for msg_id in expired_ids:
            del self.processed_messages[msg_id]

        if expired_ids:
            logger.info(f"清理了 {len(expired_ids)} 条过期消息记录")

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        self._cleanup_expired()
        return {
            "total_processed": len(self.processed_messages),
            "expire_hours": self.expire_hours,
        }
