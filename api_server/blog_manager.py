"""
Blog Manager - Git 기반 블로그 포스트 관리

독립적으로 Git 저장소를 관리합니다.
"""

import os
import re
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 설정
BLOG_REPO_URL = os.getenv("BLOG_REPO_URL", "https://github.com/yarang/blogs.git")
BLOG_REPO_PATH = Path(os.getenv("BLOG_REPO_PATH", "/var/www/blog-repo"))
CONTENT_DIR = BLOG_REPO_PATH / "content" / "posts"

# 동기화 락
_lock = threading.Lock()


class GitManager:
    """Git 저장소 관리자"""

    def __init__(self, repo_path: Path = BLOG_REPO_PATH, repo_url: str = BLOG_REPO_URL):
        self.repo_path = repo_path
        self.repo_url = repo_url

    def ensure_repo(self) -> bool:
        """저장소가 있으면 pull, 없으면 clone"""
        if self.repo_path.exists():
            return self.pull()
        else:
            return self.clone()

    def clone(self) -> bool:
        """저장소 클론"""
        try:
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.repo_path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                logger.info(f"Cloned repo to {self.repo_path}")
                return True
            logger.error(f"Clone failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Clone error: {e}")
            return False

    def pull(self) -> bool:
        """최신 내용 가져오기"""
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                logger.info("Pulled latest changes")
                return True
            logger.error(f"Pull failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Pull error: {e}")
            return False

    def commit_and_push(self, message: str, files: List[str] = None) -> Dict:
        """커밋하고 푸시"""
        with _lock:
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
                full_msg = f"{message}\n\nBy Blog API at {timestamp}"
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


class BlogManager:
    """블로그 포스트 관리자"""

    def __init__(self):
        self.git = GitManager()
        self._ensure_ready()

    def _ensure_ready(self):
        """저장소 준비 확인"""
        if not CONTENT_DIR.exists():
            self.git.ensure_repo()

    def _generate_filename(self, title: str) -> str:
        """파일명 생성"""
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

    def sync(self) -> Dict:
        """Git 동기화"""
        if self.git.pull():
            return {"success": True, "message": "동기화 완료"}
        return {"success": False, "error": "동기화 실패"}

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
        with _lock:
            # 동기화
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

            CONTENT_DIR.mkdir(parents=True, exist_ok=True)
            filepath = CONTENT_DIR / filename
            filepath.write_text(front_matter, encoding="utf-8")

            result = {
                "success": True,
                "filename": filename,
                "path": f"content/posts/{filename}",
                "message": f"포스트 생성: {filename}"
            }

            # 자동 푸시
            if auto_push:
                git_result = self.git.commit_and_push(
                    f"Add post: {title}",
                    [result["path"]]
                )
                result["git"] = git_result

            return result

    def list_posts(self, limit: int = 20, offset: int = 0) -> Dict:
        """포스트 목록"""
        self.git.pull()

        posts = []
        for f in sorted(CONTENT_DIR.glob("*.md"), reverse=True):
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
        filepath = CONTENT_DIR / filename
        if not filepath.exists():
            return {"error": "파일 없음"}
        return {"filename": filename, "content": filepath.read_text(encoding="utf-8")}

    def update_post(self, filename: str, content: str = None, auto_push: bool = True) -> Dict:
        """포스트 수정"""
        with _lock:
            filepath = CONTENT_DIR / filename
            if not filepath.exists():
                return {"success": False, "error": "파일 없음"}

            if content:
                filepath.write_text(content, encoding="utf-8")

            result = {"success": True, "filename": filename}

            if auto_push:
                result["git"] = self.git.commit_and_push(
                    f"Update post: {filename}",
                    [f"content/posts/{filename}"]
                )

            return result

    def delete_post(self, filename: str, auto_push: bool = True) -> Dict:
        """포스트 삭제"""
        with _lock:
            filepath = CONTENT_DIR / filename
            if not filepath.exists():
                return {"success": False, "error": "파일 없음"}

            filepath.unlink()

            result = {"success": True, "message": "삭제 완료"}

            if auto_push:
                result["git"] = self.git.commit_and_push(
                    f"Delete post: {filename}"
                )

            return result

    def search_posts(self, query: str) -> Dict:
        """포스트 검색"""
        self.git.pull()

        results = []
        query_lower = query.lower()

        for f in CONTENT_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8").lower()
            if query_lower in content:
                results.append({
                    "filename": f.name,
                    "relevance": content.count(query_lower)
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return {"results": results[:20], "query": query}


# 전역 인스턴스
blog_manager = BlogManager()
