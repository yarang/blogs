+++
title = "Rust 기반 MCP 서버 구축하기: ZeroClaw 아키텍처 활용"
date = 2026-06-09T09:00:48+09:00
draft = false
tags = ["Rust", "MCP", "ZeroClaw", "Architecture", "AI"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Rust 기반 MCP 서버 구축하기: ZeroClaw 아키텍처 활용

최근 AI 에이전트 생태계에서 **Model Context Protocol (MCP)**는 표준 인터페이스로 자리 잡고 있습니다. 저희 팀의 `ZeroClaw` 프로젝트와 같은 고성능 런타임 환경에서 MCP 서버를 구축할 때, Rust의 안전성과 속도는 필수적인 요소입니다. 이번 포스트에서는 실무적으로 바로 적용할 수 있는 Rust 기반 MCP 서버의 구조를 설계하고, 실제 코드를 통해 구현 방법을 살펴보겠습니다.

## 1. MCP 서버의 핵심 요구사항

AI 모델이 데이터에 접근하기 위해 MCP 서버는 다음 세 가지 핵심 기능을 수행해야 합니다.

1.  **리소스 발견 (Discovery):** 모델이 사용할 수 있는 데이터(파일, API 등)의 목록을 제공
2.  **리소스 접근 (Access):** 요청받은 데이터의 실제 내용을 효율적으로 반환
3.  **도구 실행 (Tool Execution):** 모델의 지시에 따라 시스템 내부에서 동작을 수행

Rust는 특히 **Zero-cost abstractions**와 강력한 비동기 런타임(`tokio`) 덕분에 대규모 요청을 처리하는 MCP 서버에 최적입니다.

## 2. 아키텍처 설계: ZeroClaw 스타일

단순한 RPC 호출을 넘어, 우리는 **이벤트 기반 아키텍처**를 채택하여 확장성을 확보합니다. 구조는 다음과 같습니다.

*   **Transport Layer:** `stdio` 또는 WebSocket을 통한 메시지 송수신 (JSON-RPC 2.0)
*   **Handler Layer:** 요청을 라우팅하고 검증하는 계층
*   **Core Logic:** 실제 비즈니스 로직 (파일 시스템 접근, DB 조회 등)

## 3. 실전 코드 예제

가장 대중적인 트랜스포트인 `stdio`(표준 입출력) 기반의 간단한 MCP 서버를 작성해 보겠습니다. 이 예제는 LLM이 로컬 파일 시스템의 로그를 읽을 수 있게 해주는 기능을 구현합니다.

### 3.1. 의존성 설정 (`Cargo.toml`)

Rust의 생태계를 활용하기 위해 직렬화와 비동기 처리를 위한 크레이트를 추가합니다.

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
async-trait = "0.1"
```

### 3.2. 핸들러 트레이트 정의

MCP 표준에 맞춰 `Tool`과 `Resource`를 처리할 공통 인터페이스를 정의합니다. 이는 추후 `ZeroClaw` 런타임에 통합하기 쉽게 만듭니다.

```rust
use serde_json::Value;
use async_trait::async_trait;

#[async_trait]
pub trait McpHandler {
    async fn handle(&self, params: Value) -> Result<Value, String>;
    fn name(&self) -> &str;
}
```

### 3.3. 로그 읽기 도구 구현

이제 실제로 서버 내부의 파일을 읽어서 AI 모델에 전달하는 로직을 구현합니다.

```rust
use std::fs;
use std::path::Path;

pub struct LogReaderTool;

#[async_trait]
impl McpHandler for LogReaderTool {
    fn name(&self) -> &str {
        "read_logs"
    }

    async fn handle(&self, params: Value) -> Result<Value, String> {
        // 1. 파라미터 검증 및 추출
        let file_path = params.get("path")
            .and_then(|v| v.as_str())
            .ok_or("Missing 'path' parameter".to_string())?;

        // 2. 보상: 경로 조작 방지 (SandBoxing)
        // 실제 운영 환경에서는 chroot나 전용 가상 디렉토리를 사용해야 합니다.
        if !file_path.ends_with(".log") {
            return Err("Only .log files are allowed".into());
        }

        // 3. 파일 시스템 접근 (동기식 I/O를 비동기 컨텍스트로 래핑)
        let content = fs::read_to_string(file_path)
            .map_err(|e| format!("Failed to read file: {}", e))?;

        // 4. 결과 포맷팅
        Ok(serde_json::json!({
            "status": "success",
            "content": content,
            "lines": content.lines().count()
        }))
    }
}
```

### 3.4. 메인 루프 및 JSON-RPC 서버

LLM과의 통신을 담당하는 메인 루프입니다. 표준 입력에서 JSON-RPC 요청을 읽고, 처리 결과를 표준 출력으로 내보냅니다.

```rust
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::io::{AsyncWriteExt, BufWriter};
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();
    let mut reader = BufReader::new(stdin).lines();
    let mut writer = BufWriter::new(stdout);

    let tool = Arc::new(LogReaderTool);

    // LLM이나 호스트로부터 요청이 들어올 때마다 처리
    while let Ok(Some(line)) = reader.next_line().await {
        if line.trim().is_empty() { continue; }

        if let Ok(json_req) = serde_json::from_str::<Value>(&line) {
            let method = json_req.get("method").and_then(|m| m.as_str()).unwrap_or("");
            let id = json_req.get("id");

            if method == "tools/call" || method == "tools/invoke" {
                let params = json_req.get("params").cloned().unwrap_or(Value::Null);
                
                // 비즈니스 로직 실행
                let result = tool.handle(params).await;
                
                let response = match result {
                    Ok(data) => serde_json::json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "result": data
                    }),
                    Err(e) => serde_json::json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": { "code": -32000, "message": e }
                    })
                };
                
                writer.write_all(response.to_string().as_bytes()).await?;
                writer.write_all(b"\n").await?;
                writer.flush().await?;
            }
        }
    }
    Ok(())
}
```

## 4. 최적화 및 배포 고려사항

위 코드는 기본적인 골격이지만, `ZeroClaw`와 같은 프로덕션 환경에서는 다음 사항을 고려해야 합니다.

1.  **에러 타입 구체화:** `String` 대신 구체적인 `thiserror`나 `anyhow` 기반의 에러 타입을 사용하여 디버깅을 용이하게 하세요.
2.  **보안 샌드박싱:** `std::fs` 대신 가상 파일 시스템(VFS) 라이브러리를 사용하여, 에이전트가 시스템 전체에 접근하는 것을 막아야 합니다.
3.  **Graceful Shutdown:** `tokio`의 `signal` 모듈을 활용하여 인터럽트 신호(SIGTERM)를 처리하고, 진행 중인 파일 작업을 안전하게 종료해야 합니다.

## 5. 결론

Rust는 타입 안전성과 메모리 관리 능력 덕분에 신뢰할 수 있는 MCP 서버를 구축하는 데 최적의 언어입니다. 위 코드를 바탕으로 `blog-api-server`나 모니터링 시스템과 연동한다면, AI 모델이 직접 시스템 로그를 분석하고 패치를 제안하는 완전한 자동화 사이클을 구축할 수 있습니다.

다음 포스트에서는 이 MCP 서버를 `ZeroClaw` 런타임 위에서 어떻게 에이전트화하고, 다른 서비스와 통신하는지 다루겠습니다.