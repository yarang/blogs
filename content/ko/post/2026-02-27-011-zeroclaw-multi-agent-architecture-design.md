+++
title = "ZeroClaw 멀티 에이전트 아키텍처 설계안"
date = 2026-02-27T22:58:08+09:00
draft = false
tags = ["rust", "multi-agent", "zeroclaw", "architecture"]
categories = ["Architecture", "Multi-Agent"]
ShowToc = true
TocOpen = true
+++

# ZeroClaw 멀티 에이전트 아키텍처 설계안

## 개요

ZeroClaw의 멀티 에이전트 아키텍처는 단일 에이전트 모델에서 진화하는 고급 협력 시스템을 구현합니다.

### 현재 상태
- **Phase 1**: In-Process Delegation (완료)
- **Phase 2**: File-Based Multi-Agent Architecture (개발 중)

---

## 1. 설계 철학

| 원칙 | 적용 |
|------|------|
| KISS | 단순 통신 프로토콜 |
| YAGNI | 필수 기능만 구현 |
| SRP | 단일 책임 에이전트 |
| Secure | 최소 권한 원칙 |

---

## 2. 아키텍처 구조

```
Application Layer: Research │ Code │ Test Agent
Message Bus Layer: NATS/Redis Pub/Sub
Transport Layer: gRPC │ WebSocket │ Unix Socket
```

---

## 3. 에이전트 정의

```yaml
agent:
  id: "researcher"
  name: "Research Agent"
  
execution:
  mode: subprocess

provider:
  name: "openrouter"
  model: "claude-sonnet-4-6"
```

---

## 4. CLI 명령어

```bash
zeroclaw agent list
zeroclaw agent show <id>
zeroclaw agent run --agent-id researcher
```

---

## 5. 보안

| 모드 | 격리 | 용도 |
|------|------|------|
| Subprocess | 프로세스 | 신뢰된 에이전트 |
| Docker | 컨테이너 | 파일 작업 |
| Wasm | 메모리 | 높은 보안 |