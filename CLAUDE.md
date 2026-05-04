# Blog Agent Operations Center — CLAUDE.md

> arm1의 Claude Code가 블로그 시스템을 에이전트로 운영하기 위한 시스템 프롬프트.

## 시스템 개요

| 서버 | 역할 |
|------|------|
| **ec1** | 블로그 호스팅 (nginx + Hugo) + Blog API (FastAPI :8000) |
| **arm1** (여기) | 통합 에이전트 (blog-agent, Flask :8081) |
| **GitHub** | 중앙 저장소 (yarang/blogs.git) + Discussions (giscus 댓글) |

arm1에서 ec1으로: **HTTPS API만 가능** (SSH 불가). `https://blog.fcoinfup.com/api/` 경로 사용.

→ 상세: `.claudekb/infrastructure/system-architecture.md`

---

## 1. 글 작성

Blog API를 통해 포스트를 관리한다. 파일 직접 편집 금지.

```bash
API_KEY=$(cat /etc/auto-comment-worker/credentials/blog-api-key)
BASE="https://blog.fcoinfup.com/api"
```

| 작업 | 명령 |
|------|------|
| 목록 | `curl -s -H "X-API-Key: $API_KEY" "$BASE/posts?language=ko"` |
| 조회 | `curl -s -H "X-API-Key: $API_KEY" "$BASE/posts/{filename}"` |
| 생성 | `curl -s -X POST ... "$BASE/posts"` (JSON body) |
| 수정 | `curl -s -X PUT ... "$BASE/posts/{filename}"` |
| 삭제 | `curl -s -X DELETE ... "$BASE/posts/{filename}"` |
| 검색 | `curl -s -H "X-API-Key: $API_KEY" "$BASE/search?q=키워드"` |
| 번역 | `curl -s -X POST ... "$BASE/translate"` |
| 동기화 | `curl -s -X POST -H "X-API-Key: $API_KEY" "$BASE/sync"` |

**포스트 작성 규칙:**
1. slug 명시 필수 (제목의 `/`, `()` 등이 permalink를 깨뜨림)
2. 날짜는 현재 시간 이전으로 설정
3. 시리즈: `series = ["시리즈명"]`

→ 상세: `.claudekb/operations/blog-writing-guide.md`

---

## 2. 서버 관리

### arm1 서비스 (직접 관리)

```bash
sudo systemctl status blog-agent              # 상태
sudo systemctl restart blog-agent             # 재시작
sudo journalctl -u blog-agent -f              # 로그
```

### ec1 상태 (API로 확인)

```bash
curl -s "$BASE/health"                                        # 헬스체크
curl -s -H "X-API-Key: $API_KEY" "$BASE/status"              # Git 상태
```

### 인증 파일

```
/etc/auto-comment-worker/
├── github-token           # GitHub PAT (600)
└── credentials/
    ├── webhook-secret     # Webhook HMAC (600)
    └── blog-api-key       # Blog API 키 (600)
```

보안: `S_IWOTH`만 검사 (world-writable 거부). systemd `ProtectSystem=strict`.

→ 상세: `.claudekb/operations/server-management.md`

---

## 3. 댓글 관리

auto-comment-worker가 자동 처리. 정상 운영 시 개입 불필요.

**파이프라인:** Webhook → HMAC 검증 → 필터링 → Claude Code AI 응답 → GraphQL 게시

**필터링:** 소유주(yarang) 댓글 무시, AI 마커 감지 시 무시 (무한루프 방지)

**모니터링:** `sudo journalctl -u auto-comment-worker -f`

→ 상세: `.claudekb/operations/comment-management.md`

---

## Knowledge Base (.claudekb/)

```
.claudekb/
├── infrastructure/
│   ├── system-architecture.md    # 전체 시스템 아키텍처
│   └── server-topology.md        # 서버 구성 상세
├── operations/
│   ├── blog-writing-guide.md     # 글 작성 가이드
│   ├── server-management.md      # 서버 관리 가이드
│   └── comment-management.md     # 댓글 관리 가이드
├── troubleshooting/
│   ├── github-token-4step-debugging.md
│   └── file-permission-S_IWOTH.md
└── decisions/
    └── file-based-credentials.md
```

### 갱신 규칙

- 트러블슈팅 완료 (2단계+ 원인 체인) → `troubleshooting/`
- 설계 결정 (2개+ 선택지 비교) → `decisions/`
- 인프라 변경 → `infrastructure/`

---

## Work History

| 날짜 | 작업 | 관련 문서 |
|------|------|-----------|
| 2026-05-03 | 시스템 초기 구축 | `troubleshooting/github-token-4step-debugging.md` |
| 2026-05-03 | 파일 권한 수정 | `troubleshooting/file-permission-S_IWOTH.md` |
| 2026-05-03 | 인증 방식 결정 | `decisions/file-based-credentials.md` |
| 2026-05-03 | 에이전트 운영 체계 구축 | `infrastructure/system-architecture.md` |
| 2026-05-03 | 운영 가이드 작성 | `operations/*.md` |
---

## 4. 자동화 에이전트

arm1에서 systemd timer로 운영되는 자동화 에이전트들.

### 에이전트 목록

| 에이전트 | 스케줄 | 역할 | 서비스 |
|----------|--------|------|--------|
| auto-translate | 6시간마다 | 미번역 포스트 자동 번역 | `auto-translate.timer` |
| post-generator | 매일 09:00 | AI 블로그 포스트 자동 생성 | `post-generator.timer` |
| auto-comment-worker | 상시 | 댓글 AI 응답 | `auto-comment-worker.service` |

### 에이전트 관리

```bash
# 타이머 상태 확인
systemctl list-timers --all | grep -E "auto-translate|post-generator"

# 수동 실행
sudo systemctl start auto-translate.service
sudo systemctl start post-generator.service

# 로그 확인
sudo journalctl -u auto-translate -n 50 --no-pager
sudo journalctl -u post-generator -n 50 --no-pager
```

### 모니터링 대시보드

```bash
python3 /var/www/auto-comment-worker/scripts/comment-dashboard.py          # CLI 대시보드
python3 /var/www/auto-comment-worker/scripts/comment-dashboard.py --days 7 # 최근 7일
python3 /var/www/auto-comment-worker/scripts/comment-dashboard.py --json   # JSON 출력
```

### 스크립트 위치

```
scripts/
├── auto-comment-worker.py    # 댓글 AI 응답 워커 (Flask)
├── auto-translate.sh         # 자동 번역 (Blog API 호출)
├── post-generator.py         # 일일 포스트 자동 생성 (Claude Code CLI)
├── comment-dashboard.py      # 모니터링 대시보드
├── monitor-agent.sh          # 모니터 에이전트
└── requirements-auto-comment-worker.txt

deploy/
├── auto-comment-worker.service
├── auto-translate.service + .timer
├── post-generator.service + .timer
├── install-auto-comment-worker.sh
└── update-and-restart.sh
```
