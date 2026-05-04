# GITHUB_TOKEN 로드 실패 — 4단계 디버깅 체인

**발생일**: 2026-05-03
**심각도**: 서비스 기동 불가 (Critical)
**해결 시간**: ~2시간

## 증상

Flask 워커가 시작은 되지만 GitHub API 호출 시 401 Unauthorized 반환.
`journalctl -u auto-comment-worker`에서 `GITHUB_TOKEN configured: False` 확인.

## 원인 체인 (4단계)

각 단계를 해결할 때마다 다음 단계의 문제가 드러남.

### 1단계: systemd LoadCredential + %d 미해석

```ini
# 실패 — %d가 해석되지 않음
LoadCredential=github-token:/etc/auto-comment-worker/github-token
Environment=GITHUB_TOKEN_FILE=%d/github-token
```

`%d`는 `RuntimeDirectory`가 설정되어야 해석됨. 없으면 빈 문자열.

**해결**: 절대 경로를 직접 사용.

```ini
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
```

### 2단계: 토큰 파일 소유자 root:root

```bash
$ ls -la /etc/auto-comment-worker/github-token
-rw-r----- 1 root root 93 ...
```

서비스가 `User=ubuntu`로 실행되므로 root 소유 파일 읽기 불가.

**해결**:

```bash
sudo chown ubuntu:ubuntu /etc/auto-comment-worker/github-token
```

### 3단계: ReadOnlyPaths와 ProtectSystem=strict 충돌

```ini
ProtectSystem=strict           # 전체 FS 읽기 전용
ReadOnlyPaths=/etc/auto-comment-worker  # 중복 + 일부 환경에서 충돌
```

`ProtectSystem=strict`가 이미 `/etc`를 읽기 전용으로 마운트하므로 `ReadOnlyPaths`는 불필요. 일부 systemd 버전에서 mount namespace 충돌 발생.

**해결**: `ReadOnlyPaths=` (빈 값)으로 설정.

### 4단계: Python S_IRWXG 파일 권한 검증이 640 거부

```python
# 문제 코드
if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
    raise PermissionError("Token file must be 600 or 400")
```

640 (`rw-r-----`) 파일에서 `S_IRWXG` 비트(0o070)와 AND 연산 → 0o040 (그룹 읽기) → 0이 아님 → 거부.

**해결**: world-writable만 검사.

```python
if st.st_mode & stat.S_IWOTH:
    raise PermissionError("Token file must not be world-writable")
```

## 교훈

- systemd의 credential 메커니즘은 `RuntimeDirectory`와 짝으로 사용해야 함
- 파일 권한 검증은 "실제 위협"에 집중 — 지나치게 엄격하면 정상 운영을 방해
- 4단계 원인 체인처럼, 하나를 고치면 다음 문제가 드러나는 패턴에서는 한 번에 모두 고치려 하지 말고 단계별로 확인
