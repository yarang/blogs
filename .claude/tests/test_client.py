"""Unit tests for BlogAPIClient"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from mcp_server import BlogAPIClient


class TestBlogAPIClient:
    """BlogAPIClient unit tests"""

    def test_init(self):
        """Test client initialization"""
        client = BlogAPIClient("http://test.com", "test_key")

        assert client.base_url == "http://test.com"
        assert client.api_key == "test_key"
        assert client._client is None
        assert client.headers == {
            "X-API-Key": "test_key",
            "Content-Type": "application/json"
        }

    def test_init_base_url_trailing_slash(self):
        """Test trailing slash is removed from base_url"""
        client = BlogAPIClient("http://test.com/", "test_key")
        assert client.base_url == "http://test.com"

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self):
        """Test _get_client creates new HTTP client"""
        client = BlogAPIClient("http://test.com", "test_key")

        http_client = await client._get_client()

        assert http_client is not None
        assert http_client.is_closed is False
        assert client._client == http_client

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(self):
        """Test _get_client reuses existing client"""
        client = BlogAPIClient("http://test.com", "test_key")

        first_client = await client._get_client()
        second_client = await client._get_client()

        assert first_client == second_client

    @pytest.mark.asyncio
    async def test_get_client_recreates_when_closed(self):
        """Test _get_client creates new client when previous is closed"""
        client = BlogAPIClient("http://test.com", "test_key")

        first_client = await client._get_client()
        await client.close()

        second_client = await client._get_client()

        assert first_client != second_client

    @pytest.mark.asyncio
    async def test_close(self):
        """Test client resource cleanup"""
        client = BlogAPIClient("http://test.com", "test_key")

        # Initialize the HTTP client
        await client._get_client()
        assert client._client is not None

        # Close it
        await client.close()

        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_when_already_closed(self):
        """Test close handles already closed client gracefully"""
        client = BlogAPIClient("http://test.com", "test_key")

        # Should not raise exception
        await client.close()
        await client.close()

    @pytest.mark.asyncio
    async def test_request_get_success(self):
        """Test GET request success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": "test"}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/test")

            assert result == {"success": True, "data": "test"}
            mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_post_success(self):
        """Test POST request success"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"success": True, "id": 123}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("POST", "/posts", data={"title": "Test"})

            assert result == {"success": True, "id": 123}
            mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_put_success(self):
        """Test PUT request success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.put = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("PUT", "/posts/test.md", data={"content": "updated"})

            assert result == {"success": True}
            mock_http_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_delete_success(self):
        """Test DELETE request success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.delete = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("DELETE", "/posts/test.md")

            assert result == {"success": True}
            mock_http_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_401_unauthorized(self):
        """Test 401 error handling"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/test")

            assert result["success"] is False
            assert "인증 실패" in result["error"]

    @pytest.mark.asyncio
    async def test_request_403_forbidden(self):
        """Test 403 error handling"""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Forbidden"}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/test")

            assert result["success"] is False
            assert "권한 없음" in result["error"]

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """Test timeout error handling"""
        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/test")

            assert result["success"] is False
            assert "타임아웃" in result["error"]

    @pytest.mark.asyncio
    async def test_request_unknown_error(self):
        """Test unknown error handling"""
        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=Exception("Unknown error"))
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/test")

            assert result["success"] is False
            assert "Unknown error" in result["error"]

    @pytest.mark.asyncio
    async def test_request_unknown_method(self):
        """Test unknown HTTP method"""
        client = BlogAPIClient("http://test.com", "test_key")

        result = await client.request("PATCH", "/test")

        assert result["success"] is False
        assert "Unknown method" in result["error"]

    @pytest.mark.asyncio
    async def test_request_with_params(self):
        """Test request with query parameters"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        client = BlogAPIClient("http://test.com", "test_key")

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await client.request("GET", "/search", params={"q": "test"})

            # Verify params were passed
            call_args = mock_http_client.get.call_args
            assert call_args.kwargs.get("params") == {"q": "test"}

    @pytest.mark.asyncio
    async def test_connection_pooling_settings(self):
        """Test connection pooling is properly configured"""
        client = BlogAPIClient("http://test.com", "test_key")

        # Client should be created with connection pooling support
        http_client = await client._get_client()

        # Verify client exists and supports pooling
        assert http_client is not None
        assert http_client.is_closed is False
        # The client should have timeout configured (httpx uses Timeout object)
        assert http_client.timeout is not None
