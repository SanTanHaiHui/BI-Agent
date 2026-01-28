"""Channel 模块

提供不同平台的消息处理 Channel，包括飞书和钉钉。
"""

from bi_agent.channel.channel_factory import ChannelFactory
from bi_agent.channel.channel import ApiClientBase, ReportReplyBase, ChannelServerBase
from bi_agent.channel.common import UserManager, TaskHandler, MessageQueue, MessageTask, UserFileInfo

__all__ = [
    'ChannelFactory',
    'ApiClientBase',
    'ReportReplyBase',
    'ChannelServerBase',
    'UserManager',
    'TaskHandler',
    'MessageQueue',
    'MessageTask',
    'UserFileInfo',
]
