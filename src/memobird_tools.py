import logging
import time
from typing import Optional, Generator

# 导入配置和客户端 (根据实际项目结构调整)
try:
    from .memobird_client import MemobirdDevice, PrintPayloadBuilder, ContentError, ApiError, NetworkError
    from .config import ENV_AK, ENV_DEVICE_ID
except (ImportError, ValueError):
    try:
        from memobird_client import MemobirdDevice, PrintPayloadBuilder, ContentError, ApiError, NetworkError
        from config import ENV_AK, ENV_DEVICE_ID
    except ImportError:
        from src.memobird_client import MemobirdDevice, PrintPayloadBuilder, ContentError, ApiError, NetworkError
        from src.config import ENV_AK, ENV_DEVICE_ID


import os

log = logging.getLogger(__name__)

class MemobirdTools:
    """
    Provides tools that can be called by FastMCP.
    Manages a single MemobirdDevice instance.
    """

    def __init__(self, mcp_instance):
        self.mcp = mcp_instance
        self._device: Optional[MemobirdDevice] = None
        self._init_device_lazily() # Attempt to initialize on startup, but allow lazy init

        # Register methods with MCP
        # Format: mcp_instance.register_tool(external_name, internal_function, "description")
        self.mcp.register_tool(
            "print_text",
            self.print_text,
            "Prints the given text to the Memobird device. Usage: print_text text_to_print",
            args_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        )
        self.mcp.register_tool(
            "print_image_from_url",
            self.print_image_from_url,
            "Downloads an image from a URL and prints it. Usage: print_image_from_url image_url",
            args_schema={"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}, "required": ["url"]}
        )
        self.mcp.register_tool(
            "check_print_status",
            self.check_print_status,
            "Checks the print status of a given content ID. Usage: check_print_status content_id",
            args_schema={"type": "object", "properties": {"content_id": {"type": "integer"}}, "required": ["content_id"]}
        )
        self.mcp.register_tool(
            "stream_test",
            self.stream_test,
            "A test tool that streams multiple events. Usage: stream_test [count=3]",
            args_schema={"type": "object", "properties": {"count": {"type": "integer", "default": 3}}}
        )
        log.info("MemobirdTools registered.")

    def _get_device(self) -> MemobirdDevice:
        """Lazily initializes and returns the MemobirdDevice instance."""
        if self._device is None:
            log.debug("Attempting to lazily initialize MemobirdDevice...")
            ak = os.environ.get(ENV_AK)
            device_id = os.environ.get(ENV_DEVICE_ID)
            if not ak:
                raise ValueError(
                    f"Memobird API Key not found. Set the {ENV_AK} environment variable."
                )
            if not device_id:
                raise ValueError(
                    f"Memobird Device ID not found. Set the {ENV_DEVICE_ID} environment variable."
                )
            try:
                self._device = MemobirdDevice(ak=ak, device_id=device_id)
                log.info("MemobirdDevice initialized successfully through _get_device.")
            except (ApiError, NetworkError) as e:
                log.error(f"Failed to initialize MemobirdDevice: {e}")
                raise RuntimeError(f"Memobird device connection failed: {e}") from e
        return self._device
    
    def _init_device_lazily(self):
        """Tries to initialize the device if env vars are present, but doesn't fail if not."""
        ak = os.environ.get(ENV_AK)
        device_id = os.environ.get(ENV_DEVICE_ID)
        if ak and device_id:
            try:
                log.info("Attempting pre-emptive lazy initialization of MemobirdDevice...")
                self._get_device()
            except Exception as e:
                log.warning(f"Pre-emptive lazy initialization failed: {e}. Will try again on first tool use.")
        else:
            log.info("Skipping pre-emptive lazy initialization: AK or Device ID not set in environment.")


    def print_text(self, text: str) -> str:
        """Prints text to the Memobird device."""
        if not text:
            return "Error: Text cannot be empty."
        log.info(f"Tool 'print_text' called with text: '{text[:30]}...'")
        try:
            device = self._get_device()
            content_id = device.print_text(text)
            return f"Text sent to printer. Content ID: {content_id}"
        except (ContentError, ApiError, NetworkError, ValueError, RuntimeError) as e:
            log.error(f"Error in print_text tool: {e}")
            return f"Error: {e}"

    def print_image_from_url(self, url: str) -> str:
        """Downloads an image from a URL and prints it."""
        if not url:
            return "Error: URL cannot be empty."
        log.info(f"Tool 'print_image_from_url' called with URL: {url}")
        
        # Note: This is where the streaming download would be implemented
        # using self._client._make_request(stream=True) if MemobirdDevice exposed it,
        # or by adding a method to MemobirdApiClient to download and return image bytes/stream.
        # For now, we assume MemobirdDevice.print_image handles URL fetching internally
        # or we'd need to adjust MemobirdDevice.print_image to accept a URL and do the streaming download.
        # The current MemobirdDevice.print_image takes image_source: Union[str, BytesIO, Image.Image]
        # So, we'd first download the image, then pass it.
        
        # Placeholder for actual image download logic:
        # For a real implementation, you'd use requests to get the image:
        # try:
        #     response = requests.get(url, stream=True)
        #     response.raise_for_status()
        #     image_bytes = BytesIO(response.content) # Not streaming efficiently here
        # except requests.RequestException as e:
        #     return f"Error downloading image: {e}"

        # This tool currently relies on MemobirdDevice.print_image which expects a path or BytesIO.
        # A proper implementation would download the image first.
        # For this example, let's assume print_image can take a URL,
        # or we'd need a helper in MemobirdDevice.
        # To simplify, we'll just state this tool isn't fully implemented for URL download yet.
        # return "Error: Direct URL printing in this tool needs full download implementation first."

        try:
            # This is conceptual. We'd need to implement the download.
            # For now, let's assume print_image will handle it or we adjust it.
            # To make it work with current print_image, one would:
            # 1. Use requests.get(url, stream=True)
            # 2. Get BytesIO from response.raw or response.content
            # 3. Pass BytesIO to device.print_image()
            # This is a simplified path for now.
            log.warning("print_image_from_url tool currently uses a simplified path and may not stream image download.")
            device = self._get_device()
            # Let's simulate a download to BytesIO for print_image
            import requests # Temporary import for this example
            from io import BytesIO
            try:
                http_response = requests.get(url, timeout=10) # Short timeout for example
                http_response.raise_for_status()
                image_data = BytesIO(http_response.content) # Read all content for now
                content_id = device.print_image(image_data)
                return f"Image from URL sent to printer. Content ID: {content_id}"
            except requests.RequestException as e:
                log.error(f"Failed to download image from URL {url}: {e}")
                return f"Error: Failed to download image from {url}. {e}"
        except (ContentError, ApiError, NetworkError, ValueError, RuntimeError) as e:
            log.error(f"Error in print_image_from_url tool: {e}")
            return f"Error: {e}"


    def check_print_status(self, content_id: int) -> str:
        """Checks the print status of a given content ID."""
        log.info(f"Tool 'check_print_status' called for content_id: {content_id}")
        try:
            device = self._get_device()
            is_printed = device.check_print_status(content_id)
            return f"Content ID {content_id} printed status: {is_printed}"
        except (ApiError, NetworkError, ValueError, RuntimeError) as e:
            log.error(f"Error in check_print_status tool: {e}")
            return f"Error: {e}"

    def stream_test(self, count: int = 3) -> Generator[str, None, None]:
        """A test tool that streams multiple events."""
        log.info(f"Tool 'stream_test' called with count: {count}")
        if not isinstance(count, int) or count <= 0:
            yield "Error: count must be a positive integer."
            return
        
        for i in range(1, count + 1):
            message = f"Event {i} of {count}"
            log.debug(f"stream_test yielding: {message}")
            yield message # This will be sent as an SSE event data
            if i < count:
                time.sleep(0.1) # Small delay to make streaming observable
        log.info("stream_test finished.")
        # No explicit return value needed for generators if they just complete.
        # If you wanted to signal completion in a special way (FastMCP might handle this):
        # yield "Streaming complete."

# Example of how to manually test tools if needed (not part of FastMCP execution)
if __name__ == "__main__":
    # This section is for direct testing of tools, not for FastMCP integration.
    # You would need to mock or set up FastMCP instance if tools rely on it directly.
    # For MemobirdTools, it needs environment variables for AK and Device ID.

    # Set environment variables for testing (replace with your actual keys or use a .env file)
    # os.environ[ENV_AK] = "your_api_key"
    # os.environ[ENV_DEVICE_ID] = "your_device_id"

    if not os.getenv(ENV_AK) or not os.getenv(ENV_DEVICE_ID):
        print(f"Please set {ENV_AK} and {ENV_DEVICE_ID} environment variables to test MemobirdTools directly.")
    else:
        # Mock FastMCP for local testing if needed, or test methods that don't use mcp
        class MockMCP:
            def register_tool(self, *args, **kwargs):
                print(f"MockMCP: Tool registered: {args[0]}")

        mock_mcp = MockMCP()
        tools = MemobirdTools(mock_mcp)

        print("Testing print_text...")
        # print(tools.print_text("Hello from direct test!"))

        print("\nTesting stream_test...")
        for event in tools.stream_test(count=4):
            print(f"Received from stream_test: {event}")
        
        # print("\nTesting print_image_from_url (will try to download)...")
        # Test with a known public image URL if you uncomment
        # image_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
        # print(tools.print_image_from_url(image_url))

        # print("\nTesting check_print_status (requires a valid content_id)...")
        # print(tools.check_print_status(123456789)) # Replace with a real content ID
```
