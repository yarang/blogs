+++
title = "[Hugo Blog] OCI + GitHub Actions Deployment"
slug = "hugo-blog-deploy-oci"
date = 2026-02-21T00:00:00+09:00
draft = false
tags = ["hugo", "oci", "github-actions", "devops"]
categories = ["Infrastructure"]
ShowToc = true
TocOpen = true
+++

## Overview

This blog is built using the Hugo static site generator and automatically deployed to an Oracle Cloud Infrastructure (OCI) Free Tier server via GitHub Actions.

## Architecture

```
Write Markdown locally
    ↓
GitHub Push (main branch)
    ↓
GitHub Actions (Hugo build)
    ↓
SSH + rsync deployment
    ↓
OCI Server (Nginx)
    ↓
https://blog.fcoinfup.com
```

## Tech Stack

| Component | Technology |
|-----------|------|
| Static Site Generator | Hugo |
| Theme | PaperMod |
| CI/CD | GitHub Actions |
| Server | OCI Free Tier (ARM) |
| Web Server | Nginx |
| Deployment Method | SSH + rsync |

## Configuration Management

The project centrally manages settings through the `.blogrc.yaml` file.

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

GitHub Secrets synchronization is automated through the `scripts/sync-secrets.sh` script.

## Deployment Pipeline

The GitHub Actions workflow executes in the following steps:

1. **Checkout**: Clone repository (including submodules)
2. **Hugo Setup**: Install Hugo extended version
3. **Build**: Run `hugo --minify`
4. **Deploy**: Transfer to OCI server via rsync

```yaml
# .github/workflows/deploy.yml
- name: Deploy to OCI server
  run: |
    rsync -avz --delete \
      -e "ssh -i ~/.ssh/deploy_key" \
      public/ \
      ${{ secrets.OCI_USER }}@${{ secrets.OCI_HOST }}:${{ secrets.OCI_DEPLOY_PATH }}
```

## Post Writing Workflow

```bash
# Create new post
hugo new content/posts/my-new-post.md

# Local preview
hugo server -D

# Commit and push (auto deploy)
git add .
git commit -m "Add new post"
git push
```

## Security Considerations

- SSH keys use ED25519 algorithm
- Private keys are securely stored in GitHub Secrets
- Nginx security header configuration (X-Frame-Options, X-Content-Type-Options, etc.)

## References

- [Hugo Official Documentation](https://gohugo.io/)
- [GitHub Actions Documentation](https://docs.github.com/actions)
- [PaperMod Theme](https://github.com/adityatelange/hugo-PaperMod)
