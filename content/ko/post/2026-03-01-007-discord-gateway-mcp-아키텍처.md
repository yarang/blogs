+++
title = "Discord Gateway MCP 아키텍처"
date = 2026-03-01T00:49:06+09:00
draft = false
tags = ["discord", "mcp", "fastapi"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

---
title: "Discord Gateway MCP 아키텍처"
date: 2026-03-01
categories: ["Development", "Architecture"]
tags: ["discord", "mcp", "fastapi", "claude-code"]
---

# Discord Gateway MCP 아키텍처

Claude Code 팀에서 Discord를 통한 사용자 소통을 위해 Discord Gateway Service를 설계했다. 이 글에서는 주요 아키텍처처 결정 사항들을 정리한다.

---

## 1. 전체 아키텍처

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

---

## 3. MCP 선택 방식: 4단계 하이브리드

| 순위 | 방식 | 예시 | 설명 |
|:----:|------|------|------|
| 1 | 슬래시 커맨드 | /gcp status | 가장 명시적 |
| 2 | @멘션 | @gcp-monitor status | 자연스러운 대화 |
| 3 | 키워드 감지 | gcp 서버 상태 | 키워드 자동 인식 |
| 4 | 채널별 지정 | #gcp-모니터링 | 채널 기본 MCP |

### 슬래시 커맨드 목록
| 커맨드 | MCP | 설명 |
|--------|-----|------|
| /gcp status | gcp-mcp | GCP 서버 상태 |
| /gcp list | gcp-mcp | GCP 인스턴스 목록 |
| /oci status | oci-mcp | OCI 서버 상태 |
| /oci list | oci-mcp | OCI 인스턴스 목록 |
| /db query | db-mcp | DB 쿼리 실행 |
| /alert check | alert-mcp | 알림 확인 |

---

## 4. Thread Lock 규칙

- 첫 응답하는 MCP가 락 획득
- 기본 유지 시간: 5분 (300초)
- 활동 시 자동 연장
- 타임아웃 시 자동 해제

### Lock API
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/threads/{id}/acquire | 락 획득 |
| POST | /api/threads/{id}/release | 락 해제 |
| GET | /api/threads/{id}/lock | 락 상태 확인 |

---

## 5. MCP 도구 (8개)
| 도구 | 설명 |
|------|------|
| discord_send_message | 메시지 전송 |
| discord_get_messages | 메시지 조회 |
| discord_wait_for_message | 메시지 대기 |
| discord_create_thread | 스레드 생성 |
| discord_list_threads | 스레드 목록 |
| discord_archive_thread | 스레드 아카이브 |
| discord_acquire_thread | 락 획득 |
| discord_release_thread | 락 해제 |

---

## 6. 파일 구조
```
server_monitor/
├── gateway/                    # Gateway Service
│   ├── main.py              # FastAPI 앱
│   ├── discord_ws.py        # Discord WebSocket
│   ├── thread_lock.py       # Lock 매니저
│   └── sse.py               # SSE 스트리밍
├── discord_mcp/                # MCP Server
│   └── server.py               # 8개 도구
├── mcp_shared/                 # 공유 MCP 도구
└── docs/
    ├── MCP_SELECTION_STRATEGY.md
    └── OCI_DEPLOYMENT.md
```

---

## 7. 실행 방법
```bash
# Gateway Service 시작
uvicorn gateway.main:app --host 0.0.0.0 --port 8081

# 헬스체크
curl http://localhost:8081/health
```

### Claude Code MCP 설정
```json
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