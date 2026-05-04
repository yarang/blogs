+++
title = "Building a Blog AI Auto-Comment System (3/3): Deployment and Troubleshooting"
slug = "ai-auto-comment-system-part3-deployment"
date = "2026-05-03T01:20:00+09:00"
draft = "false"
tags = ["systemd", "nginx", "deployment", "troubleshooting", "oci", "arm", "linux"]
categories = ["Development", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = "true"
TocOpen = "true"
+++

```

## Overview

In [Part 1](/ko/post/ai-auto-comment-system-part1-architecture/), we covered the architecture and implementation, and in [Part 2](/ko/post/ai-auto-comment-system-part2-security/), we looked at security enhancements. In this 3rd part, we record the process of deploying to an actual OCI ARM server and the troubleshooting encountered.

In particular, we share in detail the actual debugging process where we tracked and resolved the issue of **GITHUB_TOKEN not loading** over 4 steps. The core of this article is how we narrowed down the cause in a situation where "it's set up, so why isn't it working?"

---

## Infrastructure Configuration

### Server Configuration

| Server | Role | Specs |
|------|------|------|
| ec1 (x86) | Web Server (nginx, Hugo blog) | OCI |
| arm1 (ARM) | Worker Server (Flask, Claude Code) | OCI ARM |

The blog is built and served with Hugo on ec1, while the AI comment worker runs on arm1. The GitHub Webhook is delivered directly to arm1.

### Worker Server Directory Structure

```
/var/www/auto-comment-worker/        # Application
├── scripts/
│   └── auto-comment-worker.py
├── deploy/
│   └── auto-comment-worker.service
├── venv/                            # Python virtual environment
└── logs/

/etc/auto-comment-worker/            # Credentials
├── github-token                     # 640, ubuntu:ubuntu
└── credentials/
    └── webhook-secret               # 600, ubuntu:ubuntu

/home/ubuntu/.local/bin/claude       # Claude Code CLI
```

---

## systemd Service Configuration

### Service File

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

# Resource Limits
MemoryMax=512M
CPUQuota=50%
TasksMax=100

[Install]
WantedBy=multi-user.target
```

### Key Configuration Explanation

**`Type=simple`**: Since the Flask worker runs in the foreground, `simple` is appropriate. `forking` is used for processes that daemonize.

**`User=ubuntu`**: Although a dedicated service account could be created, it runs as `ubuntu` because the Claude Code CLI depends on the `ubuntu` user's home directory configuration.

**`ProtectHome=false`**: Usually set to `true`, but allows home directory access because Claude Code requires the `~/.agent_forge_for_zai.json` configuration file.

**`ReadOnlyPaths=`** (Empty value): Initially specified `/etc/auto-comment-worker`, but left empty due to conflict with `ProtectSystem=strict`.

### Service Management Commands

```bash
# Copy service file
sudo cp deploy/auto-comment-worker.service /etc/systemd/system/

# Register and start service
sudo systemctl daemon-reload
sudo systemctl enable auto-comment-worker
sudo systemctl start auto-comment-worker

# Check status
sudo systemctl status auto-comment-worker

# Check logs (real-time)
sudo journalctl -u auto-comment-worker -f

# Check recent logs
sudo journalctl -u auto-comment-worker --since "10 minutes ago"
```

---

## nginx Reverse Proxy

### Webhook Endpoint Configuration

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Webhook Proxy
    location /webhook {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # GitHub Webhook signature header forwarding (Required!)
        proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;

        # Timeout (Waiting for Claude Code response)
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8081;
    }
}
```

`proxy_read_timeout 120s` is set generously because the Claude Code CLI can take up to 60 seconds to generate an AI response. Since the default timeout for GitHub Webhooks is 10 seconds, asynchronous processing could be considered in practice.

---

## Deployment Process

### Manual Deployment (After rsync Failure)

Initially, we attempted deployment with rsync, but it failed because the target directory did not exist on the server:

```
rsync: [Receiver] mkdir "/var/www/auto-comment-worker/scripts" failed:
No such file or directory
```

As an alternative, we proceeded with scp-based manual deployment:

```bash
# 1. Create directory on server
ssh ubuntu@arm1 "sudo mkdir -p /var/www/auto-comment-worker/scripts"
ssh ubuntu@arm1 "sudo chown -R ubuntu:ubuntu /var/www/auto-comment-worker"

# 2. Transfer files
scp scripts/auto-comment-worker.py ubuntu@arm1:/var/www/auto-comment-worker/scripts/
scp deploy/auto-comment-worker.service ubuntu@arm1:/tmp/

# 3. Install service file
ssh ubuntu@arm1 "sudo cp /tmp/auto-comment-worker.service /etc/systemd/system/"

# 4. Set up Python virtual environment
ssh ubuntu@arm1 "cd /var/www/auto-comment-worker && python3 -m venv venv"
ssh ubuntu@arm1 "cd /var/www/auto-comment-worker && venv/bin/pip install flask flask-limiter marshmallow requests"

# 5. Configure authentication files
ssh ubuntu@arm1 "sudo mkdir -p /etc/auto-comment-worker/credentials"
# Token file is created directly on the server (not transferred via scp)

# 6. Start service
ssh ubuntu@arm1 "sudo systemctl daemon-reload && sudo systemctl enable --now auto-comment-worker"
```

### Heredoc Variable Expansion Pitfall

A common mistake when writing installation scripts with heredoc:

```bash
# Single quotes: Variables are NOT expanded!
ssh ubuntu@arm1 << 'ENDSSH'
echo $CREDENTIALS_DIR   # Prints empty string
ENDSSH

# No quotes: Variables are expanded locally
ssh ubuntu@arm1 << ENDSSH
echo $CREDENTIALS_DIR   # Expanded to local variable value
ENDSSH
```

To avoid this problem, we switched to executing commands individually instead of using a script.

---

## Troubleshooting: GITHUB_TOKEN Loading Failure

This was the issue that consumed the most time while deploying this system. When the comment Webhook arrived, the following error repeated:

```
INFO:__main__:GITHUB_TOKEN configured: False
INFO:__main__:GitHub API response status: 401
ERROR:__main__:Failed to get Discussion GraphQL ID
```

We record the process of tracking down the cause step by step.

### Step 1: LoadCredential Path Issue

Initially, we used the `LoadCredential` directive in systemd:

```ini
LoadCredential=github-token:/etc/auto-comment-worker/github-token
Environment=GITHUB_TOKEN_FILE=%d/github-token
```

`%d` is a systemd special variable replaced with the credentials directory path. However, this variable was not interpreted as intended, causing the token file path to be set incorrectly.

**Solution**: Instead of `LoadCredential`, we specified the absolute path directly.

```ini
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
```

### Step 2: File Ownership Issue

`GITHUB_TOKEN configured: False` still appeared. Checking the file revealed:

```bash
$ ls -la /etc/auto-comment-worker/github-token
-rw------- 1 root root 93 May  3 01:10 github-token
```

Since the file owner is `root` and permissions are `600`, the service running as the `ubuntu` user cannot read this file.

**Solution**:

```bash
sudo chown ubuntu:ubuntu /etc/auto-comment-worker/github-token
sudo chmod 640 /etc/auto-comment-worker/github-token
```

### Step 3: ReadOnlyPaths Conflict

Even after changing ownership, `GITHUB_TOKEN configured: False` persisted. The cause was the `ReadOnlyPaths` setting in the systemd service file:

```ini
# This setting blocked file reading
ReadOnlyPaths=/etc/auto-comment-worker
```

`ProtectSystem=strict` already mounts the entire filesystem read-only. Adding `ReadOnlyPaths` on top of that can cause mount namespace conflicts in some environments.

**Solution**: Changed `ReadOnlyPaths` to an empty value.

```ini
ReadOnlyPaths=
```

### Step 4: Python File Permission Validation Code (Root Cause)

Even after resolving all previous 3 steps, the token still did not load. The final cause was the overly strict file permission validation in the Python code:

```python
# File permission 640 → Group read bit (0o040) is set → Denied!
if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
    raise PermissionError("Token file must be 600 or 400")
```

Because we changed to `chmod 640` in Step 2, the group read bit was set, triggering this validation. However, the error message did not appear in the logs, delaying discovery — because the `PermissionError` occurred at the module import time, preventing the service from starting at all.

**Solution**: As explained in Part 2, we modified it to check only `stat.S_IWOTH`.

### Importance of Debugging Logs

The debugging logs added to track this issue:

```python
logger.info(f"GITHUB_TOKEN configured: {bool(GITHUB_TOKEN)}")
logger.info(f"GitHub API response status: {response.status_code}")
logger.info(f"GitHub API response body: {response.text[:500]}")
```

Without these logs, it would have taken much longer to identify the cause. Always log token load success/failure and API response status for authentication-related code.

### Debugging Flow Summary

```
[1] LoadCredential %d not interpreted → Changed to absolute path
                ↓ (Still failed)
[2] File owner root:root → Changed to ubuntu:ubuntu
                ↓ (Still failed)
[3] ReadOnlyPaths conflict → Removed
                ↓ (Still failed)
[4] Python permission check S_IRWXG → Relaxed to S_IWOTH
                ↓
            [Resolved!]
```

Lessons learned from this 4-step debugging:
1. **Change one at a time and verify**: If you change multiple settings at once, you won't know which one is the cause.
2. **Trust logs, but suspect where there are no logs**: Exceptions at module load time may not appear in standard logs.
3. **Security validation code can also be a source of bugs**: When security code blocks normal operation — balancing security and operations.

---

## Health Check

A health check endpoint to verify the service is running correctly:

```python
@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy'})
```

Monitoring systems periodically call `/health` to verify the service status:

```bash
curl -s http://localhost:8081/health
# {"status": "healthy"}
```

---

## Future Improvements

1. **Asynchronous Processing**: Asynchronize AI response generation using Celery or Redis Queue to respond within the GitHub Webhook timeout (10 seconds).
2. **Retry Logic**: Exponential backoff retry on GitHub API call failures.
3. **Monitoring Dashboard**: Monitor response time, success rate, and error rate with Prometheus + Grafana.
4. **Automated Deployment**: Build an automated deployment pipeline with GitHub Actions on code changes.
5. **Testing**: Write integration tests mocking Webhook payloads.

---

## Conclusion

Over three parts, we have recorded the entire build process of the blog AI auto-comment system:

- **Part 1**: Full architecture of giscus → GitHub Webhook → Flask → Claude Code → GraphQL
- **Part 2**: File-based authentication, HMAC verification, input sanitization, systemd security
- **Part 3**: Actual deployment, nginx proxy, 4-step debugging process

The greatest value of this system is that it **automates communication with blog readers**. While it is difficult for blog operators to respond to every comment immediately, an AI assistant can provide a first response, improving the reader experience.

The full code is available at the [GitHub repository](https://github.com/yarang/blogs).

---

*This article is Part 3 (the final part) of the AgentForge blog auto-comment system series.*
```