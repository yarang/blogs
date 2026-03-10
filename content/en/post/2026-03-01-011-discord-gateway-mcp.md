---
title: "Discord Gateway MCP"
date: 2026-03-01T01:06:24+09:00
draft: false
tags: ["discord", "mcp", "fastapi"]
categories: ["Development", "Architecture"]
showToc: true
tocOpen: true
---

# Discord Gateway MCP

Claude Code team's Discord integration service design.

## Architecture

| Layer | Components |
|-------|------------|
| Discord | Bot, Channel |
| Gateway | WebSocket, REST |
| MCP | gcp, oci, db |

## Redis Removal

In-Memory is sufficient for single instance.

## MCP Selection

1. /command
2. @mention
3. Keyword
4. Per-channel

## 8 Tools

- send_message
- get_messages
- wait_for_message
- create_thread
- list_threads
- archive_thread
- acquire_thread
- release_thread

## Execution

```bash
uvicorn gateway.main:app --port 8081
```

---

**Korean Version:** [한국어 버전](/ko/post/2026-03-01-011-discord-gateway-mcp/)
