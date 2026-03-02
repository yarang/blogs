+++
title = "[Discord Decision MCP] Architecture Design Document"
slug = "discord-decision-mcp-architecture-design-v2"
date = 2026-03-02T21:36:30+09:00
draft = false
tags = ["discord", "mcp", "claude-code", "architecture", "python"]
categories = ["Development"]
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
│   ├── __init__.py
│   ├── test_parser.py
│   └── test_state.py
│
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

**Execution**:
```bash
discord-mcp  # or python -m discord_mcp.server
```

### 3.2 Configuration Management (`config.py`)

**Role**: Load configuration values from environment variables

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord Bot Token (includes "Bot " prefix) | Required |
| `DISCORD_CHANNEL_ID` | Default question channel ID | Required |
| `PROJECT_NAME` | Used for question_id generation | "project" |
| `PENDING_DIR` | State file storage path | `~/.claude/pending_decisions` |
| `POLL_INTERVAL_SECONDS` | Discord polling interval (seconds) | 5 |

### 3.3 Discord API Client (`bot/`)

#### 3.3.1 REST API Client (`client.py`)

**Role**: Discord REST API calls (httpx-based)

**Key Methods**:
```python
class DiscordClient:
    async def send_message(channel_id, content, embeds=None)
    async def get_messages(channel_id, after=None, limit=50)
    async def create_thread(channel_id, name, first_message)
    async def archive_thread(thread_id)
```

**Features**:
- Automatic rate limit handling (retry on 429 response)
- Singleton pattern (`get_client()`)

#### 3.3.2 WebSocket Gateway (`gateway.py`)

**Role**: Discord Gateway WebSocket connection (receive only)

**Features**:
- Real-time MESSAGE_CREATE event reception
- Reduces polling delay from 5 seconds to instant
- System works without Gateway (polling fallback)
- Automatic reconnection (Exponential backoff)

```python
class GatewayClient:
    async def run()     # Start event reception
    async def stop()    # Close connection
```

### 3.4 Decision Request Management (`decision/`)

#### 3.4.1 DecisionManager (`manager.py`)

**Role**: Coordinate the entire lifecycle of decision requests

```python
class DecisionManager:
    async def ask(question, context, options, timeout_seconds, thread_id) -> PollResult
    async def restore_pending() -> list[DecisionState]
```

**Flow**:
1. Check for duplicate questions
2. Create thread (or reuse existing thread)
3. Create state file (`~/.claude/pending_decisions/{question_id}.json`)
4. Run poller to wait for response
5. Mark disconnected state on SIGHUP signal

#### 3.4.2 DecisionPoller (`poller.py`)

**Role**: Poll Discord channel and wait for response

```python
class DecisionPoller:
    async def wait(state: DecisionState) -> PollResult
```

**Features**:
- Default: infinite wait (`timeout_seconds=None`)
- Real-time waiting status display in tmux pane (ANSI escape)
- Re-question up to 2 times for ambiguous responses

#### 3.4.3 Response Parser (`parser.py`)

**Role**: Parse user Discord responses

**Supported Patterns**:
- Option matching: "A", "a", "A번", "A로 해줘", "1", "1번"
- Affirmative/Negative: "yes", "네", "예", "no", "아니요"
- Natural language: 15+ characters or 3+ Korean characters

```python
def parse_response(text: str, options: list[str]) -> ParseResult
def build_clarify_message(...) -> str  # Generate re-question message
```

#### 3.4.4 State Store (`state.py`)

**Role**: Persist decision request state to JSON files

**State File Location**: `~/.claude/pending_decisions/{question_id}.json`

```python
class DecisionState(BaseModel):
    question_id: str
    project: str
    question: str
    context: str
    options: list[str]
    timeout_seconds: float | None
    thread_id: str
    message_id: str
    asked_at: str
    status: Literal["pending", "disconnected", "resolved", "aborted", "timeout"]
    clarify_attempts: int
    resolved_at: str | None
    resolution: str | None
    selected_option: str | None

class StateStore:
    def save(state: DecisionState)
    def load(question_id: str) -> DecisionState | None
    def load_all_pending() -> list[DecisionState]
    def resolve(question_id, resolution, selected_option)
    def is_duplicate(question: str) -> bool
```

### 3.5 MCP Tools (`tools/`)

| Tool | Blocking | Description |
|------|----------|-------------|
| `discord_ask_decision` | ✅ | User decision request |
| `discord_notify` | ❌ | Progress notification |
| `discord_report_progress` | ❌ | Task completion report |
| `discord_check_pending` | ❌ | Check pending questions |
| `discord_read_inbox` | ❌ | Inbox message query |
| `discord_clear_inbox` | ❌ | Inbox message deletion |

### 3.6 Watcher Daemon (`daemon/`)

#### 3.6.1 DiscordWatcher (`watcher.py`)

**Role**: Monitor Discord channel and record new messages to inbox file

**Execution**:
```bash
discord-watch --interval 10
# or
tmux new-session -d -s discord-watch 'uv run discord-watch'
```

**Features**:
- Periodically poll specified channel(s)
- Record new user messages to inbox
- Display status in tmux pane

#### 3.6.2 InboxStore (`inbox.py`)

**Role**: JSON file-based storage for Discord messages

**Inbox File Location**: `~/.claude/discord_inbox.json`

```python
class InboxMessage:
    message_id: str
    channel_id: str
    thread_id: str | None
    author: str
    author_id: str
    content: str
    timestamp: str
    read: bool

class InboxStore:
    def add_message(msg: InboxMessage)
    def get_unread() -> list[InboxMessage]
    def mark_read(message_id: str)
    def clear_read()  # Delete read messages
```

---

## 4. Data Flow Diagrams

### 4.1 Decision Request Flow

```
┌─────────────────┐
│  Claude Code    │
└────────┬────────┘
         │ discord_ask_decision()
         ▼
┌─────────────────────────────────────┐
│  MCP Server (server.py)             │
│  ┌───────────────────────────────┐  │
│  │ DecisionManager.ask()         │  │
│  │  1. Duplicate check           │  │
│  │  2. Thread creation           │  │
│  │  3. State file save           │  │
│  └───────────────┬───────────────┘  │
└──────────────────┼──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│  DecisionPoller.wait()              │
│  ┌───────────────────────────────┐  │
│  │ Polling loop                  │  │
│  │  1. tmux status update        │  │
│  │  2. Discord API call          │  │
│  │  3. Response parsing          │  │
│  │  4. Re-question if ambiguous  │  │
│  └───────────────┬───────────────┘  │
└──────────────────┼──────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌───────────────────┐  ┌──────────────────┐
│  Discord REST API │  │  Discord Thread  │
│    (client.py)    │  │                  │
└───────────────────┘  └────────┬─────────┘
                                 │
                        ┌────────▼────────┐
                        │  User Response  │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  parser.py      │
                        │  - Option match │
                        │  - Ambiguity    │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  store.resolve()│
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  PollResult     │
                        │  Return         │
                        └─────────────────┘
```

### 4.2 Watcher Daemon Flow

```
┌─────────────────────────────────────────────┐
│  DiscordWatcher (daemon/watcher.py)         │
│  ┌───────────────────────────────────────┐  │
│  │ 1. Set initial message ID             │  │
│  │ 2. Periodic polling (default 10s)     │  │
│  │ 3. Detect new messages                │  │
│  │ 4. InboxStore.add_message()           │  │
│  └───────────────────┬───────────────────┘  │
└──────────────────────┼──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  ~/.claude/discord_inbox.json               │
│  {                                          │
│    "last_message_id": "...",                │
│    "messages": [                            │
│      { "message_id": "...", ... }           │
│    ]                                        │
│  }                                          │
└──────────────────────┬──────────────────────┘
                       ▲
                       │ discord_read_inbox()
┌──────────────────────┴──────────────────────┐
│  Claude Code                                │
└─────────────────────────────────────────────┘
```

### 4.3 Session Restoration Flow

```
┌─────────────────────────────────────────────┐
│  Claude Code session start                  │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  discord_check_pending()                    │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  DecisionManager.restore_pending()          │
│  ┌───────────────────────────────────────┐  │
│  │ 1. ~/.claude/pending_decisions/*.json │  │
│  │ 2. Check Thread via Discord API       │  │
│  │ 3. If answered → Auto-resolve         │  │
│  │ 4. If no answer → Restart notification│  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 5. MCP Tools List

### 5.1 discord_ask_decision

**Description**: Send question to Discord Thread and wait for response when user decision is needed (blocking)

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `question` | string | ✅ | Question content |
| `context` | string | ✅ | Current work context |
| `options` | string[] | ❌ | List of options (empty array for free response) |
| `timeout_seconds` | float | ❌ | Wait timeout (null for infinite wait) |
| `thread_id` | string | ❌ | Existing Thread ID (null to create new Thread) |

**Return Value**:
```json
{
  "success": true,
  "answer": "A) Execute now",
  "selected_option": "A) Execute now",
  "question_id": "project_20260301_abc123",
  "timed_out": false,
  "aborted": false
}
```

### 5.2 discord_notify

**Description**: Send progress notification to Discord (non-blocking)

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `message` | string | ✅ | Notification message |
| `level` | string | ❌ | info/warning/success/error (default: info) |
| `thread_id` | string | ❌ | Thread ID to send to (null for default channel) |

### 5.3 discord_report_progress

**Description**: Report task completion or milestone completion (non-blocking)

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | ✅ | Report title |
| `summary` | string | ✅ | Task result summary |
| `details` | string[] | ❌ | List of detail items |
| `thread_id` | string | ❌ | Thread ID to send to |

### 5.4 discord_check_pending

**Description**: Check pending questions at session start (non-blocking)

**Parameters**: None

**Return Value**:
```json
{
  "has_pending": true,
  "pending_questions": [
    {
      "question_id": "project_20260301_abc123",
      "question": "Deploy?",
      "thread_id": "1234567890",
      "asked_at": "2026-03-01T10:30:00Z",
      "status": "pending"
    }
  ]
}
```

### 5.5 discord_read_inbox

**Description**: Query messages stored in Inbox (non-blocking)

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `unread_only` | boolean | true | Return only unread messages |
| `mark_read` | boolean | false | Mark queried messages as read |

### 5.6 discord_clear_inbox

**Description**: Delete Inbox messages (non-blocking)

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `read_only` | boolean | true | Delete only read messages |

---

## 6. Dependency Information

### 6.1 Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp` | >= 0.1.0 | MCP server framework |
| `httpx` | >= 0.27.0 | Async HTTP client |
| `websockets` | >= 12.0 | WebSocket client |
| `python-dotenv` | >= 1.0.0 | Environment variable loading |
| `pydantic` | >= 2.0.0 | Data model validation |
| `anyio` | >= 4.0.0 | Async execution |

### 6.2 Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-mock` | Mock support |
| `respx` | httpx mocking |

### 6.3 CLI Commands

```bash
discord-mcp      # Run MCP server
discord-watch    # Run watcher daemon
```

---

## 7. State File Format

### 7.1 Decision State File

**Location**: `~/.claude/pending_decisions/{question_id}.json`

```json
{
  "question_id": "project_20260301_abc123",
  "project": "my-project",
  "question": "Run DB migration?",
  "context": "v1→v2 schema change",
  "options": ["A) Execute now", "B) Staging first", "C) Hold"],
  "timeout_seconds": null,
  "thread_id": "1234567890",
  "message_id": "0987654321",
  "asked_at": "2026-03-01T10:30:00Z",
  "status": "pending",
  "clarify_attempts": 0,
  "resolved_at": null,
  "resolution": null,
  "selected_option": null
}
```

### 7.2 Inbox File

**Location**: `~/.claude/discord_inbox.json`

```json
{
  "last_message_id": "1234567890",
  "messages": [
    {
      "message_id": "1234567890",
      "channel_id": "1234567890",
      "thread_id": null,
      "author": "username",
      "author_id": "1234567890",
      "content": "Message content",
      "timestamp": "2026-03-01T00:00:00Z",
      "read": false
    }
  ]
}
```

---

## 8. Architecture Principles

### 8.1 Design Principles

1. **Singleton Pattern**: DiscordClient, StateStore, InboxStore are module-level singletons
2. **State Persistence**: All decision request states are persisted to files
3. **Infinite Wait Default**: Timeout default is None so Claude does not proceed unilaterally
4. **Re-question Limit**: Ambiguous responses are re-asked up to 2 times
5. **Rate Limit Handling**: Automatic wait and retry on Discord API 429 responses

### 8.2 Error Handling

| Situation | Handling |
|-----------|----------|
| Discord API 429 | Automatic wait and retry (max 5 times) |
| WebSocket disconnection | Reconnect with exponential backoff |
| Response parsing failure | Re-question up to 2 times then abort |
| Timeout occurrence | Send abort notification and set aborted state |
| Session disconnect (SIGHUP) | Save as disconnected state |

---

*Document Version: 1.0.0*
*Last Modified: 2026-03-02*
