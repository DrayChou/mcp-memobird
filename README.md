# MCP-Memobird

基于 Model Context Protocol (MCP) 的咕咕机（Memobird）打印服务器。通过这个服务，你可以向咕咕机发送文本、图片或网页链接进行打印。

## 功能特点

- 支持多种传输协议：
  - `stdio`: 通过标准输入/输出进行交互。
  - `sse`: 通过 **Server-Sent Events (SSE)** 提供 **streamable HTTP 支持**。当工具产生分块或逐步的数据时，这些数据可以通过 SSE 流式传输给客户端。
- 提供多种打印功能：
  - 打印文本
  - 打印图片（支持本地文件路径、URL、或 base64 编码数据）
  - 打印 URL 网页内容 (由咕咕机设备直接获取)
- **客户端增强**: 底层的 `memobird_client` 已得到增强，支持消费 HTTP 流。这对于从 URL 高效处理潜在的大数据（如图像）非常有用，尽管面向咕咕机 API 的主要打印操作本身仍然是非流式的。
- 详细的错误处理和日志记录
- 易于集成到其他应用程序中
- 支持使用 uv 包管理工具安装

## 安装

### 使用 uv 安装（推荐）

1. 确保已安装 [uv](https://github.com/astral-sh/uv)

2. 从本地安装（开发模式）：

```bash
git clone https://github.com/DrayChou/mcp-memobird.git
cd mcp-memobird
uv pip install -e .
```

3. 或直接从 Git 仓库安装：

```bash
uv pip install git+https://github.com/DrayChou/mcp-memobird.git
```

### 使用传统 pip 安装

```bash
git clone https://github.com/DrayChou/mcp-memobird.git
cd mcp-memobird
pip install -e .
```

## 使用方法

### 配置

使用前需要准备：
- 咕咕机 API 密钥 (AK)
- 设备 ID (通过连续按设备两次获取)

可以通过以下两种方式配置：
1. 命令行参数：`--ak YOUR_AK` 和 `--did YOUR_DEVICE_ID`
2. 环境变量：`MEMOBIRD_AK` 和 `MEMOBIRD_DEVICE_ID`

### 启动服务器

安装后可以通过以下方式启动：

```bash
# 使用命令行脚本（安装后可用）
mcp-memobird --ak YOUR_MEMOBIRD_AK --did YOUR_DEVICE_ID --transport stdio

# 或使用 Python 模块 (假设您在项目根目录)
python -m src.main --ak YOUR_MEMOBIRD_AK --did YOUR_DEVICE_ID --transport stdio

# 或使用环境变量启动 SSE 模式
export MEMOBIRD_AK=YOUR_MEMOBIRD_AK
export MEMOBIRD_DEVICE_ID=YOUR_DEVICE_ID
mcp-memobird --transport sse --port 8000
```

### 可用的 MCP 工具

服务器提供以下 MCP 工具函数：

1.  **`print_text(text: str)`**
    - 描述：打印给定的文本。
    - 示例：`print_text "你好，咕咕机！"`

2.  **`print_image_from_url(url: str)`**
    - 描述：从指定的 URL 下载图片并打印。
    - 示例：`print_image_from_url "https://www.example.com/image.png"`
    - _注意：此工具会尝试下载网络图片进行打印。_

3.  **`check_print_status(content_id: int)`**
    - 描述：检查指定打印内容 ID 的打印状态。
    - 示例：`check_print_status 123456789`

4.  **`stream_test(count: int = 3)`**
    - 描述：一个演示工具，用于流式传输多个事件。当使用 SSE 传输时，每个事件将作为单独的 SSE 消息发送。
    - 示例：`stream_test count=5`

_注意：旧的 `print_image` 工具接受本地文件路径或 base64 数据，为了简化工具列表，推荐使用 `print_image_from_url` 处理网络图片，或通过其他方式将图片内容传递给如 `print_text`（如果适用，例如传递 base64 字符串给一个更通用的打印工具，但这超出了当前工具的直接范围）。如需打印本地图片，请确保服务器可以访问该路径，或将其转换为适合传输的格式。_


## SSE 模式 API 端点

当使用 `--transport sse` 模式运行时，服务器通过 FastMCP 框架提供服务。主要的交互方式是：

- **工具调用**: 客户端通常会向类似 `/api/v1/call/<tool_name>` 的端点发出请求（具体取决于客户端库或直接的 HTTP 请求构造）。
    - 对于如 `stream_test` 这样的生成器工具，FastMCP 会自动通过 SSE 连接流式传输其产生的数据。客户端应使用支持 SSE 的库（如 `sseclient-py`）或正确处理 `text/event-stream` 响应。
- **FastMCP 标准端点**: FastMCP 可能还会暴露其他标准端点（例如，用于列出工具 `/api/v1/tools`）。请参考 FastMCP 文档或实际服务器输出来获取确切信息。

## 为开发者

如果您想为项目做贡献，可以按以下步骤设置开发环境：

```bash
git clone https://github.com/DrayChou/mcp-memobird.git
cd mcp-memobird
```

### 安装依赖

项目使用 `pyproject.toml` 定义依赖。

- **主依赖**: 使用 `uv pip install -e .` 或 `pip install -e .` 安装。
- **开发依赖**: 包括用于测试、linting 等的工具。可以通过 `uv pip install -e ".[dev]"` 或 `pip install -e ".[dev]"` 安装。
  另外，一些特定的测试（如集成测试）可能需要额外的库。这些库列在 `requirements-dev.txt` 中，例如 `sseclient-py` 用于测试 SSE 流。您可以使用 `uv pip install -r requirements-dev.txt` 或 `pip install -r requirements-dev.txt` 来安装它们。

### 运行测试

（在此处添加关于如何运行测试的说明，例如 `python -m unittest discover tests`）

## 项目结构 (概览)

```
mcp-memobird/
├── pyproject.toml        # 项目配置、主依赖和构建信息
├── README.md             # 项目文档
├── requirements-dev.txt  # 开发和测试特定依赖
├── src/                  # 源代码目录
│   ├── __init__.py
│   ├── config.py         # 配置文件
│   ├── main.py           # 主程序和服务器启动 (替代旧的 run.py)
│   ├── memobird_client.py # 咕咕机客户端核心逻辑
│   └── memobird_tools.py  # MCP 工具定义
└── tests/                # 测试目录
    ├── __init__.py
    ├── test_memobird_client.py
    └── test_main_integration.py
```

## 配置说明

配置文件 `src/config.py` 中包含以下可配置项：

- 服务器配置：服务名称和默认端口
- API 配置：API 基础 URL 和请求超时时间
- 图像处理配置：最大图像宽度
- 日志配置：日志级别和格式

## 主要依赖

- [fastmcp](https://github.com/microsoft/mcp) - 快速 MCP 实现
- Pillow - 图像处理
- requests - HTTP 客户端
- Starlette/Uvicorn - 用于 SSE 模式 (FastMCP 底层可能使用)

## 环境要求

- Python 3.8+

## 许可证

[MIT License](LICENSE)
