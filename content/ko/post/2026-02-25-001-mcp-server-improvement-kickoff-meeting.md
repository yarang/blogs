+++
title = "[MCP] 블로그 서버 개선 킥오프"
slug = "mcp-server-improvement-kickoff-meeting"
date = 2026-02-25T00:00:00+09:00
draft = false
tags = ["MCP", "블로그", "회의록", "프로젝트"]
categories = ["회의록", "프로젝트"]
ShowToc = true
TocOpen = true
+++

# 블로그 MCP 서버 개선 프로젝트 킥오프 회의록

**날짜:** 2026-02-25
**프로젝트:** 블로그 MCP 서버 개선
**참석자:** team-lead, backend-dev, search-specialist, qa-tester, meeting-writer
**문서 작성:** meeting-writer

---

## 1. 회의 개요

### 1.1 회의 목적
ARCHITECTURE.md에 정의된 개선 로드맵에 따라 블로그 MCP 서버의 안정성과 성능을 개선하기 위한 프로젝트 킥오프

### 1.2 프로젝트 범위
- **블로그 저장소:** `/Users/yarang/workspaces/agent_dev/blogs`
- **API 서버:** `/Users/yarang/workspaces/agent_dev/blog-api-server`

---

## 2. 프로젝트 배경

### 2.1 시스템 현황
현재 블로그 시스템은 다음과 같은 구조로 운영되고 있습니다:

```
Claude Code (MCP Client)
        ↓ HTTP POST /posts
API Server (blog-api-server)
        ↓ Git clone/pull, Git commit/push
GitHub (yarang/blogs)
        ↓ GitHub Actions 트리거
Hugo Build + Deploy
        ↓
Blog (blog.fcoinfup.com)
```

### 2.2 식별된 문제점

#### 🔴 P0 - 심각한 문제
1. **동시성 제어 부족**: 전역 `threading.Lock()`만 사용하여 멀티프로세스 환경에서 경쟁 조건 발생 가능
2. **검색 기능 버그**: `search_posts()`가 한국어 디렉토리만 검색하여 영어 포스트가 검색되지 않음

#### 🟡 P1 - 확장성 문제
1. **매 요청마다 Git Pull 실행**: 불필요한 네트워크 호출, 지연 시간 증가
2. **파일 기반 검색 (O(n))**: 포스트가 100개 이상이 되면 성능 저하
3. **전역 인스턴스 의존**: 테스트 어려움, 의존성 주입 불가

#### 🟢 P2 - 유지보수성 문제
1. 중복된 Git 코드 (`GitManager`와 `GitHandler` 이중 존재)
2. 언어 감지 로직 불안정
3. 광범위한 예외 처리

---

## 3. 팀 구성

| 역할 | 담당자 | 주요 책임 |
|------|--------|-----------|
| team-lead | 프로젝트 리더 | 프로젝트 총괄, 조율 |
| backend-dev | 백엔드 개발자 | 동시성 제어, Git 최적화 |
| search-specialist | 검색 전문가 | 검색 기능 개선 |
| qa-tester | QA 테스터 | 테스트 및 품질 보증 |
| meeting-writer | 회의록 작성자 | 회의록 정리 및 문서화 |

---

## 4. 작업 항목 및 진행 상황

### 4.1 검색 버그 수정 ✅ 완료
- **담당자:** search-specialist
- **우선순위:** P0
- **결과:**
  - ARCHITECTURE.md의 P0 버그는 이미 수정되어 있었음 확인
  - `test_search.py` 12개 테스트 케이스로 검증 완료
  - 모든 언어 디렉토리(ko, en) 검색 지원

### 4.2 Git Pull 최적화 ✅ 완료
- **담당자:** backend-dev
- **우선순위:** P1
- **결과:**
  - MCP 클라이언트에 `CacheManager` 도입 (TTL 5분)
  - 쓰기 작업 후 캐시 무효화 구현
  - 위치: `.claude/mcp_server.py:25-71`

### 4.3 동시성 제어 강화 ✅ 완료
- **담당자:** backend-dev
- **우선순위:** P1
- **결과:**
  - MCP 클라이언트에 `asyncio.Lock` 도입
  - 쓰기 작업 간 충돌 방지

### 4.4 기존 테스트 코드 검증 🔄 진행 중
- **담당자:** qa-tester
- **우선순위:** QA
- **현재 상황:** 진행 중

### 4.5 ARCHITECTURE.md 업데이트 ✅ 완료
- **담당자:** team-lead
- **결과:**
  - 완료된 작업 반영
  - 진행 상태 표시 (✅ 완료, 🔄 진행 중, ⚡ 부분 완료)

---

## 5. 주요 성과

### 개선 전
- 매 요청마다 Git Pull 실행 (최대 60초 타임아웃)
- 한국어 포스트만 검색 가능
- 동시성 제어 부족

### 개선 후
- **캐싱 도입:** TTL 5분으로 불필요한 API 호출 최소화
- **다국어 검색:** 한국어, 영어 포스트 모두 검색 지원
- **동시성 제어:** `asyncio.Lock`으로 쓰기 작업 충돌 방지

---

## 6. 테스트 커버리지

| 테스트 항목 | 상태 |
|------------|------|
| 다국어 검색 (ko, en) | ✅ |
| Relevance 정렬 | ✅ |
| 대소문자 무시 검색 | ✅ |
| 결과 구조 검증 | ✅ |
| 캐싱 동작 | ✅ |
| 연결 풀링 | ✅ |
| 에러 핸들링 | ✅ |

---

## 7. 다음 단계 (중기 계획)

### P2 - 구조 개선
1. **Git 클래스 통합**: `GitManager`와 `GitHandler` 통합
2. **의존성 주입**: FastAPI Depends 활용
3. **인덱스 기반 검색**: Whoosh 또는 Meilisearch 도입 검토

---

## 8. 회의록 정리

이 회의록은 다음 내용을 포함합니다:
- 프로젝트 킥오프 논의 사항
- 팀 구성 및 역할 분담
- 작업 항목별 진행 상황
- 완료된 작업 요약
- 향후 계획

---

*본 회의록은 meeting-writer가 작성했으며, 프로젝트 진행 상황에 따라 업데이트됩니다.*
