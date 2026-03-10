---
title: "Discord Gateway MCP Architecture Design"
date: 2026-03-01T00:45:20+09:00
draft: false
tags: ["discord", "mcp", "fastapi", "claude-code"]
categories: ["Development", "Architecture"]
showToc: true
tocOpen: true
---

# Discord Gateway MCP Architecture Design

The Claude Code team designed the Discord Gateway Service for user communication through Discord. This article summarizes key architecture decisions.

---

## 1. Overall Architecture

### Components

| Layer | Components | Role |
|-------|-----------|------|
| **Discord** | Bot, Channel, Thread | User Interface |
| **Gateway** | WebSocket, REST API, SSE | Message Routing |
| **MCP** | gcp-mcp, oci-mcp, db-mcp | Tool Execution |

### Message Flow

```mermaid
flowchart LR
    subgraph Discord["Discord"]
        User[User]
    end

    subgraph Gateway["Gateway Service :8081"]
        WS[WebSocket]
        API[REST API]
        SSE[SSE]
    end

    subgraph MCPs["MCP Servers"]
        GCP[gcp-mcp]
        OCI[oci-mcp]
        DB[db-mcp]
    end

    User -->|Message| WS
    WS --> API
    API --> GCP
    API --> OCI
    API --> DB
    GCP -->|Response| SSE
    OCI -->|Response| SSE
    DB -->|Response| SSE
    SSE -->|Broadcast| User
```

---

## 2. Simple Architecture Without Redis

### Why Remove Redis?

| Item | Redis Usage | In-Memory Usage |
|------|-------------|-----------------|
| Thread Lock | Redis SET NX | Python dict |
| Event Distribution | Redis Streams | Direct SSE |
| State Storage | Redis Cache | Memory Cache |

**Conclusion**: In-Memory is sufficient for single-instance environment.

### Gateway Structure

```mermaid
flowchart TB
    subgraph Gateway["Gateway Service"]
        Bot["Discord Bot<br/>(WebSocket)"]
        Lock["Thread Lock<br/>(In-Memory)"]
        Cache["Message Cache<br/>(1000 limit)"]
        SSE["SSE Manager"]
    end

    Discord[Discord API] <--> Bot
    Bot --> Lock
    Bot --> Cache
    Bot --> SSE
    SSE --> Clients[WebSocket Clients]
```

### Component Details

| Module | Role | Features |
|--------|------|----------|
| Discord Bot | WebSocket connection | Auto-reconnect |
| Thread Lock | Concurrency control | 5min timeout |
| Message Cache | Message storage | Max 1000 messages |
| SSE Manager | Real-time streaming | Broadcast to all MCPs |

---

## 3. MCP Selection: 4-Stage Hybrid

### Selection Priority

| Priority | Method | Example | Description |
|:--------:|--------|--------|-------------|
| 1️⃣ | Slash Command | `/gcp status` | Most explicit |
| 2️⃣ | @Mention | `@gcp-monitor status` | Natural conversation |
| 3️⃣ | Keyword Detection | `gcp server status` | Auto keyword recognition |
| 4️⃣ | Per-Channel Default | #gcp-monitoring | Channel default MCP |

### Fallback Flow

```mermaid
flowchart TD
    A[Message Received] --> B{Slash Command?}
    B -->|Yes| C[Call MCP]
    B -->|No| D{@Mention?}
    D -->|Yes| C
    D -->|No| E{Keyword Detection?}
    E -->|Yes| C
    E -->|No| F{Channel Default MCP?}
    F -->|Yes| C
    F -->|No| G[Broadcast<br/>All MCPs]
```

### Slash Command List

| Command | MCP | Description |
|---------|-----|-------------|
| `/gcp status [server]` | gcp-mcp | GCP server status |
| `/gcp list` | gcp-mcp | GCP instance list |
| `/oci status [server]` | oci-mcp | OCI server status |
| `/oci list` | oci-mcp | OCI instance list |
| `/db query <sql>` | db-mcp | Execute DB query |
| `/db list` | db-mcp | Database list |
| `/alert check` | alert-mcp | Check alerts |

---

## 4. Thread Lock Rules

### Lock Behavior

```mermaid
sequenceDiagram
    participant MCP1 as gcp-mcp
    participant Gateway as Gateway
    participant MCP2 as oci-mcp
    participant Discord as Discord Thread

    MCP1->>Gateway: Request lock
    Gateway-->>MCP1: Lock acquired
    MCP1->>Discord: Send response

    MCP2->>Gateway: Request lock
    Gateway-->>MCP2: Lock failed (owned by gcp-mcp)

    Note over MCP1,Gateway: 5min timeout

    Gateway->>Gateway: Auto-release lock
    MCP2->>Gateway: Request lock
    Gateway-->>MCP2: Lock acquired
```

### Lock API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/threads/{id}/acquire` | Acquire lock |
| `POST` | `/api/threads/{id}/release` | Release lock |
| `GET` | `/api/threads/{id}/lock` | Check lock status |

---

## 5. MCP Tools (8 tools)

### Tool List

| Tool | Description | Key Parameters |
|------|-------------|-----------------|
| `discord_send_message` | Send message | channel_id, content |
| `discord_get_messages` | Get messages | channel_id, limit |
| `discord_wait_for_message` | Wait for message | channel_id, timeout |
| `discord_create_thread` | Create thread | channel_id, message_id |
| `discord_list_threads` | List threads | channel_id |
| `discord_archive_thread` | Archive thread | thread_id |
| `discord_acquire_thread` | Acquire lock | thread_id, agent_name |
| `discord_release_thread` | Release lock | thread_id, agent_name |

### Tool Relationship

```mermaid
flowchart TB
    subgraph Tools["MCP Tools"]
        direction TB

        subgraph Message["Message Tools"]
            Send[discord_send_message]
            Get[discord_get_messages]
            Wait[discord_wait_for_message]
        end

        subgraph Thread["Thread Tools"]
            Create[discord_create_thread]
            List[discord_list_threads]
            Archive[discord_archive_thread]
        end

        subgraph Lock["Lock Tools"]
            Acquire[discord_acquire_thread]
            Release[discord_release_thread]
        end
    end

    Acquire --> Create
    Create --> Send
    Send --> Release
```

---

## 6. File Structure

```mermaid
flowchart TB
    subgraph Project["server_monitor/"]
        subgraph Gateway["gateway/"]
            Main["main.py<br/>FastAPI app"]
            WS["discord_ws.py<br/>WebSocket"]
            Lock["thread_lock.py<br/>Lock manager"]
            SSE["sse.py<br/>SSE streaming"]
        end

        subgraph MCP["discord_mcp/"]
            Server["server.py<br/>8 tools"]
        end

        subgraph Shared["mcp_shared/"]
            Monitor["monitor/"]
        end

        subgraph Docs["docs/"]
            Strategy["MCP_SELECTION_STRATEGY.md"]
            Deploy["OCI_DEPLOYMENT.md"]
        end
    end

    Main --> WS
    Main --> Lock
    Main --> SSE
    WS <--> Server
```

### Directory Description

| Path | Description |
|------|-------------|
| `gateway/` | Gateway Service (FastAPI) |
| `discord_mcp/` | MCP Server (8 tools) |
| `mcp_shared/` | Shared MCP tools |
| `docs/` | Documentation |

---

## 7. How to Run

### Local Execution

```bash
# Start Gateway Service
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# Health check
curl http://localhost:8081/health

# Response
{"status": "healthy", "discord_connected": true}
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

## 8. Roadmap

```mermaid
timeline
    title Discord Gateway Roadmap

    section Phase 1 (Complete)
        Gateway Service : FastAPI app
        Discord Connection : WebSocket
        Thread Lock : In-Memory
        MCP Server : 8 tools

    section Phase 2 (In Progress)
        Slash Commands : /gcp, /oci
        Per-Channel MCP : Default MCP settings
        Keyword Detection : Auto recognition

    section Phase 3 (Planned)
        API Authentication : API Key
        Rate Limiting : Request limits
        Persistence : SQLite
```

### Phase 1: Complete

- [x] FastAPI Gateway Service
- [x] Discord WebSocket connection
- [x] Thread Lock (In-Memory)
- [x] SSE broadcast
- [x] MCP Server (8 tools)

### Phase 2: In Progress

- [ ] Slash command implementation
- [ ] Per-channel default MCP settings
- [ ] Keyword auto-detection
- [ ] Routing configuration file

### Phase 3: Optional

- [ ] API authentication (API Key)
- [ ] Rate limiting
- [ ] Message persistence (SQLite)

---

## Conclusion

We chose a strategy of starting with simple architecture and extending as needed.

| Item | Current | Future |
|------|--------|--------|
| State Storage | In-Memory | SQLite (if needed) |
| Distributed Lock | Not used | Redis (multi-instance) |
| Authentication | None | API Key (if needed) |

The current structure is sufficient for a single instance, with plans for gradual expansion as traffic grows.

---

**Korean Version:** [한국어 버전](/ko/post/2026-03-01-005-discord-gateway-mcp-아키텍처-설계/)
