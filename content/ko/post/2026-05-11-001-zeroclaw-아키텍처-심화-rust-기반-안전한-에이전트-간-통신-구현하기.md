+++
title = "ZeroClaw 아키텍처 심화: Rust 기반 안전한 에이전트 간 통신 구현하기"
date = 2026-05-11T09:01:26+09:00
draft = false
tags = ["Rust", "ZeroClaw", "Multi-Agent", "MCP", "Architecture", "Security"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# ZeroClaw 아키텍처 심화: Rust 기반 안전한 에이전트 간 통신 구현하기

안녱하세요! ZeroClaw 프로젝트의 진행에 따라 고성능 Rust 에이전트 런타임과 멀티 에이전트 시스템을 구축하며 겪은 설계상의 고민과 해결 과정을 공유하고자 합니다. 최근 'Obsidian 플러그인을 악용한 원격 접속 트로이어나(RAT)' 사건과 같은 보안 이슈들은 플러그인 및 에이전트 시스템에서 **보안(Security)**과 **신뢰성(Trust)**이 얼마나 중요한지를 다시금 상기시켜 줍니다.

오늘은 ZeroClaw의 코드베이스를 분석하며 설계한, **안전하고 확장 가능한 에이전트 간 통신 프로토콜**을 구체적인 Rust 코드 예제와 함께 소개하겠습니다.

---

## 1. 서론: 보안을 고려한 에이전트 통신의 필요성

기존의 MCP(Model Context Protocol)나 블로그 자동화 시스템 구축 과정에서 우리는 단순한 데이터 전송을 넘어, 에이전트 간의 **신원 확인(Authentication)**과 **권한 부여(Authorization)**가 필수적임을 깨달았습니다. 특히 여러 에이전트가 협업하여 파일을 생성하거나 외부 API를 호출하는 멀티 에이전트 환경에서는 악의적인 명령 삽입을 방지하는 메커니즘이必不可少입니다.

ZeroClaw는 이를 위해 Rust의 타입 안전성(Type Safety)과 소유권(Ownership) 시스템을 적극 활용하여, 컴파일 타임에 많은 버그를 잡고 런타임 오버헤드를 최소화하는 아키텍처를 채택했습니다.

## 2. 통신 프로토콜 설계: IPC와 메시지 큐

ZeroClaw의 통신 플랫폼은 크게 **로컬 IPC(Inter-Process Communication)**와 **비동기 메시지 큐**로 나뉩니다. 로그 시스템 개선 과정에서 얻은 경험을 바탕으로, 모든 통신은 비동기(async)로 처리되며 각 에이전트의 독립성을 보장합니다.

### 주요 설계 원칙
1.  **Zero-Copy Serialization:** `serde`와 `bincode`를 활용하여 데이터 직렬화 오버헤드를 최소화합니다.
2.  **Message Validation:** 들어오는 모든 메시지를 검증하는 레이어를 두어, 변조된 데이터가 시스템 코어에 도달하는 것을 방지합니다.
3.  **Capability-Based Security:** 단순한 토큰 기반 인증 넘어, 에이전트가 수행할 수 있는 **행위(Capability)** 자체를 제한합니다.

## 3. Rust로 구현하는 안전한 메시징 핸들러

이제 실제 코드를 통해 어떻게 구현했는지 살펴보겠습니다. 이 예제는 `tokio`를 기반으로 하며, 안전한 메시지 전달을 위한 기본 구조를 보여줍니다.

### 3.1 메시지 정의 및 검증

먼저, 에이전트 간에 오가는 데이터 구조를 정의하고, `validator` 크레이트를 사용하여 입력값을 검증합니다.

```rust
// message.rs
use serde::{Deserialize, Serialize};
use validator::Validate;

/// 에이전트 간 통신 메시지 타입
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AgentMessage {
    TaskRequest { id: String, payload: TaskPayload },
    TaskResponse { id: String, result: String },
    Heartbeat,
}

/// 작업 페이로드 (검증 로직 포함)
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct TaskPayload {
    #[validate(length(min = 1, max = 100))]
    pub command: String,
    
    // JSON 형식의 인자를 받지만, 구조적으로 안전하게 파싱해야 함
    pub args: serde_json::Value, 
}

impl AgentMessage {
    /// 바이트 배열로부터 안전하게 메시지를 역직렬화합니다.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, Box<dyn std::error::Error>> {
        // 1. 기본 직렬화 검증
        let msg: AgentMessage = bincode::deserialize(bytes)?;
        
        // 2. 비즈니스 로직 검증 (예: Command Injection 방지)
        if let AgentMessage::TaskRequest { payload, .. } = &msg {
            payload.validate()?; // validator 크레이트 사용
            
            // 보안: 허용되지 않는 쉘 명령어 필터링 예시
            if payload.command.contains("rm ") || payload.command.contains("sudo") {
                return Err("Blocked potentially dangerous command".into());
            }
        }
        
        Ok(msg)
    }
}
```

### 3.2 액터 모델 기반 에이전트 구조

각 에이전트는 자신의 상태를 가지며, 메시지를 받아 처리하는 `Actor` 패턴을 따릅니다. Rust의 `tokio::sync::mpsc` 채널을 사용하여 메일박스를 구현합니다.

```rust
// agent.rs
use tokio::sync::mpsc;
use super::message::AgentMessage;

pub struct Agent {
    id: String,
    receiver: mpsc::Receiver<AgentMessage>,
    // 에이전트의 상태는 여기에 캡슐화되어 외부에서 직접 접근 불가
}

impl Agent {
    pub fn new(id: String, receiver: mpsc::Receiver<AgentMessage>) -> Self {
        Self { id, receiver }
    }

    /// 에이전트의 메인 루프
    pub async fn run(mut self) {
        println!("[{}] Agent started", self.id);
        
        while let Some(msg) = self.receiver.recv().await {
            if let Err(e) = self.handle_message(msg).await {
                eprintln!("[{}] Error handling message: {:?}", self.id, e);
            }
        }
    }

    async fn handle_message(&self, msg: AgentMessage) -> Result<(), Box<dyn std::error::Error>> {
        match msg {
            AgentMessage::TaskRequest { id, payload } => {
                println!("[{}] Executing task {}: {}", self.id, id, payload.command);
                // 여기에 실제 작업 실행 로직 (예: LLM 호출, 파일 쓰기 등)
                // 안전 장치: 샌드박스 환경에서 실행하거나 권한을 제한합니다.
            },
            AgentMessage::Heartbeat => {
                // 생존 신호 처리
            },
            _ => return Err("Unknown message type".into()),
        }
        Ok(())
    }
}
```

### 3.3 런타임 및 메시지 라우팅

마지막으로, 여러 에이전트를 생성하고 메시지를 라우팅하는 간단한 런타임 시스템입니다.

```rust
// runtime.rs
use tokio::sync::mpsc;
use std::collections::HashMap;
use super::agent::Agent;
use super::message::AgentMessage;

pub struct Runtime {
    agents: HashMap<String, mpsc::Sender<AgentMessage>>,
}

impl Runtime {
    pub fn new() -> Self {
        Self { agents: HashMap::new() }
    }

    pub fn spawn_agent(&mut self, id: &str) {
        let (tx, rx) = mpsc::channel(32);
        let agent = Agent::new(id.to_string(), rx);
        
        // 에이전트를 별도의 태스크로 실행
        tokio::spawn(agent.run());
        
        self.agents.insert(id.to_string(), tx);
        println!("Runtime: Agent '{}' spawned", id);
    }

    pub async fn broadcast(&self, msg: AgentMessage) {
        for (id, tx) in self.agents.iter() {
            if let Err(e) = tx.send(msg.clone()).await {
                eprintln!("Failed to send to {}: {:?}", id, e);
            }
        }
    }
}
```

## 4. 마무리 및 다음 단계

위에서 구현한 코드는 ZeroClaw 멀티 에이전트 시스템의 핵심인 **'안전한 통신'**과 **'격리된 상태 관리'**를 보여줍니다. Obsidian 플러그인 사건처럼, 외부 입력이나 스크립트를 실행하는 시스템은 언제나 공격의 대상이 될 수 있습니다.

ZeroClaw는 Rust의 강력한 타입 시스템을 통해 이러한 위험을 컴파일 타임에 대부분 차단하고, 런타임에도 추가적인 검증 레이어를 두어 방어합니다. 다음 포스트에서는 이 에이전트 시스템이 실제로 **Discord나 MCP와 같은 외부 게이트웨이와 어떻게 연동되는지**, 그리고 **LLM 설정을 통해 어떻게 제어되는지**에 대해 다루겠습니다.

지금까지 ZeroClaw의 아키텍처 설계 현황을 공유했습니다. 고성능이면서도 안전한 에이전트 시스템을 구축하려는 분들께 도움이 되기를 바랍니다!

---

**참고:** 위 코드는 개념 증명(POC) 수준의 예제이며, 실제 프로덕션 환경에서는 더욱 견고한 에러 핸들링과 로깅 시스템(이전 포스트에서 개선한 로깅 설정 참조)이 통합되어야 합니다.