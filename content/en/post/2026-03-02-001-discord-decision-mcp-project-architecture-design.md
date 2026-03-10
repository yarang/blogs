+++
title = "[Discord Decision MCP] Project Architecture Design Document"
slug = "discord-decision-mcp-project-architecture-design"
date = 2026-03-02T00:04:54+09:00
draft = false
tags = ["discord", "mcp", "claude-code", "architecture", "python"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

# Discord Decision MCP — Architecture Design Document

## 1. Project Overview

### 1.1 Purpose

An MCP (Model Context Protocol) server that allows Claude Code, while operating in tmux Teammate mode for autonomous work, to ask questions via Discord when user decisions are needed and resume work after receiving responses.

### 1.2 Key Features

| Feature | Description |
|---------|-------------|
| **One Bot per Project** | Each project uses an independent Discord Bot |
| **Infinite Wait Default** | Wait for user response without timeout (Claude must not proceed unilaterally) |
| **State Persistence** | Restore waiting state after process restart |
| **Korean-Friendly** | Korean options, Yes/No response support |
| **MCP-Based Communication** | All Discord communication through MCP Tools |

### 1.3 Version Information

- **Version**: 1.0.0
- **Python Requirement**: >= 3.11
- **MCP Framework**: FastMCP >= 0.1.0

---

## 2. Directory Structure

```
discord-decision/
├── discord_mcp/              # Main package
│   ├── __init__.py
│   ├── server.py             # MCP server entry point
│   ├── config.py             # Environment variable configuration
│   │
│   ├── bot/                  # Discord API client
│   │   ├── __init__.py
│   │   ├── client.py         # REST API client (httpx)
│   │   └── gateway.py        # WebSocket gateway (receive only)
│   │
│   ├── decision/             # Decision request management
│   │   ├── __init__.py
│   │   ├── manager.py        # Decision request lifecycle management
│   │   ├── poller.py         # Discord polling and response waiting
│   │   ├── parser.py         # User response parsing
│   │   └── state.py          # State persistence (JSON files)
│   │
│   ├── tools/                # MCP Tools implementation
│   │   ├── __init__.py
│   │   ├── ask.py            # discord_ask_decision
│   │   ├── notify.py         # discord_notify
│   │   ├── report.py         # discord_report_progress
│   │   ├── status.py         # discord_check_pending
│   │   ├── inbox.py          # discord_read_inbox, discord_clear_inbox
│   │   └── _templates.py     # Discord message templates
│   │
│   └── daemon/               # Watcher daemon
│       ├── __init__.py
│       ├── watcher.py        # Discord channel monitoring (discord-watch CLI)
│       └── inbox.py          # Inbox file management
│
├── scripts/                  # Utility scripts
│   └── start-discord-watch.sh
│
├── tests/                    # Test suite
├── docs/                     # Documentation
├── CLAUDE.md                 # Claude Code project instructions
├── README.md                 # Project description
├── pyproject.toml            # Project configuration and dependencies
└── mcp.json.example          # MCP configuration example
```

---

## 3. Key Module Descriptions

### 3.1 Server Entry Point (`server.py`)

**Role**: FastMCP server creation and MCP Tool registration

```python
mcp = FastMCP(name="discord-decision-mcp")
# Tool registration
mcp.tool()(discord_ask_decision)
mcp.tool()(discord_notify)
mcp.tool()(discord_report_progress)
mcp.tool()(discord_check_pending)
mcp.tool()(discord_read_inbox)
mcp.tool()(discord_clear_inbox)
```

### 3.2 Configuration Management (`config.py`)

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord Bot Token | Required |
| `DISCORD_CHANNEL_ID` | Default question channel ID | Required |
| `PROJECT_NAME` | Used for question_id generation | "project" |
| `PENDING_DIR` | State file storage path | `~/.claude/pending_decisions` |
| `POLL_INTERVAL_SECONDS` | Discord polling interval | 5 |

### 3.3 Discord API Client (`bot/`)

- **REST API Client**: httpx-based, automatic rate limit handling
- **WebSocket Gateway**: Real-time MESSAGE_CREATE event reception

### 3.4 Decision Request Management (`decision/`)

- **DecisionManager**: Decision request lifecycle coordination
- **DecisionPoller**: Discord channel polling and response waiting
- **Response Parser**: A/B/C, Yes/No, natural language response support
- **State Store**: Persistence via JSON files

---

## 4. Data Flow Diagrams

### 4.1 Decision Request Flow

```
Claude Code → discord_ask_decision()
    ↓
MCP Server → DecisionManager.ask()
    ↓
Thread Creation → State File Save
    ↓
DecisionPoller.wait() → Discord API Polling
    ↓
User Response → Parsing → PollResult Return
```

### 4.2 Watcher Daemon Flow

```
DiscordWatcher → Periodic Polling (10s)
    ↓
New Message Detection → InboxStore.add_message()
    ↓
~/.claude/discord_inbox.json Save
    ↓
Claude Code → discord_read_inbox() Query
```

---

## 5. MCP Tools List

| Tool | Blocking | Description |
|------|----------|-------------|
| `discord_ask_decision` | ✅ | User decision request |
| `discord_notify` | ❌ | Progress notification |
| `discord_report_progress` | ❌ | Task completion report |
| `discord_check_pending` | ❌ | Check pending questions |
| `discord_read_inbox` | ❌ | Inbox message query |
| `discord_clear_inbox` | ❌ | Inbox message deletion |

---

## 6. Dependency Information

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp` | >= 0.1.0 | MCP server framework |
| `httpx` | >= 0.27.0 | Async HTTP client |
| `websockets` | >= 12.0 | WebSocket client |
| `pydantic` | >= 2.0.0 | Data model validation |

### CLI Commands

```bash
discord-mcp      # Run MCP server
discord-watch    # Run watcher daemon
```

---

## 7. Architecture Principles

1. **Singleton Pattern**: DiscordClient, StateStore, InboxStore
2. **State Persistence**: All decision request states persisted to files
3. **Infinite Wait Default**: Claude must not proceed unilaterally, timeout default is None
4. **Re-question Limit**: Ambiguous responses re-asked up to 2 times
5. **Rate Limit Handling**: Automatic wait and retry on Discord API 429 responses

---

*Document Version: 1.0.0*
*Last Modified: 2026-03-01*


---

**Korean Version:** [한국어 버전](/ko/post/2026-03-02-001-discord-decision-mcp-project-architecture-design/)