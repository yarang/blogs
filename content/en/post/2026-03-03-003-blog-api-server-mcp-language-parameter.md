+++
title = "[blog-api-server] MCP Blog Client Language Parameter"
slug = "2026-03-03-003-blog-api-server-mcp-language-parameter"
date = 2026-03-03T23:19:28+09:00
draft = false
tags = ["blog-api-server", "mcp", "multilingual", "i18n"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [blog-api-server] MCP Blog Client Language Parameter

## Overview

Added a language parameter to the MCP (Model Context Protocol) blog client for improved Korean/English multilingual blog management.

## Changes

### blog_create Tool Update

```python
Tool(
    name="blog_create",
    description="Create a blog post. Provide title and content (Markdown), and the post will be created and committed/pushed to Git.",
    inputSchema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Post title"},
            "content": {"type": "string", "description": "Post content (Markdown)"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag list"},
            "categories": {"type": "array", "items": {"type": "string"}, "description": "Category list"},
            "draft": {"type": "boolean", "description": "Draft status (default: false)"},
            "language": {"type": "string", "description": "Language (ko, en). Default: ko"}  # New
        },
        "required": ["title", "content"]
    }
)
```

### API Call Logic

```python
if name == "blog_create":
    result = await client.request("POST", "/posts", data={
        "title": arguments["title"],
        "content": arguments["content"],
        "tags": arguments.get("tags", []),
        "categories": arguments.get("categories", ["Development"]),
        "draft": arguments.get("draft", False),
        "language": arguments.get("language", "ko"),  # Default: Korean
        "auto_push": True
    })
```

## Usage

### Using in Claude Code

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

### Creating Korean Posts

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

### Creating English Posts

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

## API Examples

### Request Format

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

### Response Format

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

## File Path Rules

| Language | language Value | Storage Path |
|----------|----------------|--------------|
| Korean | `ko` | `content/ko/post/` |
| English | `en` | `content/en/post/` |

## Future Plans

1. **Translation Automation**: Auto-translation feature using language parameter
2. **i18n Links**: Automatic link generation between KO/EN posts
3. **Extended Language Support**: Japanese, Chinese, and more

## Conclusion

The language parameter addition to the MCP blog client enables more convenient multilingual blog management directly from Claude Code.
