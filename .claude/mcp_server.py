#!/usr/bin/env python3
"""
Blog MCP Server - Claude Code CLI용

독립적으로 Git 저장소를 관리합니다.
다른 모듈과는 Git을 통해서만 동기화됩니다.
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

# ============================================================
# Block: Git Manager (독립 모듈)
# ============================================================

class GitManager:
    """Git 저장소 관리 - 다른 모듈과 독립적"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._lock = threading.Lock()

    def pull(self) -> Dict:
        """원격에서 최신 가져오기"""
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.repo_path,
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return {"success": True, "message": "동기화 완료"}
            return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def commit_and_push(self, message: str, files: List[str] = None) -> Dict:
        """커밋하고 푸시"""
        with self._lock:
            try:
                # 파일 추가
                if files:
                    for f in files:
                        subprocess.run(
                            ["git", "add", f],
                            cwd=self.repo_path, capture_output=True
                        )
                else:
                    subprocess.run(
                        ["git", "add", "content/", "static/"],
                        cwd=self.repo_path, capture_output=True
                    )

                # 변경사항 확인
                result = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=self.repo_path, capture_output=True
                )
                if result.returncode == 0:
                    return {"success": True, "message": "변경사항 없음"}

                # 커밋
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                full_msg = f"{message}\n\nBy Blog MCP at {timestamp}"
                result = subprocess.run(
                    ["git", "commit", "-m", full_msg],
                    cwd=self.repo_path, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Commit 실패: {result.stderr}"}

                # 푸시
                result = subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=self.repo_path, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Push 실패: {result.stderr}"}

                return {"success": True, "message": "커밋 및 푸시 완료"}

            except Exception as e:
                return {"success": False, "error": str(e)}

    def status(self) -> Dict:
        """Git 상태"""
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return {
            "clean": result.stdout.strip() == "",
            "status": result.stdout
        }


# ============================================================
# Block: Blog Manager (독립 모듈)
# ============================================================

class BlogManager:
    """블로그 포스트 관리 - Git과 독립적 통신"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.content_dir = repo_path / "content" / "posts"
        self.git = GitManager(repo_path)
        self._lock = threading.Lock()

    def _generate_filename(self, title: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug)[:50]

        existing = list(self.content_dir.glob(f"{today}-*.md"))
        num = len(existing) + 1

        while True:
            filename = f"{today}-{num:03d}-{slug}.md"
            if not (self.content_dir / filename).exists():
                return filename
            num += 1

    def create_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        draft: bool = False,
        auto_push: bool = True
    ) -> Dict:
        """포스트 생성"""
        with self._lock:
            # 최신 동기화
            self.git.pull()

            tags = tags or []
            categories = categories or ["Development"]
            filename = self._generate_filename(title)

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

            self.content_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.content_dir / filename
            filepath.write_text(front_matter, encoding="utf-8")

            result = {
                "success": True,
                "filename": filename,
                "path": f"content/posts/{filename}",
                "message": f"포스트 생성: {filename}"
            }

            # Git 동기화
            if auto_push:
                result["git"] = self.git.commit_and_push(
                    f"Add post: {title}",
                    [result["path"]]
                )

            return result

    def list_posts(self, limit: int = 20, offset: int = 0) -> Dict:
        """포스트 목록"""
        self.git.pull()

        posts = []
        for f in sorted(self.content_dir.glob("*.md"), reverse=True):
            try:
                content = f.read_text(encoding="utf-8")
                title = "Unknown"
                for line in content.split("\n")[1:10]:
                    if line.startswith('title = '):
                        title = line.split('"')[1]
                        break
                posts.append({"filename": f.name, "title": title})
            except:
                pass

        return {"posts": posts[offset:offset+limit], "total": len(posts)}

    def get_post(self, filename: str) -> Dict:
        """포스트 조회"""
        filepath = self.content_dir / filename
        if not filepath.exists():
            return {"error": "파일 없음"}
        return {"filename": filename, "content": filepath.read_text(encoding="utf-8")}

    def delete_post(self, filename: str, auto_push: bool = True) -> Dict:
        """포스트 삭제"""
        with self._lock:
            filepath = self.content_dir / filename
            if not filepath.exists():
                return {"success": False, "error": "파일 없음"}

            filepath.unlink()
            result = {"success": True, "message": "삭제 완료"}

            if auto_push:
                result["git"] = self.git.commit_and_push(f"Delete post: {filename}")

            return result

    def search_posts(self, query: str) -> Dict:
        """포스트 검색"""
        self.git.pull()

        results = []
        query_lower = query.lower()

        for f in self.content_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8").lower()
            if query_lower in content:
                results.append({
                    "filename": f.name,
                    "relevance": content.count(query_lower)
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return {"results": results[:20], "query": query}


# ============================================================
# Block: MCP Server (인터페이스)
# ============================================================

# 설정
BLOG_ROOT = Path(os.getenv("BLOG_ROOT", Path(__file__).parent.parent))

# 인스턴스
blog_manager = BlogManager(BLOG_ROOT)
server = Server("blog-manager")


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="blog_create",
            description="블로그 포스트 생성 + Git 동기화",
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
        result = blog_manager.create_post(
            title=arguments["title"],
            content=arguments["content"],
            tags=arguments.get("tags", []),
            categories=arguments.get("categories", ["Development"]),
            draft=arguments.get("draft", False)
        )

    elif name == "blog_list":
        result = blog_manager.list_posts(
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0)
        )

    elif name == "blog_get":
        result = blog_manager.get_post(arguments["filename"])

    elif name == "blog_delete":
        result = blog_manager.delete_post(arguments["filename"])

    elif name == "blog_search":
        result = blog_manager.search_posts(arguments["query"])

    elif name == "blog_sync":
        result = blog_manager.git.pull()

    elif name == "blog_status":
        result = blog_manager.git.status()

    else:
        result = {"error": f"알 수 없는 도구: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
