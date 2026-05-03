+++
title = ""
date = "2026-03-01T00:45:20+09:00"
draft = "false"
tags = ["discord", "mcp", "fastapi"]
categories = ["Development", "Architecture"]
ShowToc = "true"
TocOpen = "true"
+++

---
title: "Discord Gateway MCP Architecture Design"
date: 2026-03-01
categories: ["Development", "Architecture"]
tags: ["discord", "mcp", "fastapi", "claude-code"]
---

# Discord Gateway MCP Architecture Design

The Claude Code team designed a Discord Gateway Service for user communication via Discord. This article summarizes the key architectural decisions.

---

## 1. Overall Architecture

### Components

| Layer | Component | Role |
|------|-----------|------|
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

## 2. Lightweight Architecture Operating Without Redis

### Why Remove Redis?

| Item | Using Redis | Using In-Memory |
|------|-------------|-----------------|
| Thread Lock | Redis SET NX | Python dict |
| Event Distribution | Redis Streams | Direct SSE |
| State Storage | Redis Cache | Memory Cache |

**Conclusion**: In-Memory is sufficient for a single-instance environment.

### Gateway Structure

```mermaid
flowchart TB
    subgraph Gateway["Gateway Service"]
        Bot["Discord Bot<br/>(WebSocket)"]
        Lock["Thread Lock<br/>(In-Memory)"]
        Cache["Message Cache<br/>(Limit 1000)"]
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
|------|------|----------|
| Discord Bot | WebSocket Connection | Auto Reconnect |
| Thread Lock | Concurrency Control | 5 min timeout |
| Message Cache | Message Retention | Max 1000 |
| SSE Manager | Real-time Transmission | Broadcast to all MCPs |

---

## 3. MCP Selection Method: 4-Step Hybrid

### Selection Priority

| Rank | Method | Example | Description |
|:----:|--------|---------|-------------|
| 1️⃣ | Slash Command | `/gcp status` | Most explicit |
| 2️⃣ | @Mention | `@gcp-monitor status` | Natural conversation |
| 3️⃣ | Keyword Detection | `gcp server status` | Automatic keyword recognition |
| 4️⃣ | Channel-specific | #gcp-monitoring | Channel default MCP |

### Fallback Behavior Sequence

```mermaid
flowchart TD
    A[Message Received] --> B{Slash Command?}
    B -->|Yes| C[Call Relevant MCP]
    B -->|No| D{@Mention?}
    D -->|Yes| C
    D -->|No| E{Keyword Detected?}
    E -->|Yes| C
    E -->|No| F{Channel Default MCP?}
    F -->|Yes| C
    F -->|No| G[Broadcast<br/>Send to all MCPs]
```

### Slash Command List

| Command | MCP | Description |
|--------|-----|-------------|
| `/gcp status [server]` | gcp-mcp | GCP Server Status |
| `/gcp list` | gcp-mcp | GCP Instance List |
| `/oci status [server]` | oci-mcp | OCI Server Status |
| `/oci list` | oci-mcp | OCI Instance List |
| `/db query <sql>` | db-mcp | Execute DB Query |
| `/db list` | db-mcp | DB List |
| `/alert check` | alert-mcp | Check Alerts |

---

## 4. Thread Lock Rules

### Lock Operation Method

```mermaid
sequenceDiagram
    participant MCP1 as gcp-mcp
    participant Gateway as Gateway
    participant MCP2 as oci-mcp
    participant Discord as Discord Thread

    MCP1->>Gateway: Request Lock Acquisition
    Gateway-->>MCP1: Lock Acquired Successfully
    MCP1->>Discord: Send Response

    MCP2->>Gateway: Request Lock Acquisition
    Gateway-->>MCP2: Lock Acquisition Failed (Owned by gcp-mcp)

    Note over MCP1,Gateway: Timeout after 5 minutes

    Gateway->>Gateway: Auto Release Lock
    MCP2->>Gateway: Request Lock Acquisition
    Gateway-->>MCP2: Lock Acquired Successfully
```

### Lock API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/threads/{id}/acquire` | Acquire Lock |
| `POST` | `/api/threads/{id}/release` | Release Lock |
| `GET` | `/api/threads/{id}/lock` | Check Lock Status |

---

## 5. MCP Tools (8)

### Tool List

| Tool | Description | Main Parameters |
|------|-------------|-----------------|
| `discord_send_message` | Send Message | channel_id, content |
| `discord_get_messages` | Get Messages | channel_id, limit |
| `discord_wait_for_message` | Wait for Message | channel_id, timeout |
| `discord_create_thread` | Create Thread | channel_id, message_id |
| `discord_list_threads` | List Threads | channel_id |
| `discord_archive_thread` | Archive Thread | thread_id |
| `discord_acquire_thread` | Acquire Lock | thread_id, agent_name |
| `discord_release_thread` | Release Lock | thread_id, agent_name |

### Tool Relationship Diagram

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
            Main["main.py<br/>FastAPI App"]
            WS["discord_ws.py<br/>WebSocket"]
            Lock["thread_lock.py<br/>Lock Manager"]
            SSE["sse.py<br/>SSE Streaming"]
        end

        subgraph MCP["discord_mcp/"]
            Server["server.py<br/>8 Tools"]
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
| `discord_mcp/` | MCP Server (8 Tools) |
| `mcp_shared/` | Shared MCP Tools |
| `docs/` | Documentation |

---

## 7. How to Run

### Local Execution

```bash
# Start Gateway Service
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# Health Check
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

    section Phase 1 (Completed)
        Gateway Service : FastAPI App
        Discord Connection : WebSocket
        Thread Lock : In-Memory
        MCP Server : 8 Tools

    section Phase 2 (In Progress)
        Slash Commands : /gcp, /oci
        Per-Channel MCP : Default MCP Settings
        Keyword Detection : Auto Recognition

    section Phase 3 (Planned)
        API Auth : API Key
        Rate Limiting : Request Limit
        Persistence : SQLite
```

### Phase 1: Completed

- [x] FastAPI Gateway Service
- [x] Discord WebSocket Connection
- [x] Thread Lock (In-Memory)
- [x] SSE Broadcast
- [x] MCP Server (8 Tools)

### Phase 2: Planned

- [ ] Implement Slash Commands
- [ ] Set Default MCP per Channel
- [ ] Automatic Keyword Detection
- [ ] Routing Configuration File

### Phase 3: Optional

- [ ] API Authentication (API Key)
- [ ] Rate Limiting
- [ ] Message Persistence (SQLite)

---

## Conclusion

We chose a strategy of starting with a lightweight architecture and scaling when necessary.

| Item | Current | Future |
|------|---------|--------|
| State Storage | In-Memory | SQLite (if needed) |
| Distributed Lock | Not Used | Redis (for multi-instance) |
| Authentication | None | API Key (if needed) |

The current structure is sufficient for a single instance, and we plan to scale gradually as traffic increases.

---

**Korean Version:** [Korean Version](/post/2026-03-01-005-discord-gateway-mcp-architecture-design/)
```