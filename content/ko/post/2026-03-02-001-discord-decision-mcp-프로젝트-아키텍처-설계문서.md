+++
title = "[Discord Decision MCP] 프로젝트 아키텍처 설계문서"
date = 2026-03-02T00:04:54+09:00
draft = false
tags = ["discord", "mcp", "claude-code", "architecture", "python"]
categories = ["\uac1c\ubc1c", "\uc544\ud0a4\ud14d\ucc98"]
ShowToc = true
TocOpen = true
+++

# Discord Decision MCP — 아키텍처 설계문서

## 1. 프로젝트 개요

### 1.1 목적

Claude Code가 tmux Teammate 모드로 자율 작업 중, 사용자 결정이 필요한 시점에 Discord를 통해 질문하고 응답을 받아 작업을 재개하는 MCP (Model Context Protocol) 서버입니다.

### 1.2 핵심 특징

| 특징 | 설명 |
|------|------|
| **프로젝트당 Bot 1개** | 각 프로젝트는 독립된 Discord Bot 사용 |
| **무한 대기 기본값** | Timeout 없이 사용자 응답 대기 (Claude가 독단 진행 금지) |
| **상태 영속화** | 프로세스 재시작 후에도 대기 상태 복원 |
| **한국어 친화적** | 한글 선택지, Yes/No 응답 지원 |
| **MCP 기반 통신** | 모든 Discord 통신은 MCP Tool을 통해 이루어짐 |

### 1.3 버전 정보

- **버전**: 1.0.0
- **Python 요구사항**: >= 3.11
- **MCP 프레임워크**: FastMCP >= 0.1.0

---

## 2. 디렉토리 구조

```
discord-decision/
├── discord_mcp/              # 메인 패키지
│   ├── __init__.py
│   ├── server.py             # MCP 서버 진입점
│   ├── config.py             # 환경변수 설정 관리
│   │
│   ├── bot/                  # Discord API 클라이언트
│   │   ├── __init__.py
│   │   ├── client.py         # REST API 클라이언트 (httpx)
│   │   └── gateway.py        # WebSocket 게이트웨이 (수신 전용)
│   │
│   ├── decision/             # 결정 요청 관리
│   │   ├── __init__.py
│   │   ├── manager.py        # 결정 요청 생명주기 관리
│   │   ├── poller.py         # Discord Polling 및 응답 대기
│   │   ├── parser.py         # 사용자 응답 파싱
│   │   └── state.py          # 상태 영속화 (JSON 파일)
│   │
│   ├── tools/                # MCP Tools 구현
│   │   ├── __init__.py
│   │   ├── ask.py            # discord_ask_decision
│   │   ├── notify.py         # discord_notify
│   │   ├── report.py         # discord_report_progress
│   │   ├── status.py         # discord_check_pending
│   │   ├── inbox.py          # discord_read_inbox, discord_clear_inbox
│   │   └── _templates.py     # Discord 메시지 템플릿
│   │
│   └── daemon/               # 감시 데몬
│       ├── __init__.py
│       ├── watcher.py        # Discord 채널 감시 (discord-watch CLI)
│       └── inbox.py          # Inbox 파일 관리
│
├── scripts/                  # 유틸리티 스크립트
│   └── start-discord-watch.sh
│
├── tests/                    # 테스트 스위트
├── docs/                     # 문서
├── CLAUDE.md                 # Claude Code 프로젝트 지침
├── README.md                 # 프로젝트 설명
├── pyproject.toml            # 프로젝트 설정 및 의존성
└── mcp.json.example          # MCP 설정 예시
```

---

## 3. 주요 모듈 설명

### 3.1 서버 진입점 (`server.py`)

**역할**: FastMCP 서버 생성 및 MCP Tool 등록

```python
mcp = FastMCP(name="discord-decision-mcp")
# Tool 등록
mcp.tool()(discord_ask_decision)
mcp.tool()(discord_notify)
mcp.tool()(discord_report_progress)
mcp.tool()(discord_check_pending)
mcp.tool()(discord_read_inbox)
mcp.tool()(discord_clear_inbox)
```

### 3.2 설정 관리 (`config.py`)

| 환경변수 | 설명 | 기본값 |
|----------|------|--------|
| `DISCORD_BOT_TOKEN` | Discord Bot Token | 필수 |
| `DISCORD_CHANNEL_ID` | 기본 질문 채널 ID | 필수 |
| `PROJECT_NAME` | question_id 생성에 사용 | "project" |
| `PENDING_DIR` | 상태 파일 저장 경로 | `~/.claude/pending_decisions` |
| `POLL_INTERVAL_SECONDS` | Discord polling 간격 | 5 |

### 3.3 Discord API 클라이언트 (`bot/`)

- **REST API 클라이언트**: httpx 기반, Rate limit 자동 처리
- **WebSocket 게이트웨이**: MESSAGE_CREATE 이벤트 실시간 수신

### 3.4 결정 요청 관리 (`decision/`)

- **DecisionManager**: 결정 요청 생명주기 조율
- **DecisionPoller**: Discord 채널 polling 및 응답 대기
- **응답 파서**: A/B/C, Yes/No, 자연어 응답 지원
- **상태 저장소**: JSON 파일로 영속화

---

## 4. 데이터 흐름도

### 4.1 결정 요청 흐름

```
Claude Code → discord_ask_decision()
    ↓
MCP Server → DecisionManager.ask()
    ↓
Thread 생성 → 상태 파일 저장
    ↓
DecisionPoller.wait() → Discord API Polling
    ↓
사용자 응답 → 파싱 → PollResult 반환
```

### 4.2 감시 데몬 흐름

```
DiscordWatcher → 주기적 Polling (10초)
    ↓
새 메시지 감지 → InboxStore.add_message()
    ↓
~/.claude/discord_inbox.json 저장
    ↓
Claude Code → discord_read_inbox()로 조회
```

---

## 5. MCP 도구 목록

| Tool | 블로킹 | 설명 |
|------|--------|------|
| `discord_ask_decision` | ✅ | 사용자 결정 요청 |
| `discord_notify` | ❌ | 진행 상황 알림 |
| `discord_report_progress` | ❌ | 작업 완료 리포트 |
| `discord_check_pending` | ❌ | 미해결 질문 확인 |
| `discord_read_inbox` | ❌ | Inbox 메시지 조회 |
| `discord_clear_inbox` | ❌ | Inbox 메시지 삭제 |

---

## 6. 의존성 정보

### 핵심 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `fastmcp` | >= 0.1.0 | MCP 서버 프레임워크 |
| `httpx` | >= 0.27.0 | 비동기 HTTP 클라이언트 |
| `websockets` | >= 12.0 | WebSocket 클라이언트 |
| `pydantic` | >= 2.0.0 | 데이터 모델 검증 |

### CLI 명령어

```bash
discord-mcp      # MCP 서버 실행
discord-watch    # 감시 데몬 실행
```

---

## 7. 아키텍처 원칙

1. **싱글톤 패턴**: DiscordClient, StateStore, InboxStore
2. **상태 영속화**: 모든 결정 요청 상태는 파일로 영속화
3. **무한 대기 기본값**: Claude가 독단적으로 진행하지 않도록 timeout 기본값 None
4. **재질문 제한**: 모호한 응답은 최대 2회까지만 재질문
5. **Rate Limit 처리**: Discord API 429 응답 시 자동 대기 후 재시도

---

*문서 버전: 1.0.0*  
*마지막 수정: 2026-03-01*