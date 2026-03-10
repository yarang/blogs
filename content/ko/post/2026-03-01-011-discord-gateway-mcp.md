+++
title = "Discord Gateway MCP"
date = 2026-03-01T01:06:24+09:00
draft = false
tags = ["discord", "mcp"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

---
title: Discord Gateway MCP 아키텍처
date: 2026-03-01
---

# Discord Gateway MCP 아키텍처

Claude Code 팀의 Discord 통합 서비스 설계.

## 아키텍처

| 계층 | 구성요소 |
|------|----------|
| Discord | Bot, Channel |
| Gateway | WebSocket, REST |
| MCP | gcp, oci, db |

## Redis 제거

In-Memory로 단일 인스턴스 충분.

## MCP 선택

1. /커맨드
2. @멘션
3. 키워드
4. 채널별

## 도구 8개

- send_message
- get_messages
- wait_for_message
- create_thread
- list_threads
- archive_thread
- acquire_thread
- release_thread

## 실행

```bash
uvicorn gateway.main:app --port 8081
```

---

**영어 버전:** [English Version](/post/2026-03-01-011-discord-gateway-mcp/)
