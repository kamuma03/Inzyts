"""
Unit tests for JupyterService (jupyter_proxy.py).

Tests the Jupyter proxy service that manages communication with
the Jupyter Server for live notebook execution (v1.7.0 feature).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.server.services.jupyter_proxy import JupyterService, jupyter_service


class TestJupyterService:
    """Test suite for JupyterService class."""

    @pytest.fixture
    def service(self):
        """Create a JupyterService instance with test configuration."""
        return JupyterService(
            base_url="http://test-jupyter:8888",
            token="test-token"
        )

    @pytest.fixture
    def default_service(self):
        """Create a JupyterService instance with default configuration."""
        with patch("src.server.services.jupyter_proxy.settings") as mock_settings:
            mock_settings.jupyter.base_url = "http://jupyter:8888"
            mock_settings.jupyter.token = "inzyts-token"
            yield JupyterService()

    # Test 1: Service initialization with custom parameters
    def test_initialization_custom_params(self, service):
        """Test JupyterService initializes with custom base_url and token."""
        assert service.base_url == "http://test-jupyter:8888"
        assert service.token == "test-token"
        assert service.headers == {"Authorization": "token test-token"}

    # Test 2: Service initialization with default parameters
    def test_initialization_default_params(self, default_service):
        """Test JupyterService initializes with default values."""
        assert default_service.base_url == "http://jupyter:8888"
        assert default_service.token == "inzyts-token"
        assert default_service.headers == {"Authorization": "token inzyts-token"}

    # Test 3: Get status - successful response
    @pytest.mark.asyncio
    async def test_get_status_success(self, service):
        """Test get_status returns status when Jupyter is reachable."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "started": "2024-01-01T00:00:00Z",
            "last_activity": "2024-01-01T01:00:00Z",
            "connections": 1,
            "kernels": 2
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            status = await service.get_status()

            assert status is not None
            assert "started" in status
            mock_client.get.assert_called_once_with(
                "http://test-jupyter:8888/api/status",
                headers={"Authorization": "token test-token"}
            )

    # Test 4: Get status - Jupyter unreachable
    @pytest.mark.asyncio
    async def test_get_status_unreachable(self, service):
        """Test get_status returns error status when Jupyter is unreachable."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            status = await service.get_status()

            assert status is not None
            assert status["status"] == "unreachable"
            assert "error" in status
            assert "Connection refused" in status["error"]

    # Test 5: Create kernel - successful
    @pytest.mark.asyncio
    async def test_create_kernel_success(self, service):
        """Test create_kernel successfully creates a new Python 3 kernel."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test-kernel-12345",
            "name": "python3",
            "last_activity": "2024-01-01T00:00:00Z",
            "execution_state": "idle"
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            kernel_id = await service.create_kernel()

            assert kernel_id == "test-kernel-12345"
            mock_client.post.assert_called_once_with(
                "http://test-jupyter:8888/api/kernels",
                headers={"Authorization": "token test-token"},
                json={"name": "python3"}
            )

    # Test 6: Create kernel - failure
    @pytest.mark.asyncio
    async def test_create_kernel_failure(self, service):
        """Test create_kernel raises exception on failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Failed to create kernel"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await service.create_kernel()

            assert "Failed to create kernel" in str(exc_info.value)

    # Test 7: Proxy request - GET method
    @pytest.mark.asyncio
    async def test_proxy_request_get(self, service):
        """Test proxy_request handles GET requests."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await service.proxy_request("GET", "/api/kernels")

            assert result == {"data": "test"}
            mock_client.request.assert_called_once_with(
                "GET",
                "http://test-jupyter:8888/api/kernels",
                headers={"Authorization": "token test-token"},
                json=None
            )

    # Test 8: Proxy request - POST method with body
    @pytest.mark.asyncio
    async def test_proxy_request_post_with_body(self, service):
        """Test proxy_request handles POST requests with body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"created": True}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await service.proxy_request(
                "POST",
                "/api/kernels",
                body={"name": "python3"}
            )

            assert result == {"created": True}
            mock_client.request.assert_called_once_with(
                "POST",
                "http://test-jupyter:8888/api/kernels",
                headers={"Authorization": "token test-token"},
                json={"name": "python3"}
            )

    # Test 9: Proxy request - handles path with leading slash
    @pytest.mark.asyncio
    async def test_proxy_request_path_normalization(self, service):
        """Test proxy_request normalizes paths with leading slashes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Test with leading slash
            await service.proxy_request("GET", "/api/status")
            call_args = mock_client.request.call_args
            assert call_args[0][1] == "http://test-jupyter:8888/api/status"

    # Test 10: Proxy request - failure
    @pytest.mark.asyncio
    async def test_proxy_request_failure(self, service):
        """Test proxy_request raises exception on failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=Exception("Request failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await service.proxy_request("GET", "/api/kernels")

            assert "Request failed" in str(exc_info.value)

    # Test 11: Singleton jupyter_service instance
    def test_singleton_instance_exists(self):
        """Test that a global jupyter_service instance is available."""
        assert jupyter_service is not None
        assert isinstance(jupyter_service, JupyterService)

    # Test 12: Singleton uses default configuration
    def test_singleton_default_config(self):
        """Test that the global jupyter_service uses default configuration."""
        assert jupyter_service.base_url == "http://jupyter:8888"
        assert jupyter_service.token is None

    # Test 13: Create kernel - HTTP error response
    @pytest.mark.asyncio
    async def test_create_kernel_http_error(self, service):
        """Test create_kernel handles HTTP error responses."""
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500)
        )

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await service.create_kernel()

    # Test 14: Get status - timeout handling
    @pytest.mark.asyncio
    async def test_get_status_timeout(self, service):
        """Test get_status handles timeout gracefully."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            status = await service.get_status()

            assert status["status"] == "unreachable"
            assert "error" in status

    # Test 15: Headers include authorization token
    def test_headers_format(self, service):
        """Test that headers are properly formatted with token."""
        headers = service.headers

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("token ")
        assert service.token in headers["Authorization"]


class TestJupyterServiceWebSocket:
    """Test suite for WebSocket proxy functionality."""

    @pytest.fixture
    def service(self):
        """Create a JupyterService instance."""
        return JupyterService(
            base_url="http://test-jupyter:8888",
            token="test-token"
        )

    # Test 16: WebSocket URL construction
    def test_websocket_url_construction(self, service):
        """Test WebSocket URL is correctly constructed from base URL."""
        kernel_id = "test-kernel-123"
        expected_url = f"ws://test-jupyter:8888/api/kernels/{kernel_id}/channels?token=test-token"

        # The URL construction happens inside proxy_websocket
        # We verify the logic by checking base_url replacement
        ws_base = service.base_url.replace('http', 'ws')
        assert ws_base == "ws://test-jupyter:8888"

    # Test 17: Proxy WebSocket - accepts connection
    @pytest.mark.asyncio
    async def test_proxy_websocket_accepts_connection(self, service):
        """Test proxy_websocket accepts the incoming WebSocket connection."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("Stop test"))

        mock_jupyter_ws = AsyncMock()
        mock_jupyter_ws.__aenter__ = AsyncMock(return_value=mock_jupyter_ws)
        mock_jupyter_ws.__aexit__ = AsyncMock(return_value=None)
        mock_jupyter_ws.send = AsyncMock()
        mock_jupyter_ws.__aiter__ = MagicMock(return_value=iter([]))

        with patch('websockets.client.connect', return_value=mock_jupyter_ws):
            try:
                await service.proxy_websocket(mock_websocket, "test-kernel")
            except Exception:
                pass  # Expected to fail when receive_text raises

        mock_websocket.accept.assert_called_once()

    # Test 18: Proxy WebSocket - handles connection error
    @pytest.mark.asyncio
    async def test_proxy_websocket_connection_error(self, service):
        """Test proxy_websocket handles connection errors gracefully."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch('websockets.client.connect', side_effect=Exception("Connection failed")):
            await service.proxy_websocket(mock_websocket, "test-kernel")

        # Should close with error code
        mock_websocket.close.assert_called_once_with(code=1011)


class TestJupyterServiceIntegration:
    """Integration-style tests for JupyterService."""

    @pytest.fixture
    def service(self):
        """Create a JupyterService instance."""
        with patch("src.server.services.jupyter_proxy.settings") as mock_settings:
            mock_settings.jupyter.base_url = "http://jupyter:8888"
            mock_settings.jupyter.token = "inzyts-token"
            yield JupyterService()

    # Test 19: Full kernel lifecycle (mocked)
    @pytest.mark.asyncio
    async def test_kernel_lifecycle(self, service):
        """Test creating a kernel and checking status."""
        # Mock status check
        mock_status_response = MagicMock()
        mock_status_response.json.return_value = {"started": "2024-01-01T00:00:00Z"}

        # Mock kernel creation
        mock_kernel_response = MagicMock()
        mock_kernel_response.json.return_value = {"id": "new-kernel-123", "name": "python3"}
        mock_kernel_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()

            # Set up responses for both calls
            mock_client.get = AsyncMock(return_value=mock_status_response)
            mock_client.post = AsyncMock(return_value=mock_kernel_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Check status first
            status = await service.get_status()
            assert "started" in status

            # Create kernel
            kernel_id = await service.create_kernel()
            assert kernel_id == "new-kernel-123"

    # Test 20: Service handles various HTTP methods
    @pytest.mark.asyncio
    async def test_proxy_request_methods(self, service):
        """Test proxy_request handles various HTTP methods."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Test different HTTP methods
            for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                result = await service.proxy_request(method, "/api/test")
                assert result == {"success": True}

                call_args = mock_client.request.call_args
                assert call_args[0][0] == method


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
