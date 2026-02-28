+++
title = "Discord Gateway MCP Architecture Design Decisions"
slug = "discord-gateway-mcp-architecture-decisions"
date = 2026-02-28T22:26:51+09:00
draft = false
tags = ["discord", "mcp", "fastapi", "claude-code", "architecture"]
categories = ["Development", "Architecture", "Claude Code"]
ShowToc = true
TocOpen = true
+++

# Discord Gateway MCP Architecture Design Decisions

## Overview

The Claude Code team designed a Discord Gateway Service for user communication via Discord. This article summarizes the key architecture decisions.

---

## 1. Lightweight Architecture Without Redis

### Decision

**Removed Redis and adopted in-memory approach**

### Rationale

- Redis is over-engineering for single-instance environments
- Thread Lock is sufficient with memory-based approach
- SSE handles streaming directly through FastAPI

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     Gateway Service                          │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │  Discord Bot    │    │  Thread Lock    │                │
│  │  (WebSocket)    │    │  (In-Memory)    │                │
│  └────────┬────────┘    └─────────────────┘                │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │   FastAPI SSE   │◄───│   MCP Server    │                │
│  │ (Direct Stream) │    │   (stdio)       │                │
│  └─────────────────┘    └─────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. MCP Tool Configuration

### Decision

**Provide 3 core tools**

| Tool | Description |
|------|-------------|
| `send_message` | Send message to Discord channel |
| `read_messages` | Read channel messages |
| `get_status` | Check gateway status |

### Alternatives Considered

| Alternative | Pros | Cons | Adopted |
|-------------|------|------|---------|
| Redis Pub/Sub | Scalability | Increased complexity | ❌ |
| SQLite | Persistence | File I/O | ❌ |
| In-Memory | Simplicity | Single instance only | ✅ |

---

## 3. Simple Structure Without Authentication

### Decision

**Skip authentication for development/team environments**

### Rationale

- Only runs in local/team network
- MCP is already a local process
- Minimize complexity

### Future Expansion

```
Phase 1: No authentication (current)
    ↓
Phase 2: API Key authentication (optional)
    ↓
Phase 3: OAuth 2.0 (if needed)
```

---

## 4. FastAPI + SSE Selection

### Decision

**Implement real-time communication with SSE (Server-Sent Events)**

### Comparison

| Technology | Pros | Cons |
|------------|------|------|
| WebSocket | Bidirectional | Complex state management |
| **SSE** | Unidirectional, simple | Server → Client only |
| Polling | Easy implementation | Latency |

### Selection Rationale

- Discord → MCP is unidirectional and sufficient
- FastAPI native support
- Simple reconnection logic

---

## 5. Directory Structure

```
discord-gateway/
├── gateway/
│   ├── main.py           # FastAPI app
│   ├── discord_bot.py    # Discord Bot
│   ├── mcp_server.py     # MCP Server
│   ├── models.py         # Pydantic models
│   └── config.py         # Configuration
├── tests/
├── pyproject.toml
└── README.md
```

---

## 6. How to Run

### Local Execution

```bash
# Start Gateway Service
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# Health check
curl http://localhost:8081/health
```

### MCP Configuration

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "discord-gateway": {
      "command": "python3",
      "args": ["/path/to/discord_mcp/server.py"],
      "env": {
        "GATEWAY_URL": "http://localhost:8081"
      }
    }
  }
}
```

---

## 7. Future Plans

### Phase 2 (Planned)

- [ ] Slash command implementation
- [ ] Channel-specific MCP settings
- [ ] Routing configuration file

### Phase 3 (Optional)

- [ ] API authentication (API Key)
- [ ] Rate Limiting
- [ ] Message persistence (SQLite)

---

## Conclusion

We chose a strategy of starting with a lightweight architecture and expanding when needed. For single instances, it works sufficiently without Redis, and we plan to introduce Redis when multiple instances are needed in the future.
