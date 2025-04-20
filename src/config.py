"""
Memobird 打印机 MCP 服务的配置文件
"""

# 服务器配置
SERVER_NAME = "Memobird Printer Server"
DEFAULT_SSE_PORT = 8000

# API配置
MEMOBIRD_API_BASE_URL = "http://open.memobird.cn/home"
DEFAULT_REQUEST_TIMEOUT = 15  # seconds

# 图像处理配置
IMAGE_MAX_WIDTH = 384  # 打印机最大宽度

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# 环境变量名称
ENV_AK = "MEMOBIRD_AK"
ENV_DEVICE_ID = "MEMOBIRD_DEVICE_ID"