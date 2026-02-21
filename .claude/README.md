# Blog MCP Server (통합 버전)

API 서버 없이 직접 Git과 파일 시스템에 접근하는 MCP 서버입니다.

## 아키텍처

```
┌─────────────────┐
│  Claude Code    │
│  (같은 머신)     │
└────────┬────────┘
         │ MCP
         ▼
┌─────────────────┐      ┌─────────────────┐
│  MCP Server     │ ───► │  Git / Files    │
│  (Python)       │      │  (Local)        │
└─────────────────┘      └────────┬────────┘
                                  │ push
                                  ▼
                         ┌─────────────────┐
                         │    GitHub       │
                         │   → Actions     │
                         │   → Deploy      │
                         └─────────────────┘
```

## 설치

```bash
cd /path/to/blogs/.claude
pip install -r requirements.txt
```

## Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blog-manager": {
      "command": "python3",
      "args": ["/path/to/blogs/.claude/mcp_server.py"],
      "env": {
        "BLOG_ROOT": "/path/to/blogs"
      }
    }
  }
}
```

## 사용법

### 포스트 작성

```
"Python 리스트 컴프리헨션에 대한 블로그 포스트 작성해줘"
```

### 초안 정리

```
"이 노트를 블로그 포스트로 정리해줘:
- 회의 내용
- 결정사항
- 액션 아이템"
```

### 검색

```
"Docker 관련 포스트 검색해줘"
```

## 제공 도구

| 도구 | 설명 |
|------|------|
| `blog_create_post` | 포스트 생성 + Git 커밋/푸시 |
| `blog_list_posts` | 포스트 목록 |
| `blog_get_post` | 포스트 조회 |
| `blog_delete_post` | 포스트 삭제 |
| `blog_search_posts` | 포스트 검색 |
| `blog_git_status` | Git 상태 |
| `blog_git_sync` | 원격 동기화 |

## 워크플로우

```
1. Claude Code에서 요청
2. MCP 서버가 파일 생성
3. 자동으로 git commit / push
4. GitHub Actions 트리거
5. 블로그 자동 배포
```

## 제한사항

- **같은 머신에서만 작동**
- 블로그 저장소가 로컬에 있어야 함
- Git credential이 설정되어 있어야 함
