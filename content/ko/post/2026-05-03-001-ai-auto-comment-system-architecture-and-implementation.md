+++
title = "블로그 AI 자동 댓글 시스템 구축기 (1/3) — 아키텍처와 구현"
date = 2026-05-03T02:00:00+09:00
draft = false
tags = ["ai", "giscus", "github-discussions", "webhook", "flask", "claude-code", "automation", "blog"]
categories = ["Development", "AI", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = true
TocOpen = true
+++

## 개요

블로그 댓글에 AI가 자동으로 응답하는 시스템을 구축했습니다. 독자가 블로그 포스트에 댓글을 남기면, AI 어시스턴트가 포스트 컨텍스트를 분석하여 기술적으로 정확하면서도 친절한 답변을 자동으로 생성합니다.

이 시리즈는 3부작으로 구성됩니다:
- **1부 (이 글)**: 전체 아키텍처 설계와 핵심 코드 구현
- **2부**: 파일 기반 인증, 권한 관리, 보안 강화
- **3부**: systemd 배포, nginx 프록시, 트러블슈팅

---

## 시스템 아키텍처

### 전체 데이터 흐름

```
독자 댓글 작성
    ↓
[giscus] → GitHub Discussions에 댓글 생성
    ↓
[GitHub Webhook] → HTTP POST 전송
    ↓
[nginx reverse proxy] → 헤더 포워딩
    ↓
[Flask Worker] → 시그니처 검증 → 댓글 분석
    ↓
[Claude Code CLI] → AI 응답 생성
    ↓
[GitHub GraphQL API] → Discussion에 답변 게시
    ↓
[giscus] → 블로그에 답변 표시
```

이 아키텍처에서 핵심은 **giscus가 GitHub Discussions를 댓글 저장소로 사용한다**는 점입니다. 따라서 GitHub Webhook으로 새 댓글 이벤트를 수신하고, 같은 GitHub API로 응답을 게시할 수 있습니다.

### 구성 요소

| 구성 요소 | 역할 | 기술 |
|-----------|------|------|
| giscus | 블로그 댓글 위젯 | GitHub Discussions 기반 |
| GitHub Webhook | 이벤트 전달 | `discussion_comment` 이벤트 |
| nginx | 리버스 프록시 | 헤더 포워딩, SSL 터미네이션 |
| Flask Worker | 웹훅 수신 및 처리 | Python, Flask, Flask-Limiter |
| Claude Code | AI 응답 생성 | `--print` 모드 CLI 호출 |
| GitHub GraphQL | 응답 게시 | Mutation API |

---

## giscus 설정

Hugo 블로그에 giscus를 통합하려면 `hugo.toml`에 다음 설정이 필요합니다:

```toml
[params]
    [params.comments]
        enabled = true
        provider = "giscus"
        [params.comments.giscus]
            repo = "yarang/blogs"
            repoId = "YOUR_REPO_ID"
            category = "General"
            categoryId = "YOUR_CATEGORY_ID"
            mapping = "pathname"
            strict = "0"
            reactionsEnabled = "1"
            emitMetadata = "0"
            inputPosition = "bottom"
            lang = "ko"
            theme = "noborder_gray"
```

`mapping = "pathname"`은 포스트 URL 경로를 기준으로 Discussion을 매핑합니다. 이렇게 하면 각 블로그 포스트마다 독립적인 Discussion이 생성됩니다.

---

## GitHub Webhook 구성

GitHub 리포지토리 Settings > Webhooks에서:

- **Payload URL**: `https://your-domain/webhook`
- **Content type**: `application/json`
- **Secret**: HMAC-SHA256 서명용 시크릿 (보안 편에서 상세히 다룸)
- **Events**: `Discussion comments` 선택

Webhook은 댓글이 생성될 때마다 `discussion_comment` 이벤트를 Flask 워커로 전송합니다.

---

## Flask 워커 구현

### 프로젝트 구조

```
auto-comment-worker/
├── scripts/
│   └── auto-comment-worker.py    # 메인 워커
├── deploy/
│   └── auto-comment-worker.service  # systemd 서비스
├── venv/                          # Python 가상환경
└── logs/
    └── audit.log                  # 감사 로그
```

### 핵심 의존성

```python
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError
```

- **Flask**: 경량 웹 프레임워크로 Webhook 엔드포인트 제공
- **Flask-Limiter**: 속도 제한으로 남용 방지 (분당 10회)
- **marshmallow**: 요청 스키마 검증으로 안전한 데이터 파싱

### 웹훅 엔드포인트

```python
@app.route('/webhook', methods=['POST'])
@limiter.limit("10 per minute")
def github_webhook():
    """GitHub Webhook 수신"""
    # 1. 시그니처 검증
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook_signature(request.data, signature):
        log_audit('SIGNATURE_INVALID', {'ip': request.remote_addr})
        return jsonify({'status': 'unauthorized'}), 401

    # 2. 요청 스키마 검증
    schema = WebhookSchema()
    try:
        payload = schema.load(request.json)
    except ValidationError as err:
        return jsonify({'status': 'invalid'}), 400

    # 3. 댓글 정보 추출 및 필터링
    comment = payload.get('comment', {})
    discussion = payload.get('discussion', {})
    original_author = comment.get('user', {}).get('login', '사용자')

    # 블로그 소유주의 댓글이면 무시
    if _is_blog_owner(original_author):
        return jsonify({'status': 'owner_comment_ignored'}), 200

    # AI가 생성한 댓글이면 무시 (무한 루프 방지)
    if _is_ai_generated_comment(comment.get('body', '')):
        return jsonify({'status': 'ai_comment_ignored'}), 200

    # 4. AI 응답 생성 및 게시
    discussion_graphql_id = get_discussion_graphql_id(
        repo_owner, repo_name, discussion_number
    )
    context = f"제목: {discussion_title}\n\n내용: {discussion_body}"
    reply = analyze_comment(context, comment_body)
    post_reply_graphql(discussion_graphql_id, comment_body, original_author, reply)
```

핵심 흐름은 4단계입니다:
1. **시그니처 검증**: HMAC-SHA256으로 요청이 GitHub에서 왔는지 확인
2. **스키마 검증**: marshmallow로 페이로드 구조 검증
3. **필터링**: 블로그 소유주와 AI 자신의 댓글을 무시 (무한 루프 방지)
4. **응답**: Claude Code로 AI 응답 생성 후 GraphQL API로 게시

### 무한 루프 방지

AI가 생성한 댓글에 다시 AI가 응답하면 무한 루프에 빠집니다. 이를 방지하기 위해 마커 기반 감지를 사용합니다:

```python
def _is_ai_generated_comment(body: str) -> bool:
    """AI가 생성한 댓글인지 식별"""
    ai_markers = [
        '🤖 AI 어시스턴트',
        'AI 어시스턴트',
        'AgentForge',
        'Claude Code로 자동 생성',
        '자동 생성되었습니다'
    ]
    body_lower = body.lower()
    return any(marker.lower() in body_lower for marker in ai_markers)
```

AI 응답을 게시할 때 반드시 이 마커들 중 하나를 본문에 포함합니다:

```python
body = f"""---
**🤖 AI 어시스턴트**

{safe_reply}

*이 댓글은 AgentForge + Claude Code로 자동 생성되었습니다.*
---
"""
```

### Claude Code CLI 호출

Claude Code의 `--print` 모드를 사용하여 비대화형으로 AI 응답을 생성합니다:

```python
def analyze_comment(context: str, comment: str) -> str:
    """AgentForge 설정으로 Claude Code 실행"""
    prompt = f"""## 블로그 포스트 문맥
{context[:2000]}

## 독자 댓글
{comment}

이 댓글에 대한 응답을 작성해주세요.
- 기술 블로그 어시스턴트로서 전문적이면서 친절하게
- 200자 이내로 간결하게
- 필요한 경우 추가 정보나 링크 제시
"""

    cmd = [
        CLAUDE_CODE_PATH,
        '--settings', AGENTFORGE_CONFIG,
        '--print', prompt
    ]

    result = run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    return "의견 감사합니다! 기술적인 부분에 대해 더 논의해보면 좋을 것 같습니다. 🙏"
```

`--settings` 플래그로 AgentForge 전용 설정 파일을 지정합니다. 이 설정 파일에서 모델, 토큰 제한 등을 관리할 수 있습니다.

`--print` 플래그는 Claude Code를 비대화형 모드로 실행하여 결과를 stdout으로 출력합니다. 대화형 모드와 달리 프롬프트-응답 한 번으로 종료됩니다.

### GitHub GraphQL API 통합

giscus는 GitHub Discussions를 사용하므로, 응답도 GitHub GraphQL API로 게시해야 합니다.

**Discussion GraphQL ID 조회:**

```python
def get_discussion_graphql_id(repo_owner, repo_name, discussion_number):
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
            discussion(number: $number) {
                id
            }
        }
    }
    """
    variables = {
        "owner": repo_owner,
        "name": repo_name,
        "number": discussion_number
    }

    response = requests.post(
        GITHUB_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        },
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        return data["data"]["repository"]["discussion"]["id"]
    return None
```

Webhook 페이로드에는 Discussion의 REST API ID만 포함됩니다. 하지만 댓글을 게시하려면 GraphQL Node ID가 필요합니다. 따라서 먼저 GraphQL 쿼리로 Discussion의 Node ID를 조회한 뒤, 이를 사용하여 댓글을 게시합니다.

**응답 게시 (Mutation):**

```python
def post_reply_graphql(discussion_graphql_id, original_comment, original_author, reply):
    query = """
    mutation($discussionId: ID!, $body: String!) {
        addDiscussionComment(input: {
            discussionId: $discussionId, body: $body
        }) {
            comment { id, databaseId }
        }
    }
    """
    # ... (요청 전송)
```

`addDiscussionComment` mutation은 Discussion 전체에 새 댓글을 추가합니다. 특정 댓글에 대한 답글(reply)이 아니라 Discussion 레벨의 댓글입니다.

### 입력 Sanitization

사용자 댓글은 외부 입력이므로 반드시 sanitize합니다:

```python
def sanitize_comment(body: str) -> str:
    """사용자 입력 sanitization"""
    if not body:
        return body
    body = re.sub(r'<[^>]+>', '', body)    # HTML 태그 제거
    body = html.escape(body)                # HTML 엔티티 이스케이프
    body = body[:1000]                      # 길이 제한
    return body
```

XSS 공격을 방지하기 위해 HTML 태그를 제거하고, 남은 특수 문자를 이스케이프하며, 길이를 1000자로 제한합니다.

### 감사 로그

보안 이벤트를 추적하기 위한 감사 로그를 남깁니다:

```python
def log_audit(event_type: str, details: dict):
    """보안 이벤트 감사 로그 기록"""
    with open(AUDIT_LOG, 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'event': event_type,
            'details': details
        }) + '\n')
```

기록하는 이벤트 유형:
- `SIGNATURE_INVALID`: 웹훅 시그니처 검증 실패
- `INVALID_PAYLOAD`: 잘못된 요청 페이로드
- `WEBHOOK_RECEIVED`: 웹훅 수신 성공
- `AI_RESPONSE_SENT`: AI 응답 게시 완료

---

## 마무리

이번 1부에서는 giscus, GitHub Webhook, Flask 워커, Claude Code CLI, GitHub GraphQL API를 연결하는 전체 아키텍처와 핵심 구현 코드를 다뤘습니다.

다음 2부에서는 이 시스템의 **보안 강화** — 파일 기반 인증 관리, 파일 권한 검증, HMAC-SHA256 시그니처 검증 등을 상세히 다룹니다.

---

*이 글은 AgentForge 블로그 자동 댓글 시스템 시리즈의 1부입니다.*
