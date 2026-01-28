"""任务分类提示词"""


def get_data_reading_prompt(data_dir: str, file_list: list[str]) -> str:
    """获取数据读取提示词"""
    return f"""请读取以下数据文件并了解数据基本信息：

数据目录: {data_dir}
文件列表: {', '.join(file_list)}

要求：
1. 使用 data_reader 工具读取每个数据文件
2. 记录每个文件的行数、列数、列名、数据类型
3. 检查数据质量（缺失值、重复值等）
4. 如果有说明文件，先使用 search_knowledge 工具了解字段含义
"""


def get_data_cleaning_prompt(file_path: str, issues: list[str]) -> str:
    """获取数据清洗提示词"""
    return f"""请对以下数据文件进行清洗：

文件路径: {file_path}
发现的问题: {', '.join(issues)}

要求：
1. 使用 data_cleaner 工具进行数据清洗
2. 根据发现的问题选择合适的清洗策略
3. 将清洗后的数据保存到输出目录
4. 记录清洗前后的数据变化
"""


def get_visualization_prompt(
    file_path: str, chart_type: str, x_column: str | None = None, y_column: str | None = None
) -> str:
    """获取可视化提示词"""
    prompt = f"""请生成数据可视化图表：

数据文件: {file_path}
图表类型: {chart_type}
"""
    if x_column:
        prompt += f"X 轴: {x_column}\n"
    if y_column:
        prompt += f"Y 轴: {y_column}\n"

    prompt += """
要求：
1. 使用 visualization 工具生成图表
2. 确保图表清晰、美观
3. 添加合适的标题和标签
4. 将图表保存到输出目录
"""
    return prompt


def get_report_generation_prompt(
    title: str, findings: list[str], chart_paths: list[str] | None = None
) -> str:
    """获取报告生成提示词"""
    prompt = f"""请生成数据分析报告：

报告标题: {title}
关键发现:
"""
    for i, finding in enumerate(findings, 1):
        prompt += f"  {i}. {finding}\n"

    if chart_paths:
        prompt += f"\n图表文件: {', '.join(chart_paths)}\n"

    prompt += """
要求：
1. 使用 report_generator 工具生成报告
2. 报告应包含：分析目标、数据概况、关键发现、可视化图表、结论和建议
3. 使用 Markdown 格式
4. 确保报告结构完整、逻辑清晰
5. **重要约束**：
   - 报告中只能包含图片文件（.png, .jpg, .jpeg, .gif, .bmp, .webp 等图片格式）
   - 不要包含任何非图片文件的链接或引用（如 .csv, .xlsx, .xls, .txt, .json, .pdf 等）
   - 如果需要展示数据，请直接在报告中以文本、表格或图表的形式展示，不要引用文件
   - 用户侧无法显示除图片之外的文件，所有数据和分析结果都应该直接展示在报告中
   - 如果生成了数据文件（如 CSV、Excel），不要在报告中引用这些文件，而是直接展示关键数据
   - **图片位置**：图片应该直接放在相应的章节标题下，例如在"## 4. 可视化分析"或"## 可视化分析"标题后立即插入图片，使用格式：![图片描述](图片路径.png)，不要将图片放在报告末尾
"""
    return prompt

