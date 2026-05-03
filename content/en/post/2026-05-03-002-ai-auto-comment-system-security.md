+++
title = ""
slug = "ai-auto-comment-system-part2-security"
date = "2026-05-03T01:10:00+09:00"
draft = "false"
tags = ["security", "hmac", "credential-management", "file-permissions", "systemd", "hardening"]
categories = ["Development", "Security", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = "true"
TocOpen = "true"
+++

## Overview

In [Part 1](/ko/post/ai-auto-comment-system-part1-architecture/), we covered the architecture and implementation of the AI auto-comment system. In this Part 2, we will focus on security aspects.

Systems that receive external Webhooks, manage GitHub API tokens, and process user input require special attention to security. We will explain the process of switching from environment variables to file-based authentication, the reasons behind it, and the design of each security layer.

---

## Security Threat Model

Threats that this system must defend against:

| Threat | Attack Vector | Defense |
|------|-----------|-----------|
| Spoofed Webhook | Attacker sends fake Webhook | HMAC-SHA256 signature verification |
| Token Leak | Environment variable exposure, log exposure | File-based authentication + permission restrictions |
| XSS/Injection | Malicious comment content | Input sanitization |
| Excessive Requests | DDoS, abuse | Flask-Limiter rate limiting |
| Privilege Escalation | Worker process compromise | systemd security directives |
| Infinite Loop | AI responding to itself | Marker-based comment detection |

---

## File-Based Authentication Management

### Problems with Environment Variables

Initially, we managed GitHub tokens and Webhook secrets as environment variables:

```ini
# Initial (unsafe)
Environment=GITHUB_TOKEN=ghp_xxxxx
Environment=GITHUB_WEBHOOK_SECRET=my-secret-key
```

Problems with the environment variable approach:
- **`/proc/PID/environ`**: Process environment variables are exposed as a file in Linux
- **Log exposure**: Risk of environment variables being logged during debugging
- **Child process inheritance**: When running Claude Code with `subprocess.run`, all environment variables are inherited
- **systemd configuration file**: If the service file contains plaintext secrets, there is a risk of committing them to git

### Switching to File-Based

Store credentials in the file system and specify only **file paths** in environment variables:

```ini
# Improved — only path exposed
Environment=GITHUB_TOKEN_FILE=/etc/auto-comment-worker/github-token
Environment=GITHUB_WEBHOOK_SECRET_FILE=/etc/auto-comment-worker/credentials/webhook-secret
```

Directory structure of the server:

```
/etc/auto-comment-worker/
├── github-token              # GitHub Personal Access Token (640)
└── credentials/
    └── webhook-secret         # GitHub Webhook HMAC Secret (600)
```

### Token File Loading Code

```python
import stat

GITHUB_TOKEN_FILE = os.environ.get('GITHUB_TOKEN_FILE', '')
if GITHUB_TOKEN_FILE and os.path.exists(GITHUB_TOKEN_FILE):
    # Check file permissions
    st = os.stat(GITHUB_TOKEN_FILE)
    if st.st_mode & stat.S_IWOTH:
        raise PermissionError("Token file must not be world-writable")
    with open(GITHUB_TOKEN_FILE, 'r') as f:
        GITHUB_TOKEN = f.read().strip()
else:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
```

Core design decisions:
1. **Prefer file if it exists**: Environment variables are used only as a fallback
2. **Permission verification**: Check permissions before reading the file
3. **strip()**: Remove newline characters at the end of the file

### File Permission Validation — A Trial and Error Journey

I spent the most time on this part. The initial code was too strict:

```python
# Initial code — too strict
if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
    raise PermissionError("Token file must be 600 or 400")
```

Problem with this code: `S_IRWXO | S_IRWXG` checks **all group permissions** (read/write/execute) and **all other permissions**. That is, if the file permission is `640` (owner read/write, group read), it is rejected.

```
# Bit mask analysis
S_IRWXG = 0o070  # Group read+write+execute
S_IRWXO = 0o007  # Other read+write+execute

# 640 = 0o640
0o640 & (0o070 | 0o007) = 0o640 & 0o077 = 0o040  # Not 0 → Rejected!
```

For actual security, what matters is that **other users cannot modify the file**. Group read permission allows users in the same group to read the file and is not a security issue.

After revision:

```python
# After revision — focus on actual threat
if st.st_mode & stat.S_IWOTH:
    raise PermissionError("Token file must not be world-writable")
```

You only need to check `stat.S_IWOTH` (`0o002`). This confirms only "Does it have write permission for others?".

| Permission | Octal | Initial Code | After Revision |
|------|-------|-----------|---------|
| `600` | `0o600` | Allowed | Allowed |
| `640` | `0o640` | **Rejected** | Allowed |
| `644` | `0o644` | Rejected | Allowed |
| `646` | `0o646` | Rejected | **Rejected** |
| `666` | `0o666` | Rejected | **Rejected** |

---

## HMAC-SHA256 Signature Verification

GitHub Webhook sends a signature created by HMAC-SHA256 hashing the request body with the Webhook secret in the `X-Hub-Signature-256` header. We verify this to confirm that the request actually came from GitHub.

```python
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """GitHub webhook signature verification"""
    if not signature:
        logger.warning("Missing webhook signature")
        return False

    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not configured - skipping validation")
        return True  # Allow for development mode

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

        # Prevent timing attacks
        if not hmac.compare_digest(expected_signature, github_signature):
            return False

        return True
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False
```

Key points:
- **`hmac.compare_digest()`**: Uses constant-time comparison instead of normal `==` comparison to prevent timing attacks.
- **raw bytes usage**: Uses `request.data` (original bytes). If parsed with `request.json` and re-serialized, it may differ from the original.
- **Development mode**: Skips validation if the secret is not set. The secret must be set in production.

### nginx Header Forwarding

For signature verification to work properly, nginx must forward the `X-Hub-Signature-256` header:

```nginx
location /webhook {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
}
```

Unless `X-Hub-Signature-256` is explicitly forwarded, custom headers may not be passed with just the default `proxy_pass`.

---

## Request Validation (marshmallow Schema)

Validate the structure of the Webhook payload using a marshmallow schema:

```python
class WebhookSchema(Schema):
    action = fields.Str(required=True, validate=validate.Equal('created'))
    comment = fields.Dict(required=True)
    discussion = fields.Dict(required=True)
    repository = fields.Dict(required=True)
    sender = fields.Dict(required=False)
```

- **`action = 'created'` only**: Rejects comment edit (`edited`) or delete (`deleted`) events.
- **Required field validation**: Returns 400 error if `comment`, `discussion`, `repository` are missing.
- **ValidationError → Audit log**: Invalid requests are logged in the audit log.

---

## Input Sanitization

User comments are external input, so they must be processed:

```python
def sanitize_comment(body: str) -> str:
    """User input sanitization"""
    body = re.sub(r'<[^>]+>', '', body)    # Remove HTML tags
    body = html.escape(body)                # Escape special characters
    body = body[:1000]                      # Length limit
    return body
```

Where this sanitization is applied:
- Comment body (`comment_body`)
- Discussion title and body (`discussion_title`, `discussion_body`)
- Original author name (`original_author`)
- Quoted part when posting AI response

### Username Masking

We do not log the full username:

```python
def mask_username(username: str) -> str:
    """Username masking"""
    if not username or len(username) < 4:
        return "***"
    return f"{username[:3]}***"
```

Logs will only display masked names like `yar***`. This strikes a balance between privacy protection and debugging convenience.

---

## Rate Limiting

Apply rate limiting per endpoint using Flask-Limiter:

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

- **10 requests per minute limit**: A figure considering normal Webhook call frequency
- **`get_remote_address`**: Limits based on client IP
- **`memory://`**: In-memory storage (suitable for single process)

---

## systemd Security Directives

Part 3 will cover systemd deployment in detail, but security-related directives are explained here:

```ini
[Service]
# Security hardening
NoNewPrivileges=true       # Prevent privilege escalation
PrivateTmp=true            # Provide isolated /tmp
ProtectSystem=strict       # Read-only file system
ProtectHome=false          # Allow home directory access (for Claude Code config)
ReadWritePaths=/var/www/auto-comment-worker /var/log/auto-comment-worker

# Resource limits
MemoryMax=512M             # Memory limit
CPUQuota=50%               # CPU usage limit
TasksMax=100               # Process count limit
```

| Directive | Effect |
|----------|------|
| `NoNewPrivileges=true` | Privilege escalation via `setuid`, `setgid`, etc. is impossible |
| `PrivateTmp=true` | Isolated `/tmp` namespace, separated from other processes |
| `ProtectSystem=strict` | Mounts entire file system as read-only |
| `ReadWritePaths` | Specifies only paths allowed for writing |
| `MemoryMax=512M` | Protects the entire system in OOM situations |

### Conflict between ProtectSystem=strict and ReadOnlyPaths

Initially, adding `ReadOnlyPaths=/etc/auto-comment-worker` caused an issue where the token file could not be read. Since `ProtectSystem=strict` already sets the entire file system to read-only, a separate `ReadOnlyPaths` is unnecessary. It was removed because it could cause conflicts in some environments.

---

## Conclusion

In this Part 2, we covered file-based authentication management, the file permission validation journey, HMAC-SHA256 signature verification, input sanitization, rate limiting, and systemd security directives.

The most important lesson in security: **"Too strict validation is as harmful as too loose validation."** The initial code, which only allowed `600` permissions, was secure, but in the actual operating environment, it rejected files with `640` permissions, preventing the service from starting. Focusing only on actual threats (world-writable) is the correct approach.

In the next Part 3, we will cover **Deployment and Troubleshooting** — systemd service configuration, nginx reverse proxy, and errors actually encountered and the resolution process.

---

*This post is Part 2 of the AgentForge blog automatic comment system series.*