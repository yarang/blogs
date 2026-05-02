+++
title = "블로그 AI 자동 댓글 시스템 구축기 (2/3) — 보안 강화"
date = 2026-05-03T02:10:00+09:00
draft = false
tags = ["security", "hmac", "credential-management", "file-permissions", "systemd", "hardening"]
categories = ["Development", "Security", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = true
TocOpen = true
+++

## 개요

[1부](/ko/post/ai-auto-comment-system-architecture-and-implementation/)에서 AI 자동 댓글 시스템의 아키텍처와 구현을 다뤘습니다. 이번 2부에서는 보안 측면을 집중적으로 다룹니다.

외부 Webhook을 수신하고, GitHub API 토큰을 관리하며, 사용자 입력을 처리하는 시스템은 보안이 특히 중요합니다. 환경 변수 대신 파일 기반 인증으로 전환한 과정과 그 이유, 각 보안 계층의 설계를 설명합니다.

---

## 보안 위협 모델

이 시스템이 방어해야 하는 위협:

| 위협 | 공격 벡터 | 방어 수단 |
|------|-----------|-----------|
| 위장 Webhook | 공격자가 가짜 Webhook 전송 | HMAC-SHA256 시그니처 검증 |
| 토큰 유출 | 환경 변수 노출, 로그 노출 | 파일 기반 인증 + 권한 제한 |
| XSS/인젝션 | 악의적인 댓글 내용 | 입력 sanitization |
| 과도한 요청 | DDoS, 남용 | Flask-Limiter 속도 제한 |
| 권한 상승 | 워커 프로세스 탈취 | systemd 보안 디렉티브 |
| 무한 루프 | AI가 자신에게 응답 | 마커 기반 댓글 감지 |

---

## 파일 기반 인증 관리

### 환경 변수의 문제점

처음에는 GitHub 토큰과 Webhook 시크릿을 환경 변수로 관리했습니다:

```ini
# 초기 (안전하지 않음)
Environment=GITHUB_TOKEN=ghp_xxxxx
Environment=GITHUB_WEBHOOK_SECRET=my-secret-key
```

환경 변수 방식의 문제점:
- **`/proc/PID/environ`**: Linux에서 프로세스의 환경 변수가 파일로 노출됨
- **로그 노출**: 디버깅 중 환경 변수가 로그에 기록될 위험
- **자식 프로세스 상속**: `subprocess.run`으로 Claude Code 실행 시 모든 환경 변수가 상속됨
- **systemd 설정 파일**: 서비스 파일에 평문 시크릿이 포함되면 git에 커밋될 위험

### 파일 기반으로 전환

인증 정보를 파일 시스템에 저장하고, 환경 변수에는 **파일 경로만** 지정합니다:

```ini
# 개선 후 — 경로만 노출
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
Environment=GITHUB_WEBHOOK_SECRET_FILE=/etc/auto-comment-worker/credentials/webhook-secret
```

서버의 디렉토리 구조:

```
/etc/auto-comment-worker/
├── github-token              # GitHub Personal Access Token (640)
└── credentials/
    └── webhook-secret         # GitHub Webhook HMAC Secret (600)
```

### 토큰 파일 로드 코드

```python
import stat

GITHUB_TOKEN_FILE = os.environ.get('GITHUB_TOKEN_FILE', '')
if GITHUB_TOKEN_FILE and os.path.exists(GITHUB_TOKEN_FILE):
    # 파일 권한 검증
    st = os.stat(GITHUB_TOKEN_FILE)
    if st.st_mode & stat.S_IWOTH:
        raise PermissionError("Token file must not be world-writable")
    with open(GITHUB_TOKEN_FILE, 'r') as f:
        GITHUB_TOKEN = f.read().strip()
else:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
```

핵심 설계 결정:
1. **파일 존재 시 파일 우선**: 환경 변수는 폴백으로만 사용
2. **권한 검증**: 파일을 읽기 전에 권한을 확인
3. **strip()**: 파일 끝의 개행 문자 제거

### 파일 권한 검증 — 삽질의 기록

이 부분에서 가장 많은 시간을 소비했습니다. 초기 코드는 지나치게 엄격했습니다:

```python
# 초기 코드 — 너무 엄격함
if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
    raise PermissionError("Token file must be 600 or 400")
```

이 코드의 문제: `S_IRWXO | S_IRWXG`는 **그룹의 모든 권한**(읽기/쓰기/실행)과 **기타의 모든 권한**을 검사합니다. 즉, 파일 권한이 `640` (소유자 읽기/쓰기, 그룹 읽기)이면 거부됩니다.

```
# 비트 마스크 분석
S_IRWXG = 0o070  # 그룹의 읽기+쓰기+실행
S_IRWXO = 0o007  # 기타의 읽기+쓰기+실행

# 640 = 0o640
0o640 & (0o070 | 0o007) = 0o640 & 0o077 = 0o040  # 0이 아님 → 거부!
```

실제 보안상 중요한 것은 **다른 사용자(other)가 파일을 수정할 수 없는 것**입니다. 그룹 읽기 권한은 같은 그룹 사용자가 파일을 읽을 수 있게 해주며, 보안상 문제가 되지 않습니다.

수정 후:

```python
# 수정 후 — 실제 위협에 집중
if st.st_mode & stat.S_IWOTH:
    raise PermissionError("Token file must not be world-writable")
```

`stat.S_IWOTH` (`0o002`)만 검사하면 됩니다. 이는 "기타 사용자에게 쓰기 권한이 있는가"만 확인합니다.

| 권한 | 8진수 | 초기 코드 | 수정 후 |
|------|-------|-----------|---------|
| `600` | `0o600` | 허용 | 허용 |
| `640` | `0o640` | **거부** | 허용 |
| `644` | `0o644` | 거부 | 허용 |
| `646` | `0o646` | 거부 | **거부** |
| `666` | `0o666` | 거부 | **거부** |

---

## HMAC-SHA256 시그니처 검증

GitHub Webhook은 요청 본문을 Webhook 시크릿으로 HMAC-SHA256 해싱한 시그니처를 `X-Hub-Signature-256` 헤더로 전송합니다. 이를 검증하여 요청이 실제 GitHub에서 왔는지 확인합니다.

```python
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """GitHub 웹훅 시그니처 검증"""
    if not signature:
        logger.warning("Missing webhook signature")
        return False

    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not configured - skipping validation")
        return True  # 개발 모드 허용

    try:
        hash_algorithm, github_signature = signature.split('=', 1)
        if hash_algorithm != 'sha256':
            return False

        mac = hmac.new(
            WEBHOOK_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()

        # 타이밍 공격 방지
        if not hmac.compare_digest(expected_signature, github_signature):
            return False

        return True
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False
```

주요 포인트:
- **`hmac.compare_digest()`**: 일반 `==` 비교 대신 상수 시간 비교를 사용하여 타이밍 공격을 방지합니다.
- **raw bytes 사용**: `request.data` (원본 바이트)를 사용합니다. `request.json`으로 파싱 후 재직렬화하면 원본과 달라질 수 있습니다.
- **개발 모드**: 시크릿이 설정되지 않으면 검증을 건너뜁니다. 프로덕션에서는 반드시 시크릿을 설정해야 합니다.

### nginx 헤더 포워딩

시그니처 검증이 정상 작동하려면 nginx가 `X-Hub-Signature-256` 헤더를 포워딩해야 합니다:

```nginx
location /webhook {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
}
```

`X-Hub-Signature-256`을 명시적으로 포워딩하지 않으면, 기본 `proxy_pass`만으로는 커스텀 헤더가 전달되지 않을 수 있습니다.

---

## 요청 검증 (marshmallow 스키마)

Webhook 페이로드의 구조를 marshmallow 스키마로 검증합니다:

```python
class WebhookSchema(Schema):
    action = fields.Str(required=True, validate=validate.Equal('created'))
    comment = fields.Dict(required=True)
    discussion = fields.Dict(required=True)
    repository = fields.Dict(required=True)
    sender = fields.Dict(required=False)
```

- **`action = 'created'`만 허용**: 댓글 수정(`edited`)이나 삭제(`deleted`) 이벤트는 거부합니다.
- **필수 필드 검증**: `comment`, `discussion`, `repository`가 없으면 400 에러를 반환합니다.
- **ValidationError → 감사 로그**: 잘못된 요청은 감사 로그에 기록됩니다.

---

## 입력 Sanitization

사용자 댓글은 외부 입력이므로 반드시 처리합니다:

```python
def sanitize_comment(body: str) -> str:
    """사용자 입력 sanitization"""
    body = re.sub(r'<[^>]+>', '', body)    # HTML 태그 제거
    body = html.escape(body)                # 특수 문자 이스케이프
    body = body[:1000]                      # 길이 제한
    return body
```

이 sanitization이 적용되는 곳:
- 댓글 본문 (`comment_body`)
- 토론 제목과 본문 (`discussion_title`, `discussion_body`)
- 원작성자 이름 (`original_author`)
- AI 응답 게시 시 인용 부분

### 사용자명 마스킹

로그에 사용자 이름 전체를 기록하지 않습니다:

```python
def mask_username(username: str) -> str:
    """사용자명 마스킹"""
    if not username or len(username) < 4:
        return "***"
    return f"{username[:3]}***"
```

로그에는 `yar***`처럼 마스킹된 이름만 표시됩니다. 개인정보 보호와 디버깅 편의성 사이의 균형을 맞춥니다.

---

## 속도 제한

Flask-Limiter로 엔드포인트별 속도 제한을 적용합니다:

```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://"
)

@app.route('/webhook', methods=['POST'])
@limiter.limit("10 per minute")
def github_webhook():
    ...
```

- **분당 10회 제한**: 정상적인 Webhook 호출 빈도를 고려한 수치
- **`get_remote_address`**: 클라이언트 IP 기준으로 제한
- **`memory://`**: 인메모리 저장소 (단일 프로세스에 적합)

---

## systemd 보안 디렉티브

3부에서 systemd 배포를 상세히 다루지만, 보안 관련 디렉티브는 여기서 설명합니다:

```ini
[Service]
# 보안 강화
NoNewPrivileges=true       # 권한 상승 방지
PrivateTmp=true            # 독립된 /tmp 제공
ProtectSystem=strict       # 파일시스템 읽기 전용
ProtectHome=false          # 홈 디렉토리 접근 허용 (Claude Code 설정)
ReadWritePaths=/var/www/auto-comment-worker /var/log/auto-comment-worker

# 리소스 제한
MemoryMax=512M             # 메모리 제한
CPUQuota=50%               # CPU 사용량 제한
TasksMax=100               # 프로세스 수 제한
```

| 디렉티브 | 효과 |
|----------|------|
| `NoNewPrivileges=true` | `setuid`, `setgid` 등으로 권한 상승 불가 |
| `PrivateTmp=true` | 독립된 `/tmp` 네임스페이스, 다른 프로세스와 격리 |
| `ProtectSystem=strict` | 전체 파일시스템을 읽기 전용으로 마운트 |
| `ReadWritePaths` | 명시적으로 쓰기를 허용할 경로만 지정 |
| `MemoryMax=512M` | OOM 상황에서 시스템 전체를 보호 |

### `ProtectSystem=strict`과 `ReadOnlyPaths`의 충돌

초기에 `ReadOnlyPaths=/etc/auto-comment-worker`를 추가했다가 토큰 파일을 읽지 못하는 문제가 발생했습니다. `ProtectSystem=strict`가 이미 전체 파일시스템을 읽기 전용으로 설정하므로, 별도의 `ReadOnlyPaths`는 불필요합니다. 오히려 일부 환경에서 충돌을 일으킬 수 있어 제거했습니다.

---

## 마무리

이번 2부에서는 파일 기반 인증 관리, 파일 권한 검증 삽질기, HMAC-SHA256 시그니처 검증, 입력 sanitization, 속도 제한, systemd 보안 디렉티브를 다뤘습니다.

보안에서 가장 중요한 교훈: **"너무 엄격한 검증은 너무 느슨한 검증만큼 해롭다."** 파일 권한을 `600`만 허용하는 초기 코드는 보안상 안전했지만, 실제 운영 환경에서 `640` 권한의 파일을 거부하여 서비스가 시작되지 않았습니다. 실제 위협(world-writable)에만 집중하는 것이 올바른 접근입니다.

다음 3부에서는 **배포와 트러블슈팅** — systemd 서비스 구성, nginx 리버스 프록시, 실제 겪은 오류들과 해결 과정을 다룹니다.

---

*이 글은 AgentForge 블로그 자동 댓글 시스템 시리즈의 2부입니다.*
