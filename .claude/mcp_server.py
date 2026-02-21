#!/usr/bin/env python3
"""
Blog MCP Server - Hugo Blog Management via Model Context Protocol

이 MCP 서버는 Claude가 블로그 포스트를 관리할 수 있는 도구를 제공합니다.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

# MCP SDK imports (mcp 패키지 필요)
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 블로그 루트 경로
BLOG_ROOT = Path(__file__).parent.parent.absolute()
CONTENT_DIR = BLOG_ROOT / "content" / "posts"
STATIC_DIR = BLOG_ROOT / "static"


class PostCategory(Enum):
    AI = "AI"
    ARCHITECTURE = "Architecture"
    DEVELOPMENT = "Development"
    INFRASTRUCTURE = "Infrastructure"
    TUTORIAL = "Tutorial"
    RETROSPECT = "Retrospect"


@dataclass
class BlogPost:
    """블로그 포스트 데이터 구조"""
    title: str
    date: str
    draft: bool
    tags: List[str]
    categories: List[str]
    content: str
    filename: Optional[str] = None

    def to_front_matter(self) -> str:
        """Hugo front matter 생성"""
        return f'''+++
title = "{self.title}"
date = {self.date}
draft = {str(self.draft).lower()}
tags = {json.dumps(self.tags)}
categories = {json.dumps(self.categories)}
ShowToc = true
TocOpen = true
+++

{self.content}'''


class BlogManager:
    """블로그 관리 클래스"""

    def __init__(self, content_dir: Path = CONTENT_DIR):
        self.content_dir = content_dir
        self.content_dir.mkdir(parents=True, exist_ok=True)

    def _parse_front_matter(self, content: str) -> Dict[str, Any]:
        """TOML front matter 파싱"""
        if not content.startswith("+++"):
            return {}

        parts = content.split("+++", 2)
        if len(parts) < 3:
            return {}

        front_matter_str = parts[1].strip()
        result = {}

        # 간단한 TOML 파싱
        for line in front_matter_str.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # 문자열
                if value.startswith('"') and value.endswith('"'):
                    result[key] = value[1:-1]
                # 불리언
                elif value in ["true", "false"]:
                    result[key] = value == "true"
                # 배열
                elif value.startswith("["):
                    try:
                        result[key] = json.loads(value)
                    except:
                        result[key] = value
                else:
                    result[key] = value

        result["_content"] = parts[2].strip() if len(parts) > 2 else ""
        return result

    def _generate_filename(self, title: str, index: int = None) -> str:
        """파일명 생성: YYYY-MM-DD-NNN-slug.md"""
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")

        # slug 생성 (한글은 transliterate, 특수문자 제거)
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug)
        slug = slug[:50]  # 최대 50자

        # NNN 포맷
        nn = f"{index:03d}" if index else "001"

        return f"{date_str}-{nn}-{slug}.md"

    def list_posts(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """포스트 목록 조회"""
        posts = []

        for file in sorted(self.content_dir.glob("*.md"), reverse=True):
            content = file.read_text(encoding="utf-8")
            metadata = self._parse_front_matter(content)

            posts.append({
                "filename": file.name,
                "title": metadata.get("title", "Untitled"),
                "date": metadata.get("date", ""),
                "draft": metadata.get("draft", False),
                "tags": metadata.get("tags", []),
                "categories": metadata.get("categories", []),
            })

        return posts[offset:offset + limit]

    def get_post(self, filename: str) -> Optional[Dict]:
        """특정 포스트 조회"""
        file_path = self.content_dir / filename

        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        metadata = self._parse_front_matter(content)

        return {
            "filename": filename,
            "title": metadata.get("title", "Untitled"),
            "date": metadata.get("date", ""),
            "draft": metadata.get("draft", False),
            "tags": metadata.get("tags", []),
            "categories": metadata.get("categories", []),
            "content": metadata.get("_content", ""),
        }

    def create_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        draft: bool = False
    ) -> Dict:
        """새 포스트 생성"""
        tags = tags or []
        categories = categories or ["Development"]

        # 기존 포스트 수 확인해서 NNN 결정
        existing_count = len(list(self.content_dir.glob("*.md")))

        post = BlogPost(
            title=title,
            date=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            draft=draft,
            tags=tags,
            categories=categories,
            content=content,
        )

        filename = self._generate_filename(title, existing_count + 1)
        file_path = self.content_dir / filename

        # 중복 방지
        while file_path.exists():
            existing_count += 1
            filename = self._generate_filename(title, existing_count + 1)
            file_path = self.content_dir / filename

        post.filename = filename
        file_path.write_text(post.to_front_matter(), encoding="utf-8")

        return {
            "success": True,
            "filename": filename,
            "path": str(file_path),
            "message": f"포스트가 생성되었습니다: {filename}"
        }

    def update_post(
        self,
        filename: str,
        title: str = None,
        content: str = None,
        tags: List[str] = None,
        categories: List[str] = None,
        draft: bool = None
    ) -> Dict:
        """포스트 수정"""
        file_path = self.content_dir / filename

        if not file_path.exists():
            return {"success": False, "error": f"포스트를 찾을 수 없습니다: {filename}"}

        existing = self.get_post(filename)

        post = BlogPost(
            title=title or existing["title"],
            date=existing["date"],
            draft=draft if draft is not None else existing["draft"],
            tags=tags or existing["tags"],
            categories=categories or existing["categories"],
            content=content or existing["content"],
            filename=filename,
        )

        file_path.write_text(post.to_front_matter(), encoding="utf-8")

        return {
            "success": True,
            "filename": filename,
            "message": f"포스트가 수정되었습니다: {filename}"
        }

    def delete_post(self, filename: str) -> Dict:
        """포스트 삭제"""
        file_path = self.content_dir / filename

        if not file_path.exists():
            return {"success": False, "error": f"포스트를 찾을 수 없습니다: {filename}"}

        file_path.unlink()

        return {
            "success": True,
            "message": f"포스트가 삭제되었습니다: {filename}"
        }

    def search_posts(self, query: str) -> List[Dict]:
        """포스트 검색"""
        results = []
        query_lower = query.lower()

        for file in self.content_dir.glob("*.md"):
            content = file.read_text(encoding="utf-8").lower()

            if query_lower in content:
                metadata = self._parse_front_matter(file.read_text(encoding="utf-8"))
                results.append({
                    "filename": file.name,
                    "title": metadata.get("title", "Untitled"),
                    "relevance": content.count(query_lower),
                })

        return sorted(results, key=lambda x: x["relevance"], reverse=True)


# MCP Server 인스턴스
server = Server("blog-manager")
blog_manager = BlogManager()


@server.list_tools()
async def list_tools() -> List[Tool]:
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="blog_create_post",
            description="새 블로그 포스트를 생성합니다. 제목, 내용, 태그, 카테고리를 입력받습니다.",
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
                        "description": "태그 목록"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "카테고리 목록"
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
            name="blog_list_posts",
            description="블로그 포스트 목록을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "조회할 포스트 수 (기본값: 20)"
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
                        "description": "새 제목 (변경하지 않으려면 생략)"
                    },
                    "content": {
                        "type": "string",
                        "description": "새 내용 (변경하지 않으려면 생략)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "새 태그 목록"
                    },
                    "draft": {
                        "type": "boolean",
                        "description": "초안 상태 변경"
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    """도구 실행"""

    if name == "blog_create_post":
        result = blog_manager.create_post(
            title=arguments["title"],
            content=arguments["content"],
            tags=arguments.get("tags", []),
            categories=arguments.get("categories", []),
            draft=arguments.get("draft", False)
        )

    elif name == "blog_list_posts":
        posts = blog_manager.list_posts(
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0)
        )
        result = {"posts": posts, "count": len(posts)}

    elif name == "blog_get_post":
        result = blog_manager.get_post(arguments["filename"])
        if not result:
            result = {"error": "포스트를 찾을 수 없습니다"}

    elif name == "blog_update_post":
        result = blog_manager.update_post(
            filename=arguments["filename"],
            title=arguments.get("title"),
            content=arguments.get("content"),
            tags=arguments.get("tags"),
            categories=arguments.get("categories"),
            draft=arguments.get("draft")
        )

    elif name == "blog_delete_post":
        result = blog_manager.delete_post(arguments["filename"])

    elif name == "blog_search_posts":
        results = blog_manager.search_posts(arguments["query"])
        result = {"results": results, "count": len(results)}

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    """MCP 서버 실행"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
