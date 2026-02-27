+++
title = "Introducing ZeroClaw"
date = 2026-02-27T23:25:26+09:00
draft = false
tags = ["rust", "agent", "zeroclaw"]
categories = ["Technology"]
ShowToc = true
TocOpen = true
+++

ZeroClaw is a **high-performance autonomous agent runtime** built in Rust.

## Key Features

### Performance
- Rust-native with zero allocations
- Async/await with Tokio
- Streaming support

### Extensibility
- Trait + Factory Architecture
- 25+ Built-in Tools
- Plugin-friendly

### Security
- Sandbox Support (Firejail, Docker)
- ChaCha20-Poly1305 encryption
- Deny-by-default execution

### Platforms
- 20+ Messaging Channels
- 13+ LLM Providers

## Quick Start

```bash
cargo install zeroclaw
zeroclaw config init
zeroclaw run --channel telegram
```