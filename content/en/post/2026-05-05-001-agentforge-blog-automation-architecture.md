+++
title = "AgentForge Blog Automation Service: Full Architecture - From AI Comments to Translation and Post Generation"
slug = "2026-05-05-001-agentforge-blog-automation-architecture"
date = "2026-05-05T00:30:00+09:00"
draft = "false"
tags = ["agentforge", "automation", "llm", "gemini", "fastapi", "hugo", "architecture"]
categories = ["Development", "Architecture"]
ShowToc = "true"
TocOpen = "true"
+++

Running a blog involves three of the most tedious tasks: replying to comments, maintaining English translations, and consistently writing new posts. The [AgentForge](https://github.com/yarang) project automates all three with AI agents.

This post outlines the complete architecture of our blog automation service, which operates across two servers.

---

## System Topology

```
┌─────────────────────┐      HTTPS       ┌─────────────────────┐
│      arm1 server       │ ──────────────▶  │      ec1 server       │
│  (Agent Operator)  │                  │  (Blog Hosting)      │
├─────────────────────┤                  ├─────────────────────┤
│ blog-agent (:8081)  │                  │ Hugo (nginx)        │
│  ├─ CommentHandler  │                  │ Blog API (:8000)    │
│  ├─ TranslateHandler│                  │  ├─ translator.py   │
│  └─ PostGenerator   │                  │  ├─ blog_manager.py │
│                     │                  │  └─ git_handler.py  │
│ NATS / PostgreSQL   │                  │                     │
│ Prometheus / Grafana │                  │ Git (yarang/blogs)  │
└─────────────────────┘                  └─────────────────────┘
```

| Server | Role | Core Services |
|------|------|------------|
| **arm1** | Agent Operator | `blog-agent.service` — Flask + Scheduler + LLM Client |
| **ec1** | Blog Hosting + API | Hugo (nginx) + `blog-api.service` (FastAPI) |

Communication between the two servers is restricted to **HTTPS API calls only**. SSH access from arm1 to ec1 is blocked, so all integrations are done through the Blog API.

---

## arm1: Unified Blog Agent

### Why Unified?

Initially, comment response, translation, and post generation operated as separate processes (three systemd services). The issues were:

- Using Claude Code CLI (`--print`) for calls resulted in a **response time of 9.7 seconds** and consumed 688MB of disk space.
- Managing six systemd units was burdensome.
- No state sharing between processes was possible.

By unifying these into **one process** and switching to direct LLM API calls, we achieved the following:

| Metric | Before | After |
|------|--------|-------|
| Response Time | 9.7s | 1.7s |
| Disk Usage | 688MB | ~50MB |
| systemd Units | 6 | 1 |
| Processes | 3 | 1 |

### Architecture

```python
class BlogAgent:
    """1 Process = Flask (webhook) + Scheduler (timer) + LLM Client"""
    
    def __init__(self):
        self.config = AgentConfig.from_credentials()
        self.llm = LLMClient(self.config)       # ZAI glm-4.7
        self.api = BlogAPIClient(self.config)     # ec1 Blog API
        
        # Handlers
        self.comment = CommentHandler(self.llm, self.config)
        self.translate = TranslateHandler(self.api)
        self.post_gen = PostGenerator(self.llm, self.api)
        
        # Scheduler
        self.scheduler = Scheduler()
        self.scheduler.every(hours=6, task=self.translate.check_and_sync)
        self.scheduler.daily_at(hour=9, task=self.post_gen.generate_and_publish)
```

### Module Operations

#### 1. CommentHandler — AI Comment Response

Receives Webhook events from GitHub Discussions to automatically generate AI comments.

```
[User Comment] → GitHub Webhook → arm1 Flask → CommentHandler
    → LLM Call (ZAI glm-4.7) → Generate Reply → Post Comment via GitHub API
```

- **Trigger**: Webhook event-based (real-time)
- **Filtering**: Skips blog owner comments and AI-generated comments.
- **Security**: HMAC-SHA256 Webhook secret verification, Flask-Limiter applied.

#### 2. TranslateHandler — Automatic Translation Trigger

Requests translation synchronization from ec1's Blog API every 6 hours.

```
[Scheduler 6h] → TranslateHandler.check_and_sync()
    → POST /translate/sync → ec1 Blog API performs actual translation
```

arm1 does not perform the translation itself; it only sends a **trigger** to the ec1 API. The actual translation logic resides in `translator.py` on ec1.

#### 3. PostGenerator — Automatic Post Generation

Automatically generates technical blog posts every day at 9 AM.

```
[Scheduler 09:00 KST] → PostGenerator.generate_and_publish()
    → Collect existing topics → Refer to RSS trends → Generate content with LLM
    → Deduplication Check → Publish via Blog API
```

**Deduplication** is key. It compares the similarity between new titles and the last 100 existing titles using `difflib.SequenceMatcher`:

```python
def _is_duplicate_title(self, new_title, existing_titles):
    """Considers it a duplicate if the ratio is >= 0.6"""
    new_lower = new_title.lower().strip()
    for title in existing_titles[-100:]:
        ex_lower = title.lower().strip()
        ratio = difflib.SequenceMatcher(None, new_lower, ex_lower).ratio()
        if ratio >= 0.6:
            return True
    return False
```

---

## ec1: Blog API Translation System

### Transition to Gemini

Initially, translations were performed using ZAI (glm-4.7), but a critical issue arose:

> glm-4.7 is a **reasoning model**, which first consumes its `max_tokens` budget for `reasoning_content` (internal thought process). If `max_tokens=256`, it uses all 256 tokens for reasoning, leaving the actual `content` as an empty string.

This led to an incident where **nine English posts were translated with empty string titles**.

Solution: Replaced with **Gemini 2.5 Flash Lite**.

| Item | ZAI (Previous) | Gemini (Current) |
|------|-----------|--------------|
| Model | glm-4.7 (reasoning) | gemini-2.5-flash-lite |
| Translation Time | ~30s/post | ~8s/post |
| Cost | Paid API | Free (1,500 requests/day) |
| Empty Response Issue | Occurred | None |

### OpenAI-Compatible Endpoint

Gemini provides an OpenAI-compatible API. The existing code can be used **without any changes** by simply switching the base URL:

```python
LLM_BASE_URLS = {
    "GEMINI": "https://generativelanguage.googleapis.com/v1beta/openai",
    "ZAI":    "https://api.z.ai/api/coding/paas/v4",
}
```

### Translation Matching Logic

Pairing Korean↔English posts uses **date prefix matching**:

```
ko: 2026-05-04-001-개발-생산성-17배-극대화-deepseek-v4와-...
en: 2026-05-04-001-개발-생산성-17배-극대화-deepseek-v4와-...
                    ↑ Same prefix = Same post
```

Although the slugs might differ in language, if the `YYYY-MM-DD-NNN` part is the same, it's recognized as the same post. The prerequisite for this method is that **no two posts with the same date and number exist**.

### Title-in-Body Translation Technique

Translating the title via a separate API call caused issues with empty results from the reasoning model. The solution is to **include the title as the first line of the body**:

```python
# When requesting translation
prompt = f"# {original_title}\n\n{original_body}"

# Extracting the title from the translation result
if translated.lstrip().startswith("# "):
    lines = translated.lstrip().split("\n", 1)
    extracted_title = lines[0].lstrip("# ").strip()
    translated_body = lines[1].lstrip("\n")
```

This translates the title and body simultaneously in a single API call, preserving context and saving tokens.

---

## LLM Strategy: Role-Based Model Separation

Not all tasks are handled by a single LLM. Models are separated based on the nature of the task.

| Task | Server | Model | Reason |
|------|------|------|------|
| AI Comment Response | arm1 | ZAI glm-4.7 | Conversational, excellent Korean quality |
| Post Generation | arm1 | ZAI glm-4.7 | Long-form content generation, creativity required |
| Translation (ko→en) | ec1 | Gemini Flash Lite | Non-reasoning, fast and free |

Core Principle: **Do not use reasoning models for translation**. Reasoning models consume tokens for internal thought processes, making non-reasoning models more suitable for simple conversion tasks.

---

## Monitoring and Operations

### Health Check Endpoints

```bash
# arm1 agent
curl http://arm1:8081/health
# → {"status":"healthy","agent":"blog-agent","scheduler_jobs":2,"uptime_sec":...}

curl http://arm1:8081/status
# → {"scheduler":[{"name":"auto-translate","last_run":...},{"name":"post-generator","last_run":"2026-05-04"}]}

# ec1 Blog API
curl https://blog.example.com/api/health
# → {"status":"healthy","version":"2.0.0"}
```

### Observability Points

| Metric | Normal Range | Alert Condition |
|------|----------|----------|
| arm1 uptime | >0 | Service Down |
| scheduler_jobs | 2 | ≠ 2 |
| Translation Sync | ko post count = en post count | Discrepancy occurs |
| Post Generation | 1 post daily | No posts for over 24 hours |

---

## Lessons Learned and Operational Tips

### 1. The Pitfall of Reasoning Models

It's often not explicitly stated in documentation that `max_tokens` **combines** reasoning and content. If you get an empty response, check the `finish_reason`—if it's `"length"`, it indicates insufficient token budget.

### 2. Value of the OpenAI-Compatible Pattern

When switching translation providers from ZAI to Gemini, the code change was just **one line for the base URL**. Abstracting to an OpenAI-compatible interface from the start dramatically reduces LLM replacement costs.

### 3. Constraints of Date Prefix Matching

In the `YYYY-MM-DD-NNN` pattern, if two or more posts share the same date and number, translation matching will break. The `PostGenerator` must include logic to check the last number for that date and increment it when generating new posts.

### 4. Benefits of Process Consolidation

Consolidating three independent services into one resulted in:
- State Sharing (LLM clients, configurations, API clients initialized only once)
- Simplified Deployment (one systemd unit)
- Easier Debugging (logs consolidated in one place)

---

## Future Plans

- Review the integration of arm1 agent's LLM with Gemini.
- Comment Quality Evaluation Pipeline (monitoring the appropriateness of auto-generated comments).
- Automatic Translation Quality Verification (comparing with back-translation).
- Expanding inter-agent collaboration through the AgentForge framework.

---

Blog automation aims not for "complete automation," but for "minimal human intervention." A structure where AI generates content, humans review it, and the system alerts operators to anomalies is the key to stable operation.