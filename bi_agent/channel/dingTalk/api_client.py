"""钉钉 API 客户端"""

import os
import json
import logging
import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from alibabacloud_dingtalk.oauth2_1_0.client import Client as dingtalkoauth2_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.oauth2_1_0 import models as dingtalkoauth_2__1__0_models
from alibabacloud_dingtalk.robot_1_0.client import Client as dingtalkrobot_1_0Client
from alibabacloud_dingtalk.robot_1_0 import models as dingtalkrobot__1__0_models
from alibabacloud_tea_util import models as util_models

from bi_agent.channel.channel import ApiClientBase

logger = logging.getLogger(__name__)


class DingTalkApiClient(ApiClientBase):
    """钉钉 API 客户端"""

    def __init__(self, client_id: str, client_secret: str, robot_code: str):
        """初始化钉钉 API 客户端

        Args:
            client_id: 应用 Key
            client_secret: 应用 Secret
            robot_code: 机器人 Code
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._robot_code = robot_code
        self._token_cache = {"token": None, "expire": 0}
        self._config = self._create_config()

    def _create_config(self) -> open_api_models.Config:
        """创建 API 配置"""
        config = open_api_models.Config()
        config.protocol = 'https'
        config.region_id = 'central'
        return config

    @property
    def access_token(self) -> str:
        """获取访问令牌（自动刷新）"""
        now = time.time()
        if self._token_cache["token"] and now < self._token_cache["expire"]:
            return self._token_cache["token"]
        
        self._authorize_access_token()
        return self._token_cache["token"]

    def _authorize_access_token(self):
        """获取访问令牌"""
        client = dingtalkoauth2_1_0Client(self._config)
        get_access_token_request = dingtalkoauth_2__1__0_models.GetAccessTokenRequest(
            app_key=self._client_id,
            app_secret=self._client_secret
        )
        try:
            response = client.get_access_token(get_access_token_request)
            token = getattr(response.body, "access_token", None)
            expire_in = getattr(response.body, "expire_in", 7200)
            if token:
                now = time.time()
                self._token_cache["token"] = token
                self._token_cache["expire"] = now + expire_in - 200  # 提前200秒刷新
                logger.info(f"钉钉访问令牌已更新，有效期: {expire_in} 秒")
            else:
                raise DingTalkApiException(code=-1, msg="访问令牌为空")
        except Exception as err:
            logger.error(f"获取钉钉访问令牌失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"获取访问令牌失败: {err}")

    def send_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: str,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送文本消息

        Args:
            receive_id_type: 接收者 ID 类型（钉钉中通常不需要，保留以兼容接口）
            receive_id: 接收者 ID（群聊时为 open_conversation_id，私聊时为 user_id）
            content: 消息内容（文本）
            message_id: 要回复的消息 ID（群聊时可选）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（Stream 模式推荐使用，优先级最高）
        """
        # 如果提供了 session_webhook，优先使用（Stream 模式推荐方式）
        if session_webhook:
            # 尝试从 content 中提取标题
            title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else None
            self._send_via_webhook(session_webhook, content, title=title)
            return

        # 否则使用 OpenAPI 方式
        access_token = self.access_token
        if not access_token:
            raise DingTalkApiException(code=-1, msg="无法获取访问令牌")

        # 尝试从 content 中提取标题
        title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else None

        if is_group:
            # 群聊消息
            self._send_group_message(access_token, receive_id, content, title=title)
        else:
            # 私聊消息
            self._send_private_message(access_token, [receive_id], content, title=title)

    def _send_group_message(self, access_token: str, open_conversation_id: str, content: str, title: Optional[str] = None):
        """发送群聊消息（Markdown 格式）
        
        根据钉钉官方文档，msgParam 应包含 title 和 text 两个字段。
        title: 首屏会话中透出的展示内容
        text: Markdown 文本内容
        
        Args:
            access_token: 访问令牌
            open_conversation_id: 会话 ID
            content: Markdown 文本内容
            title: 消息标题（如果未提供，从 content 中提取或使用默认值）
        """
        # 如果没有提供标题，尝试从 Markdown 内容中提取第一个标题
        if not title:
            title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = "数据分析报告"
        
        # 根据官方文档，msgParam 应包含 title 和 text 字段
        msg_param = json.dumps({
            "title": title,
            "text": content
        }, ensure_ascii=False)
        msg_key = 'sampleMarkdown'
        
        # 输出完整的消息体到日志
        request_body = {
            "msgKey": msg_key,
            "msgParam": msg_param,
            "openConversationId": open_conversation_id,
            "robotCode": self._robot_code
        }
        logger.info(f"[钉钉] 发送群聊 Markdown 消息 - 完整消息体:")
        logger.info(f"  msgKey: {msg_key}")
        logger.info(f"  msgParam: {msg_param}")
        logger.info(f"  openConversationId: {open_conversation_id}")
        logger.info(f"  robotCode: {self._robot_code}")
        logger.info(f"  Markdown 内容长度: {len(content)} 字符")
        logger.info(f"  Markdown 内容预览:\n{content[:500]}..." if len(content) > 500 else f"  Markdown 完整内容:\n{content}")
        
        client = dingtalkrobot_1_0Client(self._config)
        org_group_send_headers = dingtalkrobot__1__0_models.OrgGroupSendHeaders()
        org_group_send_headers.x_acs_dingtalk_access_token = access_token
        org_group_send_request = dingtalkrobot__1__0_models.OrgGroupSendRequest(
            msg_param=msg_param,
            msg_key=msg_key,
            open_conversation_id=open_conversation_id,
            robot_code=self._robot_code
        )
        try:
            response = client.org_group_send_with_options(
                org_group_send_request,
                org_group_send_headers,
                util_models.RuntimeOptions()
            )
            logger.info(f"群聊消息已发送: {open_conversation_id}")
            return response
        except Exception as err:
            logger.error(f"发送群聊消息失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"发送群聊消息失败: {err}")

    def _send_private_message(self, access_token: str, user_ids: list, content: str, title: Optional[str] = None):
        """发送私聊消息（Markdown 格式）
        
        根据钉钉官方文档，msgParam 应包含 title 和 text 两个字段。
        title: 首屏会话中透出的展示内容
        text: Markdown 文本内容
        
        Args:
            access_token: 访问令牌
            user_ids: 用户 ID 列表
            content: Markdown 文本内容
            title: 消息标题（如果未提供，从 content 中提取或使用默认值）
        """
        # 如果没有提供标题，尝试从 Markdown 内容中提取第一个标题
        if not title:
            title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = "数据分析报告"
        
        # 根据官方文档，msgParam 应包含 title 和 text 字段
        msg_key = 'sampleMarkdown'
        msg_param = json.dumps({
            "title": title,
            "text": content
        }, ensure_ascii=False)

        # 输出完整的消息体到日志
        request_body = {
            "msgKey": msg_key,
            "msgParam": msg_param,
            "userIds": user_ids,
            "robotCode": self._robot_code
        }
        logger.info(f"[钉钉] 发送私聊 Markdown 消息 - 完整消息体:")
        logger.info(f"  msgKey: {msg_key}")
        logger.info(f"  msgParam: {msg_param}")
        logger.info(f"  userIds: {user_ids}")
        logger.info(f"  robotCode: {self._robot_code}")
        logger.info(f"  Markdown 内容长度: {len(content)} 字符")
        logger.info(f"  Markdown 内容预览:\n{content[:500]}..." if len(content) > 500 else f"  Markdown 完整内容:\n{content}")

        client = dingtalkrobot_1_0Client(self._config)
        batch_send_otoheaders = dingtalkrobot__1__0_models.BatchSendOTOHeaders()
        batch_send_otoheaders.x_acs_dingtalk_access_token = access_token
        batch_send_otorequest = dingtalkrobot__1__0_models.BatchSendOTORequest(
            robot_code=self._robot_code,
            user_ids=user_ids,
            msg_key=msg_key,
            msg_param=msg_param
        )
        try:
            response = client.batch_send_otowith_options(
                batch_send_otorequest,
                batch_send_otoheaders,
                util_models.RuntimeOptions()
            )
            logger.info(f"私聊消息已发送: {user_ids}")
            return response
        except Exception as err:
            logger.error(f"发送私聊消息失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"发送私聊消息失败: {err}")

    def _send_via_webhook(self, session_webhook: str, content: str, title: Optional[str] = None):
        """通过 session_webhook 发送消息（Stream 模式推荐方式）
        
        根据钉钉官方文档，Webhook 方式发送 Markdown 消息的格式为：
        {
          "msgtype": "markdown",
          "markdown": {
            "title": "标题",
            "text": "Markdown 内容"
          }
        }
        
        Args:
            session_webhook: 会话 webhook URL
            content: Markdown 文本内容
            title: 消息标题（如果未提供，从 content 中提取或使用默认值）
        """
        import requests
        
        # 如果没有提供标题，尝试从 Markdown 内容中提取第一个标题
        if not title:
            title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = "数据分析报告"
        
        request_headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*',
        }
        
        # 根据官方文档，Webhook 方式使用 msgtype="markdown" 格式
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[钉钉] 通过 Webhook 发送 Markdown 消息 - 完整消息体:")
        logger.info(f"  msgtype: markdown")
        logger.info(f"  title: {title}")
        logger.info(f"  Markdown 内容长度: {len(content)} 字符")
        logger.info(f"  Markdown 内容预览:\n{content[:500]}..." if len(content) > 500 else f"  Markdown 完整内容:\n{content}")
        logger.info(f"  完整 payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        try:
            response = requests.post(session_webhook, headers=request_headers, json=payload)
            response.raise_for_status()
            logger.info(f"通过 webhook 发送 Markdown 消息成功")
            return response.json()
        except Exception as err:
            logger.error(f"通过 webhook 发送消息失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"通过 webhook 发送消息失败: {err}")

    def send_rich_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: Dict[str, Any],
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送富文本消息（转换为 Markdown 格式）

        注意：钉钉使用 Markdown 格式发送消息，msgKey 为 sampleMarkdown。

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            content: 富文本内容（字典格式或 Markdown 字符串）
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（Stream 模式推荐使用）
        """
        # 如果 content 已经是字符串（Markdown 格式），直接使用
        if isinstance(content, str):
            markdown_content = content
        else:
            # 否则转换为 Markdown 格式
            markdown_content = self._convert_rich_text_to_markdown(content)
        
        # 使用 Markdown 格式发送消息
        self.send_text_message(
            receive_id_type,
            receive_id,
            markdown_content,
            message_id=message_id,
            is_group=is_group,
            session_webhook=session_webhook
        )

    def _convert_rich_text_to_markdown(self, content: Dict[str, Any]) -> str:
        """将富文本内容转换为钉钉 Markdown 格式
        
        支持的 Markdown 语法：
        - 标题: # 一级标题, ## 二级标题, ...
        - 引用: > 引用内容
        - 文字加粗: **bold**
        - 文字斜体: *italic*
        - 链接: [text](url)
        - 图片: ![](url)
        - 无序列表: - item
        - 有序列表: 1. item
        - 换行: \n (建议\n前后分别加2个空格)
        """
        if "zh_cn" in content:
            zh_cn = content["zh_cn"]
            title = zh_cn.get("title", "")
            content_data = zh_cn.get("content", "")
            images = zh_cn.get("images", [])
            
            lines = []
            
            # 添加标题
            if title:
                lines.append(f"# {title}")
                lines.append("")  # 空行
            
            # 处理内容
            # 1. content 是字符串（Markdown 格式）
            if isinstance(content_data, str):
                # 处理换行：确保 \n 前后有2个空格（如果还没有）
                # 将单个 \n 替换为 "  \n  "（前后各2个空格）
                content_data = re.sub(r'([^\n])\n([^\n])', r'\1  \n  \2', content_data)
                lines.append(content_data)
            # 2. content 是二维数组（飞书格式）
            elif isinstance(content_data, list):
                for row in content_data:
                    if isinstance(row, list):
                        # 行是元素列表
                        row_text = []
                        for elem in row:
                            if isinstance(elem, dict):
                                tag = elem.get("tag", "")
                                if tag == "text":
                                    text = elem.get("text", "")
                                    # 处理文本格式
                                    if elem.get("style"):
                                        styles = elem.get("style", [])
                                        if "bold" in styles:
                                            text = f"**{text}**"
                                        if "italic" in styles:
                                            text = f"*{text}*"
                                    row_text.append(text)
                                elif tag == "img":
                                    image_key = elem.get("image_key", "")
                                    if image_key:
                                        row_text.append(f"![]({image_key})")
                                    else:
                                        row_text.append("[图片]")
                                elif tag == "a":
                                    href = elem.get("href", "")
                                    link_text = elem.get("text", "")
                                    row_text.append(f"[{link_text}]({href})")
                        if row_text:
                            lines.append("".join(row_text))
                    elif isinstance(row, dict):
                        # 行本身是元素
                        tag = row.get("tag", "")
                        if tag == "text":
                            text = row.get("text", "")
                            lines.append(text)
                        elif tag == "img":
                            image_key = row.get("image_key", "")
                            if image_key:
                                lines.append(f"![]({image_key})")
                            else:
                                lines.append("[图片]")
                    elif isinstance(row, str):
                        # 行是字符串
                        lines.append(row)
            
            # 添加图片（如果有）
            if images:
                lines.append("")  # 空行
                for image_url in images:
                    lines.append(f"![]({image_url})")
            
            # 合并所有行，确保换行格式正确
            result = "\n".join(lines)
            # 确保换行前后有2个空格（钉钉要求）
            result = re.sub(r'([^\n])\n([^\n])', r'\1  \n  \2', result)
            
            return result
        
        # 如果不是预期的格式，尝试直接转换
        if isinstance(content, str):
            return content
        
        return str(content)

    def download_file(
        self,
        file_key: str,
        save_path: Path,
        message_id: Optional[str] = None,
        resource_type: str = "file",
        robot_code: Optional[str] = None
    ) -> Path:
        """下载文件（使用 downloadCode）

        钉钉 Stream 模式使用 downloadCode 下载文件。
        使用钉钉 SDK 的 robot_message_file_download 方法。

        Args:
            file_key: 文件 downloadCode
            save_path: 保存路径
            message_id: 消息 ID（如果提供，钉钉中可能不需要）
            resource_type: 资源类型
            robot_code: 机器人 Code（如果提供，优先使用；否则使用默认的 robot_code）

        Returns:
            保存的文件路径
        """
        access_token = self.access_token
        if not access_token:
            raise DingTalkApiException(code=-1, msg="无法获取访问令牌")
        
        # 使用提供的 robot_code 或默认的
        actual_robot_code = robot_code or self._robot_code
        if not actual_robot_code:
            raise DingTalkApiException(code=-1, msg="robot_code 不能为空")
        
        # 使用钉钉 SDK 下载文件
        client = dingtalkrobot_1_0Client(self._config)
        robot_message_file_download_headers = dingtalkrobot__1__0_models.RobotMessageFileDownloadHeaders()
        robot_message_file_download_headers.x_acs_dingtalk_access_token = access_token
        
        robot_message_file_download_request = dingtalkrobot__1__0_models.RobotMessageFileDownloadRequest(
            download_code=file_key,
            robot_code=actual_robot_code
        )
        
        logger.info(f"开始下载文件 - downloadCode: {file_key[:20]}..., robotCode: {actual_robot_code}")
        
        try:
            # 第一步：调用 API 获取下载链接
            response = client.robot_message_file_download_with_options(
                robot_message_file_download_request,
                robot_message_file_download_headers,
                util_models.RuntimeOptions()
            )
            
            # 从响应体中获取 downloadUrl
            if not hasattr(response, 'body'):
                raise DingTalkApiException(code=-1, msg="响应中缺少 body 字段")
            
            response_body = response.body
            # RobotMessageFileDownloadResponseBody 对象应该有 download_url 属性
            download_url = None
            if hasattr(response_body, 'download_url'):
                download_url = response_body.download_url
            elif hasattr(response_body, 'downloadUrl'):
                download_url = response_body.downloadUrl
            elif hasattr(response_body, 'downloadurl'):
                download_url = response_body.downloadurl
            else:
                # 尝试查看所有属性
                logger.warning(f"响应体属性: {dir(response_body)}")
                # 尝试通过字典方式访问
                if isinstance(response_body, dict):
                    download_url = response_body.get('downloadUrl') or response_body.get('download_url')
            
            if not download_url:
                logger.error(f"无法从响应体中获取 downloadUrl，响应体类型: {type(response_body)}, 属性: {dir(response_body)}")
                raise DingTalkApiException(code=-1, msg="响应中缺少 downloadUrl 字段")
            
            logger.info(f"获取到下载链接: {download_url[:100]}...")
            
            # 第二步：使用 downloadUrl 下载文件
            import requests
            file_response = requests.get(download_url, stream=True, timeout=30)
            file_response.raise_for_status()
            
            # 确保保存目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
            with open(save_path, "wb") as f:
                for chunk in file_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"文件已下载: {save_path} (大小: {save_path.stat().st_size} bytes)")
            return save_path
            
        except Exception as err:
            error_code = getattr(err, 'code', -1)
            error_msg = getattr(err, 'message', str(err))
            logger.error(f"下载文件失败 - 错误码: {error_code}, 错误信息: {error_msg}")
            logger.error(f"异常类型: {type(err)}, 异常详情: {err}")
            raise DingTalkApiException(code=error_code, msg=f"下载文件失败: {error_msg}")

    def upload_image(self, image_path: Path) -> str:
        """上传图片并获取 media_id

        使用钉钉的 /media/upload API 上传图片，返回 media_id。
        media_id 可以用于在 Markdown 消息中嵌入图片。

        Args:
            image_path: 图片文件路径

        Returns:
            media_id（用于在 Markdown 中嵌入图片）
        """
        return self._upload_file(image_path, file_type='image')

    def upload_file(self, file_path: Path) -> str:
        """上传文件并获取 media_id

        使用钉钉的 /media/upload API 上传文件，返回 media_id。
        media_id 可以用于发送文件消息。

        Args:
            file_path: 文件路径

        Returns:
            media_id（用于发送文件消息）
        """
        return self._upload_file(file_path, file_type='file')

    def _upload_file(self, file_path: Path, file_type: str = 'file') -> str:
        """上传文件到钉钉（通用方法）

        Args:
            file_path: 文件路径
            file_type: 文件类型（'image' 或 'file'）

        Returns:
            media_id
        """
        from urllib.parse import quote_plus
        
        access_token = self.access_token
        if not access_token:
            raise DingTalkApiException(code=-1, msg="无法获取访问令牌")
        
        # 确定 MIME 类型
        suffix = file_path.suffix.lower()
        mime_types = {
            # 图片类型
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            # 文档类型
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
        }
        mimetype = mime_types.get(suffix, 'application/octet-stream')
        
        # 上传文件
        upload_url = f'https://oapi.dingtalk.com/media/upload?access_token={quote_plus(access_token)}'
        
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'media': (file_path.name, f.read(), mimetype)
                }
                data = {
                    'type': file_type
                }
                response = requests.post(upload_url, data=data, files=files, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                if 'media_id' not in result:
                    error_msg = result.get('errmsg', '未知错误')
                    logger.error(f"上传文件失败，响应: {result}")
                    raise DingTalkApiException(code=-1, msg=f"上传文件失败: {error_msg}")
                
                media_id = result['media_id']
                logger.info(f"文件已上传: {file_path.name}, media_id: {media_id[:20]}..., 类型: {file_type}")
                return media_id
                
        except requests.exceptions.RequestException as e:
            logger.error(f"上传文件请求失败: {e}")
            raise DingTalkApiException(code=-1, msg=f"上传文件请求失败: {e}")
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            raise DingTalkApiException(code=-1, msg=f"上传文件失败: {e}")

    def send_file_message(
        self,
        receive_id_type: str,
        receive_id: str,
        file_path: Path,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送文件消息

        上传文件并作为附件发送给用户。

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID（群聊时为 open_conversation_id，私聊时为 user_id）
            file_path: 文件路径
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（Stream 模式推荐使用，优先级最高）
        """
        # 上传文件获取 media_id
        media_id = self.upload_file(file_path)
        
        # 确定文件类型
        suffix = file_path.suffix.lower()
        file_type_map = {
            '.pdf': 'pdf',
            '.doc': 'doc',
            '.docx': 'docx',
            '.xls': 'xls',
            '.xlsx': 'xlsx',
            '.csv': 'csv',
            '.txt': 'txt',
            '.json': 'json',
            '.zip': 'zip',
            '.rar': 'rar',
        }
        file_type = file_type_map.get(suffix, 'file')
        
        # 如果提供了 session_webhook，使用 webhook 方式发送
        if session_webhook:
            self._send_file_via_webhook(session_webhook, media_id, file_path.name, file_type)
            return
        
        # 否则使用 OpenAPI 方式
        access_token = self.access_token
        if not access_token:
            raise DingTalkApiException(code=-1, msg="无法获取访问令牌")
        
        if is_group:
            self._send_file_group_message(access_token, receive_id, media_id, file_path.name, file_type)
        else:
            self._send_file_private_message(access_token, [receive_id], media_id, file_path.name, file_type)

    def _send_file_group_message(
        self,
        access_token: str,
        open_conversation_id: str,
        media_id: str,
        file_name: str,
        file_type: str
    ):
        """发送群聊文件消息"""
        msg_param = json.dumps({
            "mediaId": media_id,
            "fileName": file_name,
            "fileType": file_type
        }, ensure_ascii=False)
        msg_key = 'sampleFile'
        
        # 输出完整的消息体到日志
        logger.info(f"[钉钉] 发送群聊文件消息 - 完整消息体:")
        logger.info(f"  msgKey: {msg_key}")
        logger.info(f"  msgParam: {msg_param}")
        logger.info(f"  openConversationId: {open_conversation_id}")
        logger.info(f"  robotCode: {self._robot_code}")
        logger.info(f"  文件信息: {file_name} (类型: {file_type}, mediaId: {media_id[:20]}...)")
        
        client = dingtalkrobot_1_0Client(self._config)
        org_group_send_headers = dingtalkrobot__1__0_models.OrgGroupSendHeaders()
        org_group_send_headers.x_acs_dingtalk_access_token = access_token
        org_group_send_request = dingtalkrobot__1__0_models.OrgGroupSendRequest(
            msg_param=msg_param,
            msg_key=msg_key,
            open_conversation_id=open_conversation_id,
            robot_code=self._robot_code
        )
        try:
            response = client.org_group_send_with_options(
                org_group_send_request,
                org_group_send_headers,
                util_models.RuntimeOptions()
            )
            logger.info(f"群聊文件消息已发送: {file_name}")
            return response
        except Exception as err:
            logger.error(f"发送群聊文件消息失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"发送群聊文件消息失败: {err}")

    def _send_file_private_message(
        self,
        access_token: str,
        user_ids: list,
        media_id: str,
        file_name: str,
        file_type: str
    ):
        """发送私聊文件消息"""
        msg_key = 'sampleFile'
        msg_param = json.dumps({
            "mediaId": media_id,
            "fileName": file_name,
            "fileType": file_type
        }, ensure_ascii=False)

        # 输出完整的消息体到日志
        logger.info(f"[钉钉] 发送私聊文件消息 - 完整消息体:")
        logger.info(f"  msgKey: {msg_key}")
        logger.info(f"  msgParam: {msg_param}")
        logger.info(f"  userIds: {user_ids}")
        logger.info(f"  robotCode: {self._robot_code}")
        logger.info(f"  文件信息: {file_name} (类型: {file_type}, mediaId: {media_id[:20]}...)")

        client = dingtalkrobot_1_0Client(self._config)
        batch_send_otoheaders = dingtalkrobot__1__0_models.BatchSendOTOHeaders()
        batch_send_otoheaders.x_acs_dingtalk_access_token = access_token
        batch_send_otorequest = dingtalkrobot__1__0_models.BatchSendOTORequest(
            robot_code=self._robot_code,
            user_ids=user_ids,
            msg_key=msg_key,
            msg_param=msg_param
        )
        try:
            response = client.batch_send_otowith_options(
                batch_send_otorequest,
                batch_send_otoheaders,
                util_models.RuntimeOptions()
            )
            logger.info(f"私聊文件消息已发送: {file_name}")
            return response
        except Exception as err:
            logger.error(f"发送私聊文件消息失败: {err}")
            raise DingTalkApiException(code=-1, msg=f"发送私聊文件消息失败: {err}")

    def _send_file_via_webhook(
        self,
        session_webhook: str,
        media_id: str,
        file_name: str,
        file_type: str
    ):
        """通过 webhook 发送文件消息
        
        注意：Webhook 方式可能不支持文件消息，这里尝试发送，如果失败会记录日志
        """
        import requests
        
        # Webhook 方式可能不支持文件消息，尝试发送文本消息提示
        # 或者可以尝试使用 file 类型的消息格式
        payload = {
            "msgtype": "file",
            "file": {
                "media_id": media_id,
                "file_name": file_name
            }
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[钉钉] 通过 Webhook 发送文件消息 - 完整消息体:")
        logger.info(f"  msgtype: file")
        logger.info(f"  文件信息: {file_name} (类型: {file_type}, mediaId: {media_id[:20]}...)")
        logger.info(f"  完整 payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        request_headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*',
        }
        
        try:
            response = requests.post(session_webhook, headers=request_headers, json=payload)
            response.raise_for_status()
            logger.info(f"通过 webhook 发送文件消息成功: {file_name}")
            return response.json()
        except Exception as err:
            logger.warning(f"通过 webhook 发送文件消息失败（可能不支持）: {err}")
            # Webhook 可能不支持文件消息，这里不抛出异常，只记录警告
            logger.info(f"文件已上传，media_id: {media_id[:20]}...，但无法通过 webhook 发送")


class DingTalkApiException(Exception):
    """钉钉 API 异常"""

    def __init__(self, code: int = 0, msg: str = None):
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return f"钉钉 API 错误 {self.code}: {self.msg}"

    __repr__ = __str__
