+++
title = "Building a High-Performance MCP Server with Rust and Actix Web"
date = "2026-07-07T09:00:40+09:00"
draft = "false"
tags = ["Rust", "Actix-web", "MCP", "ZeroClaw", "Architecture"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Building a High-Performance MCP Server with Rust and Actix Web

Recently, while working on the [ZeroClaw](/tag/zeroclaw) project, I've been deeply considering performance optimization for multi-agent systems. While existing Python-based MCP servers offer fast development speeds, they often encounter bottlenecks when handling highly concurrent requests due to the limitations of the GIL (Global Interpreter Lock).

In this article, I'll share how to build a high-performance MCP (Model Context Protocol) server using Rust's powerful web framework, **Actix Web**. I'll focus on how to implement an event-driven architecture for inter-agent communication, going beyond simple API servers.

## Why Rust? ZeroClaw's Choice

Rust guarantees memory safety at compile time while achieving C++ level performance. In environments that require 24/7 operation, like an agent runtime, and involve processing numerous LLM tokens and I/O operations, this safety and performance are essential.

*   **Zero-cost Abstraction:** Utilizes high-level abstractions without sacrificing execution speed.
*   **Fearless Concurrency:** The compiler prevents notorious data races.
*   **Async/Await:** Asynchronous processing based on the Tokio runtime is advantageous for handling high concurrency.

## Core Architecture: Actix Web + Message Passing

Beyond simply receiving HTTP requests, an MCP server needs the following capabilities:
1.  HTTP Request Handling (JSON-RPC over stdio or SSE)
2.  Internal Inter-Agent Message Passing
3.  Background Tasks (e.g., log collection, resource cleanup)

Actix Web's **Actor Model** provides an optimal structure to satisfy all three requirements. We will design by separating the `HttpServer` that receives HTTP requests from the `MyAgent` Actor that handles the actual logic.

## Practical Code Example

### 1. Project Setup (Cargo.toml)

First, add the dependencies. `serde` is needed for serialization, and `tokio` for the asynchronous runtime.

```toml
[dependencies]
actix-web = "4.4"
actix-rt = "2.9"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

### 2. Defining the Agent Actor

We define the Agent, the entity responsible for handling MCP requests, as an Actor. It implements the `Handler` trait to process asynchronous messages.

```rust
use actix::prelude::*;
use serde::{Deserialize, Serialize};

// MCP Request message struct
#[derive(Message, Deserialize, Serialize)]
#[rtype(result = "String")]
pub struct McpRequest {
    pub tool_name: String,
    pub params: String,
}

// High-performance agent actor struct
pub struct ZeroClawAgent {
    pub state: String, // Stores the agent's state
}

impl Actor for ZeroClawAgent {
    type Context = Context<Self>;

    fn started(&mut self, _ctx: &mut Self::Context) {
        println!("ZeroClaw Agent has started.");
    }
}

// Implementing the message handling logic
impl Handler<McpRequest> for ZeroClawAgent {
    type Result = String;

    fn handle(&mut self, msg: McpRequest, _ctx: &mut Self::Context) -> Self::Result {
        // Actual tool execution logic goes here.
        // e.g., file reading, LLM calls, etc.
        println!("Executing tool: {}", msg.tool_name);
        
        // Return the result
        format!("Executed {} with {}", msg.tool_name, msg.params)
    }
}
```

### 3. Connecting HTTP Endpoints and Actors

Now, we connect Actix Web routes with the Actor created above. The key process is transforming the client's HTTP request into an Actor message and sending it.

```rust
use actix_web::{web, App, HttpResponse, HttpServer};
use actix::Addr;

// Struct for state management
struct AppState {
    agent_addr: Addr<ZeroClawAgent>,
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Create the agent actor
    let agent = ZeroClawAgent { state: "initialized".to_string() }.start();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(AppState {
                agent_addr: agent.clone(), // Clone the address for sharing
            }))
            .route("/mcp/invoke", web::post().to(invoke_tool))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}

// HTTP handler function
async fn invoke_tool(
    req: web::Json<McpRequest>,
    data: web::Data<AppState>,
) -> HttpResponse {
    // Send message to the Agent (asynchronous)
    let result = data.agent_addr
        .send(req.into_inner()) // Convert Json -> McpRequest and send
        .await; // Wait for the response

    match result {
        Ok(res) => HttpResponse::Ok().body(res),
        Err(_) => HttpResponse::InternalServerError().body("Agent Error"),
    }
}
```

## Extensibility: Integration with File-Based Architecture

When combined with the [Multi-Agent File-Based Architecture](/blog/multi-agent-file-arch) discussed previously, this server can collaborate with persistent storage, not just in-memory data.

*   **Adding a Watchdog Task:** By adding `run_interval` to Actix's `Context`, you can periodically monitor command files (like JSON) on disk and, upon changes, send an `McpRequest` message to itself.
*   **Benefits:** This allows agents to be controlled not only through web requests but also via various external methods such as scripts or Cron jobs.

## Conclusion

By leveraging Rust and Actix Web, you can build a **stable and scalable agent runtime**, not just a "fast" server. While the code above forms the most basic skeleton of an MCP server, it can be extended with logging systems ([blog-api-server 로깅 개선](/blog/blog-api-logging)) and complex communication protocols to complete high-performance systems like [ZeroClaw](/tag/zeroclaw).

For developers familiar with Python, concepts like Ownership and Lifetimes might initially seem challenging. However, once the architecture is established, the subsequent maintenance costs and performance benefits will be beyond imagination.