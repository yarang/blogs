+++
title = "[blog-api-server] LLM Configuration Improvement and Deployment"
date = 2026-03-03T22:37:06+09:00
draft = false
tags = ["blog-api-server", "LLM", "deployment", "development"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

## Overview

Improved the LLM configuration of the blog-api-server project and deployed it to the production server.

## LLM Configuration Improvement

### Previous Issues
- Multiple API Key environment variables (`ZAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Complex provider branching logic
- Scattered model settings

### Changes

#### Simplified Environment Variables

```bash
# Before
ZAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
ZAI_MODEL=gpt-4o-mini
LLM=ZAI

# After
LLM=ZAI                    # Provider (ZAI, OPENAI, ANTHROPIC)
LLM_API_KEY=xxx           # Single API Key
LLM_MODEL=glm-4.7         # Default model
LLM_TIMEOUT=120           # Timeout (seconds)
```

#### Auto BASE_URL Selection

```python
LLM_BASE_URLS = {
    "ZAI": "https://api.z.ai/api/coding/paas/v4",
    "OPENAI": "https://api.openai.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1"
}
```

#### Improved Code Structure

```python
class Translator:
    """LLM-based Translator"""
    
    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL  # Auto-selected
        self.model = LLM_MODEL
        self.timeout = LLM_TIMEOUT
```

## Model Configuration

### Default Model
- **glm-4.7** (default)
- max_tokens: 8192

### Supported Models

| Model | max_tokens |
|-------|------------|
| glm-4 | 8192 |
| glm-4.7 | 8192 |
| gpt-4o-mini | 4096 |
| gpt-4o | 8192 |
| claude-3-5-haiku | 8192 |

## Server Deployment

### Target
- **Server**: blog.fcoinfup.com (130.162.133.47)
- **Path**: `/var/www/blog-api`

### Deployment Result
```
● blog-api.service - Blog API Server
     Active: active (running)
```

## Translation API Test

Tested the translation API after deployment:

| Input (Korean) | Output (English) |
|----------------|------------------|
| "안녕하세요, 이것은 테스트 번역입니다." | "Hello, this is a test translation." |

**Result**: API working correctly with `glm-4.7` model.

## Next Steps

1. Monitoring dashboard setup (Grafana/Prometheus)
2. Log file rotation policy
3. Alert configuration (Slack/Email)