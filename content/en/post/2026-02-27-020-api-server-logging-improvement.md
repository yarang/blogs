+++
title = "[blog-api-server] Logging Improvement Complete"
slug = "2026-02-27-020-api-server-logging-improvement"
date = 2026-02-27T23:48:07+09:00
draft = false
tags = ["API", "logging", "debugging", "Python"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# API Server Logging Improvement Complete

## Overview

Detailed logging has been added to the blog API server to track request processing.

## Added Logging

### API Level (`[API]` prefix)
- Request start/end
- Request parameters
- Processing time

### Blog Manager Level (`[BLOG_MANAGER]` prefix)
- Git lock acquire/release
- Sync progress
- Filename generation
- File writing
- Git commit/push step-by-step progress

### Git Command Level (`[GIT]` prefix)
- Git command execution start
- Command completion time
- Error and warning messages

## Fixed Issues

1. **LogRecord Reserved Attribute Conflict**: Changed reserved words like `filename`, `message` to `post_filename`, `commit_msg`
2. **Deadlock Issue**: Removed duplicate lock acquisition in `commit_and_push`
3. **Path Error**: Fixed Korean post path to `content/post/`

## Timing Analysis Example

```
Git pull: ~2.3s
File write: ~1ms
Git commit: ~42ms
Git push: ~2.5s
Total request time: ~4.8s
```

## Conclusion

With detailed logging, each step of API requests can now be clearly tracked, making it easier to identify issues when they occur.


---

**Korean Version:** [한국어 버전](/ko/post/2026-02-27-020-api-server-logging-improvement/)