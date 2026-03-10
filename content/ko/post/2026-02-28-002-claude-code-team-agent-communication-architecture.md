+++
title = "[Claude Code] 팀 에이전트 통신 아키텍처"
slug = "2026-02-28-002-claude-code-team-agent-communication-architecture"
date = 2026-02-28T14:07:38+09:00
draft = false
tags = ["claude-code", "agent", "communication", "sqlite", "mcp", "discord"]
categories = ["claude-code", "architecture", "discord"]
ShowToc = true
TocOpen = true
+++

# Claude Code 팀 에이전트 간 통신 아키텍처 설계

## 개요

Claude Code에서 여러 AI 에이전트가 협업할 때 효율적인 통신 방식이 필요합니다. 이 글에서는 Discord와 연동된 서버 모니터링 팀을 구축하며 설계한 통신 아키텍처를 공유합니다.

## 문제 정의

Claude Code에는 두 가지 유형의 에이전트가 있습니다:

1. **Python 프로세스 (Daemon)**
   - Discord Gateway, user_comm_daemon 등
   - 항상 실행 중, 파일 시스템 접근 가능

2. **LLM Agent (Task로 생성)**
   - gcp-monitor, oci-monitor, alert-manager 등
   - SendMessage 도구 사용, Claude Code 네이티브 통신

이 두 유형 간의 통신이 필요했습니다.

## 고려한 방식들

### 1. 파일 기반 메시지 큐 (기존)
```
장점: 구현 단순, 의존성 없음
단점: 지연 (~1초), 파일 관리 필요
```

### 2. WebSocket
```
장점: 실시간 양방향 통신
단점: 서버/클라이언트 구현 필요
```

### 3. gRPC
```
장점: 강력한 타입 체크, 스트리밍
단점: proto 파일 관리, 높은 복잡도
```

### 4. SQLite 메시지 허브 (채택)
```
장점: 빠름 (~10ms), 트랜잭션, 추가 의존성 없음
단점: 단일 머신에서만 동작
```

## 최종 아키텍처

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
│  (직접 접근)  │    │  (직접 접근)  │    │  (MCP Tool)  │
└──────────────┘    └──────────────┘    └──────────────┘
```

## SQLite Message Hub 구조

### 메시지 테이블

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

### 에이전트 상태 테이블

```sql
CREATE TABLE agent_status (
    agent_name TEXT PRIMARY KEY,
    status TEXT DEFAULT 'offline',
    last_heartbeat TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);
```

## 통신 방식

### LLM Agent ↔ LLM Agent
- **SendMessage** 사용 (Claude Code 네이티브)
- 자동 관리, idle notification 제공

### Python ↔ LLM Agent
- **SQLite Hub** + **MCP Tool**
- Python은 직접 SQLite 접근
- LLM Agent는 MCP Tool로 접근

## MCP Server 구현

LLM Agent를 위한 MCP 도구들:

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

## 메시지 플로우 예시

```
1. Discord 사용자: "안녕"
       ↓
2. Discord Gateway → SQLite: INSERT message
       ↓
3. user_comm Daemon → SQLite: SELECT pending
       ↓
4. user_comm → SQLite: INSERT response
       ↓
5. Discord Gateway → SQLite: SELECT response
       ↓
6. Discord 채널: "안녕하세요! 👋"
```

## 성능 비교

| 방식 | 지연 시간 | 안정성 | 복잡도 |
|------|-----------|--------|--------|
| 파일 기반 | ~1000ms | 보통 | 낮음 |
| WebSocket | ~5ms | 높음 | 중간 |
| **SQLite** | ~10ms | 높음 | 낮음 |

## 결론

SQLite Message Hub + MCP Server 조합이 Claude Code 팀 에이전트 통신에 가장 적합했습니다:

1. **낮은 지연**: 파일 기반보다 100배 빠름
2. **안정성**: 트랜잭션으로 데이터 무결성 보장
3. **단순함**: 추가 의존성 없이 Python 내장 sqlite3 사용
4. **유연성**: Python과 LLM Agent 모두 동일한 데이터 소스 사용

---

## 코드

핵심 컴포넌트:

- `message_hub.py`: SQLite Message Hub
- `team_comm_mcp_server.py`: MCP Server
- `discord_gateway.py`: Discord 연동 게이트웨이
- `user_comm_daemon.py`: 메시지 처리 데몬


---

**영어 버전:** [English Version](/en/post/2026-02-28-002-claude-code-team-agent-communication-architecture/)