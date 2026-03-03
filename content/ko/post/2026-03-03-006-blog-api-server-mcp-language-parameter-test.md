+++
title = "[blog-api-server] MCP Language Parameter Test"
date = 2026-03-03T22:42:58+09:00
draft = false
tags = ["test", "mcp", "language"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

## Overview

This is a test post to verify the language parameter functionality in the MCP blog client.

## Changes Made

1. Added `language` parameter to `blog_create` tool
2. Supports `ko` (Korean) and `en` (English)
3. Posts are saved to correct language directory:
   - Korean: `content/ko/post/`
   - English: `content/en/post/`

## Test Results

| Language | Path | Status |
|----------|------|--------|
| ko | `content/ko/post/` | Working |
| en | `content/en/post/` | Working |

## Code Example

```python
# MCP client call with language parameter
{
    "title": "Post Title",
    "content": "Post content in Markdown",
    "language": "en"  # or "ko"
}
```

## Next Steps

- Auto-detect language from content
- Support for more languages (ja, zh, etc.)