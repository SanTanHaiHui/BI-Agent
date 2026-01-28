#!/usr/bin/env python3
"""测试报告发送功能

只测试将大模型生成的报告发送给用户的功能，不执行之前的接收消息和agent执行分析任务的过程。

使用方法:
    python -m tests.channel.feishu.test_report_send
    或
    python tests/channel/feishu/test_report_send.py

环境变量（.env 文件）:
    APP_ID: 飞书应用 ID（必需）
    APP_SECRET: 飞书应用密钥（必需）
    MESSAGE_ID: 消息 ID（群聊时用于回复，可选）
    IS_GROUP: 是否为群聊（true/false，默认为 false）
    OUTPUT_DIR: 报告文件所在目录（默认为 ./feishu_data/users/user_None/output）
    REPORT_FILE: 报告文件名（默认为自动查找最新的 .md 文件）

环境变量（.env 文件）:
    RECEIVE_ID: 接收者 ID（必需，open_id 或 user_id）
    RECEIVE_ID_TYPE: 接收者 ID 类型（默认为 open_id）
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from bi_agent.channel.feishu.api_client import FeishuApiClient
from bi_agent.channel.feishu.report_reply import ReportReply

# 加载环境变量
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    # 从环境变量读取配置（.env 文件）
    app_id = os.getenv("APP_ID")
    app_secret = os.getenv("APP_SECRET")
    
    # 从环境变量读取接收者信息（测试时需要设置）
    receive_id = os.getenv("RECEIVE_ID")
    receive_id_type = os.getenv("RECEIVE_ID_TYPE", "open_id")
    
    if not receive_id:
        logger.error("必须设置 RECEIVE_ID 环境变量（在 .env 文件中）")
        sys.exit(1)
    
    # 可选参数
    message_id = os.getenv("MESSAGE_ID")
    is_group_str = os.getenv("IS_GROUP", "false").lower()
    is_group = is_group_str in ("true", "1", "yes")
    output_dir_str = os.getenv("OUTPUT_DIR", "./feishu_data/users/user_None/output")
    output_dir = Path(output_dir_str).resolve()
    report_file = os.getenv("REPORT_FILE")

    # 验证必要参数
    if not app_id or not app_secret:
        logger.error("必须设置 APP_ID 和 APP_SECRET 环境变量（在 .env 文件中）")
        sys.exit(1)

    # 确定报告文件
    if report_file:
        md_path = output_dir / report_file
    else:
        # 自动查找最新的 .md 文件
        md_files = list(output_dir.glob("*.md"))
        if not md_files:
            logger.error(f"在 {output_dir} 中未找到 .md 文件")
            sys.exit(1)
        # 使用最新的文件
        md_path = max(md_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"自动选择报告文件: {md_path.name}")

    if not md_path.exists():
        logger.error(f"报告文件不存在: {md_path}")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("开始测试报告发送功能")
    logger.info(f"应用 ID: {app_id}")
    logger.info(f"接收者 ID 类型: {receive_id_type}")
    logger.info(f"接收者 ID: {receive_id}")
    logger.info(f"消息 ID: {message_id}")
    logger.info(f"是否为群聊: {is_group}")
    logger.info(f"报告文件: {md_path}")
    logger.info("=" * 80)

    try:
        # 创建 API 客户端
        api_client = FeishuApiClient(app_id, app_secret)

        # 创建报告回复工具
        report_reply = ReportReply(api_client, output_dir)

        # 发送报告
        logger.info("开始发送报告...")
        await report_reply.send_report(
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            md_path=md_path,
            message_id=message_id,
            is_group=is_group,
        )

        logger.info("=" * 80)
        logger.info("报告发送成功！")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"发送报告失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
