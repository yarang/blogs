+++
title = "[MCP] Blog Server Improvement Kickoff"
slug = "mcp-server-improvement-kickoff-meeting"
date = 2026-02-25T00:00:00+09:00
draft = false
tags = ["MCP", "blog", "meeting", "project"]
categories = ["Meeting", "Project"]
ShowToc = true
TocOpen = true
+++

# Blog MCP Server Improvement Project Kickoff Meeting Minutes

**Date:** 2026-02-25
**Project:** Blog MCP Server Improvement
**Attendees:** team-lead, backend-dev, search-specialist, qa-tester, meeting-writer
**Document Author:** meeting-writer

---

## 1. Meeting Overview

### 1.1 Purpose
Project kickoff to improve the stability and performance of the blog MCP server according to the improvement roadmap defined in ARCHITECTURE.md

### 1.2 Project Scope
- **Blog Repository:** `/Users/yarang/workspaces/agent_dev/blogs`
- **API Server:** `/Users/yarang/workspaces/agent_dev/blog-api-server`

---

## 2. Project Background

### 2.1 Current System Status
The current blog system operates with the following structure:

```
Claude Code (MCP Client)
        ↓ HTTP POST /posts
API Server (blog-api-server)
        ↓ Git clone/pull, Git commit/push
GitHub (yarang/blogs)
        ↓ GitHub Actions trigger
Hugo Build + Deploy
        ↓
Blog (blog.fcoinfup.com)
```

### 2.2 Identified Issues

#### 🔴 P0 - Critical Issues
1. **Insufficient Concurrency Control**: Only using global `threading.Lock()`, potential race conditions in multi-process environments
2. **Search Bug**: `search_posts()` only searches Korean directory, missing English posts

#### 🟡 P1 - Scalability Issues
1. **Git Pull on Every Request**: Unnecessary network calls, increased latency
2. **File-based Search (O(n))**: Performance degradation with 100+ posts
3. **Global Instance Dependency**: Difficult testing, no dependency injection

#### 🟢 P2 - Maintainability Issues
1. Duplicate Git code (`GitManager` and `GitHandler` coexist)
2. Unstable language detection logic
3. Broad exception handling

---

## 3. Team Composition

| Role | Member | Responsibilities |
|------|--------|------------------|
| team-lead | Project Leader | Overall project management, coordination |
| backend-dev | Backend Developer | Concurrency control, Git optimization |
| search-specialist | Search Specialist | Search functionality improvement |
| qa-tester | QA Tester | Testing and quality assurance |
| meeting-writer | Meeting Scribe | Meeting notes and documentation |

---

## 4. Work Items and Progress

### 4.1 Search Bug Fix ✅ Complete
- **Owner:** search-specialist
- **Priority:** P0
- **Results:**
  - Confirmed P0 bug in ARCHITECTURE.md was already fixed
  - Verified with 12 test cases in `test_search.py`
  - All language directories (ko, en) now searchable

### 4.2 Git Pull Optimization ✅ Complete
- **Owner:** backend-dev
- **Priority:** P1
- **Results:**
  - Introduced `CacheManager` in MCP client (5-minute TTL)
  - Implemented cache invalidation after write operations
  - Location: `.claude/mcp_server.py:25-71`

### 4.3 Enhanced Concurrency Control ✅ Complete
- **Owner:** backend-dev
- **Priority:** P1
- **Results:**
  - Introduced `asyncio.Lock` in MCP client
  - Prevented write operation conflicts

### 4.4 Existing Test Code Validation 🔄 In Progress
- **Owner:** qa-tester
- **Priority:** QA
- **Status:** In progress

### 4.5 ARCHITECTURE.md Update ✅ Complete
- **Owner:** team-lead
- **Results:**
  - Reflected completed work
  - Progress indicators (✅ Complete, 🔄 In Progress, ⚡ Partial)

---

## 5. Key Achievements

### Before Improvements
- Git Pull on every request (up to 60-second timeout)
- Only Korean posts searchable
- Insufficient concurrency control

### After Improvements
- **Caching Introduced:** 5-minute TTL minimizes unnecessary API calls
- **Multi-language Search:** Both Korean and English posts searchable
- **Concurrency Control:** `asyncio.Lock` prevents write operation conflicts

---

## 6. Test Coverage

| Test Item | Status |
|-----------|--------|
| Multi-language search (ko, en) | ✅ |
| Relevance sorting | ✅ |
| Case-insensitive search | ✅ |
| Result structure validation | ✅ |
| Caching behavior | ✅ |
| Connection pooling | ✅ |
| Error handling | ✅ |

---

## 7. Next Steps (Medium-term Plan)

### P2 - Structural Improvements
1. **Git Class Consolidation**: Merge `GitManager` and `GitHandler`
2. **Dependency Injection**: Utilize FastAPI Depends
3. **Index-based Search**: Consider Whoosh or Meilisearch

---

## 8. Meeting Summary

This meeting minutes includes:
- Project kickoff discussion items
- Team composition and role assignments
- Work item progress
- Summary of completed work
- Future plans

---

*This meeting minutes was prepared by meeting-writer and will be updated as the project progresses.*
