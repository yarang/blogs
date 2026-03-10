+++
title = "[blog-api-server] Monitoring Dashboard and Alerting System"
slug = "2026-03-03-002-blog-api-server-monitoring-alerting"
date = 2026-03-03T14:53:47+09:00
draft = false
tags = ["blog-api-server", "monitoring", "prometheus", "alerting", "Python"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [blog-api-server] Monitoring Dashboard and Alerting System

## Overview

A Prometheus-based monitoring system and Slack/Email alerting have been added to blog-api-server, enabling real-time server status tracking and immediate response to issues.

## Monitoring Architecture

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

## Prometheus Metrics

### Basic HTTP Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, endpoint, status | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency distribution |
| `http_errors_total` | Counter | method, endpoint, status | Total error count |
| `active_requests` | Gauge | - | Current active requests |

### Business Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `git_operations_total` | Counter | operation, status | Git operation count |
| `git_operation_duration_seconds` | Histogram | operation | Git operation duration |
| `translation_requests_total` | Counter | source_lang, target_lang, status | Translation request count |
| `translation_duration_seconds` | Histogram | - | Translation duration |
| `post_operations_total` | Counter | operation, language, status | Post operation count |

### Metrics Collection Code

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

# Auto-collection in middleware
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

## Alerting System

### Alert Rules

| Rule Name | Condition | Severity | Cooldown |
|-----------|-----------|----------|----------|
| High Error Rate | error_rate > 5% | WARNING | 5 min |
| Critical Error Rate | error_rate > 20% | CRITICAL | 1 min |
| Slow Response Time | avg_response_time > 2000ms | WARNING | 10 min |
| High Slow Request Rate | slow_request_rate > 10% | WARNING | 5 min |

### Alert Channels

**Slack Webhook**
- Supports all severity levels
- Color-coded severity (INFO: green, WARNING: orange, ERROR: red, CRITICAL: dark red)

**Email**
- CRITICAL level only
- SMTP-based email delivery

### AlertManager Code

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

## Dashboard Configuration

### Monitoring Endpoints

| Path | Auth | Description |
|------|------|-------------|
| `/health` | Not Required | Server health check |
| `/metrics` | Required | JSON format metrics |
| `/metrics/prometheus` | Not Required | Prometheus format metrics |
| `/metrics/reset` | Required | Reset metrics |
| `/dashboard` | Not Required | Web dashboard |
| `/alerts/rules` | Required | Alert rules list |
| `/alerts/send` | Required | Manual alert send |

### Request Tracking Middleware

```python
# middleware.py
class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()

        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # Add tracking info to response headers
        response.headers["X-Process-Time"] = f"{process_time:.2f}"
        response.headers["X-Request-ID"] = request_id

        return response
```

## Environment Variables

```bash
# Slack Alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Email Alerts
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=your-email@gmail.com
ALERT_TO_EMAILS=admin@example.com,ops@example.com

# Threshold Settings
SLOW_REQUEST_THRESHOLD=1000  # 1 second
VERY_SLOW_THRESHOLD=3000     # 3 seconds
MAX_BODY_LOG_LENGTH=1000
```

## Future Plans

1. **Grafana Integration**: Visualize Prometheus data in Grafana dashboard
2. **Dynamic Alert Rules**: API to add/remove alert rules at runtime
3. **Metrics Retention**: Long-term metrics storage and analysis
4. **Enhanced Health Checks**: Dependency service (Git, LLM) status checks

## Conclusion

With Prometheus-based monitoring and Slack/Email alerting, infrastructure is now in place for real-time server monitoring and immediate incident response.


---

**Korean Version:** [한국어 버전](/ko/post/2026-03-03-002-blog-api-server-monitoring-alerting/)