"""
Blog API Server
FastAPI 기반 블로그 관리 API 서버

보안: X-API-Key 헤더를 통한 인증 필요
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from auth import verify_api_key, generate_api_key
from blog_manager import BlogManager, BLOG_ROOT
from git_handler import git_handler, auto_commit_push

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

# 블로그 매니저 인스턴스
blog_manager = BlogManager()


# Lifespan 컨텍스트
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    # 시작 시
    logger.info("Blog API Server starting...")
    logger.info(f"Blog root: {BLOG_ROOT}")
    logger.info(f"Content directory: {blog_manager.content_dir}")

    # Git 상태 확인
    status = git_handler.get_status()
    logger.info(f"Git status: {'clean' if status.get('clean') else 'has changes'}")

    yield

    # 종료 시
    logger.info("Blog API Server shutting down...")


# FastAPI 앱
app = FastAPI(
    title="Blog API",
    description="Hugo Blog 관리 API - API Key 인증 필요",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Request Models ============

class PostCreate(BaseModel):
    """포스트 생성 요청"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=lambda: ["Development"])
    draft: bool = False
    auto_commit: bool = True  # 자동 커밋 여부


class PostUpdate(BaseModel):
    """포스트 수정 요청"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    draft: Optional[bool] = None
    auto_commit: bool = True


class SearchQuery(BaseModel):
    """검색 요청"""
    query: str = Field(..., min_length=1)


# ============ Response Models ============

class SuccessResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


# ============ Health Check ============

@app.get("/health", tags=["System"])
async def health_check():
    """서버 상태 확인 (인증 불필요)"""
    return {
        "status": "healthy",
        "service": "blog-api",
        "version": "1.0.0"
    }


@app.get("/", tags=["System"])
async def root():
    """API 루트"""
    return {
        "service": "Blog API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "posts": "/posts",
            "search": "/search",
            "git": "/git",
            "health": "/health"
        }
    }


# ============ Post Endpoints ============

@app.get("/posts", tags=["Posts"])
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key)
):
    """포스트 목록 조회"""
    result = blog_manager.list_posts(limit=limit, offset=offset)
    return result


@app.get("/posts/{filename}", tags=["Posts"])
async def get_post(filename: str, api_key: str = Depends(verify_api_key)):
    """특정 포스트 조회"""
    result = blog_manager.get_post(filename)

    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.post("/posts", tags=["Posts"])
async def create_post(post: PostCreate, api_key: str = Depends(verify_api_key)):
    """새 포스트 생성"""
    result = blog_manager.create_post(
        title=post.title,
        content=post.content,
        tags=post.tags,
        categories=post.categories,
        draft=post.draft
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    # 자동 커밋
    if post.auto_commit:
        commit_result = auto_commit_push(
            message=f"Add post: {post.title}",
            files=[result["path"]]
        )
        result["git"] = commit_result

    return result


@app.put("/posts/{filename}", tags=["Posts"])
async def update_post(
    filename: str,
    post: PostUpdate,
    api_key: str = Depends(verify_api_key)
):
    """포스트 수정"""
    result = blog_manager.update_post(
        filename=filename,
        title=post.title,
        content=post.content,
        tags=post.tags,
        categories=post.categories,
        draft=post.draft
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=404 if "찾을 수 없습니다" in str(result.get("error")) else 500,
            detail=result.get("error")
        )

    # 자동 커밋
    if post.auto_commit:
        commit_result = auto_commit_push(
            message=f"Update post: {filename}",
            files=[f"content/posts/{filename}"]
        )
        result["git"] = commit_result

    return result


@app.delete("/posts/{filename}", tags=["Posts"])
async def delete_post(
    filename: str,
    auto_commit: bool = True,
    api_key: str = Depends(verify_api_key)
):
    """포스트 삭제"""
    result = blog_manager.delete_post(filename)

    if not result.get("success"):
        raise HTTPException(
            status_code=404 if "찾을 수 없습니다" in str(result.get("error")) else 500,
            detail=result.get("error")
        )

    # 자동 커밋
    if auto_commit:
        commit_result = auto_commit_push(
            message=f"Delete post: {filename}",
            files=[]
        )
        result["git"] = commit_result

    return result


# ============ Search Endpoint ============

@app.get("/search", tags=["Search"])
async def search_posts(
    q: str = Query(..., min_length=1),
    api_key: str = Depends(verify_api_key)
):
    """포스트 검색"""
    result = blog_manager.search_posts(q)
    return result


@app.post("/search", tags=["Search"])
async def search_posts_body(query: SearchQuery, api_key: str = Depends(verify_api_key)):
    """포스트 검색 (POST)"""
    result = blog_manager.search_posts(query.query)
    return result


# ============ Git Endpoints ============

@app.get("/git/status", tags=["Git"])
async def git_status(api_key: str = Depends(verify_api_key)):
    """Git 상태 확인"""
    return git_handler.get_status()


@app.post("/git/sync", tags=["Git"])
async def git_sync(api_key: str = Depends(verify_api_key)):
    """원격 저장소에서 동기화"""
    result = git_handler.sync_from_remote()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@app.post("/git/commit", tags=["Git"])
async def git_commit(
    message: str = Query(..., min_length=1),
    api_key: str = Depends(verify_api_key)
):
    """변경사항 커밋 및 푸시"""
    result = auto_commit_push(message)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return result


@app.get("/git/commits", tags=["Git"])
async def git_commits(
    limit: int = Query(5, ge=1, le=20),
    api_key: str = Depends(verify_api_key)
):
    """최근 커밋 목록"""
    return git_handler.get_recent_commits(limit)


# ============ Utility Endpoints ============

@app.post("/utils/generate-key", tags=["Utils"])
async def generate_new_key(api_key: str = Depends(verify_api_key)):
    """새 API 키 생성"""
    new_key = generate_api_key()
    return {
        "api_key": new_key,
        "message": "Store this key securely. It cannot be retrieved again."
    }


# ============ Error Handlers ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


# ============ Main ============

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
