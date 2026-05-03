+++
title = ""
date = "2026-03-03T13:01:48+09:00"
draft = "false"
tags = ["blog-api-server", "LLM", "\\ubc30\\ud3ec", "\\uac1c\\ubc1c"]
categories = ["\\uac1c\\ubc1c"]
ShowToc = "true"
TocOpen = "true"
+++

## Overview

Improved the LLM configuration for the blog-api-server project and deployed it to the server.

## LLM Configuration Improvement

### Existing Problems
- Multiple API Key environment variables (`ZAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Complex provider branching logic
- Scattered model configurations

### Changes

#### Simplifying Environment Variables

```bash
# Before
ZAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
ZAI_MODEL=gpt-4o-mini
LLM=ZAI

# After
LLM=ZAI                    # Provider (ZAI, OPENAI, ANTHROPIC)
LLM_API_KEY=xxx           # Single API Key
LLM_MODEL=glm-4.7         # Default Model
LLM_TIMEOUT=120           # Timeout (seconds)
```

#### Automatic BASE_URL Configuration

```python
LLM_BASE_URLS = {
    "ZAI": "https://api.z.ai/api/coding/paas/v4",
    "OPENAI": "https://api.openai.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1"
}
```

#### Code Structure Improvement

```python
class Translator:
    """LLM-based translator"""
    
    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL  # Automatically selected
        self.model = LLM_MODEL
        self.timeout = LLM_TIMEOUT
```

## Model Configuration

### Default Model
- **glm-4.7** (default)
- max_tokens: 8192

### Supported Models

| Model | max_tokens |
|------|------------|
| glm-4 | 8192 |
| glm-4.7 | 8192 |
| gpt-4o-mini | 4096 |
| gpt-4o | 8192 |
| claude-3-5-haiku | 8192 |

## Team Composition

Formed the blog-api-server development team.

| Role | Name | Responsibility |
|------|------|----------------|
| Team Lead | team-lead | Overall Management |
| Developer | developer | Coding, Feature Implementation |
| Deployment Manager | deployer | Server Deployment, Infrastructure |
| Monitor | monitor | Log Analysis, Performance Monitoring |

## Server Deployment

### Deployment Target
- **Server**: blog.fcoinfup.com (130.162.133.47)
- **Path**: `/var/www/blog-api`

### Deployment Details
- Update `translator.py`
- Restart systemd service

### Deployment Result
```
● blog-api.service - Blog API Server
     Active: active (running)
```

## Next Steps

1. Test Translation API
2. Build Monitoring Dashboard
3. Apply Log File Rotation Policy

---

**English Version:** [English Version](/post/2026-03-03-001-blog-api-server-llm-config-improvement-and-deployment/)