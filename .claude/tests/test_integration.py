"""Integration tests for MCP Server with mocked API"""

import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server import BlogAPIClient, list_tools, call_tool


class TestIntegration:
    """Integration tests with mocked API server"""

    @pytest.mark.asyncio
    async def test_full_post_workflow(self):
        """Test complete post creation, retrieval, update, deletion workflow"""
        mock_responses = {
            "POST /posts": {"success": True, "filename": "2026-02-24-test-post.md"},
            "GET /posts/2026-02-24-test-post.md": {
                "success": True,
                "filename": "2026-02-24-test-post.md",
                "title": "Test Post",
                "content": "Original content"
            },
            "PUT /posts/2026-02-24-test-post.md": {"success": True, "updated": True},
            "DELETE /posts/2026-02-24-test-post.md": {"success": True, "deleted": True}
        }

        async def mock_request(method, path, data=None, params=None,
                               use_cache=True, invalidate_cache=False):
            key = f"{method} {path}"
            return mock_responses.get(key, {"success": False, "error": "Not found"})

        with patch('mcp_server.client.request', new=AsyncMock(side_effect=mock_request)):
            # Create post
            create_result = await call_tool("blog_create", {
                "title": "Test Post",
                "content": "Original content"
            })
            create_data = json.loads(create_result[0].text)
            assert create_data["success"] is True
            filename = create_data["filename"]

            # Get post
            get_result = await call_tool("blog_get", {"filename": filename})
            get_data = json.loads(get_result[0].text)
            assert get_data["success"] is True

            # Update post
            update_result = await call_tool("blog_update", {
                "filename": filename,
                "content": "Updated content"
            })
            update_data = json.loads(update_result[0].text)
            assert update_data["updated"] is True

            # Delete post
            delete_result = await call_tool("blog_delete", {"filename": filename})
            delete_data = json.loads(delete_result[0].text)
            assert delete_data["deleted"] is True

    @pytest.mark.asyncio
    async def test_search_and_list_workflow(self):
        """Test search and list operations"""
        mock_responses = {
            "GET /posts": {
                "success": True,
                "posts": [
                    {"filename": "post1.md", "title": "Python Tutorial"},
                    {"filename": "post2.md", "title": "JavaScript Guide"}
                ],
                "total": 2
            },
            "GET /search": {
                "success": True,
                "results": [
                    {"filename": "post1.md", "title": "Python Tutorial"}
                ]
            }
        }

        async def mock_request(method, path, data=None, params=None,
                               use_cache=True, invalidate_cache=False):
            if method == "GET" and path == "/posts":
                return mock_responses["GET /posts"]
            elif method == "GET" and path == "/search":
                return mock_responses["GET /search"]
            return {"success": False, "error": "Not found"}

        with patch('mcp_server.client.request', new=AsyncMock(side_effect=mock_request)):
            # List all posts
            list_result = await call_tool("blog_list", {"limit": 20})
            list_data = json.loads(list_result[0].text)
            assert list_data["total"] == 2
            assert len(list_data["posts"]) == 2

            # Search posts
            search_result = await call_tool("blog_search", {"query": "Python"})
            search_data = json.loads(search_result[0].text)
            assert len(search_data["results"]) == 1
            assert search_data["results"][0]["title"] == "Python Tutorial"

    @pytest.mark.asyncio
    async def test_git_operations_workflow(self):
        """Test Git sync and status operations"""
        mock_responses = {
            "GET /status": {
                "success": True,
                "branch": "main",
                "status": "clean",
                "untracked": [],
                "modified": []
            },
            "POST /sync": {
                "success": True,
                "pulled": True,
                "pushed": False,
                "message": "Already up to date"
            }
        }

        async def mock_request(method, path, data=None, params=None,
                               use_cache=True, invalidate_cache=False):
            return mock_responses.get(f"{method} {path}", {"success": False})

        with patch('mcp_server.client.request', new=AsyncMock(side_effect=mock_request)):
            # Check status
            status_result = await call_tool("blog_status", {})
            status_data = json.loads(status_result[0].text)
            assert status_data["branch"] == "main"
            assert status_data["status"] == "clean"

            # Sync
            sync_result = await call_tool("blog_sync", {})
            sync_data = json.loads(sync_result[0].text)
            assert sync_data["success"] is True

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling across operations"""
        error_responses = {
            "GET /posts/notfound.md": {"success": False, "error": "Post not found"},
            "POST /posts": {"success": False, "error": "Invalid title"},
            "DELETE /posts/protected.md": {"success": False, "error": "Cannot delete protected post"}
        }

        async def mock_request(method, path, data=None, params=None,
                               use_cache=True, invalidate_cache=False):
            return error_responses.get(f"{method} {path}", {"success": False, "error": "Unknown"})

        with patch('mcp_server.client.request', new=AsyncMock(side_effect=mock_request)):
            # Test get not found
            get_result = await call_tool("blog_get", {"filename": "notfound.md"})
            get_data = json.loads(get_result[0].text)
            assert get_data["success"] is False
            assert "not found" in get_data["error"].lower()

            # Test create error
            create_result = await call_tool("blog_create", {"title": "", "content": "test"})
            create_data = json.loads(create_result[0].text)
            assert create_data["success"] is False

            # Test delete error
            delete_result = await call_tool("blog_delete", {"filename": "protected.md"})
            delete_data = json.loads(delete_result[0].text)
            assert delete_data["success"] is False

    @pytest.mark.asyncio
    async def test_client_lifecycle(self):
        """Test client initialization and cleanup"""
        client = BlogAPIClient("http://test.com", "test_key")

        # Initialize client
        http_client = await client._get_client()
        assert http_client is not None
        assert not http_client.is_closed

        # Close client
        await client.close()
        assert client._client is None

        # Reopen
        http_client = await client._get_client()
        assert http_client is not None

        # Cleanup
        await client.close()


class TestEnvironmentConfiguration:
    """Tests for environment variable configuration"""

    def test_api_key_required_warning(self, monkeypatch, capsys):
        """Test warning is shown when API_KEY is missing"""
        # Remove API key from environment
        monkeypatch.delenv("BLOG_API_KEY", raising=False)

        # Create a mock async context manager
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_stdio():
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            yield mock_read, mock_write

        with patch('mcp_server.stdio_server', return_value=mock_stdio()):
            # Import and run main
            from mcp_server import main
            import asyncio

            # Should print error and return early
            asyncio.run(main())

        captured = capsys.readouterr()
        assert "BLOG_API_KEY" in captured.err
