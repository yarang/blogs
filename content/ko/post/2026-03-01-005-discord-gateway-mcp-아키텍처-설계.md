+++
title = "Discord Gateway MCP 아키텍처 설계"
date = 2026-03-01T00:45:20+09:00
draft = false
tags = ["discord", "mcp", "fastapi"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

---
title: "Discord Gateway MCP 아키텍처 설계"
date: 2026-03-01
categories: ["Development", "Architecture"]
tags: ["discord", "mcp", "fastapi", "claude-code"]
---

# Discord Gateway MCP 아키텍처 설계

Claude Code 팀에서 Discord를 통한 사용자 소통을 위해 Discord Gateway Service를 설계했다. 이 글에서는 주요 아키텍처 결정 사항을 정리한다.

---

## 1. 전체 아키텍처

### 구성 요소

| 계층 | 구성요소 | 역할 |
|------|----------|------|
| **Discord** | Bot, Channel, Thread | 사용자 인터페이스 |
| **Gateway** | WebSocket, REST API, SSE | 메시지 라우팅 |
| **MCP** | gcp-mcp, oci-mcp, db-mcp | 도구 실행 |

### 메시지 흐름

```mermaid
flowchart LR
    subgraph Discord["Discord"]
        User[사용자]
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

    User -->|메시지| WS
    WS --> API
    API --> GCP
    API --> OCI
    API --> DB
    GCP -->|응답| SSE
    OCI -->|응답| SSE
    DB -->|응답| SSE
    SSE -->|브로드캐스트| User
```

---

## 2. Redis 없이 동작하는 가벼운 아키텍처

### 왜 Redis를 제거했나?

| 항목 | Redis 사용 | In-Memory 사용 |
|------|-----------|----------------|
| Thread Lock | Redis SET NX | Python dict |
| 이벤트 분배 | Redis Streams | SSE 직접 |
| 상태 저장 | Redis Cache | 메모리 캐시 |

**결론**: 단일 인스턴스 환경에서는 In-Memory로 충분

### Gateway 구조

```mermaid
flowchart TB
    subgraph Gateway["Gateway Service"]
        Bot["Discord Bot<br/>(WebSocket)"]
        Lock["Thread Lock<br/>(In-Memory)"]
        Cache["Message Cache<br/>(1000개 제한)"]
        SSE["SSE Manager"]
    end

    Discord[Discord API] <--> Bot
    Bot --> Lock
    Bot --> Cache
    Bot --> SSE
    SSE --> Clients[WebSocket Clients]
```

### 구성요소 상세

| 모듈 | 역할 | 특징 |
|------|------|------|
| Discord Bot | WebSocket 연결 | 자동 재연결 |
| Thread Lock | 동시성 제어 | 5분 타임아웃 |
| Message Cache | 메시지 보관 | 최대 1000개 |
| SSE Manager | 실시간 전송 | 모든 MCP에 브로드캐스트 |

---

## 3. MCP 선택 방식: 4단계 하이브리드

### 선택 우선순위

| 순위 | 방식 | 예시 | 설명 |
|:----:|------|------|------|
| 1️⃣ | 슬래시 커맨드 | `/gcp status` | 가장 명시적 |
| 2️⃣ | @멘션 | `@gcp-monitor status` | 자연스러운 대화 |
| 3️⃣ | 키워드 감지 | `gcp 서버 상태` | 키워드 자동 인식 |
| 4️⃣ | 채널별 지정 | #gcp-모니터링 | 채널 기본 MCP |

### Fallback 동작 순서

```mermaid
flowchart TD
    A[메시지 수신] --> B{슬래시 커맨드?}
    B -->|Yes| C[해당 MCP 호출]
    B -->|No| D{@멘션?}
    D -->|Yes| C
    D -->|No| E{키워드 감지?}
    E -->|Yes| C
    E -->|No| F{채널 기본 MCP?}
    F -->|Yes| C
    F -->|No| G[Broadcast<br/>모든 MCP에 전달]
```

### 슬래시 커맨드 목록

| 커맨드 | MCP | 설명 |
|--------|-----|------|
| `/gcp status [server]` | gcp-mcp | GCP 서버 상태 |
| `/gcp list` | gcp-mcp | GCP 인스턴스 목록 |
| `/oci status [server]` | oci-mcp | OCI 서버 상태 |
| `/oci list` | oci-mcp | OCI 인스턴스 목록 |
| `/db query <sql>` | db-mcp | DB 쿼리 실행 |
| `/db list` | db-mcp | DB 목록 |
| `/alert check` | alert-mcp | 알림 확인 |

---

## 4. Thread Lock 규칙

### 락 동작 방식

```mermaid
sequenceDiagram
    participant MCP1 as gcp-mcp
    participant Gateway as Gateway
    participant MCP2 as oci-mcp
    participant Discord as Discord Thread

    MCP1->>Gateway: 락 획득 요청
    Gateway-->>MCP1: 락 획득 성공
    MCP1->>Discord: 응답 전송

    MCP2->>Gateway: 락 획득 요청
    Gateway-->>MCP2: 락 획득 실패 (gcp-mcp 소유)

    Note over MCP1,Gateway: 5분 후 타임아웃

    Gateway->>Gateway: 락 자동 해제
    MCP2->>Gateway: 락 획득 요청
    Gateway-->>MCP2: 락 획득 성공
```

### Lock API

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/threads/{id}/acquire` | 락 획득 |
| `POST` | `/api/threads/{id}/release` | 락 해제 |
| `GET` | `/api/threads/{id}/lock` | 락 상태 확인 |

---

## 5. MCP 도구 (8개)

### 도구 목록

| 도구 | 설명 | 주요 파라미터 |
|------|------|--------------|
| `discord_send_message` | 메시지 전송 | channel_id, content |
| `discord_get_messages` | 메시지 조회 | channel_id, limit |
| `discord_wait_for_message` | 메시지 대기 | channel_id, timeout |
| `discord_create_thread` | 스레드 생성 | channel_id, message_id |
| `discord_list_threads` | 스레드 목록 | channel_id |
| `discord_archive_thread` | 스레드 아카이브 | thread_id |
| `discord_acquire_thread` | 락 획득 | thread_id, agent_name |
| `discord_release_thread` | 락 해제 | thread_id, agent_name |

### 도구 관계도

```mermaid
flowchart TB
    subgraph Tools["MCP 도구"]
        direction TB

        subgraph Message["메시지 도구"]
            Send[discord_send_message]
            Get[discord_get_messages]
            Wait[discord_wait_for_message]
        end

        subgraph Thread["스레드 도구"]
            Create[discord_create_thread]
            List[discord_list_threads]
            Archive[discord_archive_thread]
        end

        subgraph Lock["락 도구"]
            Acquire[discord_acquire_thread]
            Release[discord_release_thread]
        end
    end

    Acquire --> Create
    Create --> Send
    Send --> Release
```

---

## 6. 파일 구조

```mermaid
flowchart TB
    subgraph Project["server_monitor/"]
        subgraph Gateway["gateway/"]
            Main["main.py<br/>FastAPI 앱"]
            WS["discord_ws.py<br/>WebSocket"]
            Lock["thread_lock.py<br/>Lock 매니저"]
            SSE["sse.py<br/>SSE 스트리밍"]
        end

        subgraph MCP["discord_mcp/"]
            Server["server.py<br/>8개 도구"]
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

### 디렉토리 설명

| 경로 | 설명 |
|------|------|
| `gateway/` | Gateway Service (FastAPI) |
| `discord_mcp/` | MCP Server (8개 도구) |
| `mcp_shared/` | 공유 MCP 도구 |
| `docs/` | 문서 |

---

## 7. 실행 방법

### 로컬 실행

```bash
# Gateway Service 시작
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# 헬스체크
curl http://localhost:8081/health

# 응답
{"status": "healthy", "discord_connected": true}
```

### Claude Code MCP 설정

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

## 8. 로드맵

```mermaid
timeline
    title Discord Gateway 로드맵

    section Phase 1 (완료)
        Gateway Service : FastAPI 앱
        Discord 연결 : WebSocket
        Thread Lock : In-Memory
        MCP Server : 8개 도구

    section Phase 2 (진행중)
        슬래시 커맨드 : /gcp, /oci
        채널별 MCP : 기본 MCP 설정
        키워드 감지 : 자동 인식

    section Phase 3 (계획)
        API 인증 : API Key
        Rate Limiting : 요청 제한
        영속성 : SQLite
```

### Phase 1: 완료

- [x] FastAPI Gateway Service
- [x] Discord WebSocket 연결
- [x] Thread Lock (In-Memory)
- [x] SSE 브로드캐스트
- [x] MCP Server (8개 도구)

### Phase 2: 진행 예정

- [ ] 슬래시 커맨드 구현
- [ ] 채널별 기본 MCP 설정
- [ ] 키워드 자동 감지
- [ ] 라우팅 설정 파일

### Phase 3: 선택 사항

- [ ] API 인증 (API Key)
- [ ] Rate Limiting
- [ ] 메시지 영속성 (SQLite)

---

## 결론

가벼운 아키텍처로 시작해서 필요시 확장하는 전략을 선택했다.

| 항목 | 현재 | 향후 |
|------|------|------|
| 상태 저장 | In-Memory | SQLite (필요시) |
| 분산 락 | 미사용 | Redis (다중 인스턴스 시) |
| 인증 | 없음 | API Key (필요시) |

단일 인스턴스에서는 현재 구조로 충분하며, 트래픽이 늘어나면 점진적으로 확장할 계획이다.
