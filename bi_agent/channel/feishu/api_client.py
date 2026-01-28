"""飞书 API 客户端"""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FeishuApiClient:
    """飞书 API 客户端"""

    # API 端点
    TENANT_ACCESS_TOKEN_URI = "/open-apis/auth/v3/tenant_access_token/internal"
    MESSAGE_URI = "/open-apis/im/v1/messages"
    MESSAGE_REPLY_URI = "/open-apis/im/v1/messages/{message_id}/reply"
    MESSAGE_RESOURCE_URI = "/open-apis/im/v1/messages/{message_id}/resources/{file_key}"  # 获取消息资源
    FILE_DOWNLOAD_URI = "/open-apis/im/v1/files/{file_key}"  # 直接使用 file_key，不需要 /download
    FILE_INFO_URI = "/open-apis/im/v1/files/{file_key}"

    def __init__(self, app_id: str, app_secret: str, lark_host: str = "https://open.feishu.cn"):
        """初始化飞书 API 客户端

        Args:
            app_id: 应用 ID
            app_secret: 应用密钥
            lark_host: 飞书 API 主机地址
        """
        self._app_id = app_id
        self._app_secret = app_secret
        self._lark_host = lark_host
        self._tenant_access_token = ""
        self._token_expire_time = 0

    @property
    def tenant_access_token(self) -> str:
        """获取租户访问令牌（自动刷新）"""
        import time
        # 如果令牌为空或即将过期（提前5分钟刷新），则重新获取
        if not self._tenant_access_token or time.time() >= self._token_expire_time - 300:
            self._authorize_tenant_access_token()
        return self._tenant_access_token

    def _authorize_tenant_access_token(self):
        """获取租户访问令牌"""
        url = f"{self._lark_host}{self.TENANT_ACCESS_TOKEN_URI}"
        req_body = {
            "app_id": self._app_id,
            "app_secret": self._app_secret
        }
        logger.info(f"获取访问令牌 - URL: {url}, App ID: {self._app_id[:10]}...")
        response = requests.post(url, json=req_body)
        
        # 先检查 HTTP 状态码
        if response.status_code != 200:
            logger.error(f"获取访问令牌失败 - HTTP {response.status_code}: {response.text}")
            response.raise_for_status()
        
        # 检查响应格式
        try:
            response_dict = response.json()
        except Exception as e:
            logger.error(f"解析访问令牌响应失败: {e}, 响应内容: {response.text}")
            raise
        
        # 飞书 API 返回格式：{"code": 0, "msg": "success", "tenant_access_token": "...", "expire": 7200}
        # 注意：不是 {"data": {"tenant_access_token": "..."}} 格式
        code = response_dict.get("code", -1)
        if code != 0:
            msg = response_dict.get("msg", "未知错误")
            logger.error(f"获取访问令牌失败 - 飞书 API 错误: {code} - {msg}")
            logger.error(f"完整响应: {response_dict}")
            raise FeishuApiException(code=code, msg=msg)
        
        # 直接从响应中获取令牌
        self._tenant_access_token = response_dict.get("tenant_access_token", "")
        if not self._tenant_access_token:
            logger.error(f"访问令牌为空，响应: {response_dict}")
            raise FeishuApiException(code=-1, msg="访问令牌为空")
        
        # 令牌有效期通常是 2 小时（7200 秒）
        expire = response_dict.get("expire", 7200)
        import time
        self._token_expire_time = time.time() + expire
        logger.info(f"飞书访问令牌已更新，有效期: {expire} 秒")

    def send_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: str,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None,
    ):
        """发送文本消息

        Args:
            receive_id_type: 接收者 ID 类型（open_id, user_id, chat_id）
            receive_id: 接收者 ID
            content: 消息内容（文本）
            message_id: 要回复的消息 ID（群聊时必需）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（飞书中不使用，保留以兼容接口）
        """
        import json
        # 文本消息需要包装成 {"text": content} 格式
        text_content = json.dumps({"text": content})
        
        # 群聊使用回复接口，私聊使用创建接口
        if is_group and message_id:
            self._reply_message(message_id, "text", text_content)
        else:
            self._send_message(receive_id_type, receive_id, "text", text_content)

    def send_rich_text_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: Dict[str, Any],
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送富文本消息（post 格式）

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            content: 富文本内容（字典格式，包含 title 和 elements）
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（飞书中不使用，保留以兼容接口）
        """
        import json
        # 群聊使用回复接口，私聊使用创建接口
        if is_group and message_id:
            self._reply_post_message(message_id, content)
        else:
            self._send_message(receive_id_type, receive_id, "post", json.dumps(content))

    def send_card_message(
        self,
        receive_id_type: str,
        receive_id: str,
        card_content: Dict[str, Any],
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送卡片消息（interactive 格式）

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            card_content: 卡片内容（字典格式）
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（飞书中不使用，保留以兼容接口）
        """
        import json
        # 群聊使用回复接口，私聊使用创建接口
        # 注意：card_content 是字典，_send_message 会自动序列化，所以这里不需要 json.dumps
        if is_group and message_id:
            self._reply_card_message(message_id, card_content)
        else:
            self._send_message(receive_id_type, receive_id, "interactive", card_content)

    def send_image_message(
        self,
        receive_id_type: str,
        receive_id: str,
        image_key: str
    ):
        """发送图片消息

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            image_key: 图片 key（需要先上传图片获取）
        """
        content = {
            "image_key": image_key
        }
        self._send_message(receive_id_type, receive_id, "image", content)

    def _send_message(
        self,
        receive_id_type: str,
        receive_id: str,
        msg_type: str,
        content: Any
    ):
        """发送消息（内部方法，用于私聊）

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            msg_type: 消息类型（text, post, image 等）
            content: 消息内容
        """
        # 确保访问令牌已获取
        token = self.tenant_access_token
        if not token:
            logger.error("无法获取访问令牌")
            raise FeishuApiException(code=-1, msg="无法获取访问令牌")
        
        url = f"{self._lark_host}{self.MESSAGE_URI}?receive_id_type={receive_id_type}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        import json

        # 如果是文本消息，content 应该已经是 JSON 字符串格式 {"text": "..."}
        # 其他类型的消息需要转换为 JSON 字符串（但如果已经是字符串，则不需要再次序列化）
        if msg_type != "text" and not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        req_body = {
            "receive_id": receive_id,
            "content": content,
            "msg_type": msg_type,
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[飞书] 发送消息 - 完整消息体:")
        logger.info(f"  receive_id_type: {receive_id_type}")
        logger.info(f"  receive_id: {receive_id}")
        logger.info(f"  msg_type: {msg_type}")
        logger.info(f"  消息内容长度: {len(str(content))} 字符")
        if msg_type == "post":
            # 对于 post 类型，content 是 JSON 字符串，解析后输出
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
                logger.info(f"  富文本内容预览:\n{json.dumps(content_dict, ensure_ascii=False, indent=2)[:1000]}...")
            except:
                content_str = str(content)
                logger.info(f"  消息内容预览: {content_str[:500]}..." if len(content_str) > 500 else f"  完整消息内容:\n{content}")
        elif msg_type == "interactive":
            # 对于 interactive 类型（卡片），content 是 JSON 字符串，解析后输出
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
                logger.info(f"  卡片内容预览:\n{json.dumps(content_dict, ensure_ascii=False, indent=2)[:2000]}...")
            except:
                content_str = str(content)
                logger.info(f"  消息内容预览: {content_str[:500]}..." if len(content_str) > 500 else f"  完整消息内容:\n{content}")
        else:
            content_str = str(content)
            logger.info(f"  消息内容预览: {content_str[:500]}..." if len(content_str) > 500 else f"  完整消息内容:\n{content}")
        logger.info(f"  完整请求体: {json.dumps(req_body, ensure_ascii=False, indent=2)}")
        
        resp = requests.post(url=url, headers=headers, json=req_body)
        self._check_error_response(resp)
        logger.info(f"消息已发送到 {receive_id_type}:{receive_id}")

    def _reply_message(
        self,
        message_id: str,
        msg_type: str,
        content: Any
    ):
        """回复消息（内部方法，用于群聊）

        Args:
            message_id: 要回复的消息 ID
            msg_type: 消息类型（text, post, image 等）
            content: 消息内容
        """
        # 确保访问令牌已获取
        token = self.tenant_access_token
        if not token:
            logger.error("无法获取访问令牌")
            raise FeishuApiException(code=-1, msg="无法获取访问令牌")
        
        url = f"{self._lark_host}{self.MESSAGE_REPLY_URI.format(message_id=message_id)}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        logger.info(f"使用访问令牌: {token[:20]}...")

        import json

        # 如果是文本消息，content 应该已经是 JSON 字符串格式 {"text": "..."}
        # 其他类型的消息需要转换为 JSON 字符串
        if msg_type != "text":
            content = json.dumps(content)

        req_body = {
            "content": content,
            "msg_type": msg_type,
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[飞书] 回复消息 - 完整消息体:")
        logger.info(f"  message_id: {message_id}")
        logger.info(f"  msg_type: {msg_type}")
        logger.info(f"  消息内容长度: {len(content)} 字符")
        if msg_type == "post":
            # 对于 post 类型，content 是 JSON 字符串，解析后输出
            try:
                content_dict = json.loads(content) if isinstance(content, str) else content
                logger.info(f"  富文本内容预览:\n{json.dumps(content_dict, ensure_ascii=False, indent=2)[:1000]}...")
            except:
                logger.info(f"  消息内容预览: {content[:500]}..." if len(content) > 500 else f"  完整消息内容:\n{content}")
        else:
            logger.info(f"  消息内容预览: {content[:500]}..." if len(content) > 500 else f"  完整消息内容:\n{content}")
        logger.info(f"  完整请求体: {json.dumps(req_body, ensure_ascii=False, indent=2)}")
        
        resp = requests.post(url=url, headers=headers, json=req_body)
        self._check_error_response(resp)
        logger.info(f"消息已回复到消息: {message_id}")

    def _reply_post_message(
        self,
        message_id: str,
        content: Dict[str, Any]
    ):
        """回复富文本消息（post 格式，内部方法，用于群聊）

        Args:
            message_id: 要回复的消息 ID
            content: 富文本内容（字典格式，包含 post.zh_cn 结构）
        """
        import json
        import uuid
        # 确保访问令牌已获取
        token = self.tenant_access_token
        if not token:
            logger.error("无法获取访问令牌")
            raise FeishuApiException(code=-1, msg="无法获取访问令牌")
        
        url = f"{self._lark_host}{self.MESSAGE_REPLY_URI.format(message_id=message_id)}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # 将 content 转换为 JSON 字符串
        content_str = json.dumps(content, ensure_ascii=False)
        
        req_body = {
            "content": content_str,
            "msg_type": "post",
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[飞书] 回复富文本消息 - 完整消息体:")
        logger.info(f"  message_id: {message_id}")
        logger.info(f"  msg_type: post")
        logger.info(f"  消息内容长度: {len(content_str)} 字符")
        try:
            # 解析并格式化输出富文本内容
            content_dict = json.loads(content_str) if isinstance(content_str, str) else content_str
            logger.info(f"  富文本内容预览:\n{json.dumps(content_dict, ensure_ascii=False, indent=2)[:2000]}...")
        except:
            logger.info(f"  消息内容预览: {content_str[:1000]}...")
        logger.info(f"  完整请求体: {json.dumps(req_body, ensure_ascii=False, indent=2)}")
        
        resp = requests.post(url=url, headers=headers, json=req_body)
        self._check_error_response(resp)
        logger.info(f"富文本消息已回复到消息: {message_id}")

    def _reply_card_message(
        self,
        message_id: str,
        card_content: Dict[str, Any]
    ):
        """回复卡片消息（interactive 格式，内部方法，用于群聊）

        Args:
            message_id: 要回复的消息 ID
            card_content: 卡片内容（字典格式）
        """
        import json
        # 确保访问令牌已获取
        token = self.tenant_access_token
        if not token:
            logger.error("无法获取访问令牌")
            raise FeishuApiException(code=-1, msg="无法获取访问令牌")
        
        url = f"{self._lark_host}{self.MESSAGE_REPLY_URI.format(message_id=message_id)}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        logger.info(f"使用访问令牌: {token[:20]}...")

        req_body = {
            "content": json.dumps(card_content, ensure_ascii=False),
            "msg_type": "interactive",
        }
        
        # 输出完整的消息体到日志
        logger.info(f"[飞书] 回复卡片消息 - 完整消息体:")
        logger.info(f"  message_id: {message_id}")
        logger.info(f"  msg_type: interactive")
        logger.info(f"  卡片内容预览:\n{json.dumps(card_content, ensure_ascii=False, indent=2)[:2000]}...")
        logger.info(f"  完整请求体: {json.dumps(req_body, ensure_ascii=False, indent=2)}")
        
        resp = requests.post(url=url, headers=headers, json=req_body)
        self._check_error_response(resp)
        logger.info(f"卡片消息已回复到消息: {message_id}")

    def get_file_info(self, file_key: str) -> Dict[str, Any]:
        """获取文件信息

        Args:
            file_key: 文件 key

        Returns:
            文件信息字典
        """
        url = f"{self._lark_host}{self.FILE_INFO_URI.format(file_key=file_key)}"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
        }
        resp = requests.get(url=url, headers=headers)
        self._check_error_response(resp)
        return resp.json().get("data", {})

    def download_file(self, file_key: str, save_path: Path, message_id: Optional[str] = None, resource_type: str = "file") -> Path:
        """下载文件

        Args:
            file_key: 文件 key
            save_path: 保存路径
            message_id: 消息 ID（如果提供，使用消息资源 API）
            resource_type: 资源类型（file, image 等，默认为 file）

        Returns:
            保存的文件路径
        """
        # 确保访问令牌已获取
        token = self.tenant_access_token
        if not token:
            logger.error("无法获取访问令牌")
            raise FeishuApiException(code=-1, msg="无法获取访问令牌")
        
        # 如果提供了 message_id，使用消息资源 API（推荐方式）
        if message_id:
            url = f"{self._lark_host}{self.MESSAGE_RESOURCE_URI.format(message_id=message_id, file_key=file_key)}"
            # 添加 type 参数
            url += f"?type={resource_type}"
            logger.info(f"使用消息资源 API 下载文件 - URL: {url}, message_id: {message_id}, file_key: {file_key}, type: {resource_type}")
        else:
            # 否则使用文件下载接口（可能权限不足）
            url = f"{self._lark_host}{self.FILE_DOWNLOAD_URI.format(file_key=file_key)}"
            logger.info(f"使用文件下载 API - URL: {url}, file_key: {file_key}")
        
        headers = {
            "Authorization": f"Bearer {token}",
        }
        
        # 下载文件（使用 stream=True 以支持大文件）
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        
        # 检查响应
        if resp.status_code != 200:
            logger.error(f"下载文件失败 - HTTP {resp.status_code}: {resp.text}")
            # 尝试解析错误响应
            try:
                error_data = resp.json()
                code = error_data.get("code", -1)
                msg = error_data.get("msg", "未知错误")
                logger.error(f"飞书 API 错误: {code} - {msg}")
                if code == 234008:
                    raise FeishuApiException(
                        code=code,
                        msg=f"{msg} - 应用可能没有权限下载此文件，请检查应用权限配置。如果提供了 message_id，请确保消息中包含该文件。"
                    )
                elif code == 99991672:
                    # 权限不足错误
                    raise FeishuApiException(
                        code=code,
                        msg=f"{msg} - 请确保在飞书开发者后台开通以下权限之一：im:message.history:readonly, im:message:readonly, im:message"
                    )
                raise FeishuApiException(code=code, msg=msg)
            except FeishuApiException:
                raise
            except:
                resp.raise_for_status()
        
        # 确保保存目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存文件
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"文件已下载: {save_path} (大小: {save_path.stat().st_size} bytes)")
        return save_path

    def upload_image(self, image_path: Path) -> str:
        """上传图片并获取 image_key

        Args:
            image_path: 图片文件路径

        Returns:
            image_key
        """
        # 飞书上传图片需要使用不同的 API
        # 参考文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/image/create
        upload_uri = "/open-apis/im/v1/images"
        url = f"{self._lark_host}{upload_uri}"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
        }

        # 确定文件类型
        file_ext = image_path.suffix.lower()
        content_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        content_type = content_type_map.get(file_ext, 'image/png')

        with open(image_path, "rb") as f:
            files = {
                "image": (image_path.name, f, content_type)
            }
            data = {
                "image_type": "message"
            }
            resp = requests.post(url, headers=headers, files=files, data=data)
            self._check_error_response(resp)
            result = resp.json().get("data", {})
            return result.get("image_key", "")

    @staticmethod
    def _check_error_response(resp: requests.Response):
        """检查响应是否包含错误信息"""
        if resp.status_code != 200:
            logger.error(f"HTTP 错误: {resp.status_code}")
            logger.error(f"响应内容: {resp.text}")
            resp.raise_for_status()
        response_dict = resp.json()
        code = response_dict.get("code", -1)
        if code != 0:
            msg = response_dict.get("msg", "未知错误")
            logger.error(f"飞书 API 错误: {code} - {msg}")
            logger.error(f"完整响应: {json.dumps(response_dict, ensure_ascii=False, indent=2)}")
            raise FeishuApiException(code=code, msg=msg)


class FeishuApiException(Exception):
    """飞书 API 异常"""

    def __init__(self, code: int = 0, msg: str = None):
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return f"飞书 API 错误 {self.code}: {self.msg}"

    __repr__ = __str__
