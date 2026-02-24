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

---

## 시스템 분석 및 문제점

### 🔴 P0 - 심각한 문제

#### 1. 동시성 제어 부족
- **문제**: 전역 `threading.Lock()`만 사용하여 멀티프로세스 환경에서 경쟁 조건 발생 가능
- **위치**: `blog_manager.py:29`, `blog_manager.py:81`, `blog_manager.py:191`
- **영향**: 여러 요청이 동시에 Git 작업을 시도할 때 충돌 가능

#### 2. 검색 기능 버그
- **문제**: `search_posts()`가 `CONTENT_DIR`(한국어)만 검색하여 영어 포스트가 검색되지 않음
- **위치**: `blog_manager.py:393`
- **해결**: 모든 언어 디렉토리를 검색하도록 수정 필요

### 🟡 P1 - 확장성 문제

#### 1. 매 요청마다 Git Pull 실행
- **문제**: `list_posts()`, `search_posts()`, `get_translation_status()` 등 호출 시마다 `git pull()` 실행
- **위치**: `blog_manager.py:245`, `blog_manager.py:388`, `blog_manager.py:406`
- **영향**: 불필요한 네트워크 호출, 지연 시간 증가 (최대 60초 타임아웃)

#### 2. 파일 기반 검색 (O(n))
- **문제**: 모든 파일을 읽어서 문자열 검색
- **위치**: `blog_manager.py:386-402`
- **영향**: 포스트가 100개 이상이 되면 성능 저하

#### 3. 전역 인스턴스 의존
- **문제**: `blog_manager`, `git_handler`, `translator`가 모듈 레벨 전역 인스턴스
- **영향**: 테스트 어려움, 의존성 주입 불가

### 🟢 P2 - 유지보수성 문제

#### 1. 중복된 Git 코드
- **문제**: `GitManager` (blog_manager.py)와 `GitHandler` (git_handler.py) 두 개가 존재
- **영향**: 기능 수정 시 두 곳 모두 수정 필요

#### 2. 언어 감지 로직 불안정
- **문제**: `f.parent.parent.name`으로 언어 감지
- **위치**: `blog_manager.py:271`, `blog_manager.py:306`
- **취약점**: 디렉토리 구조가 변경되면 동작하지 않음

#### 3. 광범위한 예외 처리
- **문제**: `except:` 구문 사용
- **위치**: `blog_manager.py:278`, `blog_manager.py:377`
- **영향**: 디버깅 어려움

---

## 개선 로드맵

### 단기 (P0-P1) - 즉시 개선

1. **검색 버그 수정**
   - 모든 언어 디렉토리 검색하도록 수정
   - 우선순위: P0

2. **Git Pull 최적화**
   - 주기적 백그라운드 sync 또는 캐싱 도입
   - 마지막 sync 시간 추적하여 일정 시간 내면 skip
   - 우선순위: P1

3. **파일 락 강화**
   - `fcntl.flock()` 또는 Redis 기반 분산 락 도입
   - 우선순위: P1

### 중기 (P2) - 구조 개선

1. **Git 클래스 통합**
   - `GitManager`와 `GitHandler` 통합
   - 단일 책임 원칙 적용

2. **의존성 주입**
   - FastAPI Depends 활용
   - 테스트 가능성 향상

3. **인덱스 기반 검색**
   - Whoosh 또는 Meilisearch 도입
   - 검색 성능 개선

### 장기 (P3) - 아키텍처 재설계

1. **Git 중간 계층 제거**
   - GitHub API 직접 사용
   - 로컬 Git 저장소 클론 불필요

2. **이벤트 기반 아키텍처**
   - Webhook 기반 자동 배포
   - GitHub Actions 트리거 최적화

3. **마이크로서비스 분리**
   - API 서버와 번역 서버 분리
   - 독립적 확장 가능

---

## 아키텍처 다이어그램 (개선안)

### 현재 구조
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Claude Code │────▶│  MCP Client │────▶│  API Server │
└─────────────┘     └─────────────┘     │             │
                                          │  Git Clone  │
                                          │  Local Repo │
┌─────────────┐     ┌─────────────┐      │             │
│   GitHub    │◀────│    Git      │◀─────┤             │
│  Actions    │────▶│   Push     │      └─────────────┘
└─────────────┘     └─────────────┘             │
                                                 │
                                                 ▼
                                          ┌─────────────┐
                                          │  Hugo Build │
                                          └─────────────┘
```

### 개선안 (장기)
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Claude Code │────▶│  MCP Client │────▶│  API Server │
└─────────────┘     └─────────────┘     └─────────────┘
                                                 │
                                                 │ GitHub API
                                                 ▼
                                          ┌─────────────┐     ┌─────────────┐
                                          │   GitHub    │────▶│  Hugo Build │
                                          │   Repo      │     │  (Actions)  │
                                          └─────────────┘     └─────────────┘
```
