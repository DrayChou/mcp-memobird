import os
import argparse
import sys
import base64
from io import BytesIO

# 从本地包中导入客户端类和异常
try:
    from mcp_memobird.client import (
        MemobirdDevice,
        ApiError,
        NetworkError,
        ContentError,
        MemobirdError,
    )
except ImportError:
    print(
        "Error: mcp_memobird.client module not found or missing dependencies (Pillow, requests)."
    )
    sys.exit(1)

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.sse import SseServerTransport
except ImportError:
    print(
        "Error: mcp library not found or incomplete. Please ensure fastmcp is installed."
    )
    sys.exit(1)

try:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    import uvicorn
except ImportError:
    print(
        "Error: Starlette or Uvicorn not found. Please install them for SSE support: 'pip install starlette uvicorn[standard]'"
    )
    # Allow stdio mode to potentially still work
    Starlette = None  # Set to None to check later

# --- Configuration ---
SERVER_NAME = "Memobird Printer Server"
DEFAULT_SSE_PORT = 8000

# --- Credentials will be determined after parsing args ---
# Initial check removed, will be handled within __main__

# --- Pymobird Client will be initialized within __main__ after determining credentials ---
bird: MemobirdDevice | None = None  # Define bird globally, initialize later

# --- Create FastMCP Instance ---
mcp_fast = FastMCP(SERVER_NAME)
print(f"MCP Server '{SERVER_NAME}' created.")


# --- Define MCP Tools ---
@mcp_fast.tool()
def print_text(text: str) -> str:
    """
    Prints the given text to the Memobird printer.

    Args:
        text: The text content to print.

    Returns:
        A status message indicating success or failure.
    """
    print(f"Received print_text request: '{text[:50]}...'")
    try:
        content_id = bird.print_text(text)
        result = f"Text sent to printer successfully. Content ID: {content_id}"
        print(result)
        return result
    # Catch specific errors from our client
    except (ApiError, NetworkError) as e:
        error_msg = f"Error printing text (API/Network): {e}"
        print(error_msg)  # Consider logging instead of printing
        return error_msg
    except MemobirdError as e:  # Catch other client-related errors
        error_msg = f"Memobird client error printing text: {e}"
        print(error_msg)
        return error_msg
    except Exception as e:  # Catch unexpected errors
        error_msg = f"Unexpected error printing text: {e}"
        print(error_msg)
        return error_msg


@mcp_fast.tool()
def print_image(image_path: str) -> str:
    """
    Prints the image to the Memobird printer.

    Args:
        image_path: Either a local file path to an image, or a base64-encoded image data string.
                   For base64, use format: "data:image/png;base64,BASE64_DATA" or just the raw BASE64_DATA.

    Returns:
        A status message indicating success or failure.
    """
    print(f"Received print_image request for: {image_path[:50]}...")

    try:
        # Check if input is a base64 string
        if image_path.startswith('data:image'):
            # Extract base64 data from format like "data:image/png;base64,BASE64_DATA"
            print("Detected base64 image format with data URL prefix")
            base64_data = image_path.split('base64,')[1]
            image_bytes = BytesIO(base64.b64decode(base64_data))
            content_id = bird.print_image(image_bytes)
            result = f"Base64 image sent to printer successfully. Content ID: {content_id}"
            print(result)
            return result
        elif '/' not in image_path and '\\' not in image_path and len(image_path) > 100:
            # Likely a raw base64 string without the data URL prefix
            print("Detected raw base64 image data (no file path separators, long string)")
            try:
                image_bytes = BytesIO(base64.b64decode(image_path))
                content_id = bird.print_image(image_bytes)
                result = f"Raw base64 image sent to printer successfully. Content ID: {content_id}"
                print(result)
                return result
            except Exception as e:
                print(f"Failed to decode as base64, treating as file path: {e}")
                # Fall through to file path handling
        
        # Handle as local file path
        if not os.path.exists(image_path):
            error_msg = f"Error: Image file not found at path: {image_path}"
            print(error_msg)
            return error_msg
        if not os.path.isfile(image_path):
            error_msg = f"Error: Path is not a file: {image_path}"
            print(error_msg)
            return error_msg

        content_id = bird.print_image(image_path)
        result = f"Image sent to printer successfully. Content ID: {content_id}"
        print(result)
        return result
    
    # Catch specific errors from our client
    except ContentError as e:  # Errors during image processing/loading
        error_msg = f"Error processing image: {e}"
        print(error_msg)
        return error_msg
    except (ApiError, NetworkError) as e:
        error_msg = f"Error printing image (API/Network): {e}"
        print(error_msg)
        return error_msg
    except MemobirdError as e:  # Catch other client-related errors
        error_msg = f"Memobird client error printing image: {e}"
        print(error_msg)
        return error_msg
    except Exception as e:  # Catch unexpected errors
        error_msg = f"Unexpected error printing image: {e}"
        print(error_msg)
        return error_msg



@mcp_fast.tool()
def print_url(url: str) -> str:
    """
    Prints the content from the given URL to the Memobird printer.

    Args:
        url: The URL of the content to print.

    Returns:
        A status message indicating success or failure.
    """
    print(f"Received print_url request for URL: {url}")
    if not bird:
        return "Error: Memobird client not initialized."
    try:
        content_id = bird.print_url(url)
        result = f"URL content sent to printer successfully. Content ID: {content_id}"
        print(result)
        return result
    except (ApiError, NetworkError) as e:
        error_msg = f"Error printing URL (API/Network): {e}"
        print(error_msg)
        return error_msg
    except MemobirdError as e:
        error_msg = f"Memobird client error printing URL: {e}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error printing URL {url}: {e}"
        print(error_msg)
        return error_msg


# --- SSE Specific Setup ---
async def homepage(request: Request):
    return JSONResponse({"message": f"Welcome to the {SERVER_NAME} MCP Server"})


# Define sse_transport and actual_mcp_server_for_sse globally for access in handle_sse
sse_transport: SseServerTransport | None = None
actual_mcp_server_for_sse = mcp_fast._mcp_server


async def handle_sse(request: Request):
    """Handles the SSE connection."""
    if not sse_transport:
        # Should not happen if Starlette is available and transport is sse
        print("Error: SSE transport not initialized.")
        return JSONResponse({"error": "SSE not configured correctly"}, status_code=500)

    print("SSE connection attempt received")
    try:
        # Use request._send for Starlette >= 0.17, or adapt if needed for older versions
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            print(f"SSE connection established, streams: {streams}")
            await actual_mcp_server_for_sse.run(
                streams[0],
                streams[1],
                actual_mcp_server_for_sse.create_initialization_options(),
            )
            print("MCP SSE server finished running for this connection.")
    except Exception as e:
        print(f"Error during SSE connection handling: {e}")
        # Depending on the error, you might want to return an HTTP error response
        # but often the connection might already be closed.


def main():
    """
    Main entry point for the MCP Memobird server. Can be called as a module via `python -m mcp_memobird`
    or directly as a script.
    """
    parser = argparse.ArgumentParser(description=f"Start the {SERVER_NAME} MCP Server")
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        required=False,
        help="Transport protocol to use (stdio or sse)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_SSE_PORT,
        help=f"Port to run the SSE server on (default: {DEFAULT_SSE_PORT})",
    )
    parser.add_argument(
        "--ak",
        "--access_key",
        dest="ak",  # Ensure value stored in args.ak
        type=str,
        default=None,
        help="Memobird API Key (overrides MEMOBIRD_AK environment variable)",
    )
    # Use dest to ensure args.did is populated from either --did or --device_id
    parser.add_argument(
        "--did",
        "--device_id",
        dest="did",  # Ensure value stored in args.did
        type=str,
        default=None,
        help="Memobird Device ID (overrides MEMOBIRD_DEVICE_ID environment variable)",
    )

    args = parser.parse_args()

    # --- Determine Credentials (CLI args override Env Vars) ---
    final_ak = args.ak if args.ak else os.environ.get("MEMOBIRD_AK")
    final_did = args.did if args.did else os.environ.get("MEMOBIRD_DEVICE_ID")

    if not final_ak:
        print(
            "Error: Memobird AK not provided via --ak argument or MEMOBIRD_AK environment variable."
        )
        sys.exit(1)
    if not final_did:
        print(
            "Error: Memobird Device ID not provided via --did argument or MEMOBIRD_DEVICE_ID environment variable."
        )
        sys.exit(1)

    # --- Initialize Memobird Client with final credentials ---
    try:
        # Initialize the global 'bird' instance here
        # Catch specific errors from client initialization
        # Use the new class name and catch specific exceptions
        globals()["bird"] = MemobirdDevice(ak=final_ak, device_id=final_did)
        print("MemobirdDevice client initialized successfully with final credentials.")
    except (ApiError, NetworkError, ValueError) as e:  # Catch specific client errors
        print(f"Error initializing MemobirdDevice client: {e}")
        sys.exit(1)
    except MemobirdError as e:  # Catch base client error
        print(f"Memobird client error during initialization: {e}")
        sys.exit(1)
    except Exception as e:  # Catch any other unexpected error during init
        print(f"Unexpected error initializing Memobird client: {e}")
        sys.exit(1)

    if args.transport == "stdio":
        print("Starting server with stdio transport...")
        mcp_fast.run(transport="stdio")
        print("Server finished.")
    elif args.transport == "sse":
        if Starlette is None or uvicorn is None:
            print(
                "Error: Starlette or Uvicorn is not installed. Cannot start SSE server."
            )
            print("Please install them: 'pip install starlette uvicorn[standard]'")
            sys.exit(1)

        print(f"Starting server with SSE transport on port {args.port}...")
        global sse_transport
        sse_transport = SseServerTransport("/messages")  # Initialize here

        routes = [
            Route("/", homepage),
            Route("/sse", endpoint=handle_sse),  # GET endpoint for SSE connection
            Mount(
                "/messages", app=sse_transport.handle_post_message
            ),  # POST endpoint for messages
        ]
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
        app = Starlette(routes=routes, middleware=middleware)

        try:
            uvicorn.run(app, host="0.0.0.0", port=args.port)
        except Exception as e:
            print(f"Error running Uvicorn server: {e}")
            sys.exit(1)
        print("Server finished.")
    else:
        # Should not happen due to argparse choices
        print(f"Error: Invalid transport type '{args.transport}'")
        sys.exit(1)


if __name__ == "__main__":
    main()