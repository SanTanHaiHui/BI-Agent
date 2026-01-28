"""提示词管理模块"""

from bi_agent.prompts.system_prompt import BI_AGENT_SYSTEM_PROMPT
from bi_agent.prompts.task_prompts import (
    get_data_reading_prompt,
    get_data_cleaning_prompt,
    get_visualization_prompt,
    get_report_generation_prompt,
)

__all__ = [
    "BI_AGENT_SYSTEM_PROMPT",
    "get_data_reading_prompt",
    "get_data_cleaning_prompt",
    "get_visualization_prompt",
    "get_report_generation_prompt",
]

