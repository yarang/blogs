+++
title = "Discord Gateway MCP 아키텍처 설계 결정"
slug = "discord-gateway-mcp-architecture-decisions"
date = 2026-02-28T22:26:51+09:00
draft = false
tags = ["discord", "mcp", "fastapi", "claude-code", "architecture"]
categories = ["Development", "Architecture", "Claude Code"]
ShowToc = true
TocOpen = true
+++

# Discord Gateway MCP 아키텍처 설계 결정

## 개요

Claude Code 팀에서 Discord를 통한 사용자 소통을 위해 Discord Gateway Service를 설계했다. 이 글에서는 주요 아키텍처 결정 사항을 정리한다.

---

## 1. Redis 없이 동작하는 가벼운 아키텍처

### 결정

**Redis를 제거하고 in-memory 방식 채택**

### 이유

- 단일 인스턴스 환경에서는 Redis가 오버엔지니어링
- Thread Lock은 메모리 기반으로 충분
- SSE는 FastAPI 직접 스트리밍으로 처리

### 구조

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
│  │   (직접 스트리밍) │    │   (stdio)       │                │
│  └─────────────────┘    └─────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. MCP 도구 구성

### 결정

**3개의 핵심 도구 제공**

| 도구 | 설명 |
|------|------|
| `send_message` | Discord 채널에 메시지 전송 |
| `read_messages` | 채널 메시지 읽기 |
| `get_status` | 게이트웨이 상태 확인 |

### 대안 고려

| 대안 | 장점 | 단점 | 채택 |
|------|------|------|------|
| Redis Pub/Sub | 확장성 | 복잡도 증가 | ❌ |
| SQLite | 영속성 | 파일 I/O | ❌ |
| In-Memory | 단순함 | 단일 인스턴스만 | ✅ |

---

## 3. 인증 없는 단순 구조

### 결정

**개발/팀 환경이므로 인증 생략**

### 이유

- 로컬/팀 네트워크에서만 실행
- MCP는 이미 로컬 프로세스
- 복잡도 최소화

### 향후 확장

```
Phase 1: 인증 없음 (현재)
    ↓
Phase 2: API Key 인증 (선택)
    ↓
Phase 3: OAuth 2.0 (필요시)
```

---

## 4. FastAPI + SSE 선택

### 결정

**SSE(Server-Sent Events)로 실시간 통신 구현**

### 비교

| 기술 | 장점 | 단점 |
|------|------|------|
| WebSocket | 양방향 | 복잡한 상태 관리 |
| **SSE** | 단방향, 단순 | 서버 → 클라이언트만 |
| Polling | 구현 쉬움 | 지연 발생 |

### 선택 이유

- Discord → MCP는 단방향으로 충분
- FastAPI 네이티브 지원
- 재연결 로직 단순

---

## 5. 디렉토리 구조

```
discord-gateway/
├── gateway/
│   ├── main.py           # FastAPI 앱
│   ├── discord_bot.py    # Discord Bot
│   ├── mcp_server.py     # MCP Server
│   ├── models.py         # Pydantic 모델
│   └── config.py         # 설정
├── tests/
├── pyproject.toml
└── README.md
```

---

## 6. 실행 방법

### 로컬 실행

```bash
# Gateway Service 시작
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# 헬스체크
curl http://localhost:8081/health
```

### MCP 설정

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

## 7. 향후 계획

### Phase 2 (진행 예정)

- [ ] 슬래시 커맨드 구현
- [ ] 채널별 기본 MCP 설정
- [ ] 라우팅 설정 파일

### Phase 3 (선택)

- [ ] API 인증 (API Key)
- [ ] Rate Limiting
- [ ] 메시지 영속성 (SQLite)

---

## 결론

가벼운 아키텍처로 시작해서 필요시 확장하는 전략을 선택했다. 단일 인스턴스에서는 Redis 없이도 충분히 동작하며, 향후 다중 인스턴스가 필요하면 그때 Redis를 도입할 계획이다.
