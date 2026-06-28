+++
title = "MCP 통합 가이드: ZeroClaw 런타임에서 Discord MCP 연동하기"
date = 2026-06-28T09:00:35+09:00
draft = false
tags = ["ZeroClaw", "MCP", "Rust", "Discord", "Architecture", "LLM"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

최근 고성능 Rust 에이전트 런타임인 **ZeroClaw**를 발표하며, 멀티 에이전트 시스템의 효율성을 극대화하는 방안에 대한 고민이 깊어졌습니다. 특히 [Discord Decision MCP] 아키텍처 설계를 진행하면서 겪었던 통신 프로토콜의 복잡성은 MCP(Model Context Protocol)를 표준 인터페이스로 채택하게 된 결정적인 계기가 되었습니다.

이번 포스트에서는 ZeroClaw의 환경에서 **Discord MCP**를 실제로 통합하여, 에이전트가 Discord 메시지를 수신하고 처리하는 과정을 구체적인 코드와 함께 설명하겠습니다.

### 1. 아키텍처 설계: 단일 채널에서의 이중 통신

기존 [Discord MCP] Gateway 아키텍처에서는 게이트웨이가 이벤트를 필터링하고 에이전트에게 전달하는 역할을 했습니다. 하지만 ZeroClaw 내부적으로 MCP 클라이언트를 직접 구현함으로써 중간 계층을 제거하고 지연 시간을 줄이는 방향으로 설계를 변경했습니다.

핵심은 **`MCP Client`**가 Discord 이벤트를 `stdio`를 통해 ZeroClaw 프로세스로 전달하고, 에이전트의 응답을 다시 Discord로 보내는 흐름입니다.

### 2. 필수 의존성 및 설정 (Rust)

ZeroClaw는 Rust로 작성되었으므로, 높은 동시성 처리를 위해 비동기 런타임인 `tokio`와 JSON 처리를 위한 `serde`를 사용합니다. MCP 서버와의 통신은 JSON-RPC 메시지를 표준 입출력(stdio)으로 주고받는 방식을 가정합니다.

```toml
# Cargo.toml
[dependencies]
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
async-trait = "0.1"
```

### 3. MCP 클라이언트 구현

ZeroClaw 내부에서 Discord MCP 서버를 제어하기 위한 간단한 클라이언트 구조를 정의합니다. 이 클라이언트는 MCP 표준을 따르는 `tools/call` 메서드를 사용하여 Discord 봇의 기능을 실행합니다.

```rust
use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use std::io::{BufReader, BufWriter, Write};

#[derive(Debug, Serialize, Deserialize)]
struct MCPRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize)]
struct MCPResponse {
    jsonrpc: String,
    id: u64,
    result: Option<serde_json::Value>,
}

pub struct DiscordMCPClient {
    id: u64,
}

impl DiscordMCPClient {
    pub fn new() -> Self {
        Self { id: 0 }
    }

    /// Discord 채널에 메시지를 전송하는 MCP 툴 실행
    pub async fn send_message(&mut self, channel_id: &str, content: &str) -> Result<(), Box<dyn std::error::Error>> {
        self.id += 1;
        
        // MCP 서버 프로세스 실행 (예: Python 기반 Discord MCP 서버)
        let mut child = Command::new("python3")
            .arg("discord_mcp_server.py")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()?;

        let stdin = child.stdin.as_mut().ok("Failed to open stdin")?;
        let mut stdout = BufReader::new(child.stdout.as_mut().ok("Failed to open stdout")?);

        let request = MCPRequest {
            jsonrpc: "2.0".to_string(),
            id: self.id,
            method: "tools/call".to_string(),
            params: serde_json::json!({
                "name": "send_message",
                "arguments": {
                    "channel_id": channel_id,
                    "content": content
                }
            }),
        };

        // 요청 전송
        let request_json = serde_json::to_string(&request)?;
        writeln!(stdin, "{}", request_json)?;

        // (실제 구현 시에는 비동기 리더에서 응답을 파싱하는 로직 필요)
        // 여기서는 간단한 예시를 위해 생략합니다.
        
        Ok(())
    }
}
```

### 4. ZeroClaw 에이전트와의 통합

이제 위에서 만든 `DiscordMCPClient`를 ZeroClaw의 에이전트 루프 내에서 사용해봅시다. 에이전트가 특정 작업을 완료했을 때, 이를 Discord에 알리는 시나리오입니다.

```rust
struct ZeroClawAgent {
    discord_client: DiscordMCPClient,
}

impl ZeroClawAgent {
    async fn run_task(&mut self, task: &str) {
        println!("[Agent] 작업 시작: {}", task);
        
        // 복잡한 추론 또는 파일 처리 로직 (생략)
        // ...

        let result = format!("작업 '{}' 완료됨.", task);

        // 결과를 Discord로 전송
        match self.discord_client.send_message("123456789", &result).await {
            Ok(_) => println!("[Agent] Discord 알림 전송 성공"),
            Err(e) => eprintln!("[Agent] 전송 실패: {}", e),
        }
    }
}

#[tokio::main]
async fn main() {
    let mut agent = ZeroClawAgent {
        discord_client: DiscordMCPClient::new(),
    };

    agent.run_task("서버 로그 분석").await;
}
```

### 5. 효율성 및 보안 고려사항 (Architecture Insights)

1.  **리소스 관리**: [Hacker News]의 최신 트렌드인 'Adrafinil'처럼, 에이전트가 유휴 상태일 때는 Discord MCP 연결을 끊고 작업이 활성화되었을 때만 연결을 맺는 `speculative decoding` 방식을 적용하면 리소스를 아낄 수 있습니다.
2.  **보안**: [Anonymous GitHub account] 관련 이슈처럼, MCP 서버에 전달되는 파라미터(예: API 토큰)는 환경 변수로 관리하거나 별도의 보안 저장소(Vault)에서 가져오도록 설계해야 합니다. 코드 내에 하드코딩된 시크릿은 치명적입니다.
3.  **에러 처리**: 통신 플랫폼 설계 고찰에서 언급된 바와 같이, Discord API의 Rate Limit을 고려하여 MCP 클라이언트에 재시도 로직(Retry Logic)을 포함하는 것이 중요합니다.

### 마무리하며

ZeroClaw와 Discord MCP의 통합은 단순히 봇을 만드는 것을 넘어, 에이전트가 외부 세계와 상호작용하는 **표준화된 인터페이스**를 구축하는 과정입니다. 앞으로도 [MCP] 블로그 자동화 시스템 구축 경험을 살려, 더욱 정교한 멀티 에이전트 협업 시스템을 발전시켜 나갈 계획입니다.