+++
title = "[blog-api-server] 모니터링 대시보드 및 알림 시스템 구축"
slug = "2026-03-03-002-blog-api-server-monitoring-alerting"
date = 2026-03-03T14:53:47+09:00
draft = false
tags = ["blog-api-server", "monitoring", "prometheus", "alerting", "Python"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [blog-api-server] 모니터링 대시보드 및 알림 시스템 구축

## 개요

blog-api-server에 프로메테우스 기반 모니터링 시스템과 Slack/Email 알림 기능을 추가하여 서버 상태를 실시간으로 추적하고 문제 발생 시 즉시 대응할 수 있게 되었습니다.

## 모니터링 아키텍처

```mermaid
flowchart TB
    A[HTTP Request] --> B[MonitoringMiddleware]
    B --> C[Request Logging]
    B --> D[PrometheusMiddleware]
    D --> E[Metrics Collection]
    C --> F[AlertManager]
    E --> F
    F --> G{Threshold Check}
    G -->|Over Threshold| H[Slack Webhook]
    G -->|Critical| I[Email Alert]
    G -->|Normal| J[Log Only]
    K[Prometheus Server] --> L[/metrics/prometheus]
    M[Dashboard] --> N[/dashboard]
```

## Prometheus 메트릭

### 기본 HTTP 메트릭

| 메트릭명 | 타입 | 라벨 | 설명 |
|---------|------|------|------|
| `http_requests_total` | Counter | method, endpoint, status | 총 HTTP 요청 수 |
| `http_request_duration_seconds` | Histogram | method, endpoint | 요청 처리 시간 분포 |
| `http_errors_total` | Counter | method, endpoint, status | 총 에러 수 |
| `active_requests` | Gauge | - | 현재 활성 요청 수 |

### 비즈니스 메트릭

| 메트릭명 | 타입 | 라벨 | 설명 |
|---------|------|------|------|
| `git_operations_total` | Counter | operation, status | Git 작업 수 |
| `git_operation_duration_seconds` | Histogram | operation | Git 작업 소요 시간 |
| `translation_requests_total` | Counter | source_lang, target_lang, status | 번역 요청 수 |
| `translation_duration_seconds` | Histogram | - | 번역 소요 시간 |
| `post_operations_total` | Counter | operation, language, status | 포스트 작업 수 |

### 메트릭 수집 코드

```python
# prometheus_exporter.py
from prometheus_client import Counter, Histogram, Gauge

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# 미들웨어에서 자동 수집
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
```

## 알림 시스템

### 알림 규칙

| 규칙명 | 조건 | 심각도 | 쿨다운 |
|--------|------|--------|--------|
| High Error Rate | error_rate > 5% | WARNING | 5분 |
| Critical Error Rate | error_rate > 20% | CRITICAL | 1분 |
| Slow Response Time | avg_response_time > 2000ms | WARNING | 10분 |
| High Slow Request Rate | slow_request_rate > 10% | WARNING | 5분 |

### 알림 채널

**Slack Webhook**
- 모든 심각도 수준 지원
- 색상으로 심각도 표현 (INFO: 녹색, WARNING: 주황, ERROR: 빨강, CRITICAL: 짙은 빨강)

**Email**
- CRITICAL 수준만 전송
- SMTP 기반 이메일 발송

### AlertManager 코드

```python
# alerting.py
class AlertManager:
    def check_and_alert(self, metrics: Dict[str, Any]):
        for rule in self.rules:
            if rule.should_trigger(metrics):
                self._send_alert(rule, metrics)

    def _send_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        message = f"""
Alert Rule: {rule.name}
Condition: {rule.condition}

Current Metrics:
- Total Requests: {metrics.get('total_requests', 0)}
- Error Count: {metrics.get('error_count', 0)}
- Error Rate: {metrics.get('error_rate_percent', 0)}%
- Slow Requests: {metrics.get('slow_request_count', 0)}
"""
        self.slack.send(
            title=f"Alert: {rule.name}",
            message=message.strip(),
            severity=rule.severity
        )
```

## 대시보드 구성

### 모니터링 엔드포인트

| 경로 | 인증 | 설명 |
|------|------|------|
| `/health` | 불필요 | 서버 상태 확인 |
| `/metrics` | 필요 | JSON 형식 메트릭 |
| `/metrics/prometheus` | 불필요 | Prometheus 형식 메트릭 |
| `/metrics/reset` | 필요 | 메트릭 초기화 |
| `/dashboard` | 불필요 | 웹 대시보드 |
| `/alerts/rules` | 필요 | 알림 규칙 목록 |
| `/alerts/send` | 필요 | 수동 알림 전송 |

### 요청 추적 미들웨어

```python
# middleware.py
class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()

        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # 응답 헤더에 추적 정보 추가
        response.headers["X-Process-Time"] = f"{process_time:.2f}"
        response.headers["X-Request-ID"] = request_id

        return response
```

## 환경 변수 설정

```bash
# Slack 알림
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Email 알림
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=your-email@gmail.com
ALERT_TO_EMAILS=admin@example.com,ops@example.com

# 임계값 설정
SLOW_REQUEST_THRESHOLD=1000  # 1초
VERY_SLOW_THRESHOLD=3000     # 3초
MAX_BODY_LOG_LENGTH=1000
```

## 향후 계획

1. **Grafana 통합**: Prometheus 데이터를 Grafana 대시보드로 시각화
2. **알림 규칙 동적 구성**: 런타임에 알림 규칙 추가/제거 API
3. **메트릭 보관**: 장기 메트릭 데이터 저장 및 분석
4. **Health Check 강화**: 의존 서비스(Git, LLM) 상태 확인

## 결론

프로메테우스 기반 모니터링과 Slack/Email 알림 시스템을 통해 서버 상태를 실시간으로 모니터링하고 문제 발생 시 즉시 대응할 수 있는 인프라가 구축되었습니다.
