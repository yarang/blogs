# 결정: 파일 기반 인증 관리

**결정일**: 2026-05-03
**상태**: 채택됨

## 맥락

GitHub PAT와 Webhook HMAC 시크릿을 시스템에서 관리하는 방법을 결정해야 했다.

## 선택지

### A. 환경 변수 직접 지정 (기각)

```ini
Environment=GITHUB_TOKEN=ghp_xxxxx
```

문제점:
- `/proc/PID/environ`에서 평문 노출
- 디버깅 로그에 환경 변수 유출 위험
- `subprocess.run`으로 자식 프로세스에 모든 환경 변수 상속
- systemd 서비스 파일에 평문 시크릿 → git 커밋 위험

### B. 파일 기반 + 경로만 환경 변수 (채택)

```ini
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
```

장점:
- 환경 변수에는 경로만 노출, 시크릿 값은 파일에만 존재
- 파일 권한(640, 600)으로 접근 제어
- 서비스 파일을 git에 안전하게 커밋 가능
- `/proc/PID/environ`에 시크릿 미노출

### C. systemd LoadCredential (부분 시도 후 기각)

```ini
LoadCredential=github-token:/etc/auto-comment-worker/github-token
```

문제: `%d` 변수가 `RuntimeDirectory` 없이는 해석되지 않음. 추가 설정 필요.

## 결정

**B안 채택**: 단순하고 검증 가능하며, 기존 파일 시스템 권한 모델을 활용.

## 구현 규칙

1. 시크릿 파일은 `/etc/auto-comment-worker/` 아래에 저장
2. 토큰 파일 소유자: `ubuntu:ubuntu`, 권한: `640`
3. webhook-secret 파일 소유자: `ubuntu:ubuntu`, 권한: `600`
4. Python에서 파일 읽기 전 `S_IWOTH` 검사 (world-writable 거부)
5. 파일 존재 시 파일 우선, 없으면 환경 변수 폴백
