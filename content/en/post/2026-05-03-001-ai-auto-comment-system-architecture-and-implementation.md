+++
title = "Building a Blog AI Auto-Comment System (1/3) — Architecture and Implementation"
slug = "ai-auto-comment-system-part1-architecture"
date = "2026-05-03T01:00:00+09:00"
draft = "false"
tags = ["ai", "giscus", "github-discussions", "webhook", "flask", "claude-code", "automation", "blog"]
categories = ["Development", "AI", "DevOps"]
series = ["블로그 AI 자동 댓글 시스템"]
ShowToc = "true"
TocOpen = "true"
+++

## Overview

I built a system where AI automatically responds to blog comments. When a reader leaves a comment on a blog post, the AI assistant analyzes the post context and automatically generates a technically accurate yet friendly reply.

This series consists of three parts:
- **Part 1 (This post)**: Overall architecture design and core code implementation
- **Part 2**: File-based authentication, permission management, security hardening
- **Part 3**: systemd deployment, nginx proxy, troubleshooting

---

## System Architecture

### Overall Data Flow

```
Reader writes a comment
    ↓
[giscus] → Creates a comment on GitHub Discussions
    ↓
[GitHub Webhook] → Sends HTTP POST
    ↓
[nginx reverse proxy] → Header forwarding
    ↓
[Flask Worker] → Signature verification → Comment analysis
    ↓
[Claude Code CLI] → Generates AI response
    ↓
[GitHub GraphQL API] → Posts reply to Discussion
    ↓
[giscus] → Displays reply on blog
```

The key point in this architecture is that **giscus uses GitHub Discussions as a comment storage**. Therefore, we can receive new comment events via GitHub Webhook and post responses using the same GitHub API.

### Components

| Component | Role | Technology |
|-----------|------|------|
| giscus | Blog comment widget | Based on GitHub Discussions |
| GitHub Webhook | Event delivery | `discussion_comment` event |
| nginx | Reverse proxy | Header forwarding, SSL termination |
| Flask Worker | Webhook receiving and processing | Python, Flask, Flask-Limiter |
| Claude Code | AI response generation | `--print` mode CLI call |
| GitHub GraphQL | Response posting | Mutation API |

---

## giscus Configuration

To integrate giscus into a Hugo blog, the following configuration is required in `hugo.toml`:

```toml
[params]
    [params.comments]
        enabled = true
        provider = "giscus"
        [params.comments.giscus]
            repo = "yarang/blogs"
            repoId = "YOUR_REPO_ID"
            category = "General"
            categoryId = "YOUR_CATEGORY_ID"
            mapping = "pathname"
            strict = "0"
            reactionsEnabled = "1"
            emitMetadata = "0"
            inputPosition = "bottom"
            lang = "ko"
            theme = "noborder_gray"
```

`mapping = "pathname"` maps Discussions based on the post URL path. This creates an independent Discussion for each blog post.

---

## GitHub Webhook Configuration

In the GitHub repository Settings > Webhooks:

- **Payload URL**: `https://your-domain/webhook`
- **Content type**: `application/json`
- **Secret**: Secret for HMAC-SHA256 signature (covered in detail in the security post)
- **Events**: Select `Discussion comments`

The Webhook sends a `discussion_comment` event to the Flask worker whenever a comment is created.

---

## Flask Worker Implementation

### Project Structure

```
auto-comment-worker/
├── scripts/
│   └── auto-comment-worker.py    # Main worker
├── deploy/
│   └── auto-comment-worker.service  # systemd service
├── venv/                          # Python virtual environment
└── logs/
    └── audit.log                  # Audit log
```

### Core Dependencies

```python
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError
```

- **Flask**: Provides Webhook endpoints as a lightweight web framework
- **Flask-Limiter**: Prevents abuse with rate limiting (10 times per minute)
- **marshmallow**: Safe data parsing via request schema validation

### Webhook Endpoint

```python
@app.route('/webhook', methods=['POST'])
@limiter.limit("10 per minute")
def github_webhook():
    """Receives GitHub Webhook"""
    # 1. Signature verification
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook_signature(request.data, signature):
        log_audit('SIGNATURE_INVALID', {'ip': request.remote_addr})
        return jsonify({'status': 'unauthorized'}), 401

    # 2. Request schema validation
    schema = WebhookSchema()
    try:
        payload = schema.load(request.json)
    except ValidationError as err:
        return jsonify({'status': 'invalid'}), 400

    # 3. Extract and filter comment information
    comment = payload.get('comment', {})
    discussion = payload.get('discussion', {})
    original_author = comment.get('user', {}).get('login', 'User')

    # Ignore if it's the blog owner's comment
    if _is_blog_owner(original_author):
        return jsonify({'status': 'owner_comment_ignored'}), 200

    # Ignore if AI generated comment (prevent infinite loop)
    if _is_ai_generated_comment(comment.get('body', '')):
        return jsonify({'status': 'ai_comment_ignored'}), 200

    # 4. Generate and post AI response
    discussion_graphql_id = get_discussion_graphql_id(
        repo_owner, repo_name, discussion_number
    )
    context = f"Title: {discussion_title}\n\nContent: {discussion_body}"
    reply = analyze_comment(context, comment_body)
    post_reply_graphql(discussion_graphql_id, comment_body, original_author, reply)
```

The core flow consists of 4 steps:
1. **Signature verification**: Verifies if the request came from GitHub using HMAC-SHA256
2. **Schema validation**: Validates payload structure with marshmallow
3. **Filtering**: Ignores comments from the blog owner and the AI itself (prevents infinite loops)
4. **Response**: Generates AI response with Claude Code and posts via GraphQL API

### Preventing Infinite Loops

If AI responds to a comment created by AI, it will fall into an infinite loop. To prevent this, we use marker-based detection:

```python
def _is_ai_generated_comment(body: str) -> bool:
    """Identifies if the comment was generated by AI"""
    ai_markers = [
        '🤖 AI Assistant',
        'AI Assistant',
        'AgentForge',
        'Automatically generated by Claude Code',
        'was automatically generated'
    ]
    body_lower = body.lower()
    return any(marker.lower() in body_lower for marker in ai_markers)
```

When posting the AI response, you must include one of these markers in the body:

```python
body = f"""---
**🤖 AI Assistant**

{safe_reply}

*This comment was automatically generated by AgentForge + Claude Code.*
---
"""
```

### Calling Claude Code CLI

Use Claude Code's `--print` mode to generate an AI response non-interactively:

```python
def analyze_comment(context: str, comment: str) -> str:
    """Run Claude Code with AgentForge settings"""
    prompt = f"""## Blog Post Context
{context[:2000]}

## Reader Comment
{comment}

Please write a response to this comment.
- As a technical blog assistant, be professional yet friendly
- Concise within 200 characters
- Provide additional info or links if needed
"""

    cmd = [
        CLAUDE_CODE_PATH,
        '--settings', AGENTFORGE_CONFIG,
        '--print', prompt
    ]

    result = run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    return "Thanks for your opinion! I think it would be great to discuss the technical aspects further. 🙏"
```

Specify the AgentForge dedicated configuration file with the `--settings` flag. You can manage the model, token limits, etc. in this configuration file.

The `--print` flag runs Claude Code in non-interactive mode and outputs the result to stdout. Unlike interactive mode, it terminates after a single prompt-response.

### GitHub GraphQL API Integration

Since giscus uses GitHub Discussions, the response must also be posted via the GitHub GraphQL API.

**Retrieve Discussion GraphQL ID:**

```python
def get_discussion_graphql_id(repo_owner, repo_name, discussion_number):
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
            discussion(number: $number) {
                id
            }
        }
    }
    """
    variables = {
        "owner": repo_owner,
        "name": repo_name,
        "number": discussion_number
    }

    response = requests.post(
        GITHUB_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        },
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        return data["data"]["repository"]["discussion"]["id"]
    return None
```

The Webhook payload only includes the Discussion's REST API ID. However, to post a comment, the GraphQL Node ID is required. Therefore, we first retrieve the Discussion's Node ID via a GraphQL query, then use it to post the comment.

**Post Response (Mutation):**

```python
def post_reply_graphql(discussion_graphql_id, original_comment, original_author, reply):
    query = """
    mutation($discussionId: ID!, $body: String!) {
        addDiscussionComment(input: {
            discussionId: $discussionId, body: $body
        }) {
            comment { id, databaseId }
        }
    }
    """
    # ... (Send request)
```

The `addDiscussionComment` mutation adds a new comment to the entire Discussion. It is a Discussion-level comment, not a reply to a specific comment.

### Input Sanitization

Since user comments are external input, they must be sanitized:

```python
def sanitize_comment(body: str) -> str:
    """User input sanitization"""
    if not body:
        return body
    body = re.sub(r'<[^>]+>', '', body)    # Remove HTML tags
    body = html.escape(body)                # Escape HTML entities
    body = body[:1000]                      # Length limit
    return body
```

To prevent XSS attacks, HTML tags are removed, remaining special characters are escaped, and the length is limited to 1000 characters.

### Audit Logging

We keep audit logs to track security events:

```python
def log_audit(event_type: str, details: dict):
    """Record security event audit log"""
    with open(AUDIT_LOG, 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'event': event_type,
            'details': details
        }) + '\n')
```

Event types recorded:
- `SIGNATURE_INVALID`: Webhook signature verification failed
- `INVALID_PAYLOAD`: Invalid request payload
- `WEBHOOK_RECEIVED`: Webhook received successfully
- `AI_RESPONSE_SENT`: AI response posted successfully

---

## Conclusion

In this Part 1, we covered the overall architecture and core implementation code connecting giscus, GitHub Webhook, Flask worker, Claude Code CLI, and GitHub GraphQL API.

In the upcoming Part 2, we will cover **security hardening** for this system — file-based authentication management, file permission verification, HMAC-SHA256 signature verification, and more in detail.

---

*This post is Part 1 of the AgentForge blog automatic comment system series.*

