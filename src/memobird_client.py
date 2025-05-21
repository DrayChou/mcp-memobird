import base64
import logging
import sys
from datetime import datetime
from io import BytesIO
from typing import List, Tuple, Union, Optional, Any

import requests
from PIL import Image, UnidentifiedImageError

# 导入配置
try:
    # 相对导入 - 当作为模块运行时
    from .config import (
        MEMOBIRD_API_BASE_URL,
        DEFAULT_REQUEST_TIMEOUT,
        IMAGE_MAX_WIDTH,
        LOG_LEVEL,
        LOG_FORMAT,
    )
except (ImportError, ValueError):
    try:
        # 直接导入 - 当在src目录内运行时
        from config import (
            MEMOBIRD_API_BASE_URL,
            DEFAULT_REQUEST_TIMEOUT,
            IMAGE_MAX_WIDTH,
            LOG_LEVEL,
            LOG_FORMAT,
        )
    except ImportError:
        try:
            # 包导入 - 当作为已安装的包运行时
            from src.config import (
                MEMOBIRD_API_BASE_URL,
                DEFAULT_REQUEST_TIMEOUT,
                IMAGE_MAX_WIDTH,
                LOG_LEVEL,
                LOG_FORMAT,
            )
        except ImportError:
            logging.error("Error: memobird modules not found or missing dependencies.")
            sys.exit(1)

# 设置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
log = logging.getLogger(__name__)


# --- 辅助函数 ---
def _current_timestamp() -> str:
    """返回API要求格式的当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- 自定义异常 ---
class MemobirdError(Exception):
    """Memobird客户端错误的基类"""

    pass


class ApiError(MemobirdError):
    """API错误"""

    def __init__(
        self, res_code: int, res_error: str, status_code: Optional[int] = None
    ):
        self.res_code = res_code
        self.res_error = res_error
        self.status_code = status_code
        super().__init__(
            f"API Error (HTTP Status: {status_code}, API Code: {res_code}): {res_error}"
        )


class NetworkError(MemobirdError):
    """网络相关错误"""

    pass


class ContentError(MemobirdError):
    """内容处理错误"""

    pass


# --- API响应处理 ---
def _check_api_response(resp: requests.Response) -> dict:
    """检查API响应是否有错误，成功则返回JSON数据"""
    try:
        resp.raise_for_status()  # 抛出HTTP错误（4xx或5xx）
        data = resp.json()
        # API成功代码为1
        if data.get("showapi_res_code") != 1:
            raise ApiError(
                res_code=data.get("showapi_res_code", -1),
                res_error=data.get("showapi_res_error", "Unknown API error"),
                status_code=resp.status_code,
            )
        return data
    except requests.exceptions.HTTPError as e:
        # 包含响应文本以便于调试
        response_text = ""
        try:
            response_text = f" Response: {resp.text[:200]}..."  # 限制响应文本长度
        except Exception:
            pass  # 忽略读取响应文本的错误
        raise NetworkError(f"HTTP Error: {e}.{response_text}") from e
    except requests.exceptions.JSONDecodeError as e:
        raise ApiError(
            res_code=-2,
            res_error=f"Failed to decode JSON response: {e}. Response text: {resp.text[:100]}...",
            status_code=resp.status_code,
        )
    except requests.exceptions.RequestException as e:
        # 捕获其他潜在的请求错误（超时、连接错误等）
        raise NetworkError(f"Network request failed: {e}") from e


# --- 内容构建器 ---
class PrintPayloadBuilder:
    """构建用于打印文本和图像的有效载荷字符串"""

    def __init__(self):
        self._parts: List[Tuple[str, Union[str, bytes]]] = []

    def add_text(self, text: str):
        """添加文本部分"""
        if not isinstance(text, str):
            raise TypeError("Text content must be a string.")
        log.debug("Adding text part.")
        self._parts.append(("T", text))
        return self  # 允许链式调用

    def add_image(self, image_source: Union[str, BytesIO, Image.Image]):
        """
        添加图像部分。处理图像以供打印。
        :param image_source: 图像文件路径、BytesIO对象或PIL Image对象。
        """
        log.debug(f"Adding image part from source type: {type(image_source)}")
        try:
            if isinstance(image_source, Image.Image):
                image = image_source
            else:
                # 处理路径（str）或BytesIO
                image = Image.open(image_source)

            # 确保图像为RGB模式，然后再转换为1位黑白
            if image.mode != "RGB":
                image = image.convert("RGB")

            # 如果宽度大于最大宽度，则调整大小
            width, height = image.size
            if width > IMAGE_MAX_WIDTH:
                new_height = int(height * IMAGE_MAX_WIDTH / width)
                log.info(
                    f"Resizing image from {width}x{height} to {IMAGE_MAX_WIDTH}x{new_height}"
                )
                image = image.resize(
                    (IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS
                )

            # 转换为1位黑白
            image = image.convert("1")

            # 在内存中保存为BMP格式
            with BytesIO() as buffer:
                image.save(buffer, "BMP")
                image_bytes = buffer.getvalue()

            self._parts.append(("P", image_bytes))
            log.debug("Image processed and added successfully.")

        except FileNotFoundError as e:
            raise ContentError(f"Image file not found: {image_source}") from e
        except UnidentifiedImageError as e:
            raise ContentError(
                f"Cannot identify image file: {e}. Source: {image_source}"
            ) from e
        except Exception as e:
            # 捕获其他PIL/IO错误
            raise ContentError(f"Error processing image: {e}") from e

        return self  # 允许链式调用

    def build(self) -> str:
        """将所有部分编码为用管道分隔的Base64字符串"""
        encoded_parts: List[str] = []
        num_parts = len(self._parts)

        for index, (content_type, data) in enumerate(self._parts):
            try:
                if content_type == "T":
                    text_data = data
                    # 确保文本以换行符结尾（如果不是最后一部分）
                    if index < num_parts - 1 and not text_data.endswith("\n"):
                        text_data += "\n"
                    # 使用GBK编码文本（API要求）
                    encoded_data = base64.b64encode(
                        text_data.encode("GBK", errors="ignore")
                    ).decode("ascii")
                    encoded_parts.append(f"T:{encoded_data}")
                elif content_type == "P":
                    # 编码图像BMP字节
                    encoded_data = base64.b64encode(data).decode("ascii")
                    encoded_parts.append(f"P:{encoded_data}")
            except Exception as e:
                log.error(
                    f"Error encoding part (Type: {content_type}): {e}. Skipping part."
                )

        payload = "|".join(encoded_parts)
        log.debug(f"Built payload string (length: {len(payload)}): {payload[:50]}...")
        return payload


# --- API客户端 ---
class MemobirdApiClient:
    """处理与Memobird API的直接通信"""

    def __init__(self, ak: str, session: Optional[requests.Session] = None):
        if not ak:
            raise ValueError("Memobird API Key (ak) cannot be empty.")
        self._ak = ak
        # 使用提供的会话或创建新会话
        self._session = session if session else requests.Session()
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        log.info("MemobirdApiClient initialized.")

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        stream: bool = False,  # 新增 stream 参数
    ) -> Union[dict, requests.Response]:  # 返回类型可以是 dict 或 Response
        """向Memobird API发出HTTP请求并处理响应"""
        url = MEMOBIRD_API_BASE_URL + path
        log.debug(
            f"Making {method} request to {url} with params={params}, json={json_data}, stream={stream}"
        )
        try:
            resp = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=self._headers,
                timeout=timeout,
                stream=stream,  # 将 stream 参数传递给 requests
            )
            if stream:
                # 对于流式请求，进行初步的HTTP错误检查，然后直接返回响应对象
                # 调用者负责处理内容和关闭响应
                resp.raise_for_status()  # 检查HTTP错误
                return resp

            return _check_api_response(resp)  # 对于非流式请求，按原样处理
        except MemobirdError:  # 重新抛出我们的特定错误
            raise
        except requests.exceptions.HTTPError as e:
            # 对于流式请求，如果 raise_for_status 失败，则捕获并作为 NetworkError 引发
            # 对于非流式请求，_check_api_response 内部已处理
            response_text = ""
            if e.response is not None:
                try:
                    response_text = f" Response: {e.response.text[:200]}..."
                except Exception:
                    pass
            raise NetworkError(f"HTTP Error: {e}.{response_text}") from e
        except Exception as e:  # 捕获请求期间的意外错误
            raise NetworkError(f"Unexpected error during API request: {e}") from e

    def get_user_id(self, device_id: str, user_identifying: str = "") -> str:
        """将用户绑定到设备并检索用户ID"""
        path = "/setuserbind"
        params = {
            "ak": self._ak,
            "timestamp": _current_timestamp(),
            "memobirdID": device_id,
            "useridentifying": user_identifying,
        }
        log.info(f"Getting user ID for device {device_id}...")
        api_data = self._make_request("GET", path, params=params)
        user_id = api_data.get("showapi_userid")
        if not user_id:
            raise ApiError(
                api_data.get("showapi_res_code", -1),
                "User ID not found in successful API response.",
            )
        log.info(f"Obtained user ID: {user_id}")
        return user_id

    def print_content(
        self, device_id: str, user_id: str, payload: PrintPayloadBuilder
    ) -> int:
        """将内容有效载荷发送到打印机API"""
        path = "/printpaper"
        content_string = payload.build()
        if not content_string:
            log.warning("Content payload is empty, nothing to print.")
            raise ContentError("Cannot print empty content.")

        json_data = {
            "ak": self._ak,
            "timestamp": _current_timestamp(),
            "printcontent": content_string,
            "memobirdID": device_id,
            "userID": user_id,
        }
        log.info(f"Sending content to device {device_id} (User: {user_id})...")
        api_data = self._make_request(
            "POST", path, json_data=json_data, timeout=20
        )  # 打印时超时更长
        content_id = api_data.get("printcontentid")
        if content_id is None:
            raise ApiError(
                api_data.get("showapi_res_code", -1),
                "Content ID not found in successful print API response.",
            )
        log.info(f"Print request successful. Content ID: {content_id}")
        return int(content_id)  # API返回int

    def print_url(self, device_id: str, user_id: str, url: str) -> int:
        """打印URL的内容"""
        path = "/printpaperFromUrl"
        json_data = {
            "ak": self._ak,
            "timestamp": _current_timestamp(),
            "printUrl": url,
            "memobirdID": device_id,
            "userID": user_id,
        }
        log.info(f"Sending URL {url} to device {device_id} (User: {user_id})...")
        api_data = self._make_request(
            "POST", path, json_data=json_data, timeout=30
        )  # URL打印时超时更长
        content_id = api_data.get("printcontentid")
        if content_id is None:
            raise ApiError(
                api_data.get("showapi_res_code", -1),
                "Content ID not found in successful print URL API response.",
            )
        log.info(f"Print URL request successful. Content ID: {content_id}")
        return int(content_id)

    def check_print_status(self, content_id: int) -> bool:
        """检查特定内容ID的打印状态"""
        path = "/getprintstatus"
        params = {
            "ak": self._ak,
            "timestamp": _current_timestamp(),
            "printcontentid": content_id,
        }
        log.info(f"Checking print status for Content ID: {content_id}...")
        api_data = self._make_request("GET", path, params=params)
        is_printed = api_data.get("printflag") == 1
        log.info(
            f"Print status for {content_id}: {'Printed' if is_printed else 'Not Printed/Pending'}"
        )
        return is_printed


# --- 设备接口 ---
class MemobirdDevice:
    """控制单个Memobird设备的简化接口"""

    def __init__(self, ak: str, device_id: str, user_identifying: str = ""):
        log.info(f"Initializing MemobirdDevice for device: {device_id}...")
        self._client = MemobirdApiClient(ak)  # 可能抛出ValueError
        self.device_id = device_id
        # get_user_id可能抛出ApiError或NetworkError
        self.user_id = self._client.get_user_id(self.device_id, user_identifying)
        log.info(f"MemobirdDevice initialized for User ID: {self.user_id}.")

    def print_text(self, text: str) -> int:
        """在配置的设备上打印文本"""
        payload = PrintPayloadBuilder().add_text(text)
        # print_content可能抛出ApiError、NetworkError、ContentError
        return self._client.print_content(self.device_id, self.user_id, payload)

    def print_image(self, image_source: Union[str, BytesIO, Image.Image]) -> int:
        """在配置的设备上打印图像"""
        try:
            payload = PrintPayloadBuilder().add_image(image_source)
            # print_content可能抛出ApiError、NetworkError
            return self._client.print_content(self.device_id, self.user_id, payload)
        except ContentError as e:
            # 记录并重新抛出
            log.error(f"Failed to prepare image for printing: {e}")
            raise

    def print_payload(self, payload: PrintPayloadBuilder) -> int:
        """打印预构建的有多个部分的有效载荷"""
        # print_content可能抛出ApiError、NetworkError、ContentError（如果构建失败）
        return self._client.print_content(self.device_id, self.user_id, payload)

    def print_url(self, url: str) -> int:
        """在配置的设备上打印URL的内容"""
        # print_url可能抛出ApiError、NetworkError
        return self._client.print_url(self.device_id, self.user_id, url)

    def check_print_status(self, content_id: int) -> bool:
        """检查配置设备的打印状态"""
        # check_print_status可能抛出ApiError、NetworkError
        return self._client.check_print_status(content_id)
