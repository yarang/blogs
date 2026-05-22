+++
title = "ZeroClaw 멀티 에이전트 시스템: Docker Compose를 활용한 로컬 테스트 환경 구축 가이드"
date = 2026-05-22T09:01:21+09:00
draft = false
tags = ["ZeroClaw", "Multi-Agent", "Rust", "Docker", "MCP", "DevOps"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# ZeroClaw 멀티 에이전트 시스템: Docker Compose를 활용한 로컬 테스트 환경 구축 가이드

최근 **[ZeroClaw]** 프로젝트를 통해 고성능 Rust 에이전트 런타임과 멀티 에이전트 아키텍처를 설계하며, 개별 에이전트의 격리성과 통신 안정성의 중요성을 실감했습니다. 특히 **[blog-api-server]**와 같이 외부 API와 연동되는 MCP(Model Context Protocol) 클라이언트를 개발할 때, 로컬 환경에서 실제 운영 환경과 유사한 구조를 갖춰 테스트하는 것은 필수적입니다.

이번 포스트에서는 복잡한 멀티 에이전트 시스템을 로컬에서 쉽게 실행하고 디버깅할 수 있도록 **Docker Compose**를 활용한 테스트 환경 구축 방법을 공유합니다. 본 가이드는 Linux 환경(예: Ubuntu 16.04에서 FreeBSD로 이전 중인 서버 등)을 기반으로 하지만, Windows와 macOS에서도 동일하게 적용 가능합니다.

## 1. 아키텍처 설계: 마이크로서비스형 에이전트 구조

ZeroClaw의 핵심은 파일 기반 아키텍처와 게이트웨이 패턴을 차용한 통신 플랫폼입니다. 각 에이전트를 독립된 마이크로서비스로 간주하고, 이들을 Docker 컨테이너로 격리합니다.

### 구성 요소
*   **Agent Container**: Rust로 작성된 개별 에이전트 (ZeroClaw Runtime 기반)
*   **Gateway Container**: 외부 요청을 내부 에이전트로 라우팅하는 Nginx 또는 Envoy
*   **Message Broker (Optional)**: RabbitMQ 또는 Redis (비동기 통신 필요 시)

## 2. Dockerfile 작성: Rust 에이전트 최적화

Rust 애플리케이션은 컴파일 시간이 오래 걸리므로, **Multi-stage build**를 사용하여 최종 이미지 크기를 줄이고 빌드 캐싱을 최적화해야 합니다.

```dockerfile
# Dockerfile

# 1. Build Stage
FROM rust:1.75-slim as builder

WORKDIR /app

# 의존성 캐싱을 위해 Cargo.toml과 Cargo.lock 먼저 복사
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# 실제 소스 코드 복사 및 빌드
COPY src ./src
RUN touch src/main.rs && cargo build --release

# 2. Runtime Stage
FROM debian:bookworm-slim

# 런타임 의존성 설치 (예: OpenSSL)
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 빌드된 바이너리 복사
COPY --from=builder /app/target/release/zero-claw-agent /app/agent

# 실행 권한 부여
RUN chmod +x /app/agent

# 포트 노출 (MCP 통신용)
EXPOSE 8080

CMD ["/app/agent"]
```

## 3. Docker Compose로 오케스트레이션 구성

`docker-compose.yml` 파일을 사용하여 여러 에이전트와 네트워크를 정의합니다. 이를 통해 `docker-compose up` 하나로 전체 시스템을 기동할 수 있습니다.

```yaml
# docker-compose.yml
version: '3.8'

services:
  # 메시지 브로커 (선택 사항, 통신 프로토콜에 따라 사용)
  redis:
    image: redis:7-alpine
    container_name: zero-claw-redis
    ports:
      - "6379:6379"
    networks:
      - zero-claw-net

  # Agent 1: Blog Handler (blog-api-server 역할)
  blog-agent:
    build:
      context: ./services/blog-agent
      dockerfile: Dockerfile
    container_name: zero-claw-blog-agent
    environment:
      - AGENT_ID=blog-agent-01
      - LOG_LEVEL=debug
      - MCP_SERVER_URL=http://mock-api:3000
    depends_on:
      - redis
    networks:
      - zero-claw-net
    restart: unless-stopped

  # Agent 2: Monitor (Cloud Monitor 역할)
  monitor-agent:
    build:
      context: ./services/monitor-agent
      dockerfile: Dockerfile
    container_name: zero-claw-monitor-agent
    environment:
      - AGENT_ID=monitor-agent-01
    depends_on:
      - redis
    networks:
      - zero-claw-net
    restart: unless-stopped

  # Gateway (Discord MCP Gateway 역할)
  gateway:
    image: nginx:alpine
    container_name: zero-claw-gateway
    ports:
      - "8080:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - blog-agent
      - monitor-agent
    networks:
      - zero-claw-net

networks:
  zero-claw-net:
    driver: bridge
```

## 4. 실행 및 테스트

이제 다음 명령어로 전체 시스템을 실행할 수 있습니다.

```bash
# 빌드 및 백그라운드 실행
docker-compose up --build -d

# 로그 확인 (특정 에이전트 집중 모니터링)
docker-compose logs -f blog-agent

# 트래픽 테스트 (Gateway를 통한 요청)
curl -X POST http://localhost:8080/api/v1/agent/blog/ping \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from ZeroClaw"}'
```

## 5. 마치며

이 구조를 활용하면 **[ZeroClaw]**의 멀티 에이전트 통신 프로토콜을 변경하거나, **[LLM]** 설정을 에이전트별로 주입하여 테스트하는 작업이 훨씬 수월해집니다. 특히 `docker-compose.yml`의 환경 변수만 수정하면 운영 환경 배포 스크립트와 로컬 테스트 환경을 거의 동일하게 유지할 수 있어 "It works on my machine" 문제를 해결할 수 있습니다.

다음 포스트에서는 이 환경에서 수집된 로그를 **[Loki]**나 **[Prometheus]**를 통해 시각화하는 방법을 다루어 보겠습니다.