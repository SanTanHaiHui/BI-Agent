"""钉钉报告回复工具（将 MD 文件转换为钉钉友好的格式）"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from bi_agent.channel.channel import ReportReplyBase, ApiClientBase

logger = logging.getLogger(__name__)


class DingTalkReportReply(ReportReplyBase):
    """钉钉报告回复工具

    将 BI-Agent 生成的 Markdown 报告转换为钉钉友好的格式。
    """

    def parse_markdown(self, md_path: Path) -> Dict[str, Any]:
        """解析 Markdown 文件

        Args:
            md_path: Markdown 文件路径

        Returns:
            解析后的内容字典
        """
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else "数据分析报告"

        image_pattern = r"!\[.*?\]\((.*?)\)"
        images = re.findall(image_pattern, content)
        
        image_info_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        image_matches = re.findall(image_info_pattern, content)

        file_link_pattern = r"\[([^\]]+)\]\(([^)]+\.(?:csv|xlsx|xls|txt|json|pdf))\)"
        file_links = re.findall(file_link_pattern, content, re.IGNORECASE)

        text_content = content
        image_placeholders = []
        
        for idx, (alt_text, img_path) in enumerate(image_matches):
            placeholder = f"__IMAGE_PLACEHOLDER_{idx}__"
            image_placeholders.append((placeholder, alt_text, img_path))
            pattern = re.escape(f"![{alt_text}]({img_path})")
            if pattern in text_content or f"![{alt_text}]({img_path})" in text_content:
                text_content = text_content.replace(f"![{alt_text}]({img_path})", placeholder, 1)
            else:
                text_content = re.sub(pattern, placeholder, text_content, count=1)
        
        def replace_file_link(match):
            link_text = match.group(1)
            file_path = match.group(2)
            if not file_path.startswith(('http://', 'https://')):
                file_name = Path(file_path).name
                if link_text == file_path or link_text == file_name:
                    return file_name
                return f"{link_text}: {file_name}"
            return match.group(0)
        
        text_content = re.sub(file_link_pattern, replace_file_link, text_content, flags=re.IGNORECASE)
        text_content = re.sub(r"\n{3,}", "\n\n", text_content).strip()
        
        if text_content.startswith(f"# {title}"):
            text_content = re.sub(rf"^#\s+{re.escape(title)}\s*\n+", "", text_content, flags=re.MULTILINE)
        text_content = re.sub(r"^---\s*$", "", text_content, flags=re.MULTILINE)
        text_content = re.sub(r"\n{3,}", "\n\n", text_content).strip()
        
        return {
            "title": title,
            "text": text_content,
            "images": images,
            "image_placeholders": image_placeholders,  # 保存图片占位符信息，用于后续替换
            "file_links": file_links,  # 保存文件链接信息（可选，用于后续处理）
        }

    async def send_report(
        self,
        receive_id_type: str,
        receive_id: str,
        md_path: Path,
        message_id: Optional[str] = None,
        is_group: bool = False,
        session_webhook: Optional[str] = None
    ):
        """发送报告到钉钉

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            md_path: Markdown 文件路径
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（Stream 模式推荐使用）
        """
        # 使用报告文件所在的目录作为 output_dir，确保图片路径解析正确
        # 这样相对路径的图片（如 "销售增长率对比图.png"）可以正确找到
        original_output_dir = self.output_dir
        self.output_dir = md_path.parent
        logger.info(f"使用报告文件所在目录作为 output_dir: {self.output_dir}")
        
        try:
            parsed = self.parse_markdown(md_path)

            # 构建钉钉 Markdown 消息内容
            markdown_content = self._build_rich_text_content(parsed)
            
            # 发送 Markdown 消息
            self.api_client.send_rich_text_message(
                receive_id_type,
                receive_id,
                markdown_content,  # 直接传递 Markdown 字符串
                message_id=message_id,
                is_group=is_group,
                session_webhook=session_webhook
            )
            
            # 不发送非图片文件附件（根据用户要求，只支持图片格式）
            # 文件链接已在文本中转换为纯文本显示，不再作为附件发送
            file_links = parsed.get('file_links', [])
            if file_links:
                logger.info(f"检测到 {len(file_links)} 个文件链接，已转换为文本显示，不发送文件附件（仅支持图片格式）")
        finally:
            self.output_dir = original_output_dir

    def _build_rich_text_content(self, parsed: Dict[str, Any]) -> str:
        """构建钉钉 Markdown 消息内容

        钉钉使用 Markdown 格式发送消息，msgKey 为 sampleMarkdown。
        支持的 Markdown 语法包括：标题、引用、加粗、斜体、链接、图片、列表、换行。
        
        图片会先上传到钉钉获取 media_id，然后将文本中的图片路径替换为 media_id。
        确保同一张图片只出现一次（去重处理）。

        Args:
            parsed: 解析后的 Markdown 内容

        Returns:
            钉钉 Markdown 格式的字符串
        """
        title_text = parsed['title'] or "数据分析报告"
        content_text = parsed['text']
        image_placeholders = parsed.get('image_placeholders', [])
        
        # 用于去重的字典：key 是标准化路径，value 是 media_id
        uploaded_images = {}  # {标准化路径: media_id}
        
        # 处理图片占位符，上传图片并替换为 media_id
        for placeholder, alt_text, image_url in image_placeholders:
            image_path = Path(image_url)
            if not image_path.is_absolute():
                image_path = self.output_dir / image_path
            
            # 标准化路径用于去重
            try:
                image_path_resolved = image_path.resolve()
            except:
                image_path_resolved = image_path
            image_path_str_key = str(image_path_resolved)
            
            if image_path_str_key in uploaded_images:
                media_id = uploaded_images[image_path_str_key]
                logger.info(f"使用已上传的图片 media_id: {image_path.name}, media_id: {media_id[:20]}...")
            elif image_path.exists():
                try:
                    media_id = self.api_client.upload_image(image_path)
                    uploaded_images[image_path_str_key] = media_id
                    logger.info(f"图片已上传: {image_path.name}, media_id: {media_id[:20]}...")
                except Exception as e:
                    logger.error(f"上传图片失败 {image_path}: {e}")
                    # 如果上传失败，保留占位符或使用原始 URL（如果可用）
                    if image_url.startswith(('http://', 'https://')):
                        media_id = image_url
                    else:
                        content_text = content_text.replace(placeholder, "")
                        continue
            else:
                logger.warning(f"图片文件不存在: {image_path}")
                if image_url.startswith(('http://', 'https://')):
                    media_id = image_url
                else:
                    content_text = content_text.replace(placeholder, "")
                    continue
            
            alt_text_display = alt_text if alt_text else "图片"
            if placeholder in content_text:
                content_text = content_text.replace(placeholder, f"![{alt_text_display}]({media_id})", 1)
            else:
                logger.warning(f"占位符 {placeholder} 在内容中未找到，可能已被处理")
        
        content_text = re.sub(r'([^\n])\n([^\n])', r'\1  \n  \2', content_text)
        result = re.sub(r'([^\n])\n([^\n])', r'\1  \n  \2', content_text)
        
        logger.info(f"构建钉钉 Markdown 消息 - 标题: {title_text}, 文本长度: {len(result)}, 已上传图片数量: {len(uploaded_images)}")
        
        return result
