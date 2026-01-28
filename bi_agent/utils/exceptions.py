"""异常处理模块"""


class BIAgentError(Exception):
    """BI-Agent 基础异常类"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DataFileError(BIAgentError):
    """数据文件相关错误"""

    pass


class ToolExecutionError(BIAgentError):
    """工具执行错误"""

    pass


class ConfigurationError(BIAgentError):
    """配置错误"""

    pass

