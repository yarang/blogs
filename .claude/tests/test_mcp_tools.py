"""Unit tests for MCP Server tools"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from mcp.types import TextContent

from mcp_server import list_tools, call_tool, server, BlogAPIClient, CacheManager


class TestMCPTools:
    """MCP Server tools tests"""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test list_tools returns all expected tools"""
        tools = await list_tools()

        tool_names = {tool.name for tool in tools}

        expected_tools = {
            "blog_create",
            "blog_list",
            "blog_get",
            "blog_update",
            "blog_delete",
            "blog_search",
            "blog_sync",
            "blog_status",
            "blog_cache_clear"  # 새로운 캐시 클리어 도구
        }

        assert tool_names == expected_tools

    @pytest.mark.asyncio
    async def test_list_tools_schemas(self):
        """Test tool schemas are properly defined"""
        tools = await list_tools()

        # Check blog_create schema
        create_tool = next(t for t in tools if t.name == "blog_create")
        assert "title" in create_tool.inputSchema["properties"]
        assert "content" in create_tool.inputSchema["properties"]
        assert create_tool.inputSchema["required"] == ["title", "content"]

        # Check blog_get schema
        get_tool = next(t for t in tools if t.name == "blog_get")
        assert "filename" in get_tool.inputSchema["properties"]
        assert get_tool.inputSchema["required"] == ["filename"]

    @pytest.mark.asyncio
    async def test_call_tool_blog_create(self):
        """Test blog_create tool call"""
        mock_response = {"success": True, "filename": "test-post.md"}

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_create", {
                "title": "Test Post",
                "content": "Test content",
                "tags": ["test"],
                "categories": ["Development"]
            })

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["success"] is True

            # Verify the API was called correctly (invalidate_cache=True 추가됨)
            mock_request.assert_called_once_with("POST", "/posts", data={
                "title": "Test Post",
                "content": "Test content",
                "tags": ["test"],
                "categories": ["Development"],
                "draft": False,
                "auto_push": True
            }, invalidate_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_create_defaults(self):
        """Test blog_create with default values"""
        mock_response = {"success": True}

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            await call_tool("blog_create", {
                "title": "Test",
                "content": "Content"
            })

            call_args = mock_request.call_args
            data = call_args.kwargs["data"]

            # Check defaults
            assert data["tags"] == []
            assert data["categories"] == ["Development"]
            assert data["draft"] is False
            assert data["auto_push"] is True

    @pytest.mark.asyncio
    async def test_call_tool_blog_list(self):
        """Test blog_list tool call"""
        mock_response = {
            "success": True,
            "posts": ["post1.md", "post2.md"],
            "total": 2
        }

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_list", {"limit": 10, "offset": 0})

            response_data = json.loads(result[0].text)
            assert response_data["posts"] == ["post1.md", "post2.md"]

            mock_request.assert_called_once_with("GET", "/posts", params={
                "limit": 10,
                "offset": 0
            }, use_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_list_defaults(self):
        """Test blog_list with default pagination"""
        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            await call_tool("blog_list", {})

            call_args = mock_request.call_args
            params = call_args.kwargs.get("params", {})

            # Check defaults
            assert params.get("limit") == 20
            assert params.get("offset") == 0

    @pytest.mark.asyncio
    async def test_call_tool_blog_get(self):
        """Test blog_get tool call"""
        mock_response = {
            "success": True,
            "filename": "test.md",
            "content": "# Test\n\nContent"
        }

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_get", {"filename": "test.md"})

            response_data = json.loads(result[0].text)
            assert response_data["content"] == "# Test\n\nContent"

            mock_request.assert_called_once_with("GET", "/posts/test.md", use_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_update(self):
        """Test blog_update tool call"""
        mock_response = {"success": True, "updated": "test.md"}

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_update", {
                "filename": "test.md",
                "content": "# Updated\n\nNew content"
            })

            response_data = json.loads(result[0].text)
            assert response_data["success"] is True

            mock_request.assert_called_once_with("PUT", "/posts/test.md", data={
                "content": "# Updated\n\nNew content",
                "auto_push": True
            }, invalidate_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_delete(self):
        """Test blog_delete tool call"""
        mock_response = {"success": True, "deleted": "test.md"}

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_delete", {"filename": "test.md"})

            response_data = json.loads(result[0].text)
            assert response_data["deleted"] == "test.md"

            mock_request.assert_called_once_with("DELETE", "/posts/test.md", invalidate_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_search(self):
        """Test blog_search tool call"""
        mock_response = {
            "success": True,
            "results": [
                {"filename": "post1.md", "title": "Test Post 1"},
                {"filename": "post2.md", "title": "Test Post 2"}
            ]
        }

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_search", {"query": "test"})

            response_data = json.loads(result[0].text)
            assert len(response_data["results"]) == 2

            mock_request.assert_called_once_with("GET", "/search", params={"q": "test"}, use_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_sync(self):
        """Test blog_sync tool call"""
        mock_response = {"success": True, "synced": True}

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_sync", {})

            response_data = json.loads(result[0].text)
            assert response_data["synced"] is True

            mock_request.assert_called_once_with("POST", "/sync", invalidate_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_blog_status(self):
        """Test blog_status tool call"""
        mock_response = {
            "success": True,
            "git_status": "clean",
            "branch": "main"
        }

        with patch('mcp_server.client.request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await call_tool("blog_status", {})

            response_data = json.loads(result[0].text)
            assert response_data["git_status"] == "clean"

            mock_request.assert_called_once_with("GET", "/status", use_cache=True)

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self):
        """Test unknown tool returns error"""
        result = await call_tool("unknown_tool", {})

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "알 수 없는 도구" in response_data["error"]

    @pytest.mark.asyncio
    async def test_call_tool_blog_cache_clear(self):
        """Test blog_cache_clear tool call"""
        with patch('mcp_server.client.invalidate_cache', new_callable=AsyncMock) as mock_invalidate:
            result = await call_tool("blog_cache_clear", {})

            response_data = json.loads(result[0].text)
            assert response_data["success"] is True
            assert "캐시가 삭제되었습니다" in response_data["message"]

            mock_invalidate.assert_called_once()


class TestCacheManager:
    """CacheManager 클래스 단위 테스트"""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """캐시 저장 및 조회 테스트"""
        cache = CacheManager(ttl=1.0)

        await cache.set("key1", {"data": "value1"})
        result = await cache.get("key1")

        assert result is not None
        assert result["data"] == "value1"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """캐시 미스 테스트"""
        cache = CacheManager()

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """캐시 만료 테스트"""
        import time

        cache = CacheManager(ttl=0.1)  # 100ms TTL

        await cache.set("key1", {"data": "value1"})

        # 즉시 조회 - 성공
        result = await cache.get("key1")
        assert result is not None

        # TTL 경과 후 - 실패
        await asyncio.sleep(0.15)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidate(self):
        """캐시 무효화 테스트"""
        cache = CacheManager()

        await cache.set("posts:list", {"posts": ["a", "b"]})
        await cache.set("posts:item1", {"content": "item1"})
        await cache.set("status", {"branch": "main"})

        # 패턴 기반 무효화
        await cache.invalidate("posts:")

        assert await cache.get("posts:list") is None
        assert await cache.get("posts:item1") is None
        assert await cache.get("status") is not None  # status는 유지

    @pytest.mark.asyncio
    async def test_cache_clear_read_cache(self):
        """clear_read_cache 테스트"""
        cache = CacheManager()

        await cache.set("posts:list", {"posts": ["a"]})
        await cache.set("posts:item1", {"content": "item1"})
        await cache.set("status", {"branch": "main"})
        await cache.set("other:data", {"value": "keep"})

        await cache.clear_read_cache()

        assert await cache.get("posts:list") is None
        assert await cache.get("posts:item1") is None
        assert await cache.get("status") is None
        assert await cache.get("other:data") is not None  # 패턴에 없는 항목 유지

    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self):
        """동시성 제어 테스트"""
        cache = CacheManager()

        # 여러 코루틴이 동시에 쓰기
        tasks = [
            cache.set(f"key{i}", {"value": i})
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # 모든 키가 존재하는지 확인
        for i in range(10):
            result = await cache.get(f"key{i}")
            assert result is not None
            assert result["value"] == i


class TestBlogAPIClient:
    """BlogAPIClient 클래스 단위 테스트"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """클라이언트 초기화 테스트"""
        client = BlogAPIClient("http://test.com", "test_key", cache_ttl=60.0)

        assert client.base_url == "http://test.com"
        assert client.api_key == "test_key"
        assert client._cache is not None
        assert client._cache._ttl == 60.0

    @pytest.mark.asyncio
    async def test_request_with_cache(self):
        """캐시를 통한 요청 테스트"""
        client = BlogAPIClient("http://test.com", "test_key", cache_ttl=1.0)

        # HTTP 클라이언트 모킹
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"success": True, "data": "cached"})

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        client._client = mock_http_client

        # 첫 번째 요청 - API 호출
        result1 = await client.request("GET", "/test", params={"q": "search"})
        assert result1["success"] is True

        # 두 번째 요청 - 캐시에서 반환 (API 호출 안 함)
        result2 = await client.request("GET", "/test", params={"q": "search"})
        assert result2["success"] is True
        # 캐시 히트 표시 확인
        assert "_cached" in result2

        # API는 한 번만 호출되어야 함
        assert mock_http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_request_cache_invalidation(self):
        """쓰기 작업 후 캐시 무효화 테스트"""
        client = BlogAPIClient("http://test.com", "test_key", cache_ttl=1.0)

        # 캐시에 데이터 저장
        await client._cache.set("posts:list", {"posts": ["a", "b"]})

        # 캐시가 있음을 확인
        cached = await client._cache.get("posts:list")
        assert cached is not None

        # 쓰기 작업으로 캐시 무효화
        await client.invalidate_cache()

        # 캐시가 삭제되었는지 확인
        cached = await client._cache.get("posts:list")
        assert cached is None
