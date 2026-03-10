+++
title = "[ZeroClaw] 소개 - 고성능 Rust 에이전트 런타임"
slug = "2026-02-27-introducing-zeroclaw"
date = 2026-02-27T19:30:00+09:00
draft = false
tags = ["rust", "agent", "ai", "llm", "zeroclaw"]
categories = ["Technology"]
ShowToc = true
TocOpen = true
+++

# ZeroClaw 소개: 고성능 Rust 에이전트 런타임

ZeroClaw는 Rust로 구축된 **고성능 자율 에이전트 런타임**으로, AI 기반 애플리케이션에서 속도, 효율성, 안정성이 필요한 개발자를 위해 설계되었습니다.

## 핵심 기능

### 성능 우선
- **Rust 네이티브**: 가능한 한 할당 없음
- **Tokio 기반 Async/await**: 효율적인 동시 작업
- **스트리밍 지원**: 실시간 응답 스트리밍

### 확장성
- **Trait + Factory 아키텍처**: Trait 구현으로 확장
- **25개 이상의 내장 도구**: Shell, 파일 작업, 메모리, 브라우저, HTTP
- **플러그인 친화적**: 코어 수정 없이 Provider, Channel, Tool 추가 가능

### 기본 보안
- **샌드박스 지원**: Firejail, Bubblewrap, Landlock, Docker
- **페어링 프로토콜**: 6자리 CSPRNG 코드
- **비밀 저장소**: ChaCha20-Poly1305 AEAD 암호화

### 멀티 플랫폼
- **20개 이상의 메시징 채널**: Telegram, Discord, Slack, WhatsApp, Signal, Matrix
- **13개 이상의 LLM Provider**: OpenAI, Anthropic, Gemini, Ollama, Bedrock, OpenRouter

## 빠른 시작

```bash
cargo install zeroclaw
zeroclaw config init
zeroclaw run --channel telegram
```

## 아키텍처

```
ZeroClaw Agent
├── Providers (OpenAI, Anthropic, Gemini, Ollama)
├── Channels (Telegram, Discord, Slack, WhatsApp)
├── Tools (Shell, File, Memory, Browser, HTTP)
├── Memory (SQLite, PostgreSQL, Markdown)
└── Security (Policy, Sandbox, Secret Store)
```

## 로드맵

- **1단계**: 향상된 멀티 에이전트 (진행 중)
- **2단계**: 더 많은 통합
- **3단계**: 엔터프라이즈 기능


---

**영어 버전:** [English Version](/en/post/2026-02-27-010-introducing-zeroclaw/)