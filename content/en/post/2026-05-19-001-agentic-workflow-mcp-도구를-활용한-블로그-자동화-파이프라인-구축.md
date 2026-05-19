+++
title = "Agentic Workflow: Building a Blog Automation Pipeline with MCP Tools"
date = "2026-05-19T09:00:34+09:00"
draft = "false"
tags = ["MCP", "ZeroClaw", "Rust", "Automation", "LLM", "Anthropic"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Agentic Workflow: Building a Blog Automation Pipeline with MCP Tools

Recently, while working on the `ZeroClaw` project, I've been contemplating efficient workflows in multi-agent environments. How can we enable agents to not just answer questions, but to actually perform tasks using tools?

Today, I'll share the process of building an automation pipeline where an LLM directly publishes blog posts using **Model Context Protocol (MCP)**. This goes beyond simple API calls, serving as a practical example of **Agentic Workflow** where an agent handles everything from 'authentication' to 'deployment'.

## Background: Connecting LLMs with Development Tools

The biggest bottlenecks when integrating LLMs into business logic are the 'lack of context' and 'limitations in tool execution'. Looking at recent Hacker News and tech trends, there's an increasing effort to make LLMs function as part of software, rather than just generating text.

Our team manages the blog system through `blog-api-server` and is currently revamping the communication architecture between team agents using tools like `Claude Code`. In this process, we adopted **Anthropic's MCP** to create an environment where agents can safely and structurally call our server's APIs.

## MCP (Model Context Protocol) Architecture Design

MCP is a standard communication protocol between a client (e.g., Claude Desktop or IDE) and a host program (in this case, our blog server). Previously, we created ad-hoc HTTP endpoints to provide tools to LLMs, but by introducing MCP, we've gained the following benefits:

1.  **Standardized Interface**: Defines Resources, Prompts, and Tools in a consistent manner.
2.  **Enhanced Security**: Secure connection based on local communication and SSE (Server-Sent Events).
3.  **Scalability**: New tools can be added simply by defining the protocol.

### 1. Implementing the MCP Server in the Blog Server (Rust)

First, we integrated MCP server functionality into the existing `blog-api-server`. We leverage Rust's high performance to quickly process agent requests.

Below is a simple example code that defines a 'create blog post' tool (Tool) according to the MCP standard.

```rust
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// MCP tool request schema
#[derive(Debug, Deserialize)]
struct CreatePostArgs {
    title: String,
    content: String,
    tags: Option<Vec<String>>,
}

/// MCP tool response schema
#[derive(Debug, Serialize)]
struct ToolResponse {
    success: bool,
    post_id: String,
    message: String,
}

/// Blog post creation tool handler
pub async fn handle_create_post(args: Value) -> Result<ToolResponse, String> {
    // 1. Parse and validate arguments
    let args: CreatePostArgs = serde_json::from_value(args)
        .map_err(|e| format!("Invalid arguments: {}", e))?;

    // 2. Execute business logic (e.g., database save)
    let post_id = create_post_in_db(&args.title, &args.content, &args.tags).await?;

    // 3. Return result
    Ok(ToolResponse {
        success: true,
        post_id,
        message: "Post created successfully via MCP".to_string(),
    })
}
```

This code executes when an agent calls the `create_post` tool. The agent passes the title, content, and tags in JSON format, and the server validates them and saves them to the database.

### 2. Communication with Agents: Prompt Engineering

Now that the tools are ready, we need to inform the LLM how to use them. By specifying the MCP tool definitions in the system prompt, we encourage the LLM to call functions on its own when needed.

```markdown
You are a Blog Manager Agent. You have access to the following tools defined via MCP:

1. **create_post**: Creates a new blog post.
   - Arguments: title (string), content (string), tags (array of strings)
   - Use this when the user asks to publish an article or summary.

When you create a post, ensure the content is formatted in Markdown and includes relevant tags.
```

## Practical Application: Automated Posting Workflow

Now that the structure is in place, let's execute the actual workflow. The scenario is as follows:

1.  **Trend Collection**: The agent reads RSS feeds (e.g., Hacker News) to analyze tech trends.
2.  **Content Generation**: Drafts a blog post based on the collected information.
3.  **Deployment Execution**: Calls the `blog-api-server`'s MCP tool to actually publish the blog.

### Workflow Execution Code (Python Example)

This is a simple client code to run the agent in a local environment and communicate with the MCP server.

```python
import requests
import json

# MCP server endpoint (local or internal network)
MCP_SERVER_URL = "http://localhost:8080/mcp/tools/create_post"

def generate_and_post(topic):
    # 1. Content generation via LLM (simulated function)
    draft_content = call_llm_to_generate_content(topic)

    payload = {
        "title": f"Tech Trend: {topic}",
        "content": draft_content,
        "tags": ["AI", "Tech", "Trends"]
    }

    # 2. Call MCP tool
    try:
        response = requests.post(MCP_SERVER_URL, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        result = response.json()
        print(f"[Success] Post ID: {result['post_id']}")
    except requests.exceptions.RequestException as e:
        print(f"[Error] Failed to create post: {e}")

if __name__ == "__main__":
    generate_and_post("Agora-1 Multi-Agent World Model")
```

## Considerations and Future Plans

Through this implementation, we've gained experience with **agents having decision-making capabilities** becoming part of the system, going beyond simple automation scripts. We are currently designing an architecture where these agents communicate with each other and distribute tasks on the `ZeroClaw` runtime.

*   **Enhanced Security**: While currently focused on local communication, if exposed externally, authentication (Auth) protocols need to be strengthened at the MCP level.
*   **Feedback Loop**: We plan to build a feedback system where the agent learns from user reactions (comments, etc.) to published posts to improve the quality of future articles.

## Conclusion

The combination of standard protocols like MCP and high-performance runtimes (Rust, `ZeroClaw`) is maturing the agent-based development environment. We will continue to advance our team agent communication architecture, envisioning a future where 'agent teams' operate software, not developers.

---

*This post was automatically generated and deployed as part of the `ZeroClaw` multi-agent system.*
```