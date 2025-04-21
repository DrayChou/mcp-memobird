import os
import argparse
import sys
import logging
from fastmcp import FastMCP

# 导入配置和工具
try:
    # 相对导入 - 当作为模块运行时
    from .config import (
        SERVER_NAME,
        DEFAULT_SSE_PORT,
        ENV_AK,
        ENV_DEVICE_ID,
        LOG_LEVEL,
        LOG_FORMAT,
    )
    from .memobird_tools import MemobirdTools
except (ImportError, ValueError):
    try:
        # 直接导入 - 当在src目录内运行时
        from config import (
            SERVER_NAME,
            DEFAULT_SSE_PORT,
            ENV_AK,
            ENV_DEVICE_ID,
            LOG_LEVEL,
            LOG_FORMAT,
        )
        from memobird_tools import MemobirdTools
    except ImportError:
        try:
            # 包导入 - 当作为已安装的包运行时
            from src.config import (
                SERVER_NAME,
                DEFAULT_SSE_PORT,
                ENV_AK,
                ENV_DEVICE_ID,
                LOG_LEVEL,
                LOG_FORMAT,
            )
            from src.memobird_tools import MemobirdTools
        except ImportError:
            logging.error("Error: memobird modules not found or missing dependencies.")
            sys.exit(1)

# 设置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
log = logging.getLogger(__name__)

# 创建FastMCP实例
mcp = FastMCP(SERVER_NAME)


def _register():
    """注册所有工具到MCP实例"""
    log.info("开始注册工具...")

    # 注册Memobird打印工具
    MemobirdTools(mcp)

    # 可以在这里添加更多工具类的初始化
    # ExampleTools(mcp)

    log.info("工具注册完成")


def run():
    parser = argparse.ArgumentParser(description=f"Start the {SERVER_NAME}")
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol to use",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_SSE_PORT,
        help=f"Port for SSE server (default: {DEFAULT_SSE_PORT})",
    )
    parser.add_argument(
        "--ak",
        "--access_key",
        dest="ak",
        type=str,
        default=None,
        help="Memobird API Key (overrides MEMOBIRD_AK env var)",
    )
    parser.add_argument(
        "--did",
        "--device_id",
        dest="did",
        type=str,
        default=None,
        help="Memobird Device ID (overrides MEMOBIRD_DEVICE_ID env var)",
    )

    args = parser.parse_args()

    # 设置环境变量（便于其他函数访问）
    if args.ak:
        os.environ[ENV_AK] = args.ak
    if args.did:
        os.environ[ENV_DEVICE_ID] = args.did

    log.info(f"Starting {SERVER_NAME} with transport: {args.transport}")

    # 注册各种组件
    _register()

    log.info("所有组件注册完成，准备启动服务...")

    # 启动MCP服务器
    if args.transport == "stdio":
        log.info("Running with stdio transport...")
        mcp.run()
    else:
        log.info(f"Running with SSE transport on port {args.port}...")
        import asyncio

        asyncio.run(
            mcp.run_sse_async(host="0.0.0.0", port=args.port, log_level=LOG_LEVEL.lower())
        )


if __name__ == "__main__":
    run()
