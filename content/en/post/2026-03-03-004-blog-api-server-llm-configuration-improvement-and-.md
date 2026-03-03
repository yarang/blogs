+++
title = "[blog-api-server] LLM Configuration Improvement and Deployment"
date = 2026-03-03T22:41:32+09:00
draft = false
tags = ["blog-api-server", "LLM", "deployment"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

## Overview

Improved the LLM configuration of the blog-api-server project and deployed it to the production server.

## LLM Configuration Improvement

### Simplified Environment Variables

```bash
LLM=ZAI
LLM_API_KEY=xxx
LLM_MODEL=glm-4.7
LLM_TIMEOUT=120
```

### Auto BASE_URL Selection

```python
LLM_BASE_URLS = {
    "ZAI": "https://api.z.ai/api/coding/paas/v4",
    "OPENAI": "https://api.openai.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1"
}
```

## Model Configuration

| Model | max_tokens |
|-------|------------|
| glm-4 | 8192 |
| glm-4.7 | 8192 |
| gpt-4o-mini | 4096 |
| gpt-4o | 8192 |

## Translation API Test

- Input: "안녕하세요, 이것은 테스트 번역입니다." (Korean)
- Output: "Hello, this is a test translation." (English)
- Status: Working correctly

## Next Steps

1. Monitoring dashboard setup
2. Log file rotation policy
3. Alert configuration