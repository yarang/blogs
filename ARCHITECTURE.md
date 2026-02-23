# Blog System Architecture

## 저장소 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    yarang/blogs                              │
│                                                              │
│  목적: Hugo 블로그 콘텐츠 (순수 정적 사이트)                  │
│                                                              │
│  구조:                                                       │
│  ├── hugo.toml              # Hugo 설정                      │
│  ├── content/               # 블로그 콘텐츠                   │
│  │   ├── ko/post/          # 한국어 포스트                   │
│  │   └── en/post/          # 영어 포스트                     │
│  ├── themes/stack/         # Hugo 테마                       │
│  └── .github/workflows/    # GitHub Actions (배포)           │
│                                                              │
│  URL: https://blog.fcoinfup.com                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 yarang/blog-api-server                       │
│                                                              │
│  목적: API 서버 + MCP 클라이언트 (백엔드 서비스)              │
│                                                              │
│  구조:                                                       │
│  ├── main.py               # FastAPI 엔드포인트              │
│  ├── blog_manager.py       # 블로그 + Git 관리               │
│  ├── translator.py         # LLM 번역                        │
│  ├── auth.py               # API Key 인증                    │
│  ├── git_handler.py        # Git 작업                        │
│  ├── mcp_client/           # MCP 클라이언트                  │
│  │   ├── mcp_blog_client.py                                  │
│  │   ├── install.sh                                          │
│  │   └── remote-install.sh                                   │
│  └── requirements.txt                                        │
│                                                              │
│  URL: http://130.162.133.47:8000                             │
└─────────────────────────────────────────────────────────────┘
```

## 데이터 흐름

```
Claude Code (MCP Client)
        │
        │ HTTP POST /posts
        ▼
API Server (blog-api-server)
        │
        │ Git clone/pull yarang/blogs
        │ Git commit/push yarang/blogs
        ▼
GitHub (yarang/blogs)
        │
        │ GitHub Actions 트리거
        ▼
Hugo Build + Deploy
        │
        ▼
Blog (blog.fcoinfup.com)
```

## 설치 및 사용

### MCP 클라이언트 설치

```bash
# 방법 1: 저장소 클론
git clone https://github.com/yarang/blog-api-server.git
cd blog-api-server/mcp_client
./install.sh

# 방법 2: 원격 설치
curl -fsSL https://raw.githubusercontent.com/yarang/blog-api-server/main/mcp_client/remote-install.sh | bash
```

### .mcp.json 설정

```json
{
  "mcpServers": {
    "blog": {
      "command": "/path/to/blog-api-server/mcp_client/.venv/bin/python",
      "args": ["/path/to/blog-api-server/mcp_client/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "http://130.162.133.47",
        "BLOG_API_KEY": "your_api_key"
      }
    }
  }
}
```

## API 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /health` | 서버 상태 |
| `GET /posts` | 포스트 목록 |
| `POST /posts` | 포스트 생성 |
| `GET /posts/{filename}` | 포스트 조회 |
| `PUT /posts/{filename}` | 포스트 수정 |
| `DELETE /posts/{filename}` | 포스트 삭제 |
| `POST /translate` | LLM 번역 |

## 환경 변수

### API 서버 (.env)
```
BLOG_API_KEYS=blog_xxx,blog_yyy
BLOG_REPO_URL=https://github.com/yarang/blogs.git
BLOG_REPO_PATH=/var/www/blog-repo
ANTHROPIC_API_KEY=sk-ant-xxx
```

### MCP 클라이언트
```
BLOG_API_URL=http://130.162.133.47
BLOG_API_KEY=blog_xxx
```
