+++
title = "File-Based Multi-Agent Architecture Design"
slug = "2026-02-27-001-file-based-multi-agent-architecture-design"
date = 2026-02-27T09:30:57+09:00
draft = false
tags = ["rust", "multi-agent", "architecture", "zeroclaw", "ipc"]
categories = ["Architecture", "Multi-Agent", "Design"]
ShowToc = true
TocOpen = true
+++

# File-Based Multi-Agent Architecture Design

**Status:** Design Proposal  
**Author:** multi-agent-architect  
**Date:** 2026-02-24  
**Type:** Alternative Architecture (Process-Per-Agent)

---

## Executive Summary

This document defines a **file-based, process-per-agent** architecture where each agent is defined as a separate configuration file and runs as an independent process. Agents are invoked on-demand and report results back to a main coordinator agent.

### Core Principles

1. **File-Based Agent Definition**: Each agent is a `.toml` file in `agents/`
2. **Process Isolation**: Each agent runs in its own process
3. **On-Demand Invocation**: Main agent spawns subprocess agents as needed
4. **Reporting Protocol**: Structured result reporting via IPC
5. **Zero-Config Discovery**: Auto-discovery of agent definitions

---

## 1. Agent Definition File Structure

### 1.1 Directory Layout

```
~/.zeroclaw/
├── config.toml              # Main configuration
├── agents/                  # Agent definitions directory
│   ├── researcher.toml      # Research agent
│   ├── coder.toml           # Code generation agent
│   ├── tester.toml          # Testing agent
│   ├── reviewer.toml        # Code review agent
│   └── summarizer.toml      # Summarization agent
├── agents.d/                # Optional: additional agent dirs
│   └── custom/
│       └── my_agent.toml
└── workspace/               # Shared workspace
```

### 1.2 Agent File Schema

```toml
# agents/researcher.toml

# Agent metadata
[agent]
id = "researcher"
name = "Research Agent"
version = "1.0.0"
description = "Conducts research on given topics using web search and knowledge bases"

# Execution configuration
[agent.execution]
# How to run this agent: "subprocess" | "wasm" | "docker"
mode = "subprocess"

# Command to spawn (template variables: {agent_id}, {workspace}, {config_dir})
command = "zeroclaw"
args = [
    "agent",
    "run",
    "--agent-id", "{agent_id}",
    "--config", "{config}/agents/researcher.toml",
    "--workspace", "{workspace}"
]

# Working directory for the subprocess
working_dir = "{workspace}"

# Environment variables for the subprocess
[agent.execution.env]
ZEROCLAW_AGENT_MODE = "worker"
ZEROCLAW_AGENT_ID = "researcher"

# Provider configuration (overrides main config)
[provider]
name = "openrouter"
model = "anthropic/claude-sonnet-4-6"
api_key = null  # Inherit from main, or set agent-specific key
temperature = 0.3
max_tokens = 4096

# Tools available to this agent
[[tools]]
name = "web_search"
enabled = true

[[tools]]
name = "web_fetch"
enabled = true

# Tools explicitly denied to this agent
[[tools.deny]]
name = "shell"
reason = "Research agent should not execute shell commands"

# System prompt
[system]
prompt = """
You are a Research Agent. Your role is to:
1. Search for and gather information from credible sources
2. Synthesize findings into structured reports
3. Cite sources and provide references
4. Avoid speculation - stick to verified information
"""

# Memory configuration
[memory]
backend = "shared"  # "shared" | "isolated"
category = "research"

# Reporting configuration
[reporting]
mode = "ipc"
format = "json"  # "json" | "markdown" | "both"
timeout_seconds = 300

# Retry configuration
[retry]
max_attempts = 3
backoff_ms = 1000
```

---

## 2. Agent Registry

The AgentRegistry discovers and manages agent definitions:

```rust
pub struct AgentRegistry {
    agents_dir: PathBuf,
    agents: HashMap<String, AgentDefinition>,
    security: Arc<SecurityPolicy>,
}

impl AgentRegistry {
    pub fn new(agents_dir: PathBuf, security: Arc<SecurityPolicy>) -> Result<Self>;
    pub fn discover(&mut self) -> Result<()>;
    pub fn get(&self, id: &str) -> Option<&AgentDefinition>;
    pub fn list(&self) -> Vec<String>;
}
```

---

## 3. Inter-Process Communication (IPC)

### Task Message (Main → Agent)

```rust
pub struct AgentTask {
    pub task_id: String,
    pub from_agent: String,
    pub to_agent: String,
    pub prompt: String,
    pub context: HashMap<String, serde_json::Value>,
    pub input: Option<serde_json::Value>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub deadline: Option<chrono::DateTime<chrono::Utc>>,
}
```

### Result Message (Agent → Main)

```rust
pub struct AgentResult {
    pub task_id: String,
    pub agent_id: String,
    pub status: AgentStatus,
    pub data: Option<serde_json::Value>,
    pub output: String,
    pub error: Option<String>,
    pub metrics: AgentMetrics,
    pub artifacts: Vec<Artifact>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}
```

---

## 4. Security Considerations

| Execution Mode | Isolation | Use Case |
|----------------|-----------|----------|
| Subprocess | Process-level | Trusted agents |
| Docker | Container | Untrusted, file operations |
| Wasm | Memory-only | High security needs |

---

## 5. CLI Commands

```bash
# List available agents
zeroclaw agent list

# Show agent details
zeroclaw agent show <agent_id>

# Run an agent directly (for testing)
zeroclaw agent run --agent-id researcher --prompt "Research X"

# Create a new agent from template
zeroclaw agent create --id my-agent --name "My Agent"

# Validate agent definition
zeroclaw agent validate <agent_id>
```

---

## 6. Success Criteria

- [ ] Agent definition files validated on load
- [ ] Subprocess agents spawn and complete tasks
- [ ] IPC protocol supports tasks >1GB data
- [ ] Main agent can invoke worker agents via tool
- [ ] Failed agents don't crash main agent
- [ ] Security policy enforced per-agent
- [ ] CLI commands for agent management