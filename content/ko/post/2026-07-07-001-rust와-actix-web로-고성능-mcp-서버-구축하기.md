+++
title = "Rust와 Actix Web로 고성능 MCP 서버 구축하기"
date = 2026-07-07T09:00:40+09:00
draft = false
tags = ["Rust", "Actix-web", "MCP", "ZeroClaw", "Architecture"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Rust와 Actix Web로 고성능 MCP 서버 구축하기

최근 [ZeroClaw](/tag/zeroclaw) 프로젝트를 진행하며 멀티 에이전트 시스템의 퍼포먼스 최적화에 대해 깊게 고민하게 되었습니다. 기존 Python 기반의 MCP 서버들은 개발 속도는 빠르지만, 동시성 높은 요청을 처리할 때 GIL(Global Interpreter Lock) 한계로 인해 병목이 발생하곤 했습니다.

이번 글에서는 Rust의 강력한 웹 프레임워크인 **Actix Web**을 사용하여, 고성능이 요구되는 MCP(Model Context Protocol) 서버를 구축하는 구체적인 방법을 공유하고자 합니다. 특히 단순한 API 서버를 넘어, 에이전트 간 통신을 위한 이벤트 드리븐 아키텍처를 어떻게 구현할 수 있는지 집중적으로 다루겠습니다.

## 왜 Rust인가? ZeroClaw의 선택

Rust는 메모리 안전성을 컴파일 타임에 보장하면서도 C++ 수준의 성능을 냅니다. 에이전트 런타임과 같이 24시간 돌아가야 하고, 수많은 LLM 토큰 처리 및 I/O 작업이 발생하는 환경에서는 이 안전성과 성능이 필수적입니다.

*   **Zero-cost Abstraction:** 고수준의 추상화를 사용하면서도 실행 속도를 저하시키지 않습니다.
*   **Fearless Concurrency:** 악명 높은 데이터 레이스(Data Race)를 컴파일러가 잡아줍니다.
*   **Async/Await:** Tokio 런타임 기반의 비동기 처리는 높은 동시성 처리에 유리합니다.

## 핵심 아키텍처: Actix Web + Message Passing

단순히 HTTP 요청을 받는 것을 넘어, MCP 서버는 다음과 같은 능력이 필요합니다.
1.  HTTP 요청 처리 (JSON-RPC over stdio or SSE)
2.  내부 에이전트 간 메시지 전달
3.  백그라운드 작업 (예: 로그 수집, 리소스 정리)

Actix Web의 **Actor 모델**은 이 세 가지를 모두 만족시키기에 최적의 구조입니다. HTTP 요청을 받는 `HttpServer`와 실제 로직을 처리하는 `MyAgent` Actor를 분리하여 설계해보겠습니다.

## 실전 코드 예제

### 1. 프로젝트 설정 (Cargo.toml)

먼저 의존성을 추가합니다. `serde`는 직렬화를, `tokio`는 비동기 런타임을 위해 필요합니다.

```toml
[dependencies]
actix-web = "4.4"
actix-rt = "2.9"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

### 2. 에이전트 액터(Actor) 정의

MCP 요청을 처리하는 주체인 Agent를 Actor로 정의합니다. `Handler` 트레이트를 구현하여 비동기 메시지를 처리합니다.

```rust
use actix::prelude::*;
use serde::{Deserialize, Serialize};

// MCP 요청 메시지 구조체
#[derive(Message, Deserialize, Serialize)]
#[rtype(result = "String")]
pub struct McpRequest {
    pub tool_name: String,
    pub params: String,
}

// 고성능 에이전트 액터 구조체
pub struct ZeroClawAgent {
    pub state: String, // 에이전트의 상태 저장
}

impl Actor for ZeroClawAgent {
    type Context = Context<Self>;

    fn started(&mut self, _ctx: &mut Self::Context) {
        println!("ZeroClaw Agent가 시작되었습니다.");
    }
}

// 메시지 처리 핸들러 구현
impl Handler<McpRequest> for ZeroClawAgent {
    type Result = String;

    fn handle(&mutself, msg: McpRequest, _ctx: &mut Self::Context) -> Self::Result {
        // 여기에 실제 툴 실행 로직이 들어갑니다.
        // 예: 파일 읽기, LLM 호출 등
        println!("툴 실행: {}", msg.tool_name);
        
        // 결과 반환
        format!("Executed {} with {}", msg.tool_name, msg.params)
    }
}
```

### 3. HTTP 엔드포인트와 Actor 연결

이제 Actix Web의 경로(route)와 위에서 만든 Actor를 연결합니다. 클라이언트의 HTTP 요청을 Actor의 메시지로 변환하여 전달하는 과정이 핵심입니다.

```rust
use actix_web::{web, App, HttpResponse, HttpServer};
use actix::Addr;

// 상태(State) 관리를 위한 구조체
struct AppState {
    agent_addr: Addr<ZeroClawAgent>,
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // 에이전트 액터 생성
    let agent = ZeroClawAgent { state: "initialized".to_string() }.start();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(AppState {
                agent_addr: agent.clone(), // 주소를 복사하여 공유
            }))
            .route("/mcp/invoke", web::post().to(invoke_tool))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}

// HTTP 핸들러 함수
async fn invoke_tool(
    req: web::Json<McpRequest>,
    data: web::Data<AppState>,
) -> HttpResponse {
    // Agent에게 메시지 전송 (비동기)
    let result = data.agent_addr
        .send(req.into_inner()) // Json -> McpRequest 변환 후 전송
        .await; // 응답 대기

    match result {
        Ok(res) => HttpResponse::Ok().body(res),
        Err(_) => HttpResponse::InternalServerError().body("Agent Error"),
    }
}
```

## 확장 가능성: 파일 기반 아키텍처와 통합

이전에 논의된 [Multi-Agent 파일 기반 아키텍처](/blog/multi-agent-file-arch)와 결합하면, 이 서버는 단순히 메모리에만 있는 것이 아니라 영구적인 스토리지와 협업할 수 있습니다.

*   **Watchdog 태스크 추가:** Actix의 `Context`에 `run_interval`을 추가하여 주기적으로 디스크의 명령 파일(JSON 등)을 감시하고, 변경 시 `McpRequest` 메시지를 자기 자신에게 보내는 방식입니다.
*   **이점:** 웹 요청뿐만 아니라 외부 스크립트나 Cron job 등 다양한 방식으로 에이전트를 제어할 수 있습니다.

## 결론

Rust와 Actix Web을 활용하면, 단순히 "빠른" 서버를 넘어 **안정적이고 확장 가능한 에이전트 런타임**을 구축할 수 있습니다. 위 코드는 MCP 서버의 가장 기초적인 골격이지만, 이를 기반으로 로깅 시스템([blog-api-server 로깅 개선](/blog/blog-api-logging))을 붙이고, 복잡한 통신 프로토콜을 구현하여 [ZeroClaw](/tag/zeroclaw)와 같은 고성능 시스템을 완성할 수 있습니다.

Python에 익숙한 개발자라면 처음에는 빌림(Ownership)과 라이프타임 개념이 어렵게 느껴질 수 있지만, 한 번 아키텍처를 잡으면 그 이후의 유지보수 비용과 성능 이득은 상상 이상일 것입니다.
