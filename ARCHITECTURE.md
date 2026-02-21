# Blog System Architecture

## 개요

각 모듈이 독립적으로 Git을 관리하며, Git을 통해서만 동기화됩니다.

## 블록 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                     Block 1: API Server                          │
│                      (OCI Server)                                │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   FastAPI   │───►│ BlogManager │───►│ GitManager  │          │
│  └─────────────┘    └─────────────┘    └──────┬──────┘          │
│                                                 │                 │
│  Input: HTTP API          Output: Git commit/push               │
└─────────────────────────────────────────────────┼────────────────┘
                                                  │
                                                 Git
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Block 2: GitHub                              │
│                                                                  │
│  - 중앙 저장소 (Single Source of Truth)                          │
│  - Actions 트리거                                                │
│  - 모든 블록이 여기서 pull / 여기로 push                          │
└─────────────────────────────────────────────────┼────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────┐
                    │                             │                 │
                   Git                          Git               Git
                    │                             │                 │
                    ▼                             ▼                 ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐
│ Block 3: MCP Server   │  │ Block 4: GitHub Actions│  │ Block 5: User   │
│ (Local Machine)       │  │ (GitHub)               │  │ (Any Machine)   │
│                       │  │                        │  │                 │
│ ┌─────────┐ ┌───────┐ │  │ ┌────────────────────┐ │  │  git pull/push  │
│ │ Claude  │ │ Blog  │ │  │ │ Hugo Build         │ │  │                 │
│ │ Code    │ │Manager│ │  │ │ rsync Deploy       │ │  │                 │
│ └────┬────┘ └───┬───┘ │  │ └─────────┬──────────┘ │  │                 │
│      │          │     │  │           │            │  │                 │
│      │    ┌─────▼───┐ │  │           │            │  │                 │
│      └───►│GitMgr   │ │  │           │            │  │                 │
│           └─────┬───┘ │  │           │            │  │                 │
│                 │     │  │           │            │  │                 │
└─────────────────┼─────┘  └───────────┼────────────┘  └─────────────────┘
                  │                    │
                 Git                  rsync
                  │                    │
                  ▼                    ▼
           ┌─────────────────────────────────────────┐
           │          Block 6: Blog (Deployed)        │
           │              (OCI Server)                │
           │                                          │
           │  Nginx → /var/www/blog (Static Files)   │
           │                                          │
           └─────────────────────────────────────────┘
```

## 블록 정의

### Block 1: API Server (OCI)
- **목적**: HTTP API를 통한 블로그 관리
- **입력**: HTTP 요청 (API Key 인증)
- **출력**: Git commit/push
- **독립성**: 자체 Git repo clone 보유

### Block 2: GitHub
- **목적**: 중앙 저장소, CI/CD 트리거
- **역할**: Single Source of Truth

### Block 3: MCP Server (Local)
- **목적**: Claude Code CLI 연동
- **입력**: MCP 프로토콜
- **출력**: Git commit/push
- **독립성**: 자체 Git repo 보유

### Block 4: GitHub Actions
- **목적**: 자동 빌드 및 배포
- **트리거**: push to main
- **출력**: rsync to OCI

### Block 5: User
- **목적**: 수동 Git 조작
- **입출력**: git pull/push

### Block 6: Blog (Deployed)
- **목적**: 정적 파일 서빙
- **입력**: rsync from Actions
- **출력**: HTTP 응답

## 동기화 규칙

1. **모든 수정 전 pull**: 각 블록은 수정 전 반드시 `git pull`
2. **수정 후 push**: 수정 후 즉시 `git commit && git push`
3. **충돌 해결**: 사용자가 수동으로 해결
4. **단일 진실 원천**: GitHub가 항상 최신 상태

## 장점

| 장점 | 설명 |
|------|------|
| **독립성** | 각 블록이 독립적으로 작동 |
| **단순성** | Git만 알면 동기화 |
| **유연성** | 어떤 블록에서든 수정 가능 |
| **추적성** | 모든 변경사항이 Git에 기록 |

## 파일 구조

```
blogs/
├── .mcp.json              # MCP 설정 (Block 3)
├── .claude/
│   └── mcp_server.py      # MCP Server (Block 3)
├── api_server/            # API Server (Block 1)
│   ├── main.py
│   ├── blog_manager.py
│   └── auth.py
├── .github/
│   └── workflows/
│       └── deploy.yml     # Actions (Block 4)
└── content/posts/         # 블로그 콘텐츠
```
