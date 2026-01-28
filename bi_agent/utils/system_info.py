"""系统环境信息工具"""

import platform
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_system_info() -> str:
    """获取系统环境信息
    
    通过 bash 命令获取操作系统及其版本，以及 Python 版本信息。
    
    Returns:
        格式化的系统环境信息字符串
    """
    info_lines = []
    
    # 获取操作系统信息
    try:
        # 使用 platform 模块获取基本信息
        os_name = platform.system()
        os_version = platform.version()
        os_release = platform.release()
        
        # 尝试通过 bash 命令获取更详细的系统信息
        if os_name == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ["sw_vers"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    sw_vers_output = result.stdout.strip()
                    info_lines.append(f"操作系统：macOS")
                    for line in sw_vers_output.split('\n'):
                        if 'ProductName:' in line:
                            info_lines.append(f"  产品名称：{line.split(':', 1)[1].strip()}")
                        elif 'ProductVersion:' in line:
                            info_lines.append(f"  版本：{line.split(':', 1)[1].strip()}")
                        elif 'BuildVersion:' in line:
                            info_lines.append(f"  构建版本：{line.split(':', 1)[1].strip()}")
                else:
                    info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.warning(f"无法获取 macOS 详细信息: {e}")
                info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
        elif os_name == "Linux":
            try:
                # 尝试读取 /etc/os-release
                result = subprocess.run(
                    ["cat", "/etc/os-release"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    info_lines.append(f"操作系统：Linux")
                    for line in result.stdout.split('\n'):
                        if line.startswith('PRETTY_NAME='):
                            pretty_name = line.split('=', 1)[1].strip('"')
                            info_lines.append(f"  发行版：{pretty_name}")
                        elif line.startswith('VERSION_ID='):
                            version_id = line.split('=', 1)[1].strip('"')
                            info_lines.append(f"  版本：{version_id}")
                else:
                    info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.warning(f"无法获取 Linux 详细信息: {e}")
                info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
        elif os_name == "Windows":
            try:
                result = subprocess.run(
                    ["systeminfo"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    info_lines.append(f"操作系统：Windows")
                    for line in result.stdout.split('\n'):
                        if 'OS Name:' in line:
                            info_lines.append(f"  系统名称：{line.split(':', 1)[1].strip()}")
                        elif 'OS Version:' in line:
                            info_lines.append(f"  版本：{line.split(':', 1)[1].strip()}")
                else:
                    info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.warning(f"无法获取 Windows 详细信息: {e}")
                info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
        else:
            info_lines.append(f"操作系统：{os_name} {os_release} ({os_version})")
    except Exception as e:
        logger.warning(f"获取操作系统信息失败: {e}")
        info_lines.append(f"操作系统：{platform.system()} (无法获取详细信息)")
    
    # 获取 Python 版本信息
    try:
        python_version = sys.version
        python_version_short = sys.version.split()[0]  # 例如 "3.11.0"
        python_executable = sys.executable
        
        info_lines.append(f"Python 版本：{python_version_short}")
        info_lines.append(f"Python 可执行文件：{python_executable}")
        
        # 获取 Python 详细版本信息
        try:
            result = subprocess.run(
                [sys.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info_lines.append(f"Python 完整版本信息：{result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"无法获取 Python 详细版本: {e}")
    except Exception as e:
        logger.warning(f"获取 Python 版本信息失败: {e}")
        info_lines.append(f"Python 版本：无法获取")
    
    return "\n".join(info_lines)
