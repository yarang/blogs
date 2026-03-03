+++
title = "[Hugo Blog] OCI + GitHub Actions 배포"
slug = "hugo-blog-deploy-oci"
date = 2026-02-21T00:00:00+09:00
draft = false
tags = ["hugo", "oci", "github-actions", "devops"]
categories = ["Infrastructure"]
ShowToc = true
TocOpen = true
+++

## 개요

이 블로그는 Hugo 정적 사이트 생성기를 사용하여 구축되었으며, GitHub Actions를 통해 Oracle Cloud Infrastructure (OCI) Free Tier 서버로 자동 배포됩니다.

## 아키텍처

```
로컬에서 Markdown 작성
    ↓
GitHub Push (main 브랜치)
    ↓
GitHub Actions (Hugo 빌드)
    ↓
SSH + rsync 배포
    ↓
OCI 서버 (Nginx)
    ↓
https://blog.fcoinfup.com
```

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 정적 사이트 생성기 | Hugo |
| 테마 | PaperMod |
| CI/CD | GitHub Actions |
| 서버 | OCI Free Tier (ARM) |
| 웹 서버 | Nginx |
| 배포 방식 | SSH + rsync |

## 설정 관리

프로젝트는 `.blogrc.yaml` 파일을 통해 설정을 중앙 관리합니다.

```yaml
server:
  host: oci-yarang-ec1.fcoinfup.com
  user: ubuntu
  deploy_path: /var/www/blog

blog:
  url: https://blog.fcoinfup.com
  title: "Yarang's Tech Lair"
  author: yarang
```

GitHub Secrets 동기화는 `scripts/sync-secrets.sh` 스크립트를 통해 자동화됩니다.

## 배포 파이프라인

GitHub Actions 워크플로우는 다음 단계로 실행됩니다:

1. **Checkout**: 저장소 클론 (submodules 포함)
2. **Hugo Setup**: Hugo extended 버전 설치
3. **Build**: `hugo --minify` 실행
4. **Deploy**: rsync를 통해 OCI 서버로 전송

```yaml
# .github/workflows/deploy.yml
- name: Deploy to OCI server
  run: |
    rsync -avz --delete \
      -e "ssh -i ~/.ssh/deploy_key" \
      public/ \
      ${{ secrets.OCI_USER }}@${{ secrets.OCI_HOST }}:${{ secrets.OCI_DEPLOY_PATH }}
```

## 포스트 작성 워크플로우

```bash
# 새 포스트 생성
hugo new content/posts/my-new-post.md

# 로컬 미리보기
hugo server -D

# 커밋 및 푸시 (자동 배포)
git add .
git commit -m "Add new post"
git push
```

## 보안 고려사항

- SSH 키는 ED25519 알고리즘 사용
- 개인 키는 GitHub Secrets에 안전하게 저장
- Nginx 보안 헤더 설정 (X-Frame-Options, X-Content-Type-Options 등)

## 참고 자료

- [Hugo 공식 문서](https://gohugo.io/)
- [GitHub Actions 문서](https://docs.github.com/actions)
- [PaperMod 테마](https://github.com/adityatelange/hugo-PaperMod)
