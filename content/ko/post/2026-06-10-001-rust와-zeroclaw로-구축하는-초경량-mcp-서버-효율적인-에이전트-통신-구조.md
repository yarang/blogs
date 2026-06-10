+++
title = "Rust와 ZeroClaw로 구축하는 초경량 MCP 서버: 효율적인 에이전트 통신 구조"
date = 2026-06-10T09:00:57+09:00
draft = false
tags = ["Rust", "ZeroClaw", "MCP", "Multi-Agent", "Architecture"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Rust와 ZeroClaw로 구축하는 초경량 MCP 서버: 효율적인 에이전트 통신 구조

최근 'Grit: Rewriting Git in Rust with Agents' 기사에서도 확인할 수 있듯, Rust 언어는 에이전트 시스템의 런타임으로서 그 가치를 재평가받고 있습니다. 우리 팀의 `ZeroClaw` 런타임 역시 고성능과 안전성을 목표로 개발 중이며, 이와 연계하여 MCP(Model Context Protocol) 서버를 어떻게 효율적으로 구축할지에 대한 고민이 깊어지고 있습니다.

기존의 무거운 Python 기반 서버나 복잡한 Node.js 아키텍처 대신, Rust의 병행성(concurrency)과 저지연성(low-latency)을 활용한 초경량 MCP 서버 구조를 제안합니다. 이 글에서는 `ZeroClaw` 아키텍처의 장점을 살리면서, 실무에서 바로 적용 가능한 Rust 기반 MCP 서버 예제를 작성해 보겠습니다.

## 1. ZeroClaw 아키텍처와 MCP의 결합

`ZeroClaw` 프로젝트의 핵심은 파일 기반 아키텍처 설계와 멀티 에이전트 통신 프로토콜의 효율화입니다. MCP 서버를 구축할 때 가장 중요한 점은 **데이터 직렬화/역직렬화(Serde)의 오버헤드를 줄이는 것**과 **비동기 요청 처리**입니다. 

Rust의 `tokio` 런타임과 `serde_json`을 활용하면, JSON 기반 MCP 프로토콜을 나노초(nanosecond) 단위의 오버헤드로 처리할 수 있습니다. 이는 특히 대규모 로그 처리나 모니터링 시스템(`[blog-api-server]` 경험)에서 필수적인 요소입니다.

## 2. 핵심 구조: 비동기 요청 라우팅

복잡한 의존성 없이, 표준 라이브러리와 몇 가지 필수 크레이트(crate)만으로 MCP 서버의 뼈대를 만들어 보겠습니다. 이 구조는 `ZeroClaw`의 에이전트 간 통신 패턴을 따르며, 단일 스레드가 아닌 멀티스레드 환경에서의 안전성을 보장합니다.

### 2.1. Cargo.toml 설정

먼저 프로젝트 의존성을 추가합니다.

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
hyper = { version = "0.14", features = ["full"] }
```

### 2.2. MCP 메시지 구조 정의

MCP는 기본적으로 JSON-RPC와 유사한 구조를 가집니다. 에이전트 간 통신 시 데이터의 무결성을 보장하기 위해 Rust의 타입 시스템을 적극 활용합니다.

```rustn// src/types.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct MCPRequest {
    pub jsonrpc: String, // 항상 "2.0"
    pub id: Option<String>,
    pub method: String,
    pub params: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MCPResponse {
    pub jsonrpc: String,
    pub id: Option<String>,
    pub result: Option<serde_json::Value>,
    pub error: Option<MCPError>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MCPError {
    pub code: i32,
    pub message: String,
}
```

## 3. 경량화된 요청 핸들러 구현

`ZeroClaw`의 철학처럼 불필요한 추상화 계층을 제거하고, 직관적인 핸들러를 작성합니다. 아래 코드는 들어오는 요청을 파싱하고, 메서드 이름에 따라 적절한 처리를 수행한 뒤 응답을 반환하는 흐름입니다.

```rustn// src/main.rs
use hyper::{Body, Request, Response, Server, StatusCode};
use hyper::service::{make_service_fn, service_fn};
use std::convert::Infallible;
use types::{MCPRequest, MCPResponse};

async fn handle_mcp_request(req: MCPRequest) -> MCPResponse {
    match req.method.as_str() {
        "tools/list" => {
            // 도구 목록 반환 예시
            MCPResponse {
                jsonrpc: "2.0".to_string(),
                id: req.id,
                result: Some(serde_json::json!({
                    "tools": [
                        { "name": "get_weather", "description": "Get current weather" },
                        { "name": "calculate", "description": "Perform math operations" }
                    ]
                })),
                error: None,
            }
        },
        "tools/call" => {
            // 실제 도구 실행 로직 (ZeroClaw Agent 호출 등)
            // params 검증 로직이 여기에 들어갑니다.
            println!("Agent executing with params: {:?}", req.params);
            MCPResponse {
                jsonrpc: "2.0".to_string(),
                id: req.id,
                result: Some(serde_json::json!({"status": "success"})),
                error: None,
            }
        },
        _ => {
            MCPResponse {
                jsonrpc: "2.0".to_string(),
                id: req.id,
                result: None,
                error: Some(types::MCPError {
                    code: -32601,
                    message: "Method not found".to_string(),
                }),
            }
        }
    }
}

async fn http_handler(req: Request<Body>) -> Result<Response<Body>, Infallible> {
    let whole_body = match hyper::body::to_bytes(req.into_body()).await {
        Ok(bytes) => bytes,
        Err(e) => {
            eprintln!("Error reading body: {}", e);
            return Ok(Response::builder()
                .status(StatusCode::INTERNAL_SERVER_ERROR)
                .body(Body::from("Internal Server Error"))
                .unwrap());
        }
    };

    // JSON 파싱
    let mcp_req: MCPRequest = match serde_json::from_slice(&whole_body) {
        Ok(req) => req,
        Err(_) => {
            return Ok(Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .body(Body::from("Invalid JSON"))
                .unwrap());
        }
    };

    // MCP 로직 처리
    let mcp_res = handle_mcp_request(mcp_req).await;
    
    // 응답 변환
    let json_body = match serde_json::to_string(&mcp_res) {
        Ok(json) => json,
        Err(_) => "{}".to_string(),
    };

    Ok(Response::new(Body::from(json_body)))
}

#[tokio::main]
async fn main() {
    let make_svc = make_service_fn(|_conn| {
        async { Ok::<_, Infallible>(service_fn(http_handler)) }
    });

    let addr = ([127, 0, 0, 1], 3000).into();
    let server = Server::bind(&addr).serve(make_svc);

    println!("MCP Server listening on http://{}", addr);

    if let Err(e) = server.await {
        eprintln!("Server error: {}", e);
    }
}
```

## 4. 고급 최적화: ZeroClow 통합

위 코드는 기본적인 HTTP 서버입니다. `ZeroClaw`의 진짜 힘을 끌어내기 위해서는 이 서버를 에이전트 런타임 내부의 테스크(Task)로 통합해야 합니다. 

*   **채널 기반 통신**: HTTP 요청을 직접 처리하는 대신, `tokio::sync::mpsc` 채널을 통해 요청을 내부 에이전트 큐로 보냅니다. 이는 `ZeroClaw`의 비동기 메시지 패싱 구조와 일치합니다.
*   **Stealable Work Queue**: 다중 코어 환경에서 에이전트가 작업을 효율적으로 분배받을 수 있도록, 작업 큐를 구현합니다.

## 5. 결론

Rust로 MCP 서버를 작성하면, `ZeroClaw`와 같은 고성능 런타임의 이점을 십분 활용할 수 있습니다. 단순히 언어를 바꾸는 것이 아니라, 에이전트 간 통신 오버헤드를 최소화하는 아키텍처 설계가 핵심입니다. 위 코드를 베이스로 여러분의 프로젝트에 맞는 에이전트 로직을 추가해 보시기 바랍니다.

**참고:** 이 코드는 `blog-api-server`의 로깅 개선 작업에서 얻은 경험을 바탕으로, 에러 처리와 로깅 부분을 간소화하여 실용성에 집중했습니다.