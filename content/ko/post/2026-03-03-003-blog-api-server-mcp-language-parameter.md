+++
title = "[blog-api-server] MCP 블로그 클라이언트 언어 파라미터 추가"
slug = "2026-03-03-003-blog-api-server-mcp-language-parameter"
date = 2026-03-03T23:19:28+09:00
draft = false
tags = ["blog-api-server", "mcp", "multilingual", "i18n"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [blog-api-server] MCP 블로그 클라이언트 언어 파라미터 추가

## 개요

MCP (Model Context Protocol) 블로그 클라이언트에 언어 파라미터를 추가하여 한국어/영어 다국어 블로그 관리를 개선했습니다.

## 변경 사항

### blog_create 도구 업�데이트

```python
Tool(
    name="blog_create",
    description="블로그 포스트 생성. 제목과 내용(Markdown)을 입력하면 포스트가 생성되고 Git에 커밋/푸시됩니다.",
    inputSchema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "포스트 제목"},
            "content": {"type": "string", "description": "포스트 내용 (Markdown)"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "태그 목록"},
            "categories": {"type": "array", "items": {"type": "string"}, "description": "카테고리 목록"},
            "draft": {"type": "boolean", "description": "초안 여부 (기본값: false)"},
            "language": {"type": "string", "description": "언어 (ko, en). 기본값: ko"}  # 신규
        },
        "required": ["title", "content"]
    }
)
```

### API 호출 로직

```python
if name == "blog_create":
    result = await client.request("POST", "/posts", data={
        "title": arguments["title"],
        "content": arguments["content"],
        "tags": arguments.get("tags", []),
        "categories": arguments.get("categories", ["Development"]),
        "draft": arguments.get("draft", False),
        "language": arguments.get("language", "ko"),  # 기본값: 한국어
        "auto_push": True
    })
```

## 사용 방법

### Claude Code에서 사용

```json
{
  "mcpServers": {
    "blog": {
      "command": "python3",
      "args": ["/path/to/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "https://blog.fcoinfup.com",
        "BLOG_API_KEY": "your_api_key"
      }
    }
  }
}
```

### 한국어 포스트 작성

```json
{
  "tool": "blog_create",
  "arguments": {
    "title": "[프로젝트명] 포스트 제목",
    "content": "# 내용\n\n마크다운 형식의 내용...",
    "tags": ["tag1", "tag2"],
    "categories": ["Development"],
    "language": "ko"
  }
}
```

### 영어 포스트 작성

```json
{
  "tool": "blog_create",
  "arguments": {
    "title": "[Project Name] Post Title",
    "content": "# Content\n\nMarkdown formatted content...",
    "tags": ["tag1", "tag2"],
    "categories": ["Development"],
    "language": "en"
  }
}
```

## API 예시

### 요청 형식

```bash
curl -X POST https://blog.fcoinfup.com/api/posts \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[blog-api-server] Test Post",
    "content": "# Test\n\nThis is a test post.",
    "tags": ["test"],
    "categories": ["Development"],
    "language": "en",
    "auto_push": true
  }'
```

### 응답 형식

```json
{
  "success": true,
  "filename": "2026-03-03-001-blog-api-server-test-post.md",
  "path": "/content/en/post/2026-03-03-001-blog-api-server-test-post.md",
  "git": {
    "success": true,
    "commit": "abc123...",
    "branch": "main"
  }
}
```

## 파일 경로 규칙

| 언어 | language 값 | 저장 경로 |
|------|------------|----------|
| 한국어 | `ko` | `content/ko/post/` |
| 영어 | `en` | `content/en/post/` |

## 향후 계획

1. **번역 자동화**: 언어 파라미터를 활용한 자동 번역 기능
2. **i18n 링크**: KO/EN 포스트 간 자동 연결 생성
3. **다국어 지원 확장**: 일본어, 중국어 등 추가 언어 지원

## 결론

MCP 블로그 클라이언트에 언어 파라미터를 추가하여 Claude Code에서 더 편리하게 다국어 블로그를 관리할 수 있게 되었습니다.

---

**영어 버전:** [English Version](/post/2026-03-03-003-blog-api-server-mcp-language-parameter/)
