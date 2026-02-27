+++
title = "MCP 클라이언트를 활용한 블로그 자동화 시스템"
date = 2026-02-27T20:00:00+09:00
draft = false
tags = ["MCP", "Python", "블로그", "자동화", "Claude Code"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# MCP 클라이언트를 활용한 블로그 자동화 시스템

## 개요

이 문서는 Claude Code에서 MCP(Model Context Protocol)를 통해 블로그를 자동으로 관리하는 클라이언트 시스템에 대해 설명합니다.

## MCP 클라이언트란?

MCP 클라이언트는 Claude Code와 외부 API 서버 간의 통신을 중계하는 Python 기반 애플리케이션입니다. stdio 프로토콜을 사용하여 Claude Code와 통신하고, HTTP REST API를 통해 블로그 서버와 통신합니다.

## 아키텍처

```
┌─────────────────┐      MCP       ┌─────────────────┐      HTTP      ┌─────────────────┐
│   Claude Code   │ ────────────▶  │   MCP Client    │ ────────────▶  │   API Server    │
│                 │   (stdio)      │   (Python)      │   (REST)       │   (FastAPI)     │
└─────────────────┘                └─────────────────┘                └─────────────────┘
```

## 설치 방법

```bash
curl -fsSL https://raw.githubusercontent.com/yarang/blog-api-server/main/mcp_client/install.sh | bash -s -- ~/.blog-mcp
```

## 설정 파일

`.mcp.json` 파일을 프로젝트 루트에 생성합니다:

```json
{
  "mcpServers": {
    "blog": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "https://blog.fcoinfup.com",
        "BLOG_API_BASE_PATH": "/api",
        "BLOG_API_KEY": "your_api_key"
      }
    }
  }
}
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `BLOG_API_URL` | API 서버 URL | `https://blog.fcoinfup.com` |
| `BLOG_API_BASE_PATH` | API 경로 접두사 | `/api` |
| `BLOG_API_KEY` | 인증용 API 키 | (필수) |

## 사용 가능한 도구

### blog_create
새 블로그 포스트를 생성합니다.

```
매개변수:
- title: 포스트 제목 (필수)
- content: 포스트 내용, Markdown 형식 (필수)
- tags: 태그 목록
- categories: 카테고리 목록
- draft: 초안 여부
```

### blog_list
포스트 목록을 조회합니다.

```
매개변수:
- limit: 조회할 개수
- offset: 시작 위치
```

### blog_get
특정 포스트를 조회합니다.

```
매개변수:
- filename: 파일명
```

### blog_update
포스트를 수정합니다.

```
매개변수:
- filename: 파일명
- content: 수정할 내용
```

### blog_delete
포스트를 삭제합니다.

```
매개변수:
- filename: 파일명
```

### blog_search
포스트를 검색합니다.

```
매개변수:
- query: 검색어
```

### blog_status
Git 저장소 상태를 확인합니다.

### blog_sync
Git 저장소를 동기화합니다.

## 내부 구조

### BlogClient 클래스

```python
class BlogClient:
    """Blog API HTTP 클라이언트"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    async def request(self, method: str, path: str,
                      data: Dict = None, params: Dict = None) -> Dict:
        """API 요청 실행"""
        url = f"{self.base_url}{API_BASE_PATH}{path}"
        # ... HTTP 요청 처리
```

### 캐싱

GET 요청은 5분간 캐싱되어 불필요한 API 호출을 최소화합니다.

## 문제 해결

### "Expecting value: line 1 column 1" 에러

MCP 서버가 응답하지 않을 때 발생합니다. Claude Code를 재시작하거나 `/mcp` 명령어로 재연결하세요.

### API 타임아웃

API 서버의 Git 작업이 지연될 때 발생합니다. 서버 상태를 확인하거나 잠시 후 재시도하세요.

## 날짜

2026-02-27 작성
