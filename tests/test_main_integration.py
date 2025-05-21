import unittest
import subprocess
import time
import os
import signal
import requests # For initial health check and graceful shutdown
import sseclient # From sseclient-py
import json # For parsing tool call responses if needed
from threading import Thread

# Assuming FastMCP uses /api/v1/call/<tool_name> for tool invocation
# This might need adjustment based on FastMCP's actual routing for SSE.
# Let's assume the tool call for SSE might be different, e.g., /events or a specific SSE route.
# Based on typical FastMCP patterns, it might be /api/v1/call_stream/stream_test or similar.
# For now, we'll try to call it like a regular tool and see if FastMCP handles it via SSE.
# The prompt implies /api/v1/call/stream_test.

# Configuration
TEST_HOST = "127.0.0.1"
TEST_PORT = 8765 # Use a different port than default to avoid conflicts
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"
# FastMCP tool call URL structure needs to be confirmed.
# If it's a POST to call and then an SSE stream is established, or a GET for SSE.
# Let's assume it's a GET request to a specific streaming endpoint for the tool.
# A common pattern for SSE with parameters is via query params.
# /api/v1/call_sse/<tool_name>?param1=value1
# Or the `call` endpoint itself might upgrade to SSE if the tool is a generator.
# Let's assume for now that FastMCP might expose tools that are generators
# directly on their standard call path, and if the client accepts text/event-stream,
# it will stream. This is an optimistic assumption.

# A more robust way for FastMCP might be a dedicated SSE endpoint per tool or a global one.
# Let's use the tool name `stream_test` and assume it's directly accessible via GET for SSE.
# The FastMCP client would typically handle forming the correct URL.
# For this test, we construct it manually. A common way is:
# BASE_URL + /api/v1/tools/stream_test/stream  (if it's a sub-resource for streaming)
# or BASE_URL + /api/v1/call_stream/stream_test
# Or simply, if the tool is called via GET and is a generator, it streams.
# Let's try: BASE_URL + "/api/v1/call/stream_test" with Accept: text/event-stream header.

TOOL_NAME = "stream_test"
# Constructing the payload for a GET request if params are via query
# For a tool call `stream_test count=2`
PARAMS = {"count": 2}

# Path to main.py
MAIN_PY_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'main.py')

# Environment variables for the server process
SERVER_ENV = os.environ.copy()
SERVER_ENV["MEMOBIRD_AK"] = "test_ak_integration"
SERVER_ENV["MEMOBIRD_DEVICE_ID"] = "test_did_integration"
# Suppress normal logging output from the server during tests if too verbose
# SERVER_ENV["LOG_LEVEL"] = "WARNING"


class TestMainSSEIntegration(unittest.TestCase):
    server_process = None

    @classmethod
    def setUpClass(cls):
        # Start the server
        command = [
            "python", MAIN_PY_PATH,
            "--transport", "sse",
            "--port", str(TEST_PORT)
        ]
        log.info(f"Starting server with command: {' '.join(command)}")
        cls.server_process = subprocess.Popen(command, env=SERVER_ENV, preexec_fn=os.setsid) # preexec_fn for easy group kill
        
        # Wait for the server to start
        # Implement a simple health check
        retries = 10
        while retries > 0:
            try:
                # Check a base path or a known non-streaming endpoint if available
                # If FastMCP has a health endpoint, use that. Otherwise, just try to connect.
                # For now, we'll just sleep, but a health check is better.
                # requests.get(f"{BASE_URL}/health", timeout=1)
                time.sleep(1.5) # Give server time to start
                log.info("Server presumed started.")
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
                retries -= 1
        if retries == 0:
            cls.tearDownClass() # Attempt to clean up if server didn't start
            raise Exception("Server did not start in time for tests.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            log.info("Stopping server...")
            # Send SIGTERM to the process group
            try:
                os.killpg(os.getpgid(cls.server_process.pid), signal.SIGTERM)
                cls.server_process.wait(timeout=5)
            except ProcessLookupError:
                log.info("Server process already terminated.")
            except subprocess.TimeoutExpired:
                log.warning("Server did not terminate gracefully, sending SIGKILL.")
                os.killpg(os.getpgid(cls.server_process.pid), signal.SIGKILL)
            cls.server_process = None
            log.info("Server stopped.")

    def test_stream_test_tool_sse(self):
        log.info("Starting SSE client to test stream_test tool...")
        
        # FastMCP's /api/v1/call endpoint expects a POST with JSON:
        # { "tool_name": "...", "args": { ... }, "request_id": "..." }
        # If this endpoint itself upgrades to SSE for generator tools,
        # the initial request should still be a POST.
        # However, SSE is typically initiated with a GET request.

        # Let's assume FastMCP has a specific way to initiate SSE streams for tools.
        # This might be a GET request to a URL like:
        # /api/v1/stream/<tool_name>?arg1=val1&arg2=val2
        # Or if the standard 'call' endpoint is used and it's a GET for streaming tools:
        stream_url = f"{BASE_URL}/api/v1/call/{TOOL_NAME}" 
        
        log.info(f"Connecting to SSE endpoint: {stream_url} with params: {PARAMS}")

        received_events = []
        try:
            # Using requests to make the initial call, as sseclient-py might not easily do POST then stream.
            # If FastMCP streams on GET:
            # response = requests.get(stream_url, params={"count": 2, "request_id": "test_sse_1"}, stream=True, headers={"Accept": "text/event-stream"}, timeout=10)
            # response.raise_for_status()
            # client = sseclient.SSEClient(response)
            
            # If FastMCP's `call` endpoint handles POST and then streams for generators:
            # This is less standard for SSE.
            # More likely: A dedicated GET endpoint for streaming calls.
            # If no such endpoint exists, this test will fail and indicate a design aspect of FastMCP.
            
            # Let's try with sseclient-py which makes a GET request
            # This assumes FastMCP serves SSE on GET /api/v1/call/tool_name?param=value
            # Or, if FastMCP uses a different path for streaming calls, that path should be used.
            # The prompt mentioned /api/v1/call/stream_test, which implies the standard call path.

            # We need to construct the URL with query parameters for GET.
            query_string = "&".join([f"{k}={v}" for k, v in PARAMS.items()])
            full_stream_url = f"{stream_url}?{query_string}"
            log.info(f"Attempting GET to {full_stream_url} for SSE stream.")

            # The `sseclient` takes the requests.Response object from a stream=True GET request
            http_response = requests.get(full_stream_url, stream=True, headers={"Accept": "text/event-stream"}, timeout=10)
            http_response.raise_for_status() # Check for HTTP errors first

            client = sseclient.SSEClient(http_response)
            
            expected_event_count = PARAMS["count"]
            
            for event in client:
                log.debug(f"SSE Event received: ID='{event.id}', Event='{event.event}', Data='{event.data}'")
                if event.data: # Filter out empty keep-alive messages if any
                    # FastMCP might wrap tool's yield in a JSON structure.
                    # E.g., {"type": "data", "payload": "Event 1 of 2"}
                    # Or it might send raw strings if the tool yields strings.
                    # Let's assume it sends the string directly as data for now.
                    # The `stream_test` tool yields strings like "Event X of Y".
                    try:
                        # If data is JSON string containing the actual message:
                        # data_payload = json.loads(event.data)
                        # received_events.append(data_payload["payload"]) 
                        # For now, assume raw string from tool
                        received_events.append(event.data)
                    except json.JSONDecodeError:
                        log.warning(f"Failed to parse JSON from SSE event data: {event.data}")
                        received_events.append(event.data) # Store raw data if not JSON

                if len(received_events) >= expected_event_count:
                    break 
            
            client.close() # Close the connection

        except requests.exceptions.RequestException as e:
            self.fail(f"SSE connection failed: {e}")
        except Exception as e:
            self.fail(f"Error during SSE event processing: {e}")

        log.info(f"Received events: {received_events}")

        self.assertEqual(len(received_events), expected_event_count, "Incorrect number of SSE events received.")
        
        expected_messages = [f"Event {i} of {expected_event_count}" for i in range(1, expected_event_count + 1)]
        self.assertListEqual(received_events, expected_messages, "SSE event data does not match expected messages.")

# It's good practice to have a logging setup for tests if not using a test runner that handles it.
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__)

if __name__ == '__main__':
    unittest.main()
