+++
title = "Claude Code Team Agent Communication Architecture Design"
date = 2026-02-28T14:07:38+09:00
draft = false
tags = ["claude-code", "agent", "communication", "sqlite", "mcp", "discord"]
categories = ["claude-code", "architecture", "discord"]
ShowToc = true
TocOpen = true
+++

# Claude Code Team Agent Communication Architecture Design

## Overview

When multiple AI agents collaborate in Claude Code, an efficient communication method is needed. This article shares the communication architecture designed while building a Discord-integrated server monitoring team.

## Problem Definition

Claude Code has two types of agents:

1. **Python Processes (Daemon)**
   - Discord Gateway, user_comm_daemon, etc.
   - Always running, filesystem access available

2. **LLM Agents (Created as Tasks)**
   - gcp-monitor, oci-monitor, alert-manager, etc.
   - Use SendMessage tool, Claude Code native communication

Communication between these two types was needed.

## Considered Approaches

### 1. File-based Message Queue (Existing)
```
Pros: Simple implementation, no dependencies
Cons: Latency (~1s), file management required
```

### 2. WebSocket
```
Pros: Real-time bidirectional communication
Cons: Server/client implementation required
```

### 3. gRPC
```
Pros: Strong type checking, streaming
Cons: proto file management, high complexity
```

### 4. SQLite Message Hub (Adopted)
```
Pros: Fast (~10ms), transactions, no additional dependencies
Cons: Works only on a single machine
```

## Final Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              SQLite Message Hub (messages.db)                    │
│         ~/.claude/teams/{team}/messages.db                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Discord    │    │   Python     │    │     LLM      │
│   Gateway    │    │   Daemon     │    │    Agent     │
│ (Direct Access)│  │ (Direct Access)│  │  (MCP Tool)  │
└──────────────┘    └──────────────┘    └──────────────┘
```

## SQLite Message Hub Structure

### Messages Table

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT,              -- NULL = broadcast
    message_type TEXT DEFAULT 'message',
    content TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    metadata TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

### Agent Status Table

```sql
CREATE TABLE agent_status (
    agent_name TEXT PRIMARY KEY,
    status TEXT DEFAULT 'offline',
    last_heartbeat TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);
```

## Communication Methods

### LLM Agent ↔ LLM Agent
- Use **SendMessage** (Claude Code native)
- Auto-managed, idle notification provided

### Python ↔ LLM Agent
- **SQLite Hub** + **MCP Tool**
- Python accesses SQLite directly
- LLM Agent accesses via MCP Tool

## MCP Server Implementation

MCP tools for LLM Agents:

```python
@server.list_tools()
async def list_tools():
    return [
        Tool(name="team_send_message", ...),
        Tool(name="team_read_messages", ...),
        Tool(name="team_broadcast", ...),
        Tool(name="team_get_status", ...),
        Tool(name="team_update_status", ...),
    ]
```

## Message Flow Example

```
1. Discord user: "Hello"
       ↓
2. Discord Gateway → SQLite: INSERT message
       ↓
3. user_comm Daemon → SQLite: SELECT pending
       ↓
4. user_comm → SQLite: INSERT response
       ↓
5. Discord Gateway → SQLite: SELECT response
       ↓
6. Discord channel: "Hi there! 👋"
```

## Performance Comparison

| Method | Latency | Stability | Complexity |
|--------|---------|-----------|------------|
| File-based | ~1000ms | Medium | Low |
| WebSocket | ~5ms | High | Medium |
| **SQLite** | ~10ms | High | Low |

## Conclusion

The SQLite Message Hub + MCP Server combination was most suitable for Claude Code team agent communication:

1. **Low Latency**: 100x faster than file-based
2. **Stability**: Data integrity guaranteed through transactions
3. **Simplicity**: Uses Python's built-in sqlite3 without additional dependencies
4. **Flexibility**: Both Python and LLM Agents use the same data source

---

## Code

Full code is available on [GitHub](https://github.com/yarang/claude-code-team-comm).

- `message_hub.py`: SQLite Message Hub
- `team_comm_mcp_server.py`: MCP Server
- `discord_gateway.py`: Discord integration gateway
- `user_comm_daemon.py`: Message processing daemon
