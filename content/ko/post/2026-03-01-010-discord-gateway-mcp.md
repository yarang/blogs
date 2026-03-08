+++
title = "Discord Gateway MCP"
date = 2026-03-01T01:03:34+09:00
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

Claude Code 팀에서 Discord Gateway Service를 설계했다.

## 구조

| 계층 | 구성요소 | 역할 |
|------|----------|------|
| Discord | Bot, Channel | 사용자 인터페이스 |
| Gateway | WebSocket, REST, 메시지 라우팅 |
| MCP | gcp, oci, db | 도구 실행 |

## Redis 제거

| 항목 | Redis | In-Memory |
|------|-------|-----------|
| Lock | SET NX | dict |
| 이벤트 | Streams | SSE |

**단일 인스턴스는 In-Memory 충분**

## MCP 선택: 4단계

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

## 로드맵

- Phase 1: 완료
- Phase 2: 슬래시 커맨드
- Phase 3: 인증
