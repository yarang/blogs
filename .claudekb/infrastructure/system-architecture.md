# 시스템 아키텍처

**갱신일**: 2026-05-03

## 전체 구조

```
[GitHub: yarang/blogs.git]
        |
        | push/pull
        v
+--------------------------------------------+
|  ec1 (x86, oci-yarang-ec1)                 |
|                                            |
|  nginx :443                                |
|    +-- blog.fcoinfup.com --> /var/www/blog/ |
|    +-- /api/ proxy --> Blog API :8000       |
|    +-- /webhook proxy --> arm1 :8081        |
|                                            |
|  Blog API (FastAPI :8000)                  |
|    +-- CRUD: /posts                        |
|    +-- Git: /sync, /status                 |
|    +-- Translation: /translate             |
|    +-- Search: /search                     |
|                                            |
|  blog-repo (/var/www/blog-repo/)           |
|    +-- Hugo source --> Hugo build          |
|    +-- build output --> /var/www/blog/      |
+--------------------------------------------+
        ^
        | HTTPS /api/
        |
+--------------------------------------------+
|  arm1 (ARM, oci-yarang-arm1)               |
|                                            |
|  Auto Comment Worker (Flask :8081)         |
|    +-- Webhook 수신 + HMAC 검증            |
|    +-- Claude Code CLI 호출               |
|    +-- GraphQL API로 답변 게시            |
|                                            |
|  Claude Code CLI (Agent Operator)          |
|    +-- blog-api 호출로 블로그 운영         |
|    +-- 포스트 작성/수정/삭제               |
|    +-- 번역 요청                          |
+--------------------------------------------+
```

## 서버별 서비스

### ec1 (x86_64)

| 서비스 | 포트 | systemd | 프로젝트 경로 |
|--------|------|---------|---------------|
| nginx | 443 (SSL) | nginx.service | /etc/nginx/ |
| Blog API | 8000 | blog-api.service | /var/www/blog-api/ |
| Hugo 블로그 | - | - | /var/www/blog-repo/ → /var/www/blog/ |

**Blog API 기술 스택:**
- FastAPI + uvicorn
- Git 동기화 (GitHandler)
- LLM 번역 (ZAI glm-4.7)
- API Key 인증 (X-API-Key)
- 도메인: blog.fcoinfup.com/api/

### arm1 (ARM64)

| 서비스 | 포트 | systemd | 프로젝트 경로 |
|--------|------|---------|---------------|
| Auto Comment Worker | 8081 | auto-comment-worker.service | /var/www/auto-comment-worker/ |
| Claude Code CLI | - | - | /home/ubuntu/.local/bin/claude |

## 데이터 흐름

### 1. 독자 블로그 열람

```
독자 --> ec1 nginx :443 --> /var/www/blog/ (Hugo 정적 파일)
```

### 2. 댓글 --> AI 응답

```
독자 --> giscus --> GitHub Discussions
  --> Webhook POST --> ec1 nginx /webhook
  --> proxy --> arm1 Flask :8081
  --> HMAC 검증 --> 마커 체크 (무한루프 방지)
  --> Claude Code --print --> AI 응답
  --> GitHub GraphQL addDiscussionComment
  --> giscus에 답변 표시
```

### 3. 블로그 포스트 관리 (에이전트)

```
arm1 Claude Code
  --> HTTPS blog.fcoinfup.com/api/posts (CRUD)
  --> ec1 Blog API --> blog-repo 파일 조작
  --> git commit + push --> GitHub
  --> Hugo build --> /var/www/blog/ 갱신
```

### 4. 번역

```
arm1 Claude Code
  --> HTTPS /api/translate (ko-->en)
  --> ec1 Blog API --> ZAI LLM API (glm-4.7)
  --> 번역 결과 반환
  --> POST /api/posts로 영문 포스트 생성
```

## 도메인 및 SSL

| 도메인 | 용도 | SSL |
|--------|------|-----|
| blog.fcoinfup.com | 블로그 + /api/ | Let's Encrypt (유효) |
| blog.agentthread.dev | 블로그 별칭 | 동일 인증서 |
| api.blog.fcoinfup.com | Blog API 전용 | 인증서 미등록 (사용 금지) |

**주의**: api.blog.fcoinfup.com은 SSL SAN에 미포함. arm1에서 접근 시 반드시 blog.fcoinfup.com/api/ 경로 사용.

## 인증 체계

### Blog API (ec1)
- 방식: X-API-Key 헤더
- 키 저장: ec1 /var/www/blog-api/.env (BLOG_API_KEYS)

### Auto Comment Worker (arm1)
- GitHub PAT: /etc/auto-comment-worker/github-token (640)
- Webhook Secret: /etc/auto-comment-worker/credentials/webhook-secret (600)
- Blog API Key: /etc/auto-comment-worker/credentials/blog-api-key (600)

### GitHub
- Webhook: HMAC-SHA256 시그니처 검증
- GraphQL API: Bearer token (GitHub PAT)
