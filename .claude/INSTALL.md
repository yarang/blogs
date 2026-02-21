# Claude Code CLI용 MCP 서버 설치 가이드

## 설치

### 1. 의존성 설치

```bash
cd /Users/yarang/workspaces/agent_dev/blogs/.claude
pip install -r requirements.txt
```

### 2. MCP 설정 파일 확인

프로젝트 루트에 `.mcp.json` 파일이 있어야 합니다:

```json
{
  "mcpServers": {
    "blog": {
      "command": "python3",
      "args": [".claude/mcp_server.py"],
      "env": {
        "BLOG_ROOT": "/Users/yarang/workspaces/agent_dev/blogs"
      }
    }
  }
}
```

### 3. MCP 서버 승인

처음 실행 시 MCP 서버 승인 메시지가 표시됩니다. 승인하세요.

## 사용법

### CLI에서 바로 사용

```bash
# Claude Code CLI 실행
cd /Users/yarang/workspaces/agent_dev/blogs
claude

# 또는 직접 요청
claude "블로그 포스트 목록 보여줘"
```

### 사용 예시

```
# 포스트 작성
"Python 가상환경 설정법에 대한 블로그 포스트 작성해줘"

# 포스트 검색
"Docker 관련 포스트 검색해줘"

# Git 상태
"블로그 Git 상태 확인해줘"

# 원격 동기화
"블로그 원격에서 최신 내용 가져와줘"
```

## 제공 도구

| 도구 | 설명 |
|------|------|
| `blog_create_post` | 포스트 생성 + Git 커밋/푸시 |
| `blog_list_posts` | 포스트 목록 조회 |
| `blog_get_post` | 특정 포스트 조회 |
| `blog_delete_post` | 포스트 삭제 |
| `blog_search_posts` | 포스트 검색 |
| `blog_git_status` | Git 상태 확인 |
| `blog_git_sync` | 원격 동기화 |

## 워크플로우

```
1. claude "포스트 작성해줘"
2. MCP 서버가 파일 생성
3. 자동으로 git commit / push
4. GitHub Actions 트리거
5. 블로그 자동 배포 (1-2분)
```

## 다른 프로젝트에서 사용

```bash
# 다른 디렉토리에서
cd /path/to/other-project

# 블로그 MCP 사용
claude "블로그에 새 포스트 작성해줘: ..."
```

> 참고: 다른 프로젝트에서도 `.mcp.json`에 블로그 MCP 설정이 있어야 합니다.

## 문제 해결

### MCP 서버가 로드되지 않을 때

```bash
# MCP 서버 직접 테스트
cd /Users/yarang/workspaces/agent_dev/blogs/.claude
python3 mcp_server.py

# 의존성 확인
pip show mcp
```

### Git 권한 문제

```bash
# Git credential 설정
git config --global credential.helper store
```

### 경로 문제

`.mcp.json`의 경로가 프로젝트 루트에서 상대 경로인지 확인:
- ✅ `.claude/mcp_server.py`
- ❌ `/Users/.../mcp_server.py` (다른 프로젝트에서 문제)

## 파일 구조

```
blogs/
├── .mcp.json              # MCP 서버 설정 (Claude Code CLI용)
├── .claude/
│   ├── mcp_server.py      # MCP 서버
│   ├── requirements.txt   # 의존성
│   └── INSTALL.md         # 이 파일
└── content/posts/         # 블로그 포스트
```
