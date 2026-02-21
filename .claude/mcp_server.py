#!/usr/bin/env python3
"""
Blog MCP Server - HTTP Client

API Server를 통해 블로그를 관리합니다.
로컬 Git 없이 어디서든 사용 가능합니다.
"""

import os
import json
import httpx
from typing import List, Dict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# Block: API Client
# ============================================================

class BlogAPIClient:
    """API Server HTTP 클라이언트"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def request(self, method: str, path: str, data: Dict = None, params: Dict = None) -> Dict:
        """API 요청"""
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
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

                return response.json()

            except httpx.TimeoutException:
                return {"success": False, "error": "API 타임아웃"}
            except Exception as e:
                return {"success": False, "error": str(e)}


# ============================================================
# Block: MCP Server
# ============================================================

# 설정
API_URL = os.getenv("BLOG_API_URL", "https://api.blog.fcoinfup.com")
API_KEY = os.getenv("BLOG_API_KEY", "")

# 인스턴스
client = BlogAPIClient(API_URL, API_KEY)
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
        })

    elif name == "blog_list":
        result = await client.request("GET", "/posts", params={
            "limit": arguments.get("limit", 20),
            "offset": arguments.get("offset", 0)
        })

    elif name == "blog_get":
        result = await client.request("GET", f"/posts/{arguments['filename']}")

    elif name == "blog_delete":
        result = await client.request("DELETE", f"/posts/{arguments['filename']}")

    elif name == "blog_search":
        result = await client.request("GET", "/search", params={"q": arguments["query"]})

    elif name == "blog_sync":
        result = await client.request("POST", "/sync")

    elif name == "blog_status":
        result = await client.request("GET", "/status")

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    if not API_KEY:
        import sys
        print("ERROR: BLOG_API_KEY 환경 변수가 필요합니다", file=sys.stderr)
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
