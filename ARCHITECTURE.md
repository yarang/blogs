# Blog System Architecture

## 개요

블로그와 API 서버가 분리된 마이크로서비스 아키텍처입니다.

## 블록 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                   Block 1: MCP Server (Client)                   │
│                                                                  │
│  - Claude Code CLI에서 실행                                      │
│  - 어디서든 실행 가능                                            │
│  - HTTP로 API Server에 요청                                      │
│                                                                  │
│  저장소: https://github.com/yarang/blogs (mcp_client/)          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ HTTP (API Key 인증)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Block 2: API Server (OCI)                      │
│                                                                  │
│  - 독립 저장소: https://github.com/yarang/blog-api-server       │
│  - FastAPI 기반                                                  │
│  - 모든 Git 작업 담당                                            │
│  - LLM 번역 기능                                                 │
│                                                                  │
│  URL: http://130.162.133.47:8000                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Git Push
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Block 3: GitHub (Blog)                       │
│                                                                  │
│  - 저장소: https://github.com/yarang/blogs                      │
│  - 블로그 콘텐츠 (Hugo)                                          │
│  - GitHub Actions 트리거                                        │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ Actions
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                Block 4: GitHub Actions                           │
│                                                                  │
│  1. hugo --minify (빌드)                                         │
│  2. rsync → OCI 서버 (배포)                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ rsync
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Block 5: Blog (Deployed)                         │
│                                                                  │
│  - Nginx: /var/www/blog                                         │
│  - https://blog.fcoinfup.com                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 저장소 구조

### 블로그 저장소 (blogs/)
```
blogs/
├── hugo.toml              # Hugo 설정
├── content/               # 블로그 콘텐츠
│   ├── ko/post/          # 한국어 포스트
│   └── en/post/          # 영어 포스트
├── themes/stack/         # Hugo 테마
└── .github/workflows/    # GitHub Actions
```

### API 서버 저장소 (blog-api-server/)
```
blog-api-server/
├── main.py               # FastAPI 엔드포인트
├── blog_manager.py       # 블로그 + Git 관리
├── translator.py         # LLM 번역
├── auth.py               # API Key 인증
├── git_handler.py        # Git 작업
├── mcp_client/           # MCP 클라이언트
│   ├── mcp_blog_client.py
│   ├── install.sh
│   └── remote-install.sh
└── requirements.txt      # 의존성
```

## 접속 정보

| 서비스 | URL | 저장소 |
|--------|-----|--------|
| 블로그 | https://blog.fcoinfup.com | yarang/blogs |
| API | http://130.162.133.47:8000 | yarang/blog-api-server |

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
   b. 파일 생성 (content/ko/post/...)
   c. Git commit
   d. Git push → yarang/blogs
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
