+++
title = "Rust로 구현하는 고성능 MCP 서버: ZeroMQ를 활용한 비동기 메시징"
date = 2026-05-10T09:01:24+09:00
draft = false
tags = ["Rust", "MCP", "ZeroMQ", "ZeroClaw", "Architecture", "Async"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Rust로 구현하는 고성능 MCP 서버: ZeroMQ를 활용한 비동기 메시징

최근 `ZeroClaw` 프로젝트를 진행하며 MCP(Model Context Protocol) 서버의 성능 한계를 뛰어넘을 필요성이 생겼습니다. 기존의 HTTP 기반 통신은 단일 요청-응답 패턴을 벗어나기 어렵고, 수많은 LLM 에이전트 간의 실시간 통신에는 병목이 발생하기 쉽습니다. 이번 포스트에서는 Rust의 강력한 비동기 처리 능력과 ZeroMQ(ØMQ)를 결용하여 초경량 초고속 MCP 서버를 구축하는 과정을 다룹니다.

## 왜 ZeroMQ인가? (TCP 소켓의 한계와 비교)

기존 `blog-api-server` 아키텍처에서는 표준 TCP 스트림을 사용하여 프로토콜을 직접 정의하고 사용했습니다. 하지만 멀티 에이전트 환경에서는 다음과 같은 문제가 발생합니다.

1.  **Connection Management(연결 관리) 복잡도**: 에이전트가 수십 개씩 늘어날 때, `Accept` 루프와 소켓 상태 관리를 위한 `unsafe` 코드나 복잡한 상태 머신(State Machine)이 필요합니다.
2.  **Message Enveloping(메시지 봉투)**: TCP는 바이트 스트림입니다. 메시지의 경계를 구분하기 위해 Length-Prefixing을 직접 구현해야 하며, 이는 버그의 주요 원인이 됩니다.

ZeroMQ는 이러한 하부 소켓 계층의 복잡성을 추상화하면서, TCP보다 빠른 "사용자 공간(User Space)" 전송 계층을 제공합니다. 특히 `ipc`(Inter-Process Communication) 프로토콜을 사용하면 로컬호스트 통신에서 네트워크 스택 오버헤드를 완전히 제거할 수 있습니다.

## 아키텍처 설계: ZeroMQ PUB/SUB 패턴

이번 구현에서는 에이전트 간 느슨한 결합을 위해 **Publish/Subscribe(PUB/SUB)** 패턴을 사용합니다. 하나의 에이전트가 상태를 변경(Publish)하면, 해당 토픽을 구독하는 다른 에이전트들에게 즉시 메시지가 브로드캐스트됩니다.

### 주요 의존성 (Cargo.toml)

Rust 생태계에서 ZeroMQ는 `zmq` 크레이트를 통해 사용할 수 있습니다. 비동기 런타임과의 통합을 위해 `tokio-zmq`를 사용할 수도 있지만, 순수 성능을 위해 `zmq`의 `poll` 기능을 활용하는 것이 더 안정적일 때가 많습니다.

```toml
[dependencies]
zmq = "0.10"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["full"] }
```

## 구현: 고성능 MCP Router

아래 코드는 간단한 메시지 브로커 역할을 하는 MCP Router의 구현 예제입니다. 이는 여러 LLM 에이전트(팀)가 서로 통신할 수 있는 중앙 허브 역할을 합니다.

### 1. 메시지 프로토콜 정의

먼저, 에이전트 간에 오가는 메시지 형식을 정의합니다. JSON 직렬화를 사용하여 호환성을 확보합니다.

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct McpMessage {
    pub source_id: String,
    pub target_topic: String,
    pub payload: String,
    pub timestamp: i64,
}
```

### 2. 비동기 ZeroMQ 컨텍스트 및 소켓 설정

ZeroMQ의 Context는 스레드 안전(Thread-safe)하므로, 애플리케이션 전역에서 하나만 생성하여 공유하는 것이 일반적입니다.

```rust
ouse std::time::SystemTime;
use zmq::{Context, Socket, SocketType};

struct McpRouter {
    context: Context,
    frontend: Socket, // Agents connect here
    // 필요시 다른 패턴의 소켓 추가 가능
}

impl McpRouter {
    fn new() -> Result<Self, zmq::Error> {
        let context = Context::new();
        let frontend = context.socket(SocketType::SUB)?;
        
        // 모든 메시지를 수신하도록 설정 (필터링 없음)
        frontend.set_subscribe(b"")?;
        
        Ok(McpRouter { context, frontend })
    }

    fn start(&self, endpoint: &str) -> Result<(), zmq::Error> {
        self.frontend.bind(endpoint)?;
        println!("[ZeroClaw Router] Listening on {}", endpoint);

        let mut msg = zmq::Message::new();
        loop {
            // Non-blocking receive를 위해 poll 사용 가능
            // 여기서는 간단한 blocking receive 예시
            match self.frontend.recv(&mut msg) {
                Ok(_) => {
                    let data = msg.as_str().unwrap();
                    // 메시지 파싱 및 라우팅 로직
                    if let Ok(mcp_msg) = serde_json::from_str::<McpMessage>(data) {
                        self.route_message(mcp_msg);
                    }
                }
                Err(e) => {
                    eprintln!("Receive Error: {}", e);
                }
            }
        }
    }

    fn route_message(&self, msg: McpMessage) {
        // 실제 라우팅 로직 구현
        println!("Routing from {} on topic {}", msg.source_id, msg.target_topic);
        // 예: 데이터베이스 저장, 다른 소켓으로 전달 등
    }
}
```

### 3. 에이전트 발행(Publisher) 구현

이제 개별 에이전트가 메시지를 보내는 코드를 작성해 보겠습니다. `tokio`와 함께 사용할 때는 별도의 스레드에서 ZeroMQ의 blocking 함수를 실행해야 비동기 런타임을 방해하지 않습니다.

```rust
use std::thread;

fn spawn_publisher_agent(id: &str, endpoint: &str) {
    let context = Context::new();
    let sender = context.socket(SocketType::PUB).expect("Failed to create PUB socket");
    sender.connect(endpoint).expect("Failed to connect to Router");

    // 별도 스레드에서 실행하여 Tokio 런타임과 분리
    thread::spawn(move || {
        let counter = 0..100;
        for i in counter {
            let msg = McpMessage {
                source_id: id.to_string(),
                target_topic: "general".to_string(),
                payload: format!("Message #{} from agent {}", i, id),
                timestamp: SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs() as i64,
            };

            let json_str = serde_json::to_string(&msg).unwrap();
            // ZeroMQ는 전송 실패 시 자동으로 재시도하거나 큐에 쌓음 (High-water mark 설정 필요 시)
            sender.send(json_str.as_bytes(), 0).expect("Failed to send");
            
            thread::sleep(std::time::Duration::from_millis(100));
        }
    });
}
```

## 성능 최적화 및 IPC 활용

Rust ZeroMQ 서버의 진정한 힘은 **IPC(Inter-Process Communication)** 트랜스포트를 사용할 때 발휘됩니다. TCP를 사용하면 패킷이 네트워크 스택을 거쳐 루프백(Loopback) 되지만, IPC는 Unix Domain Socket이나 Windows Named Pipes를 사용하여 메모리 복사 수준에 가까운 속도로 통신합니다.

`ipc` 프로토콜을 사용하려면 엔드포인트를 다음과 같이 변경하면 됩니다.

```rust
// TCP 대신 IPC 사용
let endpoint = "ipc:///tmp/mcp_router.ipc";
router.start(endpoint);
```

Bun이나 Zig 같은 최신 언어들이 시스템 레벨 최적화를 통해 주목받는 것처럼, Rust와 ZeroMQ의 조합은 LLM 애플리케이션의 "시스템 버스"를 구축하는 데 있어 가장 강력한 도구입니다.

## 결론

이번 글에서는 `ZeroClaw` 프로젝트의 일환으로, Rust와 ZeroMQ를 사용하여 고성능 MCP 서버를 구축하는 방법을 살펴보았습니다. 단순한 HTTP 요청을 넘어, 에이전트 간 실시간 메시징이 필요한 환경에서 이 아키텍처는 확장성과 성능 면에서 큰 이점을 제공합니다.

다음 포스트에서는 이 메시징 시스템에 안정성을 더해주는 Circuit Breaker 패턴과 에러 핸들링 전략을 다루겠습니다.

### 참고 자료
- [ZeroMQ Guide - The Framework](https://zeromq.org/get-started/)
- [Tokio Zmq](https://github.com/zeromq/tokio-zmq)
- [ZeroClaw GitHub](https://github.com/your-org/zeroclaw)
