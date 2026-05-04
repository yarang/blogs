+++
title = "[AgentForge] 블로그 자동화 서비스 전체 아키텍처 — AI 댓글, 번역, 포스트 생성까지"
slug = "2026-05-05-001-agentforge-blog-automation-architecture"
date = 2026-05-05T00:30:00+09:00
draft = false
tags = ["agentforge", "automation", "llm", "gemini", "fastapi", "hugo", "architecture"]
categories = ["Development", "Architecture"]
ShowToc = true
TocOpen = true
+++

블로그를 운영하면서 가장 번거로운 작업 세 가지가 있습니다. 댓글에 답하기, 영문 번역 유지하기, 그리고 꾸준히 글 쓰기. [AgentForge](https://github.com/yarang) 프로젝트에서는 이 세 가지를 모두 AI 에이전트로 자동화했습니다.

이 글에서는 2개 서버에 걸쳐 동작하는 블로그 자동화 서비스의 전체 아키텍처를 정리합니다.

---

## 시스템 토폴로지

```
┌─────────────────────┐      HTTPS       ┌─────────────────────┐
│      arm1 서버       │ ──────────────▶  │      ec1 서버       │
│  (에이전트 오퍼레이터)  │                  │  (블로그 호스팅)      │
├─────────────────────┤                  ├─────────────────────┤
│ blog-agent (:8081)  │                  │ Hugo (nginx)        │
│  ├─ CommentHandler  │                  │ Blog API (:8000)    │
│  ├─ TranslateHandler│                  │  ├─ translator.py   │
│  └─ PostGenerator   │                  │  ├─ blog_manager.py │
│                     │                  │  └─ git_handler.py  │
│ NATS / PostgreSQL   │                  │                     │
│ Prometheus / Grafana │                  │ Git (yarang/blogs)  │
└─────────────────────┘                  └─────────────────────┘
```

| 서버 | 역할 | 핵심 서비스 |
|------|------|------------|
| **arm1** | 에이전트 오퍼레이터 | `blog-agent.service` — Flask + Scheduler + LLM Client |
| **ec1** | 블로그 호스팅 + API | Hugo (nginx) + `blog-api.service` (FastAPI) |

두 서버 간 통신은 **HTTPS API 호출만** 가능합니다. arm1에서 ec1로의 SSH 접속은 차단되어 있어, 모든 연동은 Blog API를 통해 이루어집니다.

---

## arm1: 통합 블로그 에이전트

### 왜 통합했는가

초기에는 댓글 응답, 번역, 포스트 생성이 각각 독립 프로세스(3개 systemd 서비스)로 운영되었습니다. 문제는:

- Claude Code CLI(`--print`) 호출 방식으로 **응답 시간 9.7초**, 디스크 688MB 소모
- systemd 유닛 6개 관리 부담
- 프로세스 간 상태 공유 불가

이를 **1개 프로세스**로 통합하면서 직접 LLM API 호출로 전환했습니다. 결과:

| 지표 | Before | After |
|------|--------|-------|
| 응답 시간 | 9.7초 | 1.7초 |
| 디스크 사용 | 688MB | ~50MB |
| systemd 유닛 | 6개 | 1개 |
| 프로세스 | 3개 | 1개 |

### 아키텍처

```python
class BlogAgent:
    """1 프로세스 = Flask (webhook) + Scheduler (timer) + LLM Client"""
    
    def __init__(self):
        self.config = AgentConfig.from_credentials()
        self.llm = LLMClient(self.config)       # ZAI glm-4.7
        self.api = BlogAPIClient(self.config)     # ec1 Blog API
        
        # 핸들러
        self.comment = CommentHandler(self.llm, self.config)
        self.translate = TranslateHandler(self.api)
        self.post_gen = PostGenerator(self.llm, self.api)
        
        # 스케줄러
        self.scheduler = Scheduler()
        self.scheduler.every(hours=6, task=self.translate.check_and_sync)
        self.scheduler.daily_at(hour=9, task=self.post_gen.generate_and_publish)
```

### 모듈별 동작

#### 1. CommentHandler — AI 댓글 응답

GitHub Discussions의 Webhook 이벤트를 수신하여 자동으로 AI 댓글을 생성합니다.

```
[사용자 댓글] → GitHub Webhook → arm1 Flask → CommentHandler
    → LLM 호출 (ZAI glm-4.7) → 답변 생성 → GitHub API로 댓글 게시
```

- **트리거**: Webhook 이벤트 기반 (실시간)
- **필터링**: 블로그 소유자 댓글, AI 생성 댓글은 건너뜀
- **보안**: HMAC-SHA256 Webhook 시크릿 검증, Flask-Limiter 적용

#### 2. TranslateHandler — 자동 번역 트리거

6시간마다 ec1의 Blog API에 번역 동기화를 요청합니다.

```
[Scheduler 6h] → TranslateHandler.check_and_sync()
    → POST /translate/sync → ec1 Blog API가 실제 번역 수행
```

arm1은 번역을 직접 수행하지 않고, ec1 API에 **트리거만** 보냅니다. 실제 번역 로직은 ec1의 `translator.py`에 있습니다.

#### 3. PostGenerator — 자동 포스트 생성

매일 오전 9시에 기술 블로그 포스트를 자동 생성합니다.

```
[Scheduler 09:00 KST] → PostGenerator.generate_and_publish()
    → 기존 주제 수집 → RSS 트렌드 참조 → LLM으로 콘텐츠 생성
    → 중복 검사 → Blog API로 게시
```

**중복 방지**가 핵심입니다. `difflib.SequenceMatcher`로 새 제목과 최근 100개 기존 제목의 유사도를 비교합니다:

```python
def _is_duplicate_title(self, new_title, existing_titles):
    """threshold 0.6 이상이면 중복으로 판정"""
    new_lower = new_title.lower().strip()
    for title in existing_titles[-100:]:
        ex_lower = title.lower().strip()
        ratio = difflib.SequenceMatcher(None, new_lower, ex_lower).ratio()
        if ratio >= 0.6:
            return True
    return False
```

---

## ec1: Blog API 번역 시스템

### Gemini로의 전환

초기에는 ZAI(glm-4.7)로 번역을 수행했으나, 치명적인 문제가 발생했습니다:

> glm-4.7은 **reasoning 모델**로, `max_tokens` 예산을 `reasoning_content`(내부 사고 과정)에 먼저 소진합니다. `max_tokens=256`이면 reasoning에 256토큰을 모두 쓰고, 실제 `content`는 빈 문자열이 됩니다.

이로 인해 **9개 영문 게시글의 제목이 빈 문자열**로 번역되는 사고가 발생했습니다.

해결책: **Gemini 2.5 Flash Lite**로 교체.

| 항목 | ZAI (이전) | Gemini (현재) |
|------|-----------|--------------|
| 모델 | glm-4.7 (reasoning) | gemini-2.5-flash-lite |
| 번역 시간 | ~30초/포스트 | ~8초/포스트 |
| 비용 | API 유료 | 무료 (1,500건/일) |
| 빈 응답 문제 | 발생 | 없음 |

### OpenAI-Compatible 엔드포인트

Gemini는 OpenAI 호환 API를 제공합니다. 기존 코드를 **한 줄도 바꾸지 않고** base URL만 교체하면 됩니다:

```python
LLM_BASE_URLS = {
    "GEMINI": "https://generativelanguage.googleapis.com/v1beta/openai",
    "ZAI":    "https://api.z.ai/api/coding/paas/v4",
}
```

### 번역 매칭 로직

한국어↔영어 게시글 페어링은 **날짜 접두사 매칭**을 사용합니다:

```
ko: 2026-05-04-001-개발-생산성-17배-극대화-deepseek-v4와-...
en: 2026-05-04-001-개발-생산성-17배-극대화-deepseek-v4와-...
                    ↑ 같은 접두사 = 같은 게시글
```

slug의 언어가 다를 수 있지만, `YYYY-MM-DD-NNN` 부분이 같으면 같은 게시글로 인식합니다. 이 방식의 전제 조건은 **같은 날짜에 같은 번호가 2개 이상 존재하면 안 된다**는 것입니다.

### Title-in-Body 번역 기법

제목을 별도 API 호출로 번역하면 reasoning 모델에서 빈 결과가 나오는 문제가 있었습니다. 해결책은 **제목을 본문 첫 줄에 포함**시키는 것:

```python
# 번역 요청 시
prompt = f"# {original_title}\n\n{original_body}"

# 번역 결과에서 제목 추출
if translated.lstrip().startswith("# "):
    lines = translated.lstrip().split("\n", 1)
    extracted_title = lines[0].lstrip("# ").strip()
    translated_body = lines[1].lstrip("\n")
```

하나의 API 호출로 제목과 본문을 동시에 번역하므로, 맥락이 보존되고 토큰도 절약됩니다.

---

## LLM 전략: 역할별 모델 분리

하나의 LLM으로 모든 작업을 처리하지 않습니다. 작업 성격에 맞춰 모델을 분리했습니다.

| 작업 | 서버 | 모델 | 이유 |
|------|------|------|------|
| 댓글 AI 응답 | arm1 | ZAI glm-4.7 | 대화형, 한국어 품질 우수 |
| 포스트 생성 | arm1 | ZAI glm-4.7 | 긴 글 생성, 창의성 필요 |
| 번역 (ko→en) | ec1 | Gemini Flash Lite | 비추론형, 빠르고 무료 |

핵심 원칙: **reasoning 모델은 번역에 쓰지 않는다**. reasoning 모델은 내부 사고에 토큰을 소비하므로, 단순 변환 작업에는 비추론형 모델이 적합합니다.

---

## 모니터링과 운영

### 헬스체크 엔드포인트

```bash
# arm1 에이전트
curl http://arm1:8081/health
# → {"status":"healthy","agent":"blog-agent","scheduler_jobs":2,"uptime_sec":...}

curl http://arm1:8081/status
# → {"scheduler":[{"name":"auto-translate","last_run":...},{"name":"post-generator","last_run":"2026-05-04"}]}

# ec1 Blog API
curl https://blog.example.com/api/health
# → {"status":"healthy","version":"2.0.0"}
```

### 관찰 포인트

| 지표 | 정상 범위 | 알림 조건 |
|------|----------|----------|
| arm1 uptime | >0 | 서비스 다운 |
| scheduler_jobs | 2 | ≠ 2 |
| 번역 동기화 | ko=en 개수 일치 | 차이 발생 |
| 포스트 생성 | 매일 1건 | 24시간 이상 미생성 |

---

## 교훈과 운영 팁

### 1. Reasoning 모델의 함정

`max_tokens`가 reasoning과 content를 **합산**한다는 것을 문서에서 명시하지 않는 경우가 많습니다. 빈 응답이 나오면 `finish_reason`을 확인하세요 — `"length"`라면 토큰 예산 부족입니다.

### 2. OpenAI-Compatible 패턴의 가치

번역 제공자를 ZAI에서 Gemini로 바꿀 때 코드 변경이 **base URL 1줄**이었습니다. 처음부터 OpenAI-compatible 인터페이스로 추상화하면 LLM 교체 비용이 극적으로 줄어듭니다.

### 3. 날짜 접두사 매칭의 제약

`YYYY-MM-DD-NNN` 패턴에서 같은 날짜에 같은 번호가 2개 이상 존재하면 번역 매칭이 깨집니다. PostGenerator에서 새 게시글 생성 시 해당 날짜의 마지막 번호 + 1을 확인하는 로직이 필수입니다.

### 4. 통합 프로세스의 이점

3개 독립 서비스를 1개로 통합하면서 얻은 것:
- 상태 공유 (LLM 클라이언트, 설정, API 클라이언트를 한 번만 초기화)
- 배포 단순화 (systemd 유닛 1개)
- 디버깅 용이 (로그가 한 곳에 모임)

---

## 향후 계획

- arm1 에이전트의 LLM도 Gemini로 통합 검토
- 댓글 품질 평가 파이프라인 (자동 생성 댓글의 적절성 모니터링)
- 번역 품질 자동 검증 (역번역 비교)
- AgentForge 프레임워크를 통한 에이전트 간 협업 확대

---

블로그 자동화는 "완전 자동"이 아니라 "최소 개입"을 목표로 합니다. AI가 생성한 콘텐츠를 사람이 검토하고, 시스템이 이상 징후를 감지하면 운영자에게 알리는 구조가 안정적인 운영의 핵심입니다.
