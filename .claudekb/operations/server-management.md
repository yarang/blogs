# 서버 관리 가이드

**갱신일**: 2026-05-03

## arm1 서비스 (직접 관리)

### auto-comment-worker.service

```bash
sudo systemctl status auto-comment-worker      # 상태
sudo systemctl restart auto-comment-worker     # 재시작
sudo journalctl -u auto-comment-worker -f      # 실시간 로그
sudo journalctl -u auto-comment-worker -n 100 --no-pager  # 최근 100줄
```

### 코드 갱신

```bash
cd /var/www/auto-comment-worker
git pull origin main
sudo systemctl restart auto-comment-worker
```

## ec1 상태 확인 (API만 가능)

ec1에는 SSH 접근 불가. Blog API를 통한 상태 확인만 가능.

```bash
API_KEY=$(cat /etc/auto-comment-worker/credentials/blog-api-key)
BASE="https://blog.fcoinfup.com/api"

curl -s "$BASE/health"                                   # 헬스체크
curl -s -H "X-API-Key: $API_KEY" "$BASE/status"         # Git 상태
curl -s "$BASE/dashboard"                                # 대시보드
```

## 인증 파일 관리

### 파일 위치

```
/etc/auto-comment-worker/
├── github-token           # GitHub PAT (640, ubuntu:ubuntu)
└── credentials/
    ├── webhook-secret     # Webhook HMAC 시크릿 (600)
    └── blog-api-key       # Blog API 키 (600)
```

### 권한 점검

```bash
ls -la /etc/auto-comment-worker/
ls -la /etc/auto-comment-worker/credentials/
find /etc/auto-comment-worker -perm -o+w -type f   # world-writable 검사
```

### 토큰 갱신 절차

```bash
echo "NEW_TOKEN" | sudo tee /etc/auto-comment-worker/github-token
sudo chmod 640 /etc/auto-comment-worker/github-token
sudo chown ubuntu:ubuntu /etc/auto-comment-worker/github-token
sudo systemctl restart auto-comment-worker
```

## systemd 보안 디렉티브

| 디렉티브 | 값 | 효과 |
|----------|---|------|
| NoNewPrivileges | true | 권한 상승 차단 |
| PrivateTmp | true | 독립 /tmp |
| ProtectSystem | strict | 전체 FS 읽기 전용 |
| ProtectHome | false | Claude Code 설정 접근 |
| ReadWritePaths | /var/www/auto-comment-worker, /var/log/auto-comment-worker | 쓰기 허용 |
| MemoryMax | 512M | 메모리 제한 |

**주의**: ReadOnlyPaths 추가 시 ProtectSystem=strict와 충돌 가능. 빈 값 유지.

## 감사 로그

```bash
cat /var/log/auto-comment-worker/audit.log | python3 -m json.tool
grep "SIGNATURE_INVALID" /var/log/auto-comment-worker/audit.log
```

| 이벤트 | 의미 |
|--------|------|
| SIGNATURE_INVALID | 시그니처 실패 (공격 또는 시크릿 불일치) |
| INVALID_PAYLOAD | 잘못된 요청 (정상 방어) |
| WEBHOOK_RECEIVED | 정상 수신 |
| AI_RESPONSE_SENT | AI 답변 게시 완료 |

## 장애 대응

```bash
# 서비스 시작 실패
sudo journalctl -u auto-comment-worker -n 50 --no-pager

# Claude Code CLI 테스트
/home/ubuntu/.local/bin/claude --settings ~/.agent_forge_for_zai.json --print "test"

# GitHub API 토큰 확인
curl -s -H "Authorization: Bearer $(cat /etc/auto-comment-worker/github-token)" \
  https://api.github.com/user | head -5
```
