#!/usr/bin/env python3
"""
Blog MCP Server - HTTP Client

API Server를 통해 블로그를 관리합니다.
로컬 Git 없이 어디서든 사용 가능합니다.
"""

import os
import json
import asyncio
import time
import httpx
from typing import List, Dict, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# ============================================================
# Block: Cache Manager
# ============================================================

class CacheManager:
    """로컬 캐시 관리 - 불필요한 API 호출 최소화"""

    def __init__(self, ttl: float = 300.0):
        """
        Args:
            ttl: 캐시 유효 시간 (초), 기본 5분
        """
        self._cache: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl

    async def get(self, key: str) -> Optional[Dict]:
        """캐시된 값 조회"""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return value
                # 만료된 캐시 삭제
                del self._cache[key]
        return None

    async def set(self, key: str, value: Dict) -> None:
        """캐시 저장"""
        async with self._lock:
            self._cache[key] = (value, time.time())

    async def invalidate(self, pattern: str = None) -> None:
        """캐시 무효화

        Args:
            pattern: None이면 전체 삭제, 특정 패턴이면 일치하는 키만 삭제
        """
        async with self._lock:
            if pattern is None:
                self._cache.clear()
            else:
                keys_to_delete = [k for k in self._cache if pattern in k]
                for k in keys_to_delete:
                    del self._cache[k]

    async def clear_read_cache(self) -> None:
        """읽기 전용 캐시 삭제 (쓰기 작업 후 호출)"""
        await self.invalidate("posts:")
        await self.invalidate("status")


# ============================================================
# Block: API Client
# ============================================================

class BlogAPIClient:
    """API Server HTTP 클라이언트 (연결 풀링 + 캐싱 지원)"""

    def __init__(self, base_url: str, api_key: str, cache_ttl: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = CacheManager(ttl=cache_ttl)
        self._request_lock = asyncio.Lock()  # 동시성 제어
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """연결 풀링을 위한 HTTP 클라이언트 가져오기"""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0
            )
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=limits,
                http2=False
            )
        return self._client

    async def close(self):
        """클라이언트 리소스 해제"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, path: str, data: Dict = None, params: Dict = None,
                     use_cache: bool = True, invalidate_cache: bool = False) -> Dict:
        """API 요청

        Args:
            method: HTTP 메서드 (GET, POST, PUT, DELETE)
            path: API 경로
            data: POST/PUT 요청 데이터
            params: GET 요청 파라미터
            use_cache: 캐시 사용 여부 (GET 요청만)
            invalidate_cache: 캐시 무효화 여부 (쓰기 작업 시)
        """
        # 쓰기 작업 전 캐시 무효화
        if invalidate_cache:
            await self._cache.clear_read_cache()

        # GET 요청 캐싱
        if method == "GET" and use_cache:
            cache_key = f"{path}:{str(params)}"
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return {**cached, "_cached": True}

        url = f"{self.base_url}{API_BASE_PATH}{path}"
        client = await self._get_client()

        # 동시성 제어: 동시 요청 직렬화
        async with self._request_lock:
            try:
                if method == "GET":
                    response = await client.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    response = await client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=self.headers, params=params)
                else:
                    return {"success": False, "error": f"Unknown method: {method}"}

                if response.status_code == 401:
                    return {"success": False, "error": "인증 실패: API Key 확인"}
                if response.status_code == 403:
                    return {"success": False, "error": "권한 없음: API Key 확인"}

                result = response.json()

                # 성공한 GET 요청만 캐싱
                if method == "GET" and response.status_code == 200 and use_cache:
                    await self._cache.set(cache_key, result)

                return result

            except httpx.TimeoutException:
                return {"success": False, "error": "API 타임아웃"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def invalidate_cache(self):
        """캐시 수동 무효화"""
        await self._cache.clear_read_cache()


# ============================================================
# Block: MCP Server
# ============================================================

# 설정
API_URL = os.getenv("BLOG_API_URL", "https://blog.fcoinfup.com")
API_BASE_PATH = os.getenv("BLOG_API_BASE_PATH", "/api")  # API 경로 접두사
API_KEY = os.getenv("BLOG_API_KEY", "")
CACHE_TTL = float(os.getenv("BLOG_CACHE_TTL", "300"))  # 기본 5분

# 인스턴스
client = BlogAPIClient(API_URL, API_KEY, cache_ttl=CACHE_TTL)
server = Server("blog-manager")


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="blog_create",
            description="블로그 포스트 생성 (API Server 통해 Git 동기화)",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "제목"},
                    "content": {"type": "string", "description": "내용 (Markdown)"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "draft": {"type": "boolean"}
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="blog_list",
            description="포스트 목록 조회",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number"},
                    "offset": {"type": "number"}
                }
            }
        ),
        Tool(
            name="blog_get",
            description="특정 포스트 조회",
            inputSchema={
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_update",
            description="포스트 내용 수정",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "파일명"},
                    "content": {"type": "string", "description": "수정할 내용 (전체)"}
                },
                "required": ["filename", "content"]
            }
        ),
        Tool(
            name="blog_delete",
            description="포스트 삭제",
            inputSchema={
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_search",
            description="포스트 검색",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        ),
        Tool(
            name="blog_sync",
            description="Git 원격 동기화",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="blog_status",
            description="Git 상태 확인",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="blog_cache_clear",
            description="로컬 캐시 삭제 (운영용)",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    if name == "blog_create":
        result = await client.request("POST", "/posts", data={
            "title": arguments["title"],
            "content": arguments["content"],
            "tags": arguments.get("tags", []),
            "categories": arguments.get("categories", ["Development"]),
            "draft": arguments.get("draft", False),
            "auto_push": True
        }, invalidate_cache=True)

    elif name == "blog_list":
        result = await client.request("GET", "/posts", params={
            "limit": arguments.get("limit", 20),
            "offset": arguments.get("offset", 0)
        }, use_cache=True)

    elif name == "blog_get":
        result = await client.request("GET", f"/posts/{arguments['filename']}", use_cache=True)

    elif name == "blog_update":
        result = await client.request("PUT", f"/posts/{arguments['filename']}", data={
            "content": arguments["content"],
            "auto_push": True
        }, invalidate_cache=True)

    elif name == "blog_delete":
        result = await client.request("DELETE", f"/posts/{arguments['filename']}", invalidate_cache=True)

    elif name == "blog_search":
        result = await client.request("GET", "/search", params={"q": arguments["query"]}, use_cache=True)

    elif name == "blog_sync":
        result = await client.request("POST", "/sync", invalidate_cache=True)

    elif name == "blog_status":
        result = await client.request("GET", "/status", use_cache=True)

    elif name == "blog_cache_clear":
        # 캐시 수동 클러어 도구 (운영용)
        await client.invalidate_cache()
        result = {"success": True, "message": "캐시가 삭제되었습니다"}

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    if not API_KEY:
        import sys
        print("ERROR: BLOG_API_KEY 환경 변수가 필요합니다", file=sys.stderr)
        return

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # 클라이언트 리소스 해제
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
