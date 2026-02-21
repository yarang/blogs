# Blog System Architecture

## 개요

MCP Server가 API Server를 통해 블로그를 관리합니다.
모든 Git 작업은 API Server에서만 수행됩니다.

## 블록 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                   Block 1: MCP Server (Client)                   │
│                                                                  │
│  - Claude Code CLI에서 실행                                      │
│  - 어디서든 실행 가능 (로컬 Git 불필요)                           │
│  - HTTP로 API Server에 요청                                      │
│                                                                  │
│  환경 변수:                                                      │
│    BLOG_API_URL=https://api.blog.fcoinfup.com                   │
│    BLOG_API_KEY=your_api_key                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ HTTP (API Key 인증)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Block 2: API Server (OCI)                      │
│                                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │ FastAPI  │──►│ BlogManager  │──►│ GitManager   │            │
│  └──────────┘   └──────────────┘   └──────┬───────┘            │
│                                            │                    │
│  - 모든 Git 작업 담당                        │                    │
│  - 파일 생성/수정/삭제                      │                    │
│  - API Key 인증                             │                    │
└────────────────────────────────────────────┼────────────────────┘
                                             │
                                            Git
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Block 3: GitHub                              │
│                                                                  │
│  - 중앙 저장소 (Single Source of Truth)                          │
│  - Block 4: GitHub Actions 트리거                               │
└─────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                Block 4: GitHub Actions                           │
│                                                                  │
│  1. hugo --minify (빌드)                                         │
│  2. rsync → OCI 서버 (배포)                                      │
└─────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Block 5: Blog (Deployed)                         │
│                                                                  │
│  - Nginx: /var/www/blog                                         │
│  - https://blog.fcoinfup.com                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 데이터 흐름

```
1. Claude Code: "블로그 포스트 작성해줘"
         │
         ▼
2. MCP Server: HTTP POST /posts (API Key 포함)
         │
         ▼
3. API Server:
   a. Git pull (최신 동기화)
   b. 파일 생성
   c. Git commit
   d. Git push
         │
         ▼
4. GitHub: Actions 트리거
         │
         ▼
5. Actions: Hugo 빌드 → rsync 배포
         │
         ▼
6. Blog: https://blog.fcoinfup.com 반영
```

## 블록 정의

### Block 1: MCP Server
- **위치**: 로컬 (어디서든)
- **입력**: Claude Code CLI
- **출력**: HTTP API 요청
- **의존성**: httpx, mcp

### Block 2: API Server
- **위치**: OCI 서버
- **입력**: HTTP API 요청
- **출력**: Git commit/push
- **의존성**: FastAPI, Git

### Block 3: GitHub
- **역할**: 중앙 저장소
- **기능**: Actions 트리거

### Block 4: GitHub Actions
- **트리거**: push to main
- **작업**: Hugo 빌드, rsync 배포

### Block 5: Blog
- **위치**: OCI 서버
- **역할**: 정적 파일 서빙

## 파일 구조

```
blogs/
├── .mcp.json                    # MCP 설정 (Block 1)
├── .claude/
│   ├── mcp_server.py           # MCP Server (Block 1)
│   └── requirements.txt
│
├── api_server/                  # API Server (Block 2)
│   ├── main.py                 # FastAPI 엔드포인트
│   ├── blog_manager.py         # 블로그 + Git 관리
│   ├── auth.py                 # API Key 인증
│   └── requirements.txt
│
├── .github/workflows/
│   └── deploy.yml              # Actions (Block 4)
│
└── content/posts/              # 블로그 콘텐츠
```

## 설정

### MCP Server (.mcp.json)
```json
{
  "mcpServers": {
    "blog": {
      "command": "python3",
      "args": [".claude/mcp_server.py"],
      "env": {
        "BLOG_API_URL": "https://api.blog.fcoinfup.com",
        "BLOG_API_KEY": "your_api_key"
      }
    }
  }
}
```

### API Server (.env)
```
BLOG_API_KEYS=blog_key1,blog_key2
BLOG_REPO_URL=https://github.com/yarang/blogs.git
BLOG_REPO_PATH=/var/www/blog-repo
```

## 장점

| 장점 | 설명 |
|------|------|
| **중앙 집중** | Git 관리가 API Server에만 집중 |
| **접근성** | MCP는 어디서든 사용 가능 |
| **단순성** | MCP는 HTTP 클라이언트만 필요 |
| **보안** | API Key로 인증 |
