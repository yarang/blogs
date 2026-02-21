# Blog MCP Server

Claude가 블로그 포스트를 관리할 수 있는 MCP (Model Context Protocol) 서버입니다.

## 설치

```bash
cd /Users/yarang/workspaces/agent_dev/blogs/.claude
pip install -r requirements.txt
```

## Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json`에 다음 내용을 추가:

```json
{
  "mcpServers": {
    "blog-manager": {
      "command": "python3",
      "args": ["/Users/yarang/workspaces/agent_dev/blogs/.claude/mcp_server.py"],
      "env": {}
    }
  }
}
```

## 제공 도구

### blog_create_post

새 블로그 포스트를 생성합니다.

```
매개변수:
- title (필수): 포스트 제목
- content (필수): 포스트 내용 (Markdown)
- tags (선택): 태그 목록
- categories (선택): 카테고리 목록
- draft (선택): 초안 여부 (기본값: false)
```

### blog_list_posts

블로그 포스트 목록을 조회합니다.

```
매개변수:
- limit: 조회할 포스트 수 (기본값: 20)
- offset: 시작 위치 (기본값: 0)
```

### blog_get_post

특정 포스트의 내용을 조회합니다.

```
매개변수:
- filename (필수): 포스트 파일명
```

### blog_update_post

기존 포스트를 수정합니다.

```
매개변수:
- filename (필수): 수정할 포스트 파일명
- title: 새 제목
- content: 새 내용
- tags: 새 태그 목록
- draft: 초안 상태 변경
```

### blog_delete_post

포스트를 삭제합니다.

```
매개변수:
- filename (필수): 삭제할 포스트 파일명
```

### blog_search_posts

포스트 내용으로 검색합니다.

```
매개변수:
- query (필수): 검색어
```

## 사용 예시

Claude에게 다음과 같이 요청할 수 있습니다:

- "새로운 블로그 포스트를 작성해줘. 제목은 'Python Tips'이고 내용은..."
- "최근 블로그 포스트 목록을 보여줘"
- "'Docker' 관련 포스트를 검색해줘"
- "특정 포스트를 수정해줘"

## 파일 명명 규칙

포스트 파일명은 다음 형식으로 자동 생성됩니다:
```
YYYY-MM-DD-NNN-slug.md
```

예: `2026-02-21-004-python-tips.md`
