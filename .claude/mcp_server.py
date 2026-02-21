#!/usr/bin/env python3
"""
Blog MCP Server - 통합 버전

API 서버 없이 직접 Git과 파일 시스템에 접근합니다.
같은 머신의 Claude Code에서만 사용 가능합니다.
"""

import os
import re
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 설정
BLOG_ROOT = Path(os.getenv("BLOG_ROOT", Path(__file__).parent.parent))
CONTENT_DIR = BLOG_ROOT / "content" / "posts"
STATIC_DIR = BLOG_ROOT / "static" / "images"

# 동기화 락
_lock = threading.Lock()

# MCP Server
server = Server("blog-manager")


# ============ Git 함수 ============

def git_run(*args, cwd=BLOG_ROOT) -> tuple:
    """Git 명령어 실행"""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def git_commit_push(message: str, files: List[str] = None) -> Dict:
    """Git 커밋 및 푸시"""
    with _lock:
        # 파일 추가
        if files:
            for f in files:
                git_run("add", f)
        else:
            git_run("add", "content/", "static/")

        # 변경사항 확인
        code, stdout, _ = git_run("diff", "--cached", "--quiet")
        if code == 0:
            return {"success": True, "message": "변경사항 없음"}

        # 커밋
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"{message}\n\nBy Blog MCP at {timestamp}"
        code, _, stderr = git_run("commit", "-m", full_msg)

        if code != 0:
            return {"success": False, "error": f"Commit 실패: {stderr}"}

        # 푸시
        code, _, stderr = git_run("push", "origin", "main")

        if code != 0:
            return {"success": False, "error": f"Push 실패: {stderr}"}

        return {"success": True, "message": "커밋 및 푸시 완료"}


def git_pull() -> Dict:
    """원격에서 pull"""
    code, stdout, stderr = git_run("pull", "origin", "main")
    if code != 0:
        return {"success": False, "error": stderr}
    return {"success": True, "message": "동기화 완료"}


# ============ 블로그 함수 ============

def generate_filename(title: str) -> str:
    """파일명 생성: YYYY-MM-DD-NNN-slug.md"""
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s]+', '-', slug)[:50]

    existing = list(CONTENT_DIR.glob(f"{today}-*.md"))
    num = len(existing) + 1

    while True:
        filename = f"{today}-{num:03d}-{slug}.md"
        if not (CONTENT_DIR / filename).exists():
            return filename
        num += 1


def create_post(
    title: str,
    content: str,
    tags: List[str] = None,
    categories: List[str] = None,
    draft: bool = False
) -> Dict:
    """포스트 생성"""
    with _lock:
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)

        tags = tags or []
        categories = categories or ["Development"]
        filename = generate_filename(title)

        front_matter = f'''+++
title = "{title}"
date = {datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")}
draft = {str(draft).lower()}
tags = {json.dumps(tags)}
categories = {json.dumps(categories)}
ShowToc = true
TocOpen = true
+++

{content}'''

        filepath = CONTENT_DIR / filename
        filepath.write_text(front_matter, encoding="utf-8")

        return {
            "success": True,
            "filename": filename,
            "path": f"content/posts/{filename}",
            "message": f"포스트 생성: {filename}"
        }


def list_posts(limit: int = 20, offset: int = 0) -> Dict:
    """포스트 목록"""
    posts = []
    for f in sorted(CONTENT_DIR.glob("*.md"), reverse=True):
        try:
            content = f.read_text(encoding="utf-8")
            # 간단한 파싱
            title = "Unknown"
            for line in content.split("\n")[1:10]:
                if line.startswith('title = '):
                    title = line.split('"')[1]
                    break

            posts.append({
                "filename": f.name,
                "title": title,
            })
        except:
            pass

    return {"posts": posts[offset:offset+limit], "total": len(posts)}


def get_post(filename: str) -> Dict:
    """포스트 조회"""
    filepath = CONTENT_DIR / filename
    if not filepath.exists():
        return {"error": "파일 없음"}

    content = filepath.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}


def delete_post(filename: str) -> Dict:
    """포스트 삭제"""
    filepath = CONTENT_DIR / filename
    if not filepath.exists():
        return {"success": False, "error": "파일 없음"}

    filepath.unlink()
    return {"success": True, "message": "삭제 완료"}


def search_posts(query: str) -> Dict:
    """포스트 검색"""
    results = []
    query_lower = query.lower()

    for f in CONTENT_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").lower()
        if query_lower in content:
            results.append({"filename": f.name, "relevance": content.count(query_lower)})

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return {"results": results[:20], "query": query}


# ============ MCP 도구 ============

@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="blog_create_post",
            description="블로그 포스트를 생성하고 Git에 커밋/푸시합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "제목"},
                    "content": {"type": "string", "description": "내용 (Markdown)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "태그"},
                    "categories": {"type": "array", "items": {"type": "string"}, "description": "카테고리"},
                    "draft": {"type": "boolean", "description": "초안 여부"},
                    "auto_commit": {"type": "boolean", "description": "자동 커밋 (기본: true)"}
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="blog_list_posts",
            description="포스트 목록을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "description": "개수"},
                    "offset": {"type": "number", "description": "시작 위치"}
                }
            }
        ),
        Tool(
            name="blog_get_post",
            description="특정 포스트를 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "파일명"}
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
                    "filename": {"type": "string", "description": "파일명"}
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="blog_search_posts",
            description="포스트를 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="blog_git_status",
            description="Git 상태를 확인합니다.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="blog_git_sync",
            description="원격에서 최신 코드를 가져옵니다.",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    if name == "blog_create_post":
        result = create_post(
            title=arguments["title"],
            content=arguments["content"],
            tags=arguments.get("tags", []),
            categories=arguments.get("categories", ["Development"]),
            draft=arguments.get("draft", False)
        )

        if result.get("success") and arguments.get("auto_commit", True):
            git_result = git_commit_push(
                f"Add post: {arguments['title']}",
                [result["path"]]
            )
            result["git"] = git_result

    elif name == "blog_list_posts":
        result = list_posts(
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0)
        )

    elif name == "blog_get_post":
        result = get_post(arguments["filename"])

    elif name == "blog_delete_post":
        result = delete_post(arguments["filename"])

    elif name == "blog_search_posts":
        result = search_posts(arguments["query"])

    elif name == "blog_git_status":
        code, stdout, stderr = git_run("status", "--short")
        result = {"status": stdout, "clean": stdout.strip() == ""}

    elif name == "blog_git_sync":
        result = git_pull()

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
