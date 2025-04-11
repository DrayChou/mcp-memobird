import base64
import logging
from datetime import datetime
from io import BytesIO
from typing import List, Tuple, Union, Optional, Any

import requests
from PIL import Image, UnidentifiedImageError

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Constants ---
MEMOBIRD_API_BASE_URL = "http://open.memobird.cn/home"
DEFAULT_REQUEST_TIMEOUT = 15  # seconds
IMAGE_MAX_WIDTH = 384


# --- Helper Functions ---
def _current_timestamp() -> str:
    """Returns the current timestamp in the format required by the API."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- Custom Exceptions ---
class MemobirdError(Exception):
    """Base exception for Memobird client errors."""

    pass


class ApiError(MemobirdError):
    """Custom exception for Memobird API errors."""

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
    """Custom exception for network-related errors during API calls."""

    pass


class ContentError(MemobirdError):
    """Custom exception for errors related to content processing (e.g., image handling)."""

    pass


# --- API Response Handling ---
def _check_api_response(resp: requests.Response) -> dict:
    """Checks the API response for errors and returns JSON data on success."""
    try:
        resp.raise_for_status()  # Raise HTTPError for bad status codes (4xx or 5xx)
        data = resp.json()
        # API success code is 1
        if data.get("showapi_res_code") != 1:
            raise ApiError(
                res_code=data.get("showapi_res_code", -1),
                res_error=data.get("showapi_res_error", "Unknown API error"),
                status_code=resp.status_code,
            )
        return data
    except requests.exceptions.HTTPError as e:
        # Include response text for better debugging if possible
        response_text = ""
        try:
            response_text = (
                f" Response: {resp.text[:200]}..."  # Limit response text length
            )
        except Exception:
            pass  # Ignore errors reading response text
        raise NetworkError(f"HTTP Error: {e}.{response_text}") from e
    except requests.exceptions.JSONDecodeError as e:
        raise ApiError(
            res_code=-2,
            res_error=f"Failed to decode JSON response: {e}. Response text: {resp.text[:100]}...",
            status_code=resp.status_code,
        )
    except requests.exceptions.RequestException as e:
        # Catch other potential requests errors (timeout, connection error, etc.)
        raise NetworkError(f"Network request failed: {e}") from e


# --- Content Builder ---
class PrintPayloadBuilder:
    """Builds the payload string for printing text and images."""

    def __init__(self):
        self._parts: List[Tuple[str, Union[str, bytes]]] = []

    def add_text(self, text: str):
        """Adds a text part."""
        if not isinstance(text, str):
            raise TypeError("Text content must be a string.")
        log.debug("Adding text part.")
        self._parts.append(("T", text))
        return self  # Allow chaining

    def add_image(self, image_source: Union[str, BytesIO, Image.Image]):
        """
        Adds an image part. Processes the image for printing.
        :param image_source: Path to image file, BytesIO object, or PIL Image object.
        """
        log.debug(f"Adding image part from source type: {type(image_source)}")
        try:
            if isinstance(image_source, Image.Image):
                image = image_source
            else:
                # Handles path (str) or BytesIO
                image = Image.open(image_source)

            # Ensure image is in RGB mode before potentially converting to 1-bit
            # This helps avoid issues with palette transparency or other modes
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Optional: Flip image if needed (seems device-dependent, test without first)
            # image = image.transpose(Image.FLIP_TOP_BOTTOM)

            # Resize if wider than max width
            width, height = image.size
            if width > IMAGE_MAX_WIDTH:
                new_height = int(height * IMAGE_MAX_WIDTH / width)
                log.info(
                    f"Resizing image from {width}x{height} to {IMAGE_MAX_WIDTH}x{new_height}"
                )
                image = image.resize(
                    (IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS
                )

            # Convert to 1-bit black and white
            image = image.convert("1")

            # Save to BMP format in memory
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
            # Catch other PIL/IO errors
            raise ContentError(f"Error processing image: {e}") from e

        return self  # Allow chaining

    def build(self) -> str:
        """Encodes all parts into the pipe-separated Base64 string."""
        encoded_parts: List[str] = []
        num_parts = len(self._parts)

        for index, (content_type, data) in enumerate(self._parts):
            encoded_data = ""
            try:
                if content_type == "T":
                    text_data = data
                    # Ensure text ends with newline if not the last part
                    if index < num_parts - 1 and not text_data.endswith("\n"):
                        text_data += "\n"
                    # Encode text using GBK as required by the API
                    encoded_data = base64.b64encode(
                        text_data.encode("GBK", errors="ignore")
                    ).decode("ascii")
                    encoded_parts.append(f"T:{encoded_data}")
                elif content_type == "P":
                    # Encode image BMP bytes
                    encoded_data = base64.b64encode(data).decode("ascii")
                    encoded_parts.append(f"P:{encoded_data}")
            except Exception as e:
                log.error(
                    f"Error encoding part (Type: {content_type}): {e}. Skipping part."
                )
                # Optionally raise ContentError here instead of just logging

        payload = "|".join(encoded_parts)
        log.debug(f"Built payload string (length: {len(payload)}): {payload[:50]}...")
        return payload


# --- API Client ---
class MemobirdApiClient:
    """Handles direct communication with the Memobird API."""

    def __init__(self, ak: str, session: Optional[requests.Session] = None):
        if not ak:
            raise ValueError("Memobird API Key (ak) cannot be empty.")
        self._ak = ak
        # Use provided session or create a new one
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
    ) -> dict:
        """Makes an HTTP request to the Memobird API and handles response."""
        url = MEMOBIRD_API_BASE_URL + path
        log.debug(
            f"Making {method} request to {url} with params={params}, json={json_data}"
        )
        try:
            resp = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=self._headers,
                timeout=timeout,
            )
            return _check_api_response(resp)  # Returns JSON data on success
        except MemobirdError:  # Re-raise our specific errors
            raise
        except Exception as e:  # Catch unexpected errors during request
            raise NetworkError(f"Unexpected error during API request: {e}") from e

    def get_user_id(self, device_id: str, user_identifying: str = "") -> str:
        """Binds a user to a device and retrieves the user ID."""
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
        """Sends content payload to the printer API."""
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
        )  # Longer timeout for printing
        content_id = api_data.get("printcontentid")
        if content_id is None:
            raise ApiError(
                api_data.get("showapi_res_code", -1),
                "Content ID not found in successful print API response.",
            )
        log.info(f"Print request successful. Content ID: {content_id}")
        return int(content_id)  # API returns int

    def print_url(self, device_id: str, user_id: str, url: str) -> int:
        """Prints content from a URL."""
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
        )  # Longer timeout for URL printing
        content_id = api_data.get("printcontentid")
        if content_id is None:
            raise ApiError(
                api_data.get("showapi_res_code", -1),
                "Content ID not found in successful print URL API response.",
            )
        log.info(f"Print URL request successful. Content ID: {content_id}")
        return int(content_id)

    def check_print_status(self, content_id: int) -> bool:
        """Checks the print status of a specific content ID."""
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


# --- Device Interface ---
class MemobirdDevice:
    """Simplified interface for controlling a single Memobird device."""

    def __init__(self, ak: str, device_id: str, user_identifying: str = ""):
        log.info(f"Initializing MemobirdDevice for device: {device_id}...")
        self._client = MemobirdApiClient(ak)  # Can raise ValueError
        self.device_id = device_id
        # get_user_id can raise ApiError or NetworkError
        self.user_id = self._client.get_user_id(self.device_id, user_identifying)
        log.info(f"MemobirdDevice initialized for User ID: {self.user_id}.")

    def print_text(self, text: str) -> int:
        """Prints text to the configured device."""
        payload = PrintPayloadBuilder().add_text(text)
        # print_content can raise ApiError, NetworkError, ContentError
        return self._client.print_content(self.device_id, self.user_id, payload)

    def print_image(self, image_source: Union[str, BytesIO, Image.Image]) -> int:
        """Prints an image to the configured device."""
        try:
            payload = PrintPayloadBuilder().add_image(image_source)
            # print_content can raise ApiError, NetworkError
            return self._client.print_content(self.device_id, self.user_id, payload)
        except ContentError as e:
            # Log and re-raise or handle as needed
            log.error(f"Failed to prepare image for printing: {e}")
            raise

    def print_payload(self, payload: PrintPayloadBuilder) -> int:
        """Prints a pre-built payload with multiple parts."""
        # print_content can raise ApiError, NetworkError, ContentError (if build fails)
        return self._client.print_content(self.device_id, self.user_id, payload)

    def print_url(self, url: str) -> int:
        """Prints content from a URL to the configured device."""
        # print_url can raise ApiError, NetworkError
        return self._client.print_url(self.device_id, self.user_id, url)

    def check_print_status(self, content_id: int) -> bool:
        """Checks print status for the configured device."""
        # check_print_status can raise ApiError, NetworkError
        return self._client.check_print_status(content_id)