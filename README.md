# Hugo Blog Auto-Deploy to OCI

Hugo 기반 블로그를 GitHub Actions를 통해 OCI Free Tier 서버에 자동 배포하는 설정입니다.

## 보안 설정

### 필수 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `GITHUB_WEBHOOK_SECRET` | GitHub 웹훅 시크릿 (random 32+ bytes) | `openssl rand -base64 32` |
| `GITHUB_TOKEN` | GitHub Personal Access Token | `ghp_xxxx...` |
| `BLOG_OWNERS` | 댓글 제외할 사용자 (쉼표 구분) | `yarang,admin` |
| `AUDIT_LOG_PATH` | 감사 로그 경로 | `/var/log/auto-comment-worker/audit.log` |

### 웹훅 시크니처 설정

1. GitHub Webhook 설정에서 시크릿 생성:
   ```bash
   openssl rand -base64 32
   ```

2. 서버에 시크릿 파일 저장:
   ```bash
   sudo mkdir -p /etc/auto-comment-worker
   sudo chmod 700 /etc/auto-comment-worker
   echo "your_webhook_secret" | sudo tee /etc/auto-comment-worker/webhook-secret
   sudo chmod 600 /etc/auto-comment-worker/webhook-secret
   ```

3. GitHub Repository Settings → Webhooks → Secret에 동일한 시크릿 설정

### 감사 로그

감사 로그는 `/var/log/auto-comment-worker/audit.log`에 기록됩니다:

| 이벤트 | 설명 |
|--------|------|
| `WEBHOOK_RECEIVED` | 웹훅 수신 |
| `SIGNATURE_INVALID` | 시그니처 검증 실패 |
| `INVALID_PAYLOAD` | 요청 스키마 검증 실패 |
| `AI_RESPONSE_SENT` | AI 응답 전송 완료 |

로그 확인:
```bash
sudo tail -f /var/log/auto-comment-worker/audit.log
```

## 아키텍처

```
로컬에서 Markdown 작성
    ↓
GitHub Push (main 브랜치)
    ↓
GitHub Actions (빌드, 무료)
    ↓
SSH 배포 → OCI 서버
    ↓
Nginx로 정적 사이트 서빙
```

## 초기 설정

### 1. OCI 서버 설정

서버에 SSH로 접속하여 스크립트를 실행하세요:

```bash
# 로컬에서 스크립트를 서버로 전송
scp scripts/setup-nginx.sh ubuntu@YOUR OCI_IP:~/

# 서버에서 실행
ssh ubuntu@YOUR_OCI_IP
chmod +x setup-nginx.sh
./setup-nginx.sh ubuntu /var/www/blog your-domain.com
```

### 2. SSH 키 생성 및 설정

**로컬에서 SSH 키 쌍 생성:**
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/blog_deploy
```

**공개키를 OCI 서버에 등록:**
```bash
cat ~/.ssh/blog_deploy.pub | ssh ubuntu@YOUR_OCI_IP 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'
```

### 3. GitHub Repository 설정

1. GitHub에서 새 repository 생성
2. 코드 푸시:
```bash
git remote add origin https://github.com/yarang/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 4. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions에서 다음 시크릿 추가:

| Secret 이름 | 값 | 예시 |
|------------|-----|------|
| `SSH_PRIVATE_KEY` | `~/.ssh/blog_deploy` 내용 전체 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `OCI_HOST` | OCI 서버 공인 IP | `203.0.113.10` |
| `OCI_USER` | SSH 사용자명 | `ubuntu` |
| `OCI_DEPLOY_PATH` | 배포 경로 | `/var/www/blog` |

## 사용법

### 새 글 작성

```bash
# 새 포스트 생성
hugo new content/posts/my-new-post.md

# 내용 편집
vim content/posts/my-new-post.md

# 로컬 미리보기
hugo server -D

# 커밋 및 푸시 (자동 배포됨)
git add .
git commit -m "Add new post"
git push
```

### 포스트 작성 팁

```markdown
---
title: "포스트 제목"
date: 2026-02-20T10:00:00+09:00
draft: false
---

내용 작성...
```

## 파일 구조

```
blogs/
├── content/           # Markdown 글들
│   └── posts/
├── public/            # 빌드된 정적 파일 (생성됨)
├── themes/            # Hugo 테마
├── static/            # 이미지, CSS, JS 등 정적 리소스
├── hugo.toml          # Hugo 설정
├── .github/
│   └── workflows/
│       └── deploy.yml  # 배포 워크플로우
└── scripts/
    └── setup-nginx.sh  # 서버 설정 스크립트
```

## 트러블슈팅

### 배포 실패 시

1. **SSH 연결 확인:**
```bash
ssh -i ~/.ssh/blog_deploy ubuntu@YOUR_OCI_IP
```

2. **GitHub Actions 로그 확인:**
   - Repository → Actions → 최근 실행 → 로그 확인

3. **Nginx 로그 확인:**
```bash
ssh ubuntu@YOUR_OCI_IP
sudo tail -f /var/log/nginx/error.log
```

### 빌드 오류 시

로컬에서 빌드 테스트:
```bash
hugo --minify
```

## 참고 자료

- [Hugo 공식 문서](https://gohugo.io/)
- [GitHub Actions 문서](https://docs.github.com/actions)
- [Ananke 테마](https://github.com/theNewDynamic/gohugo-theme-ananke)
