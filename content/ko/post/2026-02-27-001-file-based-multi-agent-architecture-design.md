+++
title = "[Multi-Agent] 파일 기반 아키텍처 설계"
slug = "2026-02-27-001-file-based-multi-agent-architecture-design"
date = 2026-02-27T09:30:57+09:00
draft = false
tags = ["rust", "multi-agent", "architecture", "zeroclaw", "ipc"]
categories = ["아키텍처", "멀티 에이전트", "설계"]
ShowToc = true
TocOpen = true
+++

# 파일 기반 멀티 에이전트 아키텍처 설계

**상태:** 설계 제안
**작성자:** multi-agent-architect
**날짜:** 2026-02-24
**유형:** 대안 아키텍처 (프로세스-단위-에이전트)

---

## 개요

이 문서는 각 에이전트가 별도의 설정 파일로 정의되고 독립적인 프로세스로 실행되는 **파일 기반, 프로세스-단위-에이전트** 아키텍처를 정의합니다. 에이전트는 필요시 호출되어 메인 코디네이터 에이전트에게 결과를 보고합니다.

### 핵심 원칙

1. **파일 기반 에이전트 정의**: 각 에이전트는 `agents/` 디렉토리의 `.toml` 파일
2. **프로세스 격리**: 각 에이전트는 자체 프로세스에서 실행
3. **온디맨드 호출**: 메인 에이전트가 필요시 서브프로세스 에이전트 생성
4. **보고 프로토콜**: IPC를 통한 구조화된 결과 보고
5. **제로-설정 디스커버리**: 에이전트 정의 자동 감지

---

## 1. 에이전트 정의 파일 구조

### 1.1 디렉토리 레이아웃

```
~/.zeroclaw/
├── config.toml              # 메인 설정
├── agents/                  # 에이전트 정의 디렉토리
│   ├── researcher.toml      # 리서치 에이전트
│   ├── coder.toml           # 코드 생성 에이전트
│   ├── tester.toml          # 테스팅 에이전트
│   ├── reviewer.toml        # 코드 리뷰 에이전트
│   └── summarizer.toml      # 요약 에이전트
├── agents.d/                # 선택사항: 추가 에이전트 디렉토리
│   └── custom/
│       └── my_agent.toml
└── workspace/               # 공유 워크스페이스
```

### 1.2 에이전트 파일 스키마

```toml
# agents/researcher.toml

# 에이전트 메타데이터
[agent]
id = "researcher"
name = "Research Agent"
version = "1.0.0"
description = "Conducts research on given topics using web search and knowledge bases"

# 실행 설정
[agent.execution]
# 에이전트 실행 방식: "subprocess" | "wasm" | "docker"
mode = "subprocess"

# 실행 명령어 (템플릿 변수: {agent_id}, {workspace}, {config_dir})
command = "zeroclaw"
args = [
    "agent",
    "run",
    "--agent-id", "{agent_id}",
    "--config", "{config}/agents/researcher.toml",
    "--workspace", "{workspace}"
]

# 서브프로세스 작업 디렉토리
working_dir = "{workspace}"

# 서브프로세스 환경변수
[agent.execution.env]
ZEROCLAW_AGENT_MODE = "worker"
ZEROCLAW_AGENT_ID = "researcher"

# 프로바이더 설정 (메인 설정 오버라이드)
[provider]
name = "openrouter"
model = "anthropic/claude-sonnet-4-6"
api_key = null  # 메인에서 상속, 또는 에이전트별 키 설정
temperature = 0.3
max_tokens = 4096

# 이 에이전트에서 사용 가능한 도구
[[tools]]
name = "web_search"
enabled = true

[[tools]]
name = "web_fetch"
enabled = true

# 이 에이전트에서 명시적으로 거부된 도구
[[tools.deny]]
name = "shell"
reason = "Research agent should not execute shell commands"

# 시스템 프롬프트
[system]
prompt = """
You are a Research Agent. Your role is to:
1. Search for and gather information from credible sources
2. Synthesize findings into structured reports
3. Cite sources and provide references
4. Avoid speculation - stick to verified information
"""

# 메모리 설정
[memory]
backend = "shared"  # "shared" | "isolated"
category = "research"

# 보고 설정
[reporting]
mode = "ipc"
format = "json"  # "json" | "markdown" | "both"
timeout_seconds = 300

# 재시도 설정
[retry]
max_attempts = 3
backoff_ms = 1000
```

---

## 2. 에이전트 레지스트리

AgentRegistry는 에이전트 정의를 발견하고 관리합니다:

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

## 3. 프로세스 간 통신 (IPC)

### 태스크 메시지 (메인 → 에이전트)

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

### 결과 메시지 (에이전트 → 메인)

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

## 4. 보안 고려사항

| 실행 모드 | 격리 수준 | 사용 사례 |
|-----------|-----------|-----------|
| Subprocess | 프로세스 수준 | 신뢰할 수 있는 에이전트 |
| Docker | 컨테이너 | 신뢰할 수 없는, 파일 작업 |
| Wasm | 메모리 전용 | 높은 보안 요구사항 |

---

## 5. CLI 명령어

```bash
# 사용 가능한 에이전트 목록
zeroclaw agent list

# 에이전트 상세 정보
zeroclaw agent show <agent_id>

# 에이전트 직접 실행 (테스트용)
zeroclaw agent run --agent-id researcher --prompt "Research X"

# 템플릿에서 새 에이전트 생성
zeroclaw agent create --id my-agent --name "My Agent"

# 에이전트 정의 검증
zeroclaw agent validate <agent_id>
```

---

## 6. 성공 기준

- [ ] 에이전트 정의 파일 로드 시 검증
- [ ] 서브프로세스 에이전트 생성 및 태스크 완료
- [ ] IPC 프로토콜 1GB 이상 데이터 지원
- [ ] 메인 에이전트가 도구를 통해 워커 에이전트 호출 가능
- [ ] 실패한 에이전트가 메인 에이전트 크래시 유발하지 않음
- [ ] 에이전트별 보안 정책 적용
- [ ] 에이전트 관리 CLI 명령어
