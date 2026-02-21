# Blog MCP Client

Claude Code에서 블로그를 관리하기 위한 MCP 클라이언트입니다.

## 설치 (uv 사용)

```bash
cd mcp_client
uv sync
```

## 설정

### 1. Claude Code 설정

프로젝트 루트의 `.mcp.json`에 다음 내용이 있습니다:

```json
{
  "mcpServers": {
    "blog": {
      "command": "uv",
      "args": ["run", "--directory", "mcp_client", "python", "mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "http://130.162.133.47",
        "BLOG_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

### 2. API Key 설정

`~/.claude/settings.json`의 `env` 섹션에 API Key를 추가:

```json
{
  "env": {
    "BLOG_API_URL": "http://130.162.133.47",
    "BLOG_API_KEY": "your_api_key_here"
  },
  "enableAllProjectMcpServers": true
}
```

## 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `blog_create` | 새 포스트 작성 |
| `blog_list` | 포스트 목록 조회 |
| `blog_get` | 특정 포스트 조회 |
| `blog_update` | 포스트 수정 |
| `blog_delete` | 포스트 삭제 |
| `blog_search` | 포스트 검색 |
| `blog_status` | 서버 상태 확인 |

## 사용 예시

Claude Code에서 다음과 같이 사용할 수 있습니다:

```
블로그에 "Python으로 MCP 서버 만들기" 포스트를 작성해줘.
```

## 파일 구조

```
mcp_client/
├── mcp_blog_client.py   # MCP 클라이언트
├── pyproject.toml       # uv 패키지 설정
└── README.md            # 이 파일
```
