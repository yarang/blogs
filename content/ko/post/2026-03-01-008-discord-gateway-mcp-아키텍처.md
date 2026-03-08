+++
title = "Discord Gateway MCP 아키텍처"
date = 2026-03-01T00:50:08+09:00
draft = false
tags = ["discord", "mcp"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

---
title: Discord Gateway MCP 아키텍처
date: 2026-03-01
---

# Discord Gateway MCP 아키텍처

Claude Code 팀에서 Discord를 통한 사용자 소통을 위해 Discord Gateway Service를 설계했다.

## 전체 구조

| 계층 | 구성요소 | 역할 |
|------|----------|------|
| Discord | Bot, Channel, Thread | 사용자 인터페이스 |
| Gateway | WebSocket, REST API, SSE | 메시지 라우팅 |
| MCP | gcp-mcp, oci-mcp, db-mcp | 도구 실행 |

## Redis 없는 가벼운 아키텍처

| 항목 | Redis | In-Memory |
|------|-------|------------|
| Thread Lock | SET NX | Python dict |
| 이벤트 분배 | Streams | SSE 직접 |
| 상태 저장 | Cache | 메모리 |

**결론**: 단일 인스턴스는 In-Memory로 충분

## MCP 선택: 4단계

| 순위 | 방식 | 예시 |
|:----:|------|------|
| 1 | 슬래시 커맨드 | /gcp status |
| 2 | @멘션 | @gcp-monitor |
| 3 | 키워드 | gcp 서버 상태 |
| 4 | 채널별 | #gcp-모니터링 |

## Thread Lock 규칙
- 첫 응답 MCP가 락 획득
- 기본 5분 유지
- 활동 시 자동 연장
- 타임아웃 시 자동 해제

## MCP 도구 8개

| 도구 | 설명 |
|------|------|
| discord_send_message | 메시지 전송 |
| discord_get_messages | 메시지 조회 |
| discord_wait_for_message | 메시지 대기 |
| discord_create_thread | 스레드 생성 |
| discord_list_threads | 스레드 목록 |
| discord_archive_thread | 아카이브 |
| discord_acquire_thread | 락 획득 |
| discord_release_thread | 락 해제 |

## 실행

```bash
uvicorn gateway.main:app --port 8081
curl http://localhost:8081/health
```

## 로드맵
- Phase 1: 완료 (Gateway, Discord, Lock, SSE, MCP)
- Phase 2: 슬래시 커맨드, 채널별 MCP
- Phase 3: 인증, Rate Limit (선택)
