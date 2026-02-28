+++
title = "Discord Gateway MCP Architecture Design"
slug = "discord-gateway-mcp-architecture-design"
date = 2026-03-01T01:13:00+09:00
draft = false
tags = ["discord", "mcp", "fastapi", "claude-code", "user-comm"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

# Discord Gateway MCP Architecture Design

The Claude Code team designed a Discord Gateway Service for user communication via Discord. This article summarizes the key architecture decisions and user_comm Agent design.

---

## 1. Overall Architecture

### Components

| Layer | Component | Role |
|-------|-----------|------|
| **Discord** | Bot, Channel, Thread | User interface |
| **Gateway** | WebSocket, REST API, SSE | Message routing |
| **MCP** | gcp-mcp, oci-mcp, db-mcp | Tool execution |
| **user_comm** | Discord Agent | User communication |

### Message Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  Discord → Gateway Service :8081 → Claude Code Team → SSE → User  │
└─────────────────────────────────────────────────────────────────────┘

Components:
- Discord Bot (WebSocket)
- Gateway Service (REST API + SSE)
- MCP Servers (gcp-mcp, oci-mcp, db-mcp)
- user_comm Agent
```

---

## 2. user_comm Agent (User Communication Handler)

### Role and Responsibilities

The user_comm Agent is a member of the Claude Code team, communicating with users through Discord channels and collaborating with other agents.

| Function | Description |
|----------|-------------|
| **Input Reception** | Receive Discord messages and route to appropriate agent |
| **Opinion Request** | Query user opinions at other agents' requests |
| **Notification/Report** | Send system status, warnings, reports |
| **Team Communication** | Exchange messages with other agents |

### Internal Structure

```
user_comm Agent
├── Discord Bot (discord.py)
├── UserCommAgent (main logic)
└── TeamCommunicator (agent communication)
```

### Message Types

```python
class MessageType(Enum):
    TASK_REQUEST = "task_request"       # Task request
    NOTIFICATION = "notification"        # Notification
    OPINION_REQUEST = "opinion_request"  # Opinion request
    OPINION_RESPONSE = "opinion_response" # Opinion response
    STATUS_REPORT = "status_report"      # Status report
    ERROR = "error"                      # Error
```

---

## 3. Lightweight Architecture Without Redis

### Why Remove Redis?

| Item | With Redis | With In-Memory |
|------|-----------|----------------|
| Thread Lock | Redis SET NX | Python dict |
| Event Distribution | Redis Streams | Direct SSE |
| State Storage | Redis Cache | Memory cache |

**Conclusion**: In-memory is sufficient for single-instance environments

### Gateway Structure

```
Gateway Service
├── Discord Bot (WebSocket)
├── Thread Lock (In-Memory)
├── Message Cache (1000 limit)
└── SSE Manager
```

---

## 4. MCP Selection: 4-Stage Hybrid

### Selection Priority

| Rank | Method | Example | Description |
|:----:|--------|---------|-------------|
| 1️⃣ | Slash Command | `/gcp status` | Most explicit |
| 2️⃣ | @Mention | `@gcp-monitor status` | Natural conversation |
| 3️⃣ | Keyword Detection | `gcp server status` | Auto keyword recognition |
| 4️⃣ | Channel Assignment | #gcp-monitoring | Channel default MCP |

### Fallback Order

```
1. Slash command? → Route to MCP
2. @Mention? → Route to MCP
3. Keyword? → Route to MCP
4. Channel default? → Route to MCP
5. None → Broadcast (deliver to all MCPs)
```

### Slash Command List

| Command | MCP | Description |
|---------|-----|-------------|
| `/gcp status [server]` | gcp-mcp | GCP server status |
| `/gcp list` | gcp-mcp | GCP instance list |
| `/oci status [server]` | oci-mcp | OCI server status |
| `/oci list` | oci-mcp | OCI instance list |
| `/db query <sql>` | db-mcp | Execute DB query |
| `/db list` | db-mcp | DB list |
| `/alert check` | alert-mcp | Check alerts |

---

## 5. Thread Lock Rules

### Lock Behavior

```
1. First MCP to respond to thread acquires lock
2. Default duration: 5 minutes (300 seconds)
3. Auto-extend on activity
4. Auto-release on timeout
```

### Lock API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/threads/{id}/acquire` | Acquire lock |
| `POST` | `/api/threads/{id}/release` | Release lock |
| `GET` | `/api/threads/{id}/lock` | Check lock status |

### Request/Response Example

**Lock Acquire Request**
```bash
POST /api/threads/123456/acquire
{
  "agent_name": "gcp-mcp",
  "timeout": 300
}
```

**Lock Acquire Response**
```json
{
  "acquired": true,
  "thread_id": "123456",
  "agent": "gcp-mcp"
}
```

---

## 6. MCP Tools (8)

### Tool List

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `discord_send_message` | Send message | channel_id, content |
| `discord_get_messages` | Get messages | channel_id, limit |
| `discord_wait_for_message` | Wait for message | channel_id, timeout |
| `discord_create_thread` | Create thread | channel_id, message_id |
| `discord_list_threads` | List threads | channel_id |
| `discord_archive_thread` | Archive thread | thread_id |
| `discord_acquire_thread` | Acquire lock | thread_id, agent_name |
| `discord_release_thread` | Release lock | thread_id, agent_name |

---

## 7. File Structure

```
server_monitor/
├── gateway/                     # Gateway Service
│   ├── main.py                  # FastAPI app
│   ├── discord_ws.py            # WebSocket
│   ├── thread_lock.py           # Lock manager
│   └── sse.py                   # SSE streaming
│
├── user_comm/                   # user_comm Agent
│   ├── agent.py                 # Main Agent
│   ├── discord_bot.py           # Discord Bot
│   └── team_comm.py             # Team communication
│
├── discord_mcp/                 # MCP Server
│   └── server.py                # 8 tools
│
├── mcp_shared/                  # Shared MCP tools
│   └── monitor/
│
└── docs/
    ├── MCP_SELECTION_STRATEGY.md
    └── MCP_ROUTING_POLICY.md
```

---

## 8. How to Run

### Local Execution

```bash
# Start Gateway Service
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# Start user_comm Agent (standalone mode)
python main.py --standalone

# Start user_comm Agent (team mode)
python main.py --team server-monitor

# Health check
curl http://localhost:8081/health
# Response: {"status": "healthy", "discord_connected": true}
```

### Claude Code MCP Configuration

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

## 9. Roadmap

### Phase 1: Complete

- [x] FastAPI Gateway Service
- [x] Discord WebSocket connection
- [x] Thread Lock (In-Memory)
- [x] SSE broadcast
- [x] MCP Server (8 tools)

### Phase 2: In Progress

- [ ] user_comm Agent implementation
- [ ] Slash command implementation
- [ ] Channel default MCP settings
- [ ] Keyword auto-detection
- [ ] Routing configuration file

### Phase 3: Optional

- [ ] API authentication (API Key)
- [ ] Rate Limiting
- [ ] Message persistence (SQLite)

---

## Conclusion

We chose a strategy of starting with a lightweight architecture and expanding when needed.

| Item | Current | Future |
|------|---------|--------|
| State Storage | In-Memory | SQLite (if needed) |
| Distributed Lock | Not used | Redis (multi-instance) |
| Authentication | None | API Key (if needed) |
| User Communication | Gateway direct | user_comm Agent |

The current structure is sufficient for single instances, and we plan to expand incrementally as traffic grows. The user_comm Agent systematizes user communication and improves collaboration with other agents on the team.
