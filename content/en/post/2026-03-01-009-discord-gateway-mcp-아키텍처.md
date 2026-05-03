+++
title = ""
date = "2026-03-01T00:56:27+09:00"
draft = "false"
tags = ["discord", "mcp", "fastapi"]
categories = ["Development", "Architecture"]
ShowToc = "true"
TocOpen = "true"
+++

---
title: Discord Gateway MCP Architecture
date: 2026-03-01
categories: ["Development", "Architecture"]
---

# Discord Gateway MCP Architecture

The Claude Code team designed the Discord Gateway Service for user communication via Discord.

## 1. Overall Structure

| Layer | Component | Role |
|------|----------|------|
| Discord | Bot, Channel, Thread | User Interface |
| Gateway | WebSocket, REST API, SSE | Message Routing |
| MCP | gcp-mcp, oci-mcp, db-mcp | Tool Execution |

## 2. Message Flow

```mermaid
flowchart LR
    User[User] --> WS[WebSocket]
    WS --> API[REST API]
    API --> GCP[gcp-mcp]
    API --> OCI[oci-mcp]
    GCP --> SSE[SSE]
    SSE --> User
```

## 3. Redis Removal: Using In-Memory

| Item | Redis | In-Memory |
|------|-------|-----------|
| Thread Lock | SET NX | dict |
| Events | Streams | SSE |
| Cache | Cache | Memory |

**In-Memory is sufficient for a single instance**

## 4. MCP Selection: 4 Steps

| Rank | Method | Example |
|:----:|------|------|
| 1 | /command | /gcp status |
| 2 | @mention | @gcp-monitor |
| 3 | Keyword | gcp server |
| 4 | Channel | #gcp-monitoring |

## 5. Thread Lock

- The first responding MCP acquires the lock
- Held for 5 minutes by default
- Automatically released on timeout

## 6. 8 MCP Tools

| Tool | Description |
|------|------|
| discord_send_message | Send message |
| discord_get_messages | Get messages |
| discord_wait_for_message | Wait for message |
| discord_create_thread | Create thread |
| discord_list_threads | List threads |
| discord_archive_thread | Archive thread |
| discord_acquire_thread | Acquire thread lock |
| discord_release_thread | Release thread lock |

## 7. Execution

```bash
uvicorn gateway.main:app --port 8081
curl http://localhost:8081/health
```

## 8. Roadmap

- Phase 1: Complete: Gateway, Lock, SSE, MCP
- Phase 2: In Progress: Slash commands, Keywords
- Phase 3: Optional: Authentication, Rate Limit

---

**Conclusion**: Start with a lightweight architecture, expand when necessary

---

**English Version:** [English Version](/post/2026-03-01-009-discord-gateway-mcp-architecture/)