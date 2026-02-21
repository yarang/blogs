"""
블로그 포스트 관리 모듈
"""

import os
import re
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import frontmatter


# 블로그 루트 경로 (환경 변수로 설정 가능)
BLOG_ROOT = Path(os.getenv("BLOG_ROOT", Path(__file__).parent.parent))
CONTENT_DIR = BLOG_ROOT / "content" / "posts"


# 파일 작업 동기화를 위한 락
_file_lock = threading.Lock()


@dataclass
class PostMetadata:
    """포스트 메타데이터"""
    title: str
    date: str
    draft: bool
    tags: List[str]
    categories: List[str]
    show_toc: bool = True
    toc_open: bool = True


class BlogManager:
    """블로그 포스트 관리 클래스"""

    def __init__(self, content_dir: Path = CONTENT_DIR):
        self.content_dir = content_dir
        self.content_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, title: str) -> str:
        """파일명 생성: YYYY-MM-DD-NNN-slug.md"""
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")

        # slug 생성
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s]+', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        slug = slug[:50] or "post"

        # 다음 번호 찾기
        existing = list(self.content_dir.glob(f"{date_str}-*.md"))
        next_num = len(existing) + 1

        # 중복 방지
        while True:
            filename = f"{date_str}-{next_num:03d}-{slug}.md"
            if not (self.content_dir / filename).exists():
                break
            next_num += 1

        return filename

    def list_posts(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """포스트 목록 조회"""
        posts = []

        for file in sorted(self.content_dir.glob("*.md"), reverse=True):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)

                posts.append({
                    "filename": file.name,
                    "title": post.get("title", "Untitled"),
                    "date": str(post.get("date", "")),
                    "draft": post.get("draft", False),
                    "tags": post.get("tags", []),
                    "categories": post.get("categories", []),
                })
            except Exception as e:
                posts.append({
                    "filename": file.name,
                    "title": "Error loading post",
                    "error": str(e)
                })

        return {
            "posts": posts[offset:offset + limit],
            "total": len(posts),
            "offset": offset,
            "limit": limit
        }

    def get_post(self, filename: str) -> Optional[Dict[str, Any]]:
        """특정 포스트 조회"""
        file_path = self.content_dir / filename

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            return {
                "filename": filename,
                "title": post.get("title", "Untitled"),
                "date": str(post.get("date", "")),
                "draft": post.get("draft", False),
                "tags": post.get("tags", []),
                "categories": post.get("categories", []),
                "content": post.content,
            }
        except Exception as e:
            return {"error": str(e), "filename": filename}

    def create_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        draft: bool = False
    ) -> Dict[str, Any]:
        """새 포스트 생성"""
        with _file_lock:
            tags = tags or []
            categories = categories or ["Development"]

            filename = self._generate_filename(title)
            file_path = self.content_dir / filename

            # Front matter와 함께 포스트 생성
            post = frontmatter.Post(content)
            post["title"] = title
            post["date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
            post["draft"] = draft
            post["tags"] = tags
            post["categories"] = categories
            post["ShowToc"] = True
            post["TocOpen"] = True

            with open(file_path, 'w', encoding='utf-8') as f:
                frontmatter.dump(post, f)

            return {
                "success": True,
                "filename": filename,
                "path": str(file_path.relative_to(BLOG_ROOT)),
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
    ) -> Dict[str, Any]:
        """포스트 수정"""
        with _file_lock:
            file_path = self.content_dir / filename

            if not file_path.exists():
                return {"success": False, "error": f"포스트를 찾을 수 없습니다: {filename}"}

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)

                # 업데이트
                if title is not None:
                    post["title"] = title
                if content is not None:
                    post.content = content
                if tags is not None:
                    post["tags"] = tags
                if categories is not None:
                    post["categories"] = categories
                if draft is not None:
                    post["draft"] = draft

                with open(file_path, 'w', encoding='utf-8') as f:
                    frontmatter.dump(post, f)

                return {
                    "success": True,
                    "filename": filename,
                    "message": f"포스트가 수정되었습니다: {filename}"
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    def delete_post(self, filename: str) -> Dict[str, Any]:
        """포스트 삭제"""
        with _file_lock:
            file_path = self.content_dir / filename

            if not file_path.exists():
                return {"success": False, "error": f"포스트를 찾을 수 없습니다: {filename}"}

            try:
                file_path.unlink()
                return {
                    "success": True,
                    "message": f"포스트가 삭제되었습니다: {filename}"
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    def search_posts(self, query: str) -> Dict[str, Any]:
        """포스트 검색"""
        results = []
        query_lower = query.lower()

        for file in self.content_dir.glob("*.md"):
            try:
                content = file.read_text(encoding='utf-8')
                content_lower = content.lower()

                if query_lower in content_lower:
                    post = frontmatter.load(file)
                    results.append({
                        "filename": file.name,
                        "title": post.get("title", "Untitled"),
                        "relevance": content_lower.count(query_lower),
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x["relevance"], reverse=True)

        return {
            "results": results[:20],
            "query": query,
            "count": len(results)
        }
