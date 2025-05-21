import unittest
from unittest.mock import MagicMock, patch
import requests

# Adjust import path based on where you run the tests from
# If running from project root: from src.memobird_client import MemobirdApiClient, NetworkError
# If tests folder is considered a package (e.g. python -m unittest tests.test_memobird_client):
from src.memobird_client import MemobirdApiClient, NetworkError, DEFAULT_REQUEST_TIMEOUT

# Helper to access MemobirdApiClient's internal _session.request structure if needed,
# or we can rely on patching requests.Session.request directly.
# For this test, we'll patch requests.Session.request which is what MemobirdApiClient uses.

class TestMemobirdApiClientStreaming(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_ak"
        # We need to ensure that _session is initialized.
        # If MEMOBIRD_API_BASE_URL is not set, this might be an issue.
        # For _make_request, it constructs the full URL.
        self.client = MemobirdApiClient(ak=self.api_key)
        # Define a base URL if it's used by the client to construct full URLs.
        # Based on previous analysis, MEMOBIRD_API_BASE_URL is imported and used.
        # Let's assume it's "http://test.api/" for consistent testing.
        self.base_url = "http://test.api" 
        # If MemobirdApiClient uses self._session.base_url or similar, ensure it's set,
        # or mock the URL construction if it's more complex.
        # For now, we assume `_make_request` constructs `url = MEMOBIRD_API_BASE_URL + path`
        # So, we'll use the actual `MEMOBIRD_API_BASE_URL` from config if possible,
        # or mock it if it's problematic for tests.
        # Let's try to import it for accuracy in the test
        try:
            from src.config import MEMOBIRD_API_BASE_URL
            self.base_url = MEMOBIRD_API_BASE_URL
        except ImportError:
            # Fallback if config is hard to get in test environment
            pass


    @patch('requests.Session.request')
    def test_make_request_streaming_success_with_context_manager(self, mock_session_request):
        # Arrange
        mock_response_content_iter = iter([b"chunk1", b"chunk2"])
        
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        # Make the mock response iterable for the context manager test
        mock_response.__enter__.return_value = mock_response 
        mock_response.__exit__ = MagicMock()
        mock_response.iter_content.return_value = mock_response_content_iter
        mock_response.close = MagicMock() # To check if close is called

        mock_session_request.return_value = mock_response

        path = "/test_stream"
        full_url = self.base_url + path
        
        # Act
        # Using the client's _make_request which now returns the response for streaming
        returned_response_obj = self.client._make_request("GET", path, stream=True)
        
        # Assert initial call and response type
        self.assertIsInstance(returned_response_obj, requests.Response)
        mock_session_request.assert_called_once_with(
            method="GET",
            url=full_url,
            params=None,
            json=None,
            headers=self.client._headers,
            timeout=DEFAULT_REQUEST_TIMEOUT, 
            stream=True
        )
        mock_response.raise_for_status.assert_called_once() # Checked in _make_request

        # Now, test the context manager behavior with the returned response
        # This simulates what a user of the streaming response would do.
        with returned_response_obj as r:
            chunks = []
            for chunk in r.iter_content(chunk_size=None):
                chunks.append(chunk)
        
        # Assert iteration occurred
        self.assertEqual(chunks, [b"chunk1", b"chunk2"])
        
        # Assert that response.close() was called by the context manager `with returned_response_obj as r:`
        # This relies on the fact that requests.Response objects are context managers
        # that call self.close() on __exit__.
        mock_response.close.assert_called_once()
        # Also check that our mock __exit__ on the MagicMock itself was called (if we were testing the mock's CM behavior)
        # mock_response.__exit__.assert_called_once() # This would be for the mock's own CM, not requests.Response's

    @patch('requests.Session.request')
    def test_make_request_streaming_http_error(self, mock_session_request):
        # Arrange
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        http_error = requests.exceptions.HTTPError("404 Client Error: Not Found for url", response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_session_request.return_value = mock_response

        path = "/test_error_stream"
        full_url = self.base_url + path

        # Act & Assert
        with self.assertRaises(NetworkError) as context:
            # _make_request itself will call raise_for_status.
            # If it fails, it raises NetworkError. The response object isn't returned to the caller.
            self.client._make_request("GET", path, stream=True) 
        
        self.assertIn("HTTP Error", str(context.exception))
        self.assertIs(context.exception.__cause__, http_error) # Check that the original HTTPError is the cause

        mock_session_request.assert_called_once_with(
            method="GET",
            url=full_url,
            params=None,
            json=None,
            headers=self.client._headers,
            timeout=DEFAULT_REQUEST_TIMEOUT,
            stream=True
        )
        mock_response.raise_for_status.assert_called_once()
        # mock_response.close() should not have been called in this flow because
        # the response object was not successfully returned and entered into a 'with' block by the caller.
        mock_response.close.assert_not_called()


    @patch('src.memobird_client._check_api_response') # Patching where it's used
    @patch('requests.Session.request') # Patching where Session.request is made
    def test_make_request_non_streaming_calls_check_api_response(self, mock_session_request, mock_check_api_fn):
        # This is a sanity check to ensure the non-streaming path still works as expected.
        
        mock_api_response_dict = {"showapi_res_code": 1, "data": "success"}
        
        mock_http_response = MagicMock(spec=requests.Response) # This is the raw requests.Response
        mock_http_response.status_code = 200
        # mock_http_response.json.return_value = mock_api_response_dict # _check_api_response does the .json() call

        mock_session_request.return_value = mock_http_response
        mock_check_api_fn.return_value = mock_api_response_dict # _check_api_response returns the parsed dict

        path = "/test_non_stream"
        full_url = self.base_url + path

        # Act
        result = self.client._make_request("GET", path, stream=False) # Explicitly stream=False

        # Assert
        self.assertEqual(result, mock_api_response_dict)
        mock_session_request.assert_called_once_with(
            method="GET",
            url=full_url,
            params=None,
            json=None,
            headers=self.client._headers,
            timeout=DEFAULT_REQUEST_TIMEOUT,
            stream=False # Important
        )
        # _check_api_response is called with the response from session.request
        mock_check_api_fn.assert_called_once_with(mock_http_response)


if __name__ == '__main__':
    unittest.main()
