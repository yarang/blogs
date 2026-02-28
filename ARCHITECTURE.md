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
BLOG_CACHE_TTL=300  # 캐시 유효 시간 (초), 기본 5분
```

---

## MCP 서버 구현

### CacheManager 클래스

로컬 캐시 관리를 통해 불필요한 API 호출을 최소화합니다.

```python
class CacheManager:
    """로컬 캐시 관리 - 불필요한 API 호출 최소화"""

    def __init__(self, ttl: float = 300.0):
        # ttl: 캐시 유효 시간 (초), 기본 5분

    async def get(self, key: str) -> Optional[Dict]
    async def set(self, key: str, value: Dict) -> None
    async def invalidate(self, pattern: str = None) -> None
    async def clear_read_cache(self) -> None  # 읽기 전용 캐시 삭제
```

### BlogAPIClient 클래스

연결 풀링과 캐싱을 지원하는 HTTP 클라이언트입니다.

```python
class BlogAPIClient:
    """API Server HTTP 클라이언트 (연결 풀링 + 캐싱 지원)"""

    def __init__(self, base_url: str, api_key: str, cache_ttl: float = 300.0)
    async def request(self, method: str, path: str, data: Dict = None,
                     params: Dict = None, use_cache: bool = True,
                     invalidate_cache: bool = False) -> Dict
    async def invalidate_cache(self) -> None
```

### 캐싱 정책

| 작업 | 캐싱 | 설명 |
|------|------|------|
| GET /posts | ✅ | 포스트 목록 캐싱 (TTL 5분) |
| GET /posts/{filename} | ✅ | 포스트 조회 캐싱 |
| GET /search | ✅ | 검색 결과 캐싱 |
| GET /status | ✅ | 상태 조회 캐싱 |
| POST /posts | ❌ | 생성 후 캐시 무효화 |
| PUT /posts/{filename} | ❌ | 수정 후 캐시 무효화 |
| DELETE /posts/{filename} | ❌ | 삭제 후 캐시 무효화 |
| POST /sync | ❌ | 동기화 후 캐시 무효화 |

---

## 시스템 분석 및 문제점

### 🔴 P0 - 심각한 문제

#### 1. 동시성 제어 부족
- **문제**: 전역 `threading.Lock()`만 사용하여 멀티프로세스 환경에서 경쟁 조건 발생 가능
- **위치**: `blog_manager.py:29`, `blog_manager.py:81`, `blog_manager.py:191`
- **영향**: 여러 요청이 동시에 Git 작업을 시도할 때 충돌 가능
- **진행 중**: `asyncio.Lock` 도입으로 개선 중

#### 2. 검색 기능 버그 ✅ 해결됨
- **문제**: `search_posts()`가 `CONTENT_DIR`(한국어)만 검색하여 영어 포스트가 검색되지 않음
- **위치**: `blog_manager.py:393`
- **해결**: 모든 언어 디렉토리를 검색하도록 이미 구현됨
- **테스트**: `test_search.py` 12개 테스트 케이스로 검증 완료

### 🟡 P1 - 확장성 문제

#### 1. 매 요청마다 Git Pull 실행 ⚡ 부분 개선됨
- **문제**: `list_posts()`, `search_posts()`, `get_translation_status()` 등 호출 시마다 `git pull()` 실행
- **위치**: `blog_manager.py:245`, `blog_manager.py:388`, `blog_manager.py:406`
- **영향**: 불필요한 네트워크 호출, 지연 시간 증가 (최대 60초 타임아웃)
- **해결**: MCP 클라이언트에 `CacheManager` 도입으로 API 호출 최적화 (TTL 5분)
- **위치**: `.claude/mcp_server.py:25-71`

#### 2. 파일 기반 검색 (O(n))
- **문제**: 모든 파일을 읽어서 문자열 검색
- **위치**: `blog_manager.py:386-402`
- **영향**: 포스트가 100개 이상이 되면 성능 저하
- **개선**: MCP 클라이언트 캐싱으로 반복 검색 최적화됨
- **장기 계획**: Whoosh 또는 Meilisearch 도입 검토

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

### 단기 (P0-P1) - 완료 및 진행 중

1. **검색 버그 수정** ✅ 완료
   - 모든 언어 디렉토리 검색하도록 구현됨
   - `test_search.py` 12개 테스트 케이스로 검증
   - 우선순위: P0

2. **Git Pull 최적화** ⚡ 부분 완료
   - MCP 클라이언트에 `CacheManager` 도입 (TTL 5분)
   - 쓰기 작업 후 캐시 무효화 구현
   - API 서버 쪽은 여전히 매 호출마다 git pull 실행
   - 우선순위: P1

3. **파일 락 강화** 🔄 진행 중
   - MCP 클라이언트에 `asyncio.Lock` 도입
   - API 서버는 여전히 `threading.Lock` 사용
   - `fcntl.flock()` 또는 Redis 기반 분산 락 도입 필요
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

## 테스트

### API 서버 테스트

| 파일 | 설명 | 위치 |
|------|------|------|
| `test_search.py` | 다국어 검색 기능 테스트 | `/blog-api-server/test_search.py` |
| `test_zai_api.py` | ZAI API 연결 테스트 | `/blog-api-server/test_zai_api.py` |

### MCP 클라이언트 테스트

| 파일 | 설명 | 위치 |
|------|------|------|
| `test_mcp_tools.py` | MCP 도구 테스트 | `/.claude/tests/test_mcp_tools.py` |
| `test_client.py` | BlogAPIClient 테스트 | `/.claude/tests/test_client.py` |
| `test_integration.py` | 통합 테스트 | `/.claude/tests/test_integration.py` |

### 테스트 커버리지

- ✅ 다국어 검색 (ko, en)
- ✅ Relevance 정렬
- ✅ 대소문자 무시 검색
- ✅ 결과 구조 검증
- ✅ 캐싱 동작
- ✅ 연결 풀링
- ✅ 에러 핸들링

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
