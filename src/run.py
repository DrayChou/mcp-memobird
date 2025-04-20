import os
import argparse
import sys
import base64
from io import BytesIO
from fastmcp import FastMCP

# 导入客户端类和异常
try:
    from client import (
        MemobirdDevice,
    )
except ImportError:
    print("Error: mcp_memobird.client module not found or missing dependencies.")
    sys.exit(1)

# 配置
SERVER_NAME = "Memobird Printer Server"
DEFAULT_SSE_PORT = 8000
bird = None  # 全局Memobird客户端实例

# 创建FastMCP实例
mcp = FastMCP(SERVER_NAME)


def get_bird_client(args=None):
    """返回初始化的Memobird客户端实例"""
    global bird
    
    if bird:
        return bird
        
    if args is None:
        args = argparse.Namespace(ak=None, did=None)
        
    # 确定凭据(CLI参数覆盖环境变量)
    ak = args.ak or os.environ.get("MEMOBIRD_AK")
    did = args.did or os.environ.get("MEMOBIRD_DEVICE_ID")
    
    if not ak or not did:
        error = []
        if not ak: error.append("AK")
        if not did: error.append("Device ID")
        print(f"Error: Memobird {' and '.join(error)} not provided via arguments or environment variables.")
        sys.exit(1)
    
    # 初始化Memobird客户端
    try:
        bird = MemobirdDevice(ak=ak, device_id=did)
        print("MemobirdDevice client initialized successfully.")
        return bird
    except Exception as e:
        print(f"Error initializing MemobirdDevice client: {e}")
        sys.exit(1)


@mcp.tool()
def print_text(text: str) -> str:
    """将文本打印到Memobird打印机"""
    bird = get_bird_client()
    print(f"Received print_text request: '{text[:50]}...'")
    
    try:
        content_id = bird.print_text(text)
        result = f"Text sent to printer successfully. Content ID: {content_id}"
        print(result)
        return result
    except Exception as e:
        error_msg = f"Error printing text: {e}"
        print(error_msg)
        return error_msg


@mcp.tool()
def print_image(image_path: str) -> str:
    """将图像打印到Memobird打印机"""
    bird = get_bird_client()
    print(f"Received print_image request for: {image_path[:50]}...")
    
    try:
        # 检查输入是否为base64字符串
        if image_path.startswith("data:image"):
            # 从格式"data:image/png;base64,BASE64_DATA"中提取base64数据
            base64_data = image_path.split("base64,")[1]
            image_bytes = BytesIO(base64.b64decode(base64_data))
            content_id = bird.print_image(image_bytes)
            return f"Base64 image sent to printer successfully. Content ID: {content_id}"
        
        # 尝试解析为原始base64字符串
        if "/" not in image_path and "\\" not in image_path and len(image_path) > 100:
            try:
                image_bytes = BytesIO(base64.b64decode(image_path))
                content_id = bird.print_image(image_bytes)
                return f"Raw base64 image sent to printer successfully. Content ID: {content_id}"
            except Exception:
                pass  # 解码base64失败，继续处理为文件路径
        
        # 作为本地文件路径处理
        if not os.path.isfile(image_path):
            return f"Error: Image file not found: {image_path}"
        
        content_id = bird.print_image(image_path)
        return f"Image sent to printer successfully. Content ID: {content_id}"
    except Exception as e:
        return f"Error printing image: {e}"


@mcp.tool()
def print_url(url: str) -> str:
    """打印给定URL的内容"""
    print(f"Received print_url request for URL: {url}")
    
    try:
        content_id = get_bird_client().print_url(url)
        return f"URL content sent to printer successfully. Content ID: {content_id}"
    except Exception as e:
        return f"Error printing URL: {e}"


def main():
    parser = argparse.ArgumentParser(description=f"Start the {SERVER_NAME}")
    parser.add_argument("--transport", "-t", type=str, choices=["stdio", "sse"], 
                      default="stdio", help="Transport protocol to use")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_SSE_PORT,
                      help=f"Port for SSE server (default: {DEFAULT_SSE_PORT})")
    parser.add_argument("--ak", "--access_key", dest="ak", type=str, default=None,
                      help="Memobird API Key (overrides MEMOBIRD_AK env var)")
    parser.add_argument("--did", "--device_id", dest="did", type=str, default=None,
                      help="Memobird Device ID (overrides MEMOBIRD_DEVICE_ID env var)")
    
    args = parser.parse_args()
    
    # 设置环境变量
    if args.ak: os.environ["MEMOBIRD_AK"] = args.ak
    if args.did: os.environ["MEMOBIRD_DEVICE_ID"] = args.did
    
    print(f"Starting {SERVER_NAME} with transport: {args.transport}")
    
    # 初始化客户端（确保凭据有效）
    get_bird_client(args)
    
    # 启动MCP服务器
    if args.transport == "stdio":
        print("Running with stdio transport...")
        mcp.run()
    else:
        print(f"Running with SSE transport on port {args.port}...")
        import asyncio
        asyncio.run(mcp.run_sse_async(host="0.0.0.0", port=args.port, log_level="debug"))


if __name__ == "__main__":
    main()
