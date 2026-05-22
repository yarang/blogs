+++
title = "ZeroClaw Multi-Agent System: A Guide to Building a Local Testing Environment with Docker Compose"
date = "2026-05-22T09:01:21+09:00"
draft = "false"
tags = ["ZeroClaw", "Multi-Agent", "Rust", "Docker", "MCP", "DevOps"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# ZeroClaw Multi-Agent System: A Guide to Building a Local Testing Environment with Docker Compose

Recently, while designing the high-performance Rust agent runtime and multi-agent architecture for the **[ZeroClaw]** project, I realized the importance of isolation and communication stability for individual agents. In particular, when developing MCP (Model Context Protocol) clients that interact with external APIs, such as **[blog-api-server]**, it is essential to test them in a local environment that mimics the actual production setup.

In this post, I will share how to build a testing environment using **Docker Compose** to easily run and debug complex multi-agent systems locally. This guide is based on a Linux environment (e.g., servers transitioning from Ubuntu 16.04 to FreeBSD), but it can be applied to Windows and macOS as well.

## 1. Architecture Design: Microservices-style Agent Structure

The core of ZeroClaw is a communication platform that adopts a file-based architecture and a gateway pattern. Each agent is treated as an independent microservice and isolated within a Docker container.

### Components
*   **Agent Container**: Individual agents written in Rust (based on ZeroClaw Runtime)
*   **Gateway Container**: Nginx or Envoy for routing external requests to internal agents
*   **Message Broker (Optional)**: RabbitMQ or Redis (if asynchronous communication is needed)

## 2. Dockerfile Creation: Optimizing Rust Agents

Since Rust applications have long compile times, **Multi-stage builds** should be used to reduce the final image size and optimize build caching.

```dockerfile
# Dockerfile

# 1. Build Stage
FROM rust:1.75-slim as builder

WORKDIR /app

# Copy Cargo.toml and Cargo.lock first for dependency caching
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# Copy actual source code and build
COPY src ./src
RUN touch src/main.rs && cargo build --release

# 2. Runtime Stage
FROM debian:bookworm-slim

# Install runtime dependencies (e.g., OpenSSL)
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built binary
COPY --from=builder /app/target/release/zero-claw-agent /app/agent

# Grant execute permissions
RUN chmod +x /app/agent

# Expose port (for MCP communication)
EXPOSE 8080

CMD ["/app/agent"]
```

## 3. Orchestration Configuration with Docker Compose

Use the `docker-compose.yml` file to define multiple agents and networks. This allows the entire system to be launched with a single `docker-compose up` command.

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Message Broker (Optional, used depending on the communication protocol)
  redis:
    image: redis:7-alpine
    container_name: zero-claw-redis
    ports:
      - "6379:6379"
    networks:
      - zero-claw-net

  # Agent 1: Blog Handler (acting as blog-api-server)
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

  # Agent 2: Monitor (Cloud Monitor role)
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

  # Gateway (Discord MCP Gateway role)
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

## 4. Running and Testing

You can now run the entire system with the following command:

```bash
# Build and run in background
docker-compose up --build -d

# Check logs (focused monitoring of a specific agent)
docker-compose logs -f blog-agent

# Traffic test (request via Gateway)
curl -X POST http://localhost:8080/api/v1/agent/blog/ping \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from ZeroClaw"}'
```

## 5. Conclusion

Leveraging this structure makes tasks like modifying **[ZeroClaw]**'s multi-agent communication protocol or injecting **[LLM]** configurations per agent much easier to test. In particular, by simply modifying environment variables in `docker-compose.yml`, you can maintain a nearly identical setup for production deployment scripts and local testing environments, thus resolving the "It works on my machine" problem.

In the next post, we will cover how to visualize the logs collected in this environment using **[Loki]** or **[Prometheus]**.