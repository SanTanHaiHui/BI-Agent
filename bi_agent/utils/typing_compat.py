"""类型注解兼容性模块 - 支持 Python 3.11+"""

try:
    from typing import override
except ImportError:
    # Python < 3.12 使用 typing_extensions
    from typing_extensions import override

__all__ = ["override"]

