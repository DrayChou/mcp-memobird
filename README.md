# MCP-Memobird

基于 Model Context Protocol (MCP) 的咕咕机（Memobird）打印服务器。通过这个服务，你可以向咕咕机发送文本、图片或网页链接进行打印。

## 功能特点

- 支持多种传输协议：stdio 和 SSE（Server-Sent Events）
- 提供三种打印功能：
  - 打印文本
  - 打印图片（支持本地文件或 base64 编码数据）
  - 打印 URL 网页内容
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
1. 命令行参数：`--ak` 和 `--did`
2. 环境变量：`MEMOBIRD_AK` 和 `MEMOBIRD_DEVICE_ID`

### 启动服务器

安装后可以通过以下方式启动：

```bash
# 使用命令行脚本（安装后可用）
mcp-memobird --ak YOUR_MEMOBIRD_AK --did YOUR_DEVICE_ID --transport stdio

# 或使用 Python 模块
python -m src.run --ak YOUR_MEMOBIRD_AK --did YOUR_DEVICE_ID --transport stdio

# 或使用环境变量
export MEMOBIRD_AK=YOUR_MEMOBIRD_AK
export MEMOBIRD_DEVICE_ID=YOUR_DEVICE_ID
mcp-memobird --transport sse --port 8000
```

### 可用的 MCP 工具

服务器提供以下 MCP 工具函数：

1. **打印文本**
   ```python
   print_text("你好，咕咕机！")
   ```

2. **打印图片**
   ```python
   # 本地图片
   print_image("/path/to/image.jpg")
   
   # 或 base64 编码图片（带前缀）
   print_image("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...")
   
   # 或 base64 编码图片（原始数据）
   print_image("iVBORw0KGgoAAAANSUhEUgAA...")
   ```

3. **打印 URL 网页内容**
   ```python
   print_url("https://example.com/page.html")
   ```

## SSE 模式 API 端点

当使用 SSE 模式运行时，以下 API 端点可用：

- `GET /` - 服务器首页
- `GET /sse` - SSE 连接端点
- `POST /messages` - 发送命令到 MCP 服务器

## 为开发者

如果您想为项目做贡献，可以按以下步骤设置开发环境：

```bash
git clone https://github.com/DrayChou/mcp-memobird.git
cd mcp-memobird
# 安装开发依赖
uv pip install -e ".[dev]"
# 或使用传统 pip
pip install -e ".[dev]"
```

## 项目结构

```
mcp-memobird/
├── pyproject.toml      # 项目配置、依赖和构建信息
├── README.md           # 项目文档
├── requirements.txt    # 项目依赖
├── src/                # 源代码目录
│   ├── config.py       # 配置文件
│   ├── run.py          # 主程序和服务器实现
│   └── libs/           # 库目录
│       └── client.py   # 咕咕机客户端实现
```

## 配置说明

配置文件 `src/config.py` 中包含以下可配置项：

- 服务器配置：服务名称和默认端口
- API 配置：API 基础 URL 和请求超时时间
- 图像处理配置：最大图像宽度
- 日志配置：日志级别和格式

## 依赖

- [fastmcp](https://github.com/microsoft/mcp) - 快速 MCP 实现
- Pillow - 图像处理
- requests - HTTP 客户端
- starlette/uvicorn - 用于 SSE 模式

## 环境要求

- Python 3.8+

## 许可证

[MIT License](LICENSE)
