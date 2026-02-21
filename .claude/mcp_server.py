#!/usr/bin/env python3
"""
Blog MCP Server - Claude Code용 블로그 관리 MCP 서버

이 MCP 서버는 HTTP API 서버와 통신하여 블로그 포스트를 관리합니다.
Claude Code에서 어디서든 사용할 수 있습니다.
"""

import os
import json
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# API 서버 설정
API_BASE_URL = os.getenv("BLOG_API_URL", "https://api.blog.fcoinfup.com")
API_KEY = os.getenv("BLOG_API_KEY", "")

# MCP Server 인스턴스
server = Server("blog-manager")


async def api_request(
    method: str,
    endpoint: str,
    data: Dict = None,
    params: Dict = None
) -> Dict:
    """API 서버에 요청"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    url = f"{API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = await client.put(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code == 401:
            return {"success": False, "error": "Authentication failed. Check API Key."}
        elif response.status_code == 403:
            return {"success": False, "error": "Invalid API Key."}

        try:
            return response.json()
        except:
            return {"success": False, "error": f"API error: {response.text}"}


@server.list_tools()
async def list_tools() -> List[Tool]:
    """사용 가능한 도구 목록"""

    return [
        Tool(
            name="blog_create_post",
            description="""새 블로그 포스트를 생성하고 Git에 커밋합니다.

사용 예시:
- "Python 리스트 컴프리헨션에 대한 포스트 작성해줘"
- "Docker Compose 사용법 정리해줘"

자동으로 파일명을 생성하고 Git에 커밋/푸시합니다.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "포스트 제목"
                    },
                    "content": {
                        "type": "string",
                        "description": "포스트 내용 (Markdown 형식)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "태그 목록 (예: ['python', 'tutorial'])"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "카테고리 (예: ['Development', 'Tutorial'])"
                    },
                    "draft": {
                        "type": "boolean",
                        "description": "초안 여부 (기본값: false)"
                    }
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="blog_create_from_draft",
            description="""초안이나 노트 내용을 받아서 정리된 블로그 포스트로 변환하여 업로드합니다.

Agent가 자동으로:
1. 내용을 블로그 포스트 형식으로 정리
2. 적절한 제목, 태그 추천
3. Markdown 형식으로 변환
4. Git에 커밋

사용 예시:
- "이 회의 노트를 블로그 포스트로 정리해줘: [노트 내용]"
- "이 내용으로 기술 블로그 작성해줘: [초안]" """,
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_content": {
                        "type": "string",
                        "description": "초안/노트 내용"
                    },
                    "topic": {
                        "type": "string",
                        "description": "주제 (선택사항)"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["technical", "tutorial", "review", "retrospect"],
                        "description": "글 스타일 (기본값: technical)"
                    }
                },
                "required": ["draft_content"]
            }
        ),
        Tool(
            name="blog_list_posts",
            description="블로그 포스트 목록을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "조회할 포스트 수 (기본값: 10)"
                    },
                    "offset": {
                        "type": "number",
                        "description": "시작 위치 (기본값: 0)"
                    }
                }
            }
        ),
        Tool(
            name="blog_get_post",
            description="특정 포스트의 내용을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "포스트 파일명"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_update_post",
            description="기존 포스트를 수정합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "수정할 포스트 파일명"
                    },
                    "title": {
                        "type": "string",
                        "description": "새 제목"
                    },
                    "content": {
                        "type": "string",
                        "description": "새 내용"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "새 태그 목록"
                    },
                    "draft": {
                        "type": "boolean",
                        "description": "초안 상태"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_delete_post",
            description="포스트를 삭제합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "삭제할 포스트 파일명"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_search_posts",
            description="포스트 내용으로 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색어"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="blog_git_status",
            description="Git 저장소 상태를 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="blog_sync",
            description="원격 Git 저장소에서 최신 변경사항을 동기화합니다.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    """도구 실행"""

    if name == "blog_create_post":
        result = await api_request("POST", "/posts", data={
            "title": arguments["title"],
            "content": arguments["content"],
            "tags": arguments.get("tags", []),
            "categories": arguments.get("categories", ["Development"]),
            "draft": arguments.get("draft", False),
            "auto_commit": True
        })

    elif name == "blog_create_from_draft":
        # 초안을 정리해서 포스트 생성
        # Agent가 자동으로 내용을 정리하는 것은 Claude가 수행
        # 여기서는 안내 메시지 반환
        draft = arguments["draft_content"]
        topic = arguments.get("topic", "")
        style = arguments.get("style", "technical")

        result = {
            "action": "draft_to_post",
            "message": "초안을 블로그 포스트로 변환하려면 blog_create_post 도구를 사용하세요.",
            "draft_summary": draft[:200] + "..." if len(draft) > 200 else draft,
            "suggested": {
                "style": style,
                "topic": topic,
                "categories": ["Development"] if style == "technical" else ["Tutorial"]
            },
            "instruction": """
다음 단계로 진행하세요:
1. 초안 내용을 기반으로 정리된 Markdown 작성
2. blog_create_post로 업로드

예시:
blog_create_post(
  title="정리된 제목",
  content="정리된 Markdown 내용",
  tags=["추천태그"],
  categories=["Development"]
)
"""
        }

    elif name == "blog_list_posts":
        result = await api_request("GET", "/posts", params={
            "limit": arguments.get("limit", 10),
            "offset": arguments.get("offset", 0)
        })

    elif name == "blog_get_post":
        result = await api_request("GET", f"/posts/{arguments['filename']}")

    elif name == "blog_update_post":
        data = {k: v for k, v in arguments.items() if v is not None and k != "filename"}
        result = await api_request("PUT", f"/posts/{arguments['filename']}", data=data)

    elif name == "blog_delete_post":
        result = await api_request("DELETE", f"/posts/{arguments['filename']}")

    elif name == "blog_search_posts":
        result = await api_request("GET", "/search", params={"q": arguments["query"]})

    elif name == "blog_git_status":
        result = await api_request("GET", "/git/status")

    elif name == "blog_sync":
        result = await api_request("POST", "/git/sync")

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """MCP 서버 실행"""

    # API Key 확인
    if not API_KEY:
        print("ERROR: BLOG_API_KEY 환경 변수가 설정되지 않았습니다.", file=__import__('sys').stderr)
        print("export BLOG_API_KEY=your_api_key", file=__import__('sys').stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
