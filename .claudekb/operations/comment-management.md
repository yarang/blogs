# 댓글 관리 가이드

**갱신일**: 2026-05-03

## 개요

auto-comment-worker 서비스가 댓글에서 AI 응답까지 자동 처리.
정상 운영 시 수동 개입 불필요. 이 문서는 모니터링과 장애 대응용.

## 동작 파이프라인

```
독자 댓글 --> giscus --> GitHub Discussions
  --> Webhook POST --> ec1 nginx /webhook
  --> proxy --> arm1 Flask :8081
  --> HMAC 검증 --> 스키마 검증
  --> 소유주 댓글? --> 무시
  --> AI 마커? --> 무시 (무한루프 방지)
  --> Claude Code --print --> AI 응답 생성
  --> GitHub GraphQL --> Discussion 답변 게시
  --> giscus 표시
```

## 필터링 규칙

| 조건 | 동작 | 사유 |
|------|------|------|
| action != 'created' | 400 거부 | 수정/삭제 이벤트 무시 |
| 소유주 댓글 (yarang) | 200 무시 | 자기 블로그에 AI 답변 불필요 |
| AI 마커 감지 | 200 무시 | 무한루프 방지 |
| 시그니처 실패 | 401 거부 | 위장 Webhook 차단 |
| 스키마 실패 | 400 거부 | 잘못된 페이로드 |

## 무한루프 방지 마커

AI 응답에 삽입되는 마커 (하나라도 감지 시 무시):
- `AI 어시스턴트`
- `AgentForge`
- `Claude Code로 자동 생성`
- `자동 생성되었습니다`

## 모니터링

```bash
sudo journalctl -u auto-comment-worker -f
```

**정상 패턴:**
```
INFO: Comment from: use***
INFO: Discussion: #42
INFO: Replied to comment 12345
```

**문제 패턴:**
```
WARNING: Invalid webhook signature       --> 시크릿 불일치/공격
ERROR: Failed to get Discussion GraphQL ID --> GitHub 토큰 문제
ERROR: GraphQL errors: [...]              --> API 권한/쿼리 오류
```

## 속도 제한

- Flask-Limiter: 분당 10회
- 정상 빈도: 분당 1-2회 이하
- 초과 시: 429 Too Many Requests

## 수동 개입

### GitHub PAT 만료 시

```bash
echo "ghp_NEW_TOKEN" | sudo tee /etc/auto-comment-worker/github-token
sudo chmod 640 /etc/auto-comment-worker/github-token
sudo systemctl restart auto-comment-worker
```

### Webhook Secret 변경 시

```bash
echo "new-secret" | sudo tee /etc/auto-comment-worker/credentials/webhook-secret
sudo chmod 600 /etc/auto-comment-worker/credentials/webhook-secret
sudo systemctl restart auto-comment-worker
```
