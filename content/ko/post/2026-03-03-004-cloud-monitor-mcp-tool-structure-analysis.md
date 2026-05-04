+++
title = "[Cloud Monitor] MCP 도구 구조 및 장단점 분석"
slug = "2026-03-03-004-cloud-monitor-mcp-tool-structure-analysis"
date = 2026-03-03T15:02:49+09:00
draft = false
tags = ["mcp", "fastmcp", "discord", "ssh", "server-monitoring", "cloud"]
categories = ["DevOps", "MCP", "Cloud Monitoring"]
ShowToc = true
TocOpen = true
+++

# [server-monitor] MCP 도구 구조 및 장단점 분석

## 개요

이 문서는 server-monitor 프로젝트에 구현된 MCP (Model Context Protocol) 도구들의 구조, 장점, 단점을 분석합니다. 총 13개의 MCP 도구가 제공되며, 기존 8개의 Discord MCP 도구와 새로운 5개의 Cloud Monitor MCP 도구로 분류됩니다.

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [도구 상세 분석](#도구-상세-분석)
3. [아키텍처 구조](#아키텍처-구조)
4. [장점](#장점)
5. [단점 및 개선사항](#단점-및-개선사항)
6. [결론](#결론)

---

## 아키텍처 개요

### FastMCP 기반 아키텍처

```mermaid
graph TB
    subgraph MCP Server
        A[FastMCP Server] --> B[Discord Tools]
        A --> C[Cloud Monitor Tools]
        B --> D[Gateway Service]
        C --> D
        D --> E[Discord API]
    end

    subgraph Cloud Monitor
        F[SSH Monitor] --> G[OCI Servers]
        F --> H[Mac mini]
        G --> I[Ubuntu]
        H --> J[macOS]
    end

    subgraph Discord
        K[Bot] --> L[Channels]
        K --> M[Threads]
    end
```

### MCP 도구 분류

| 분류 | 도구 수 | 주요 기능 |
|------|---------|-----------|
| Discord MCP | 8 | 메시지, 스레드 관리 |
| Cloud Monitor MCP | 5 | 서버 모니터링, 메트릭 수집 |
| **전체** | **13** | **통합 모니터링 플랫폼** |

---

## 도구 상세 분석

### 1. 기존 Discord MCP 도구 (8개)

#### 1.1 메시지 관리 도구

| 도구 이름 | 파라미터 | 반환값 | 기능 |
|-----------|----------|--------|------|
| `discord_send_message` | `channel_id`, `content`, `thread_id?` | 결과 메시지 | 기본 메시지 전송 |
| `discord_get_messages` | `channel_id`, `limit?`, `after?` | 메시지 목록 | 메시지 조회 |
| `discord_wait_for_message` | `channel_id`, `timeout_seconds?` | 대기 상태 | 비동기 메시지 대기 (SSE 미구현) |

#### 1.2 스레드 관리 도구

| 도구 이름 | 파라미터 | 반환값 | 기능 |
|-----------|----------|--------|------|
| `discord_create_thread` | `channel_id`, `message_id`, `name?` | 스레드 정보 | 스레드 생성 |
| `discord_list_threads` | `channel_id` | 스레드 목록 | 활성 스레드 조회 |
| `discord_archive_thread` | `thread_id` | 결과 메시지 | 스레드 아카이빙 (미구현) |

#### 1.3 동시성 관리 도구

| 도구 이름 | 파라미터 | 반환값 | 기능 |
|-----------|----------|--------|------|
| `discord_acquire_thread` | `thread_id`, `agent_name`, `timeout?` | 락 획득 결과 | 멀티 에이전트 락 |
| `discord_release_thread` | `thread_id`, `agent_name` | 락 해제 결과 | 에이전트 락 해제 |

### 2. 새로운 Cloud Monitor MCP 도구 (5개)

#### 2.1 서버 관리 도구

| 도구 이름 | 파라미터 | 반환값 | 기능 |
|-----------|----------|--------|------|
| `cloud_get_server_status` | `server_name` | 서버 상태 정보 | 연결 상태, OS, 메트릭 |
| `cloud_list_servers` | `group?` | 서버 목록 | 그룹 필터링 지원 |
| `cloud_list_ssh_config_hosts` | `group?` | SSH 호스트 목록 | SSH 설정 자동 파싱 |

#### 2.2 모니터링 도구

| 도구 이름 | 파라미터 | 반환값 | 기능 |
|-----------|----------|--------|------|
| `cloud_get_metrics` | `server_name`, `metric_types?` | 메트릭 데이터 | 선택적 메트릭 조회 |
| `cloud_set_alert` | `metric_type`, `level`, `threshold` | 설정 결과 | 동적 임계값 구성 |

---

## 아키텍처 구조

### 1. FastMCP 구조

```mermaid
graph LR
    subgraph "FastMCP Layer"
        A[@mcp.tool decorator] --> B[Tool Function]
        B --> C[Parameter Validation]
        C --> D[Business Logic]
        D --> E[Result Formatting]
        E --> F[Return Response]
    end

    subgraph "Common Components"
        G[Gateway Request] --> H[HTTP Client]
        I[Config Manager] --> J[Cloud Monitor Config]
        K[Error Handler] --> L[Uniform Error Response]
    end
```

### 2. 통신 흐름

```mermaid
sequenceDiagram
    participant MCP as MCP Server
    participant GW as Gateway Service
    participant Discord as Discord API
    participant Server as Target Server

    MCP->>GW: HTTP Request
    GW->>Discord: API Call
    Discord-->>GW: Response
    GW-->>MCP: JSON Response

    MCP->>Server: SSH Connection
    Server-->>MCP: Metrics Data
    MCP->>GW: Alert Message
    GW->>Discord: Embed Message
```

### 3. 데이터 흐름

```
Configuration (config.yaml)
    ↓
Server Info parsing
    ↓
SSH Connection
    ↓
Metrics Collection
    ↓
Threshold Check
    ↓
Alert Generation
    ↓
Discord Notification
```

---

## 장점

### 1. 확장성

- **모듈형 구조**: 각 도구가 독립적으로 작동하며 확장이 용이
- **플러그인 아키텍처**: 새 도구 추가는 데코레이터 추가만으로 가능
- **클라우드 제공자 추상화**: SSH 기반으로 다양한 환경 지원

### 2. 통합성

- **통합 플랫폼**: Discord와 Cloud Monitor를 단일 MCP 서버에서 통합 관리
- **자동 연동**: 서버 이상 시 자동 Discord 알림
- **일관된 인터페이스**: 모든 도구가 동일한 파라미터 패턴 따름

### 3. 사용성

- **직관적인 도구 이름**: `cloud_get_server_status`처럼 명확한 기능 표현
- **선택적 파라미터**: 대부분 파라미터가 선택사항으로 편리
- **상세한 오류 메시지**: 실패 원인을 명확히 표시
- **JSON 응답**: 구조화된 데이터 반환으로 파싱 용이

### 4. 신뢰성

- **타임아웃 처리**: 모든 요청에 타임아웃 설정
- **연결 풀링**: 성능을 위한 SSH 연결 재사용
- **예외 처리**: 포괄적인 try-catch 블록
- **상태 추적**: 지속적인 서버 상태 모니터링

### 5. 유지보수성

- **중앙집중식 구성**: config.yaml을 통한 중앙 관리
- **환경변수 지원**: 민감 정보를 환경변수로 분리
- **로깅 시스템**: 상세한 로깅으로 디버깅 용이
- **버전 관리**: 명확한 모듈 버전 구분

---

## 단점 및 개선사항

### 1. 성능 관련

#### 문제점
- **동기식 처리**: 일부 도구가 순차적으로 작동
- **연결 지연**: 모든 SSH 연결 시 새 연결 생성
- **메모리 사용량**: 단일 이벤트 루프에서 모든 처리

#### 개선안
```python
# 비동기 처리 개선 예시
async def concurrent_monitoring(servers):
    tasks = [monitor_server(server) for server in servers]
    return await asyncio.gather(*tasks)

# 연결 풀링 도입
class ConnectionPool:
    def __init__(self, max_connections=10):
        self.pool = asyncio.Queue(maxsize=max_connections)
```

### 2. 오류 처리 관련

#### 문제점
- **구분되지 않은 오류**: 모든 오류를 동일하게 처리
- **복구 메커니즘 부재**: 실패 시 자동 복구 로직 없음
- **상세 로깅 부족**: 디버깅을 위한 로그 부족

#### 개선안
```python
# 구분된 오류 처리
class CloudMonitorError(Exception):
    pass

class ConnectionError(CloudMonitorError):
    pass

class MetricCollectionError(CloudMonitorError):
    pass

# 자동 복구 메커니즘
async def resilient_monitoring(server_info, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await monitor_server(server_info)
        except ConnectionError:
            await asyncio.sleep(2 ** attempt)
    raise CloudMonitorError("Max retries exceeded")
```

### 3. 기능 관련

#### 문제점
- **메타데이터 부족**: 도구 설명이 너무 간결
- **검증 부족**: 입력값 확인 로직 부족
- **배치 처리 미지원**: 여러 서버를 동시에 처리 불가

#### 개선안
```python
# 상세한 메타데이터
@mcp.tool(
    name="cloud_batch_monitoring",
    description="여러 서버 상태를 한 번에 조회",
    parameters={
        "server_names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "모니터링할 서버 이름 목록"
        }
    }
)
async def cloud_batch_monitoring(server_names: List[str]) -> str:
    # 배치 처리 로직
    pass
```

### 4. 보안 관련

#### 문제점
- **자격증명 노출**: 로그에 민감 정보가 노출될 가능성
- **접근 제어 미구현**:任何人이 도구 호출 가능
- **입력 검증 부족**: 악의적 입력에 대한 방어 부족

#### 개선안
```python
# 접근 제어
def require_role(required_role):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not has_role(required_role):
                raise PermissionError("Access denied")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 입력 검증
@mcp.tool()
async def secure_monitoring(server_name: str):
    if not is_valid_server_name(server_name):
        raise ValueError("Invalid server name")
    # ...
```

### 5. 사용성 관련

#### 문제점
- **문서 부족**: 도구 사용에 대한 상세한 문서 없음
- **예시 미제공**: 실제 사용 예시 없음
- **불일치 반환값**: 일부 도구는 JSON, 다른 도구는 문자열 반환

#### 개선안
```python
# 일관된 반환값 형식
@mcp.tool()
async def cloud_get_server_status_v2(server_name: str) -> dict:
    """
    서버 상태를 조회합니다.

    Args:
        server_name (str): 서버 이름

    Returns:
        dict: {
            "success": bool,
            "data": Optional[dict],
            "error": Optional[str],
            "timestamp": str
        }
    """
    # ...
    return {
        "success": True,
        "data": status,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
```

---

## 결론

### 1. 전체 평가

server-monitor 프로젝트의 MCP 도구는 다음과 같은 강점을 가집니다:

- **✅ 우수한 통합**: Discord 통합과 서버 모니터링의 완벽한 결합
- **✅ 확장 가능한 구조**: FastMCP를 활용한 모듈형 아키텍처
- **✅ 실용성**: 실제 서버 모니터링에 필요한 모든 기능 제공
- **✅ 사용 용이성**: 직관적인 도구 이름과 단순한 인터페이스

### 2. 개선 우선순위

우선순위별 개선 계획:

1. **높음**: 성능 개선 (비동기 처리, 연결 풀링)
2. **중간**: 오류 처리 강화 및 자동 복구 메커니즘
3. **낮음**: 보안 강화 및 상세 문서화

### 3. 향후 방향

- **마이크로서비스 아키텍처**: 각 도구를 독립 서비스로 분리
- **실시간 모니터링**: WebSocket/SSE를 통한 실시간 데이터 수집
- **자동 확장**: 서버 변경에 따른 자동 확장
- **머신러닝**: 이상 탐지를 위한 ML 모델 통합

### 4. 최종 평가

전체적으로 실제 운영 환경에 적합한 안정성과 기능을 제공하는 잘 설계된 MCP 도구 시스템입니다. 개선이 필요한 부분이 있지만 핵심 기능은 매우 완성도가 높으며, 지속적인 개선을 통해 더욱 강력한 모니터링 플랫폼으로 발전할 잠재력이 있습니다.

---

*작성일: 2026-03-03*
*저자: server-monitor-team*

---

**영어 버전:** [English Version](/post/2026-03-03-002-cloud-monitor-mcp-tool-structure-analysis/)
