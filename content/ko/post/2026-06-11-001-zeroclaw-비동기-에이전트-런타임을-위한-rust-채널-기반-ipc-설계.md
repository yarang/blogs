+++
title = "[ZeroClaw] 비동기 에이전트 런타임을 위한 Rust 채널 기반 IPC 설계"
date = 2026-06-11T09:00:42+09:00
draft = false
tags = ["Rust", "ZeroClaw", "Multi-Agent", "Architecture", "Async"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [ZeroClaw] 비동기 에이전트 런타임을 위한 Rust 채널 기반 IPC 설계

안녕하세요. 최근 **ZeroClaw** 프로젝트의 핵심인 '멀티 에이전트 아키텍처'를 고도화하면서, 단순한 메시지 전달을 넘어 **고성능 비동기 통신(IPC, Inter-Process Communication)** 환경을 구축한 경험을 공유하고자 합니다.

기존의 동기적 통신 방식은 에이전트 간 결합도를 높이고, 한 에이전트의 장애가 전체 시스템을 멈추게 만드는 병목 구간(Single Point of Failure)이 되었습니다. 이를 해결하기 위해 Rust의 강력한 동시성 기능인 **`tokio` 런타임**과 **MPSC(Multi-Producer, Single-Consumer) 채널**을 활용하여 이벤트 기반의 느슨한 결합 아키텍처를 설계했습니다.

이번 포스트에서는 에이전트 런타임의 효율성을 극대화하기 위해 채널을 어떻게 설계하고 구현했는지, 실제 코드와 함께 살펴보겠습니다.

## 1. 기존 아키텍처의 문제점과 비동기 설계의 필요성

이전까지의 ZeroClaw 에이전트는 메시지를 요청(Request)하고 응답(Response)을 기다리는 **동기식 RPC** 패턴을 주로 사용했습니다. 하지만 에이전트가 수십 개로 늘어나고 복잡한 작업(예: 파일 기반 아키텍처 분석, 대규모 로그 처리)을 수행하게 되면서 다음과 같은 문제가 발생했습니다.

1.  **블로킹(Blocking) 문제:** A 에이전트가 B 에이전트의 응답을 기다리는 동안, A 에이전트는 다른 작업을 수행할 수 없습니다.
2.  **복잡한 에러 전파:** 특정 에이전트가 뻗거나 타임아웃이 발생했을 때, 호출 체인 상위에 있는 에이전트들로 에러를 전달하기 복잡했습니다.

이를 해결하기 위해 우리는 **"에이전트는 메시지를 보내고 즉시 다른 작업을 수행한다, 처리된 결과는 이벤트로 수신한다"**는 비동기 패턴을 채택했습니다.

## 2. Rust의 `tokio::sync::mpsc`를 활용한 이벤트 루프 구조

Rust의 `tokio` 크레이트가 제공하는 MPSC 채널은 높은 처리량과 낮은 지연 시간을 보장하며, 에이전트 런타임에 최적화되어 있습니다. 각 에이전트는 자신만의 **Task(작업 단위)**를 가지며, 이는 `tokio::spawn`을 통해 독립적으로 실행됩니다.

### 핵심 설계 포인트

*   **Message Bus:** 각 에이전트는 송신자(`tx`)와 수신자(`rx`)를 보유합니다.
*   **Event Loop:** 수신자(`rx`)는 무한 루프(`loop`)를 돌며 메시지가 도착할 때까지 비동기적으로 대기(`recv()`)합니다.

## 3. 실전 코드: 구체적인 구현 예제

이제 실제로 ZeroClaw 런타임 내에서 에이전트들이 통신하는 코드를 작성해 보겠습니다.

### Step 1: 메시지 프로토콜 정의

먼저 에이전트 간 주고받을 데이터 구조를 정의해야 합니다. 이때 `Enum`을 사용하여 메시지의 타입을 안전하게 관리하는 것이 좋습니다.

```rust
// Cargo.toml dependencies
// [dependencies]
// tokio = { version = "1", features = ["full"] }
// serde = { version = "1", features = ["derive"] }

use tokio::sync::mpsc;
use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize)]
enum AgentMessage {
    TaskAssigned { task_id: String, description: String },
    TaskCompleted { task_id: String, result: String },
    StatusCheck,
}
```

### Step 2: 에이전트 구조체 및 러너(Runner) 구현

각 에이전트는 고유 ID와 수신자(`rx`)를 가집니다. `run` 메서드는 에이전트의 생명주기를 관리하는 핵심 함수입니다.

```rust
struct Agent {
    id: String,
    rx: mpsc::Receiver<AgentMessage>,
}

impl Agent {
    fn new(id: String, rx: mpsc::Receiver<AgentMessage>) -> Self {
        Self { id, rx }
    }

    async fn run(mut self) {
        println!("[{}] Agent started. Listening for messages...", self.id);
        
        // 메시지 수신 대기 (비동기)
        while let Some(msg) = self.rx.recv().await {
            match msg {
                AgentMessage::TaskAssigned { task_id, description } => {
                    println!("[{}] Received task: {} - {}", self.id, task_id, description);
                    // 실제 로직 처리 (예: 파일 분석, 외부 API 호출)
                    // 여기서는 예시를 위해 1초 대기 후 완료 메시지를 전송한다고 가정합니다.
                }
                AgentMessage::StatusCheck => {
                    println!("[{}] Status: Active", self.id);
                }
                _ => {}
            }
        }
        println!("[{}] Agent shutting down.", self.id);
    }
}
```

### Step 3: 메인 런타임 및 채널 연결

메인 함수에서는 여러 에이전트를 생성하고 채널을 연결한 뒤, `tokio::spawn`을 통해 병렬로 실행시킵니다.

```rust
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. 채널 생성 (용량 32)
    let (tx, rx) = mpsc::channel::<AgentMessage>(32);

    // 2. 에이전트 생성 및 실행 (비동기 태스크로 분리)
    let agent_handle = {
        let agent = Agent::new("Agent-A".to_string(), rx);
        tokio::spawn(async move {
            agent.run().await;
        })
    };

    // 3. 메인 런타임에서 메시지 송신
    // 다른 에이전트나 API 서버가 이 tx를 사용하여 메시지를 보낼 수 있습니다.
    
    // 작업 할당
    let _ = tx.send(AgentMessage::TaskAssigned {
        task_id: "T-101".to_string(),
        description: "Analyze server logs".to_string(),
    }).await;

    // 상태 확인
    let _ = tx.send(AgentMessage::StatusCheck).await;

    // 4. 에이전트가 작업을 마칠 때까지 대기 (실제 환경에서는 계속 실행됨)
    drop(tx); // 송신자 종료 -> 채널 닫힘 -> 에이전트 루프 종료 조건 성립
    
    agent_handle.await?;
    
    Ok(())
}
```

## 4. ZeroClaw 프로젝트 적용 효과

위와 같은 구조를 ZeroClaw 런타임에 적용한 결과 다음과 같은 이점을 얻었습니다.

1.  **병렬 처리 성능 향상:** 에이전트가 자신만의 `tokio` 태스크 내에서 실행되므로, CPU 코어를 효율적으로 활용할 수 있었습니다.
2.  **결합도 감소:** 메인 로직이 특정 에이전트의 내부 구현을 알 필요 없이, 단순히 `tx.send`만 호출하면 됩니다.
3.  **그레이스풀 셧다운(Graceful Shutdown):** `drop(tx)`를 통해 채널을 닫으면, 에이전트는 더 이상 메시지가 오지 않음을 감지하고 자연스럽게 `while let` 루프를 빠져나와 종료합니다.

## 마치며

Rust의 소유권(Ownership) 시스템과 `tokio`의 비동기 추상화는 멀티 에이전트 시스템 구축에 있어 강력한 무기가 됩니다. 다음 포스트에서는 이 에이전트들이 **파일 기반 아키텍처**와 결합하여 상태를 어떻게 영속화하는지 다루도록 하겠습니다.

ZeroClaw의 고성능 에이전트 런타임 개발은 계속됩니다.