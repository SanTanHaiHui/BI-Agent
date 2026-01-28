"""报告回复工具（将 MD 文件转换为飞书友好的格式）"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from bi_agent.channel.channel import ReportReplyBase

logger = logging.getLogger(__name__)


class ReportReply(ReportReplyBase):
    """报告回复工具

    将 BI-Agent 生成的 Markdown 报告转换为飞书友好的格式。
    """

    def __init__(self, api_client, output_dir: Path):
        """初始化报告回复工具

        Args:
            api_client: 飞书 API 客户端
            output_dir: 输出目录（用于查找图片文件）
        """
        super().__init__(api_client, output_dir)

    def parse_markdown(self, md_path: Path) -> Dict[str, Any]:
        """解析 Markdown 文件

        Args:
            md_path: Markdown 文件路径

        Returns:
            解析后的内容字典
        """
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取标题
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else "数据分析报告"

        # 提取图片信息（包括描述和路径），用于后续替换
        image_info_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        image_matches = re.findall(image_info_pattern, content)
        images = [img_path for _, img_path in image_matches]

        text_content = content
        image_placeholders = []
        
        for idx, (alt_text, img_path) in enumerate(image_matches):
            placeholder = f"__IMAGE_PLACEHOLDER_{idx}__"
            image_placeholders.append((placeholder, alt_text, img_path))
            text_content = text_content.replace(f"![{alt_text}]({img_path})", placeholder, 1)
        
        text_content = re.sub(r"\n{3,}", "\n\n", text_content).strip()
        text_content = re.sub(rf"^#\s+{re.escape(title)}\s*$", "", text_content, flags=re.MULTILINE)
        text_content = re.sub(r"^---\s*$", "", text_content, flags=re.MULTILINE)
        text_content = re.sub(r"\n{3,}", "\n\n", text_content).strip()
        
        return {
            "title": title,
            "text": text_content,
            "images": images,
            "image_placeholders": image_placeholders,  # 保存图片占位符信息，用于后续替换
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
        """发送报告到飞书（使用富文本格式）

        Args:
            receive_id_type: 接收者 ID 类型
            receive_id: 接收者 ID
            md_path: Markdown 文件路径
            message_id: 消息 ID（群聊时用于回复）
            is_group: 是否为群聊
            session_webhook: 会话 webhook（飞书中不使用，保留以兼容接口）
        """
        # 使用报告文件所在的目录作为 output_dir，确保图片路径解析正确
        # 这样相对路径的图片（如 "销售增长率对比图.png"）可以正确找到
        original_output_dir = self.output_dir
        self.output_dir = md_path.parent
        logger.info(f"使用报告文件所在目录作为 output_dir: {self.output_dir}")
        
        try:
            parsed = self.parse_markdown(md_path)

            # 构建卡片消息内容
            card_content = self._build_card_content(parsed)
            
            # 验证内容格式
            if not card_content:
                logger.error(f"卡片内容格式错误: {card_content}")
                # 如果格式错误，回退到文本消息
                title_text = f"# {parsed['title']}\n\n{parsed['text']}"
                self.api_client.send_text_message(
                    receive_id_type,
                    receive_id,
                    title_text,
                    message_id=message_id,
                    is_group=is_group
                )
                return

            # 发送卡片消息
            self.api_client.send_card_message(
                receive_id_type,
                receive_id,
                card_content,
                message_id=message_id,
                is_group=is_group
            )
        finally:
            self.output_dir = original_output_dir

    def _build_rich_text_content(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """构建富文本消息内容（post 格式）

        根据飞书文档：https://open.feishu.cn/document/server-docs/im-v1/message-content-description/create_json#45e0953e
        post 格式应该包含 post.zh_cn.title 和 post.zh_cn.content（二维数组）
        
        图片会先上传到飞书获取 image_key，然后将文本中的图片路径替换为 image_key。
        确保同一张图片只出现一次（去重处理）。

        Args:
            parsed: 解析后的 Markdown 内容

        Returns:
            富文本消息内容字典（post 格式）
        """
        content_rows = []  # 二维数组，每个子数组代表一行
        
        # 用于去重的字典：key 是标准化路径，value 是 image_key
        uploaded_images = {}  # {标准化路径: image_key}
        
        # 先处理图片占位符，上传图片并获取 image_key
        text_content = parsed['text']
        image_placeholders = parsed.get('image_placeholders', [])
        
        # 处理图片占位符，上传图片并替换为 image_key
        for placeholder, alt_text, image_url in image_placeholders:
            # 如果是相对路径，转换为绝对路径
            image_path = Path(image_url)
            if not image_path.is_absolute():
                image_path = self.output_dir / image_path
            
            # 标准化路径用于去重
            try:
                image_path_resolved = image_path.resolve()
            except:
                image_path_resolved = image_path
            image_path_str_key = str(image_path_resolved)
            
            # 如果已经上传过相同的图片，使用已上传的 image_key
            if image_path_str_key in uploaded_images:
                image_key = uploaded_images[image_path_str_key]
                logger.info(f"使用已上传的图片 image_key: {image_path.name}, image_key: {image_key[:20]}...")
            elif image_path.exists():
                try:
                    # 上传图片获取 image_key
                    image_key = self.api_client.upload_image(image_path)
                    uploaded_images[image_path_str_key] = image_key
                    logger.info(f"图片已上传: {image_path.name}, image_key: {image_key[:20]}...")
                except Exception as e:
                    logger.error(f"上传图片失败 {image_path}: {e}")
                    # 上传失败，移除占位符
                    text_content = text_content.replace(placeholder, "")
                    continue
            else:
                logger.warning(f"图片文件不存在: {image_path}")
                # 文件不存在，移除占位符
                text_content = text_content.replace(placeholder, "")
                continue
            
            # 替换占位符为图片标记（在飞书中，图片需要单独一行）
            # 使用 replace 替换，确保只替换第一个匹配项（保留位置）
            text_content = text_content.replace(placeholder, f"__IMAGE_MARKER_{image_key}__", 1)
        
        # 按行处理文本内容
        lines = text_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过分隔符
            if line == '---' or line.startswith('---'):
                continue
            
            # 检查是否包含图片标记
            image_marker_pattern = r"__IMAGE_MARKER_(.+?)__"
            image_markers = re.findall(image_marker_pattern, line)
            
            if image_markers:
                # 如果行中包含图片标记，先添加文本部分（如果有），然后添加图片
                text_part = re.sub(image_marker_pattern, "", line).strip()
                if text_part:
                    row_elements = []
                    para_processed = self._process_text_formatting(text_part)
                    if para_processed:
                        row_elements.append({
                            "tag": "text",
                            "text": para_processed
                        })
                    if row_elements:
                        content_rows.append(row_elements)
                
                # 添加图片（每个图片单独一行，使用 img 标签）
                for image_key in image_markers:
                    content_rows.append([
                        {
                            "tag": "img",
                            "image_key": image_key
                        }
                    ])
            else:
                # 普通文本行
                row_elements = []
                
                # 处理一级标题（# 开头的，但不在 title 中）
                if line.startswith('# ') and not line.startswith('##'):
                    title_text = re.sub(r'^#+\s*', '', line).strip()
                    if title_text:
                        row_elements.append({
                            "tag": "text",
                            "text": title_text
                        })
                # 处理二级及以上标题（## 开头的）
                elif line.startswith('##'):
                    title_text = re.sub(r'^##+\s*', '', line).strip()
                    if title_text:
                        row_elements.append({
                            "tag": "text",
                            "text": title_text
                        })
                # 处理列表项（- 开头的）
                elif line.startswith('- '):
                    list_text = line[2:].strip()
                    if list_text:
                        row_elements.append({
                            "tag": "text",
                            "text": list_text
                        })
                # 处理粗体文本（**text**）
                elif line.startswith('**') and line.endswith('**'):
                    bold_text = line.strip('*').strip()
                    row_elements.append({
                        "tag": "text",
                        "text": bold_text
                    })
                else:
                    # 普通文本段落
                    para_processed = self._process_text_formatting(line)
                    if para_processed:
                        row_elements.append({
                            "tag": "text",
                            "text": para_processed
                        })
                
                if row_elements:
                    content_rows.append(row_elements)
        
        # 确保至少有一行内容
        if not content_rows:
            # 如果没有内容，至少添加一个文本行
            content_rows.append([
                {
                    "tag": "text",
                    "text": "报告内容为空"
                }
            ])
        
        # 验证 content_rows 格式：确保每个元素都是数组，且数组中的元素都有 tag 字段
        validated_rows = []
        for row in content_rows:
            if not isinstance(row, list):
                logger.warning(f"跳过无效的行格式（不是数组）: {row}")
                continue
            if not row:
                logger.warning("跳过空行")
                continue
            # 验证每个元素都有 tag 字段
            valid_row = []
            for elem in row:
                if isinstance(elem, dict) and "tag" in elem:
                    valid_row.append(elem)
                else:
                    logger.warning(f"跳过无效的元素（缺少 tag）: {elem}")
            if valid_row:
                validated_rows.append(valid_row)
        
        if not validated_rows:
            # 如果验证后没有有效行，添加默认文本
            validated_rows.append([
                {
                    "tag": "text",
                    "text": "报告内容格式错误"
                }
            ])
        
        # 构建 post 格式的富文本消息结构（根据飞书文档格式）
        # 正确格式应该是：
        # {
        #   "zh_cn": {
        #     "title": "标题字符串",
        #     "content": [[...], [...]]
        #   }
        # }
        
        # 确保 title 不为空且长度合理
        title_text = parsed['title'] or "数据分析报告"
        if len(title_text) > 100:
            title_text = title_text[:100]  # 限制标题长度
        
        # 标题加粗：在 content 的第一行添加加粗的标题
        # 根据飞书文档，可以使用 style: ["bold"] 来加粗文本
        if validated_rows:
            # 在内容开头插入加粗的标题
            title_row = [{
                "tag": "text",
                "text": title_text,
                "style": ["bold"]
            }]
            validated_rows.insert(0, title_row)
        
        # 验证最终格式
        if not validated_rows:
            logger.warning("警告：内容为空，将添加默认文本")
            validated_rows = [[{"tag": "text", "text": "报告内容为空"}]]
        
        # 构建正确的 post 消息格式
        post_content = {
            "zh_cn": {
                "title": title_text,  # title 是字符串，不是对象
                "content": validated_rows
            }
        }
        
        logger.info(f"构建富文本消息 - 标题: {title_text}, 行数: {len(validated_rows)}")
        
        return post_content

    def _build_card_content(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """构建卡片消息内容

        根据飞书卡片文档：https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/rich-text
        卡片格式使用 interactive 类型，内容使用 rich_text 组件

        Args:
            parsed: 解析后的 Markdown 内容

        Returns:
            卡片消息内容字典
        """
        # 用于去重的字典：key 是标准化路径，value 是 image_key
        uploaded_images = {}  # {标准化路径: image_key}
        
        # 先处理图片占位符，上传图片并获取 image_key
        text_content = parsed['text']
        image_placeholders = parsed.get('image_placeholders', [])
        
        # 处理图片占位符，上传图片并替换为 image_key
        for placeholder, alt_text, image_url in image_placeholders:
            # 如果是相对路径，转换为绝对路径
            image_path = Path(image_url)
            if not image_path.is_absolute():
                image_path = self.output_dir / image_path
            
            # 标准化路径用于去重
            try:
                image_path_resolved = image_path.resolve()
            except:
                image_path_resolved = image_path
            image_path_str_key = str(image_path_resolved)
            
            # 如果已经上传过相同的图片，使用已上传的 image_key
            if image_path_str_key in uploaded_images:
                image_key = uploaded_images[image_path_str_key]
                logger.info(f"使用已上传的图片 image_key: {image_path.name}, image_key: {image_key[:20]}...")
            elif image_path.exists():
                try:
                    # 上传图片获取 image_key
                    image_key = self.api_client.upload_image(image_path)
                    uploaded_images[image_path_str_key] = image_key
                    logger.info(f"图片已上传: {image_path.name}, image_key: {image_key[:20]}...")
                except Exception as e:
                    logger.error(f"上传图片失败 {image_path}: {e}")
                    # 上传失败，移除占位符
                    text_content = text_content.replace(placeholder, "")
                    continue
            else:
                logger.warning(f"图片文件不存在: {image_path}")
                # 文件不存在，移除占位符
                text_content = text_content.replace(placeholder, "")
                continue
            
            # 替换占位符为图片标记
            # 使用 replace 替换，确保只替换第一个匹配项（保留位置）
            text_content = text_content.replace(placeholder, f"__IMAGE_MARKER_{image_key}__", 1)
        
        # 构建卡片内容
        # 根据飞书卡片文档，使用 rich_text 组件
        title_text = parsed['title'] or "数据分析报告"
        if len(title_text) > 100:
            title_text = title_text[:100]  # 限制标题长度
        
        # 构建 rich_text 内容
        # 参考文档：https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/rich-text
        # 注意：不在 content 中添加标题，因为 header 中已经有了
        rich_text_elements = []
        
        # 按行处理文本内容
        lines = text_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                # 空行添加换行
                rich_text_elements.append({
                    "tag": "text",
                    "text": "\n"
                })
                continue
            
            # 跳过分隔符
            if line == '---' or line.startswith('---'):
                continue
            
            # 检查是否包含图片标记
            image_marker_pattern = r"__IMAGE_MARKER_(.+?)__"
            image_markers = re.findall(image_marker_pattern, line)
            
            if image_markers:
                # 如果行中包含图片标记，先添加文本部分（如果有），然后添加图片
                text_part = re.sub(image_marker_pattern, "", line).strip()
                if text_part:
                    rich_text_elements.append({
                        "tag": "text",
                        "text": text_part
                    })
                    rich_text_elements.append({
                        "tag": "text",
                        "text": "\n"
                    })
                
                # 添加图片（飞书卡片 rich_text 中使用 image_key）
                for image_key in image_markers:
                    rich_text_elements.append({
                        "tag": "img",
                        "image_key": image_key
                    })
                    rich_text_elements.append({
                        "tag": "text",
                        "text": "\n"
                    })
            else:
                # 处理标题（## 开头）
                if line.startswith('##'):
                    title_text_line = re.sub(r'^##+\s*', '', line).strip()
                    if title_text_line:
                        rich_text_elements.append({
                            "tag": "text",
                            "text": title_text_line,
                            "style": ["bold"]
                        })
                        rich_text_elements.append({
                            "tag": "text",
                            "text": "\n"
                        })
                # 处理粗体文本（**text**）
                elif '**' in line:
                    # 简单的粗体处理：将 **text** 转换为加粗文本
                    parts = re.split(r'\*\*(.+?)\*\*', line)
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            # 普通文本
                            if part:
                                rich_text_elements.append({
                                    "tag": "text",
                                    "text": part
                                })
                        else:
                            # 粗体文本
                            rich_text_elements.append({
                                "tag": "text",
                                "text": part,
                                "style": ["bold"]
                            })
                    rich_text_elements.append({
                        "tag": "text",
                        "text": "\n"
                    })
                else:
                    # 普通文本段落
                    rich_text_elements.append({
                        "tag": "text",
                        "text": line
                    })
                    rich_text_elements.append({
                        "tag": "text",
                        "text": "\n"
                    })
        
        # 构建卡片结构
        # 参考文档：https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components
        # 飞书卡片不支持 rich_text block，应该使用 div 或 markdown block
        # 将 rich_text_elements 转换为多个 block（markdown 和 img）
        
        # 将 rich_text_elements 转换为多个 block
        elements = self._convert_rich_text_to_card_elements(rich_text_elements)
        
        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title_text
                }
            },
            "elements": elements
        }
        
        logger.info(f"构建卡片消息 - 标题: {title_text}, 元素数量: {len(rich_text_elements)}")
        
        return card_content

    def _convert_rich_text_to_card_elements(self, rich_text_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 rich_text elements 转换为飞书卡片 elements

        Args:
            rich_text_elements: rich_text 元素列表

        Returns:
            飞书卡片 elements 列表
        """
        card_elements = []
        current_markdown = []
        
        for elem in rich_text_elements:
            tag = elem.get("tag", "")
            
            if tag == "text":
                text = elem.get("text", "")
                styles = elem.get("style", [])
                
                # 处理样式
                if "bold" in styles:
                    text = f"**{text}**"
                if "italic" in styles:
                    text = f"*{text}*"
                if "underline" in styles:
                    text = f"<u>{text}</u>"
                
                current_markdown.append(text)
            elif tag == "img":
                # 如果当前有 markdown 内容，先添加一个 markdown block
                if current_markdown:
                    markdown_content = "".join(current_markdown)
                    card_elements.append({
                        "tag": "markdown",
                        "content": markdown_content
                    })
                    current_markdown = []
                
                # 添加图片 block
                # 参考文档：https://open.feishu.cn/document/feishu-cards/card-json-v2-components/content-components/img
                image_key = elem.get("image_key", "")
                if image_key:
                    card_elements.append({
                        "tag": "img",
                        "img_key": image_key,
                        "mode": "fit_horizontal"  # 自适应宽度，保持宽高比
                    })
            elif tag == "a":
                href = elem.get("href", "")
                text = elem.get("text", "")
                current_markdown.append(f"[{text}]({href})")
            elif tag == "at":
                user_id = elem.get("user_id", "")
                current_markdown.append(f"<at user_id=\"{user_id}\"></at>")
            elif tag == "hr":
                # 如果当前有 markdown 内容，先添加一个 markdown block
                if current_markdown:
                    markdown_content = "".join(current_markdown)
                    card_elements.append({
                        "tag": "markdown",
                        "content": markdown_content
                    })
                    current_markdown = []
                # 添加分割线
                card_elements.append({
                    "tag": "hr"
                })
            elif tag == "code_block":
                # 如果当前有 markdown 内容，先添加一个 markdown block
                if current_markdown:
                    markdown_content = "".join(current_markdown)
                    card_elements.append({
                        "tag": "markdown",
                        "content": markdown_content
                    })
                    current_markdown = []
                
                # 添加代码块
                language = elem.get("language", "")
                code = elem.get("text", "")
                card_elements.append({
                    "tag": "markdown",
                    "content": f"```{language}\n{code}\n```"
                })
            elif tag == "md":
                # 如果当前有 markdown 内容，先添加一个 markdown block
                if current_markdown:
                    markdown_content = "".join(current_markdown)
                    card_elements.append({
                        "tag": "markdown",
                        "content": markdown_content
                    })
                    current_markdown = []
                # 添加 Markdown 内容
                card_elements.append({
                    "tag": "markdown",
                    "content": elem.get("text", "")
                })
        
        # 处理剩余的 markdown 内容
        if current_markdown:
            markdown_content = "".join(current_markdown)
            card_elements.append({
                "tag": "markdown",
                "content": markdown_content
            })
        
        # 确保至少有一个元素
        if not card_elements:
            card_elements.append({
                "tag": "markdown",
                "content": "报告内容为空"
            })
        
        return card_elements

    def _process_text_formatting(self, text: str) -> str:
        """处理文本格式（将 Markdown 格式转换为纯文本，保留基本格式）

        Args:
            text: 原始文本

        Returns:
            处理后的文本
        """
        # 移除 Markdown 格式标记，保留文本内容
        # 这里简化处理，直接返回文本
        # 飞书的 rich_text 支持样式，但这里先保持简单
        return text

    def format_text_for_feishu(self, text: str) -> str:
        """将文本格式化为飞书友好的格式

        Args:
            text: 原始文本

        Returns:
            格式化后的文本
        """
        # 飞书支持基本的 Markdown 格式
        # 这里可以做一些转换，比如：
        # - 保持标题格式
        # - 保持列表格式
        # - 保持代码块格式

        # 简化处理：直接返回文本
        # 飞书会自动识别 Markdown 格式
        return text
