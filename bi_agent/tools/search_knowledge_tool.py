"""知识库搜索工具"""

from pathlib import Path

from bi_agent.utils.typing_compat import override

from bi_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class SearchKnowledgeTool(Tool):
    """搜索知识库和模式信息的工具"""

    def __init__(self, data_dir: str, model_provider: str | None = None):
        super().__init__(model_provider)
        self.data_dir = Path(data_dir)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "search_knowledge"

    @override
    def get_description(self) -> str:
        return """搜索知识库和模式信息
* 在数据目录中搜索说明文件（.txt、.md 格式）
* 提取字段含义、业务背景、数据来源等信息
* 帮助理解数据结构和业务含义
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询（字段名、关键词等）",
                required=True,
            ),
            ToolParameter(
                name="file_pattern",
                type="string",
                description="文件模式（可选，例如：*.txt、*.md、README*）",
                required=False,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        query = str(arguments.get("query", ""))
        if not query:
            return ToolExecResult(error="未提供搜索查询", error_code=-1)

        try:
            # 搜索说明文件
            file_pattern = arguments.get("file_pattern", "*.{txt,md}")
            if file_pattern:
                patterns = file_pattern.split(",")
            else:
                patterns = ["*.txt", "*.md"]

            results = []
            query_lower = query.lower()

            for pattern in patterns:
                pattern = pattern.strip()
                if "*" in pattern:
                    # 使用 glob 搜索
                    for ext in [".txt", ".md"]:
                        for file_path in self.data_dir.rglob(f"*{ext}"):
                            if self._search_in_file(file_path, query_lower):
                                results.append(str(file_path))
                else:
                    # 直接搜索文件
                    for file_path in self.data_dir.rglob(pattern):
                        if self._search_in_file(file_path, query_lower):
                            results.append(str(file_path))

            if not results:
                return ToolExecResult(
                    output=f"未找到包含 '{query}' 的说明文件。\n建议：检查数据目录中是否有 README.txt、字段说明.md 等文件。"
                )

            # 读取匹配文件的内容
            content_lines = [f"找到 {len(results)} 个相关文件：\n"]
            for file_path in results[:5]:  # 最多显示 5 个文件
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # 提取包含查询的行
                        relevant_lines = [
                            line.strip()
                            for line in content.split("\n")
                            if query_lower in line.lower()
                        ][:10]  # 最多 10 行

                        content_lines.append(f"\n文件: {file_path}")
                        if relevant_lines:
                            content_lines.append("相关内容:")
                            content_lines.extend([f"  {line}" for line in relevant_lines])
                        else:
                            content_lines.append("  (文件包含关键词但未找到具体匹配行)")
                except Exception as e:
                    content_lines.append(f"\n文件: {file_path} (读取失败: {e})")

            if len(results) > 5:
                content_lines.append(f"\n... 还有 {len(results) - 5} 个文件未显示")

            return ToolExecResult(output="\n".join(content_lines))

        except Exception as e:
            return ToolExecResult(error=f"搜索知识库时出错: {str(e)}", error_code=-1)

    def _search_in_file(self, file_path: Path, query: str) -> bool:
        """检查文件是否包含查询内容"""
        try:
            # 尝试多种编码
            for encoding in ["utf-8", "gbk", "gb2312"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read().lower()
                        if query in content:
                            return True
                    break
                except UnicodeDecodeError:
                    continue
            return False
        except Exception:
            return False

