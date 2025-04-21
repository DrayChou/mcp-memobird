"""
Memobird 打印机工具类
"""

import base64
import logging
import os
import sys
from io import BytesIO

from fastmcp import FastMCP
from PIL import Image

# 导入配置和工具
try:
    # 相对导入 - 当作为模块运行时
    from .config import (
        LOG_LEVEL,
        LOG_FORMAT,
    )
    from .memobird_client import MemobirdDevice
except (ImportError, ValueError):
    try:
        # 直接导入 - 当在src目录内运行时
        from config import (
            LOG_LEVEL,
            LOG_FORMAT,
        )
        from memobird_client import MemobirdDevice
    except ImportError:
        try:
            # 包导入 - 当作为已安装的包运行时
            from src.config import (
                LOG_LEVEL,
                LOG_FORMAT,
            )
            from src.memobird_client import MemobirdDevice
        except ImportError:
            logging.error("Error: memobird modules not found or missing dependencies.")
            sys.exit(1)

# 设置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
log = logging.getLogger(__name__)


class MemobirdTools:
    """Memobird 打印机工具类，提供打印相关功能"""

    def __init__(self, mcp: FastMCP):
        """
        初始化 Memobird 工具类

        :param mcp: FastMCP 实例
        """
        self.mcp = mcp
        self._bird_client = None

        # 注册工具方法
        mcp.add_tool(self.print_text)
        mcp.add_tool(self.print_image)
        mcp.add_tool(self.print_url)

        log.info("Memobird 工具注册完成")

    def get_bird_client(self, ak=None, device_id=None):
        """
        获取或创建 Memobird 客户端实例

        :param ak: API Key（可选）
        :param device_id: 设备ID（可选）
        :return: MemobirdDevice 实例
        """
        # 如果已有实例并且没有提供新参数，直接返回现有实例
        if self._bird_client and not (ak or device_id):
            return self._bird_client

        # 确定凭据
        try:
            # 优先尝试从当前模块导入
            from .config import ENV_AK, ENV_DEVICE_ID
        except (ImportError, ValueError):
            try:
                # 然后尝试直接导入
                from config import ENV_AK, ENV_DEVICE_ID
            except ImportError:
                # 最后尝试包导入
                from src.config import ENV_AK, ENV_DEVICE_ID

        final_ak = ak or os.environ.get(ENV_AK)
        final_device_id = device_id or os.environ.get(ENV_DEVICE_ID)

        if not final_ak or not final_device_id:
            missing = []
            if not final_ak:
                missing.append("AK")
            if not final_device_id:
                missing.append("Device ID")
            error_msg = f"Error: Memobird {' and '.join(missing)} not provided."
            log.error(error_msg)
            raise ValueError(error_msg)

        # 创建新实例或更新现有实例
        try:
            self._bird_client = MemobirdDevice(ak=final_ak, device_id=final_device_id)
            log.info("MemobirdDevice client initialized successfully.")
            return self._bird_client
        except Exception as e:
            log.error(f"Error initializing MemobirdDevice client: {e}")
            raise

    def print_text(self, text: str) -> str:
        """
        将文本打印到Memobird打印机

        :param text: 要打印的文本
        :return: 打印结果信息
        """
        bird = self.get_bird_client()
        log.info(f"Received print_text request: '{text[:50]}...'")

        try:
            content_id = bird.print_text(text)
            log.info(f"Text sent to printer. Content ID: {content_id}")
            return f"Text sent to printer successfully. Content ID: {content_id}"
        except Exception as e:
            log.error(f"Error printing text: {e}", exc_info=True)
            return f"Error printing text: {e}"

    def print_image(self, image_path: str) -> str:
        """
        将图像打印到Memobird打印机

        :param image_path: 图像路径或Base64字符串
        :return: 打印结果信息
        """
        bird = self.get_bird_client()
        log.info(f"Received print_image request for: {image_path[:50]}...")

        try:
            # 检查输入是否为base64字符串
            if image_path.startswith("data:image"):
                # 从格式"data:image/png;base64,BASE64_DATA"中提取base64数据
                base64_data = image_path.split("base64,")[1]
                image_bytes = BytesIO(base64.b64decode(base64_data))
                content_id = bird.print_image(image_bytes)
                log.info(f"Base64 image sent to printer. Content ID: {content_id}")
                return f"Base64 image sent to printer successfully. Content ID: {content_id}"

            # 尝试解析为原始base64字符串
            if (
                "/" not in image_path
                and "\\" not in image_path
                and len(image_path) > 100
            ):
                try:
                    image_bytes = BytesIO(base64.b64decode(image_path))
                    content_id = bird.print_image(image_bytes)
                    log.info(
                        f"Raw base64 image sent to printer. Content ID: {content_id}"
                    )
                    return f"Raw base64 image sent to printer successfully. Content ID: {content_id}"
                except Exception as e:
                    log.debug(f"Failed to decode as base64, treating as file path: {e}")
                    pass  # 解码base64失败，继续处理为文件路径

            # 作为本地文件路径处理
            if not os.path.isfile(image_path):
                log.error(f"Error: Image file not found: {image_path}")
                return f"Error: Image file not found: {image_path}"

            content_id = bird.print_image(image_path)
            log.info(f"Image file sent to printer. Content ID: {content_id}")
            return f"Image sent to printer successfully. Content ID: {content_id}"
        except Exception as e:
            log.error(f"Error printing image: {e}", exc_info=True)
            return f"Error printing image: {e}"

    def print_url(self, url: str) -> str:
        """
        打印给定URL的内容

        :param url: 要打印的URL
        :return: 打印结果信息
        """
        bird = self.get_bird_client()
        log.info(f"Received print_url request for URL: {url}")

        try:
            content_id = bird.print_url(url)
            log.info(f"URL content sent to printer. Content ID: {content_id}")
            return f"URL content sent to printer successfully. Content ID: {content_id}"
        except Exception as e:
            log.error(f"Error printing URL: {e}", exc_info=True)
            return f"Error printing URL: {e}"
