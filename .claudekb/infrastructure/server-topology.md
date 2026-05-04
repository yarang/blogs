# 서버 토폴로지

**갱신일**: 2026-05-03

## 서버 구성

| 호스트 | 아키텍처 | 역할 | 위치 |
|--------|----------|------|------|
| oci-yarang-ec1 (ec1) | x86_64 | 웹 서버 + Blog API | Oracle Cloud |
| oci-yarang-arm1 (arm1) | ARM64 | 에이전트 오퍼레이터 + 댓글 워커 | Oracle Cloud |

## ec1 서비스 구성

### nginx (포트 443)
- `blog.fcoinfup.com` → `/var/www/blog/` (Hugo 정적 파일)
- `blog.fcoinfup.com/api/` → `127.0.0.1:8000` (Blog API 프록시)
- `blog.agentthread.dev` → 동일 블로그

### Blog API (FastAPI, 포트 8000)
- systemd: `blog-api.service`
- 프로젝트: `/var/www/blog-api/`
- 기능: 포스트 CRUD, Git sync, LLM 번역, 검색, Mermaid 렌더링
- 인증: X-API-Key 헤더 (3개 키 등록)
- 번역 LLM: ZAI (glm-4.7)

### Hugo 블로그
- 소스: `/var/www/blog-repo/` (yarang/blogs.git 클론)
- 빌드: `/var/www/blog-repo/public/` → `/var/www/blog/`로 배포
- 테마: Stack (git submodule)

## arm1 서비스 구성

### Auto Comment Worker (Flask, 포트 8081)
- systemd: `auto-comment-worker.service`
- 프로젝트: `/var/www/auto-comment-worker/`
- 기능: GitHub Webhook 수신 → Claude Code AI 응답 → GraphQL 게시

### Claude Code CLI
- 경로: `/home/ubuntu/.local/bin/claude`
- 설정: `~/.agent_forge_for_zai.json`
- LLM: ZAI API (glm-4.7 via Anthropic 호환 엔드포인트)

## 네트워크 흐름

```
인터넷 → ec1 (nginx:443) ─┬─ 정적 파일 서빙 (/var/www/blog/)
                           ├─ Blog API 프록시 (:8000)
                           └─ Webhook → arm1 (Flask:8081)
                                          ↓
                                    Claude Code CLI
                                          ↓
                                    GitHub GraphQL API
```

### arm1 → ec1 연결

- **HTTPS**: `https://blog.fcoinfup.com/api/` 접근 가능
- **SSH**: 불가 (DNS 해석 실패)
- **주의**: `api.blog.fcoinfup.com` SSL 인증서 미등록 → `/api/` 경로 사용

## 인증 파일 (arm1)

```
/etc/auto-comment-worker/
├── github-token           # GitHub PAT (640)
└── credentials/
    ├── webhook-secret     # Webhook HMAC (600)
    └── blog-api-key       # Blog API 키 (600)
```
