+++
title = "블로그 AI 자동 댓글 시스템 구축기 (3/3) — 배포와 트러블슈팅"
slug = "ai-auto-comment-system-part3-deployment"
date = 2026-05-03T01:20:00+09:00
draft = false
tags = ["systemd", "nginx", "deployment", "troubleshooting", "oci", "arm", "linux"]
categories = ["Development", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = true
TocOpen = true
+++

## 개요

[1부](/ko/post/ai-auto-comment-system-part1-architecture/)에서 아키텍처와 구현을, [2부](/ko/post/ai-auto-comment-system-part2-security/)에서 보안 강화를 다뤘습니다. 이번 3부에서는 실제 OCI ARM 서버에 배포하고 겪은 트러블슈팅 과정을 기록합니다.

특히 **GITHUB_TOKEN이 로드되지 않는 문제**를 4단계에 걸쳐 추적하고 해결한 실제 디버깅 과정을 상세히 공유합니다. "설정했는데 왜 안 되지?"라는 상황에서 어떻게 원인을 좁혀나갔는지가 이 글의 핵심입니다.

---

## 인프라 구성

### 서버 구성

| 서버 | 역할 | 스펙 |
|------|------|------|
| ec1 (x86) | 웹 서버 (nginx, Hugo 블로그) | OCI |
| arm1 (ARM) | 워커 서버 (Flask, Claude Code) | OCI ARM |

블로그는 ec1에서 Hugo로 빌드·서빙하고, AI 댓글 워커는 arm1에서 실행합니다. GitHub Webhook은 arm1으로 직접 전달됩니다.

### 워커 서버 디렉토리 구조

```
/var/www/auto-comment-worker/        # 애플리케이션
├── scripts/
│   └── auto-comment-worker.py
├── deploy/
│   └── auto-comment-worker.service
├── venv/                            # Python 가상환경
└── logs/

/etc/auto-comment-worker/            # 인증 정보
├── github-token                     # 640, ubuntu:ubuntu
└── credentials/
    └── webhook-secret               # 600, ubuntu:ubuntu

/home/ubuntu/.local/bin/claude       # Claude Code CLI
```

---

## systemd 서비스 구성

### 서비스 파일

```ini
[Unit]
Description=Auto Comment Worker for Blog
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/var/www/auto-comment-worker
Environment=PORT=8081
Environment=CLAUDE_CODE_PATH=/home/ubuntu/.local/bin/claude
Environment=BLOG_OWNERS=yarang
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
Environment=GITHUB_WEBHOOK_SECRET_FILE=/etc/auto-comment-worker/credentials/webhook-secret
ExecStart=/var/www/auto-comment-worker/venv/bin/python /var/www/auto-comment-worker/scripts/auto-comment-worker.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=auto-comment-worker

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths=/var/www/auto-comment-worker /var/log/auto-comment-worker
ReadOnlyPaths=

# 리소스 제한
MemoryMax=512M
CPUQuota=50%
TasksMax=100

[Install]
WantedBy=multi-user.target
```

### 주요 설정 해설

**`Type=simple`**: Flask 워커는 포그라운드에서 실행되므로 `simple`이 적합합니다. `forking`은 데몬화하는 프로세스에 사용합니다.

**`User=ubuntu`**: 전용 서비스 계정을 만들 수도 있지만, Claude Code CLI가 `ubuntu` 사용자의 홈 디렉토리 설정에 의존하므로 `ubuntu`로 실행합니다.

**`ProtectHome=false`**: 보통은 `true`로 설정하지만, Claude Code가 `~/.agent_forge_for_zai.json` 설정 파일을 필요로 하므로 홈 디렉토리 접근을 허용합니다.

**`ReadOnlyPaths=`** (빈 값): 초기에 `/etc/auto-comment-worker`를 지정했지만, `ProtectSystem=strict`와 충돌하여 비워두었습니다.

### 서비스 관리 명령어

```bash
# 서비스 파일 복사
sudo cp deploy/auto-comment-worker.service /etc/systemd/system/

# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable auto-comment-worker
sudo systemctl start auto-comment-worker

# 상태 확인
sudo systemctl status auto-comment-worker

# 로그 확인 (실시간)
sudo journalctl -u auto-comment-worker -f

# 최근 로그 확인
sudo journalctl -u auto-comment-worker --since "10 minutes ago"
```

---

## nginx 리버스 프록시

### Webhook 엔드포인트 설정

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL 설정
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Webhook 프록시
    location /webhook {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # GitHub Webhook 시그니처 헤더 포워딩 (필수!)
        proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;

        # 타임아웃 (Claude Code 응답 대기)
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8081;
    }
}
```

`proxy_read_timeout 120s`는 Claude Code CLI가 AI 응답을 생성하는 데 최대 60초가 걸릴 수 있으므로 여유 있게 설정합니다. GitHub Webhook의 기본 타임아웃은 10초이므로, 실제로는 비동기 처리를 고려할 수 있습니다.

---

## 배포 과정

### 수동 배포 (rsync 실패 후)

초기에는 rsync로 배포를 시도했지만, 서버에 대상 디렉토리가 없어 실패했습니다:

```
rsync: [Receiver] mkdir "/var/www/auto-comment-worker/scripts" failed:
No such file or directory
```

대안으로 scp 기반 수동 배포를 진행했습니다:

```bash
# 1. 서버에 디렉토리 생성
ssh ubuntu@arm1 "sudo mkdir -p /var/www/auto-comment-worker/scripts"
ssh ubuntu@arm1 "sudo chown -R ubuntu:ubuntu /var/www/auto-comment-worker"

# 2. 파일 전송
scp scripts/auto-comment-worker.py ubuntu@arm1:/var/www/auto-comment-worker/scripts/
scp deploy/auto-comment-worker.service ubuntu@arm1:/tmp/

# 3. 서비스 파일 설치
ssh ubuntu@arm1 "sudo cp /tmp/auto-comment-worker.service /etc/systemd/system/"

# 4. Python 가상환경 설정
ssh ubuntu@arm1 "cd /var/www/auto-comment-worker && python3 -m venv venv"
ssh ubuntu@arm1 "cd /var/www/auto-comment-worker && venv/bin/pip install flask flask-limiter marshmallow requests"

# 5. 인증 파일 설정
ssh ubuntu@arm1 "sudo mkdir -p /etc/auto-comment-worker/credentials"
# 토큰 파일은 서버에서 직접 생성 (scp로 전송하지 않음)

# 6. 서비스 시작
ssh ubuntu@arm1 "sudo systemctl daemon-reload && sudo systemctl enable --now auto-comment-worker"
```

### heredoc 변수 확장 함정

설치 스크립트를 heredoc으로 작성할 때 흔한 실수:

```bash
# 작은따옴표: 변수가 확장되지 않음!
ssh ubuntu@arm1 << 'ENDSSH'
echo $CREDENTIALS_DIR   # 빈 문자열 출력
ENDSSH

# 큰따옴표 없음: 변수가 로컬에서 확장됨
ssh ubuntu@arm1 << ENDSSH
echo $CREDENTIALS_DIR   # 로컬 변수값으로 확장
ENDSSH
```

이 문제를 피하기 위해 스크립트 대신 명령어를 개별 실행하는 방식으로 전환했습니다.

---

## 트러블슈팅: GITHUB_TOKEN 로드 실패

이 시스템을 배포하면서 가장 많은 시간을 소비한 문제입니다. 댓글 Webhook이 도착하면 다음 에러가 반복되었습니다:

```
INFO:__main__:GITHUB_TOKEN configured: False
INFO:__main__:GitHub API response status: 401
ERROR:__main__:Failed to get Discussion GraphQL ID
```

원인을 추적하는 과정을 단계별로 기록합니다.

### 1단계: LoadCredential 경로 문제

처음에는 systemd의 `LoadCredential` 디렉티브를 사용했습니다:

```ini
LoadCredential=github-token:/etc/auto-comment-worker/github-token
Environment=GITHUB_TOKEN_FILE=%d/github-token
```

`%d`는 credentials 디렉토리 경로로 대체되는 systemd 특수 변수입니다. 하지만 이 변수가 의도대로 해석되지 않아 토큰 파일 경로가 잘못 설정되었습니다.

**해결**: `LoadCredential` 대신 절대 경로를 직접 지정했습니다.

```ini
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
```

### 2단계: 파일 소유권 문제

`GITHUB_TOKEN configured: False`가 여전히 나타났습니다. 파일을 확인해보니:

```bash
$ ls -la /etc/auto-comment-worker/github-token
-rw------- 1 root root 93 May  3 01:10 github-token
```

파일 소유자가 `root`이고 권한이 `600`이므로, `ubuntu` 사용자로 실행되는 서비스는 이 파일을 읽을 수 없습니다.

**해결**:

```bash
sudo chown ubuntu:ubuntu /etc/auto-comment-worker/github-token
sudo chmod 640 /etc/auto-comment-worker/github-token
```

### 3단계: ReadOnlyPaths 충돌

소유권을 변경한 후에도 `GITHUB_TOKEN configured: False`가 계속되었습니다. systemd 서비스 파일에 있던 `ReadOnlyPaths` 설정이 원인이었습니다:

```ini
# 이 설정이 파일 읽기를 차단함
ReadOnlyPaths=/etc/auto-comment-worker
```

`ProtectSystem=strict`가 이미 전체 파일시스템을 읽기 전용으로 마운트합니다. 여기에 `ReadOnlyPaths`를 추가하면 일부 환경에서 마운트 네임스페이스 충돌이 발생할 수 있습니다.

**해결**: `ReadOnlyPaths`를 빈 값으로 변경했습니다.

```ini
ReadOnlyPaths=
```

### 4단계: Python 파일 권한 검증 코드 (근본 원인)

이전 3단계를 모두 해결한 후에도 토큰이 로드되지 않았습니다. 마지막 원인은 Python 코드의 지나치게 엄격한 파일 권한 검증이었습니다:

```python
# 파일 권한 640 → 그룹 읽기 비트(0o040)가 설정됨 → 거부!
if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
    raise PermissionError("Token file must be 600 or 400")
```

2단계에서 `chmod 640`으로 변경했기 때문에, 그룹 읽기 비트가 설정되어 이 검증에 걸렸습니다. 하지만 에러 메시지가 로그에 나타나지 않아 발견이 늦었습니다 — `PermissionError`가 모듈 임포트 시점에 발생하여 서비스 시작 자체를 방해했기 때문입니다.

**해결**: 2부에서 설명한 것처럼 `stat.S_IWOTH`만 검사하도록 수정했습니다.

### 디버깅 로그의 중요성

이 문제를 추적하기 위해 추가한 디버깅 로그:

```python
logger.info(f"GITHUB_TOKEN configured: {bool(GITHUB_TOKEN)}")
logger.info(f"GitHub API response status: {response.status_code}")
logger.info(f"GitHub API response body: {response.text[:500]}")
```

이 로그들이 없었다면 원인을 파악하는 데 훨씬 더 오래 걸렸을 것입니다. 인증 관련 코드에는 항상 토큰 로드 성공/실패 여부와 API 응답 상태를 로깅해야 합니다.

### 디버깅 흐름 요약

```
[1] LoadCredential %d 미해석 → 절대 경로로 변경
                ↓ (여전히 실패)
[2] 파일 소유자 root:root → ubuntu:ubuntu로 변경
                ↓ (여전히 실패)
[3] ReadOnlyPaths 충돌 → 제거
                ↓ (여전히 실패)
[4] Python 권한 검증 S_IRWXG → S_IWOTH로 완화
                ↓
            [해결!]
```

4단계에 걸친 이 디버깅에서 얻은 교훈:
1. **한 번에 하나씩 변경하고 확인**: 여러 설정을 동시에 바꾸면 어떤 것이 원인인지 알 수 없음
2. **로그를 믿되, 로그가 없는 곳을 의심**: 모듈 로드 시점의 예외는 일반 로그에 안 나타날 수 있음
3. **보안 검증 코드도 버그의 원인**: 보안 코드가 정상 동작을 차단하는 경우 — 보안과 운영의 균형

---

## 헬스 체크

서비스가 정상 동작하는지 확인하는 헬스 체크 엔드포인트:

```python
@app.route('/health', methods=['GET'])
def health():
    """헬스 체크"""
    return jsonify({'status': 'healthy'})
```

모니터링 시스템에서 주기적으로 `/health`를 호출하여 서비스 상태를 확인합니다:

```bash
curl -s http://localhost:8081/health
# {"status": "healthy"}
```

---

## 향후 개선 사항

1. **비동기 처리**: GitHub Webhook 타임아웃(10초) 내에 응답하기 위해 Celery나 Redis Queue로 AI 응답 생성을 비동기화
2. **재시도 로직**: GitHub API 호출 실패 시 지수 백오프 재시도
3. **모니터링 대시보드**: Prometheus + Grafana로 응답 시간, 성공률, 에러율 모니터링
4. **자동 배포**: GitHub Actions로 코드 변경 시 자동 배포 파이프라인 구축
5. **테스트**: Webhook 페이로드 모킹으로 통합 테스트 작성

---

## 마무리

3부에 걸쳐 블로그 AI 자동 댓글 시스템의 전체 구축 과정을 기록했습니다:

- **1부**: giscus → GitHub Webhook → Flask → Claude Code → GraphQL의 전체 아키텍처
- **2부**: 파일 기반 인증, HMAC 검증, 입력 sanitization, systemd 보안
- **3부**: 실제 배포, nginx 프록시, 4단계 디버깅 과정

이 시스템의 가장 큰 가치는 **블로그 독자와의 소통을 자동화**한다는 점입니다. 블로그 운영자가 모든 댓글에 즉시 응답하기 어렵지만, AI 어시스턴트가 1차 응답을 제공하여 독자 경험을 개선할 수 있습니다.

코드 전체는 [GitHub 리포지토리](https://github.com/yarang/blogs)에서 확인할 수 있습니다.

---

*이 글은 AgentForge 블로그 자동 댓글 시스템 시리즈의 3부(마지막)입니다.*
