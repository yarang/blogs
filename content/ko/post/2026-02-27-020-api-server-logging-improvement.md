+++
title = "[blog-api-server] 로깅 개선 완료"
slug = "2026-02-27-020-api-server-logging-improvement"
date = 2026-02-27T23:48:07+09:00
draft = false
tags = ["API", "\ub85c\uae45", "\ub514\ubc84\uae45", "Python"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# API 서버 로깅 개선 완료

## 개요

블로그 API 서버에 상세 로깅을 추가하여 요청 처리 과정을 추적할 수 있게 되었습니다.

## 추가된 로깅

### API 레벨 (`[API]` prefix)
- 요청 시작/종료
- 요청 파라미터
- 처리 시간

### 블로그 매니저 레벨 (`[BLOG_MANAGER]` prefix)
- Git lock 획득/해제
- 동기화(Sync) 진행 상황
- 파일명 생성
- 파일 작성
- Git commit/push 단계별 진행

### Git 명령 레벨 (`[GIT]` prefix)
- Git 명령어 실행 시작
- 명령어 완료 시간
- 에러 및 경고 메시지

## 수정된 문제들

1. **LogRecord 예약 속성 충돌**: `filename`, `message` 등 예약어를 `post_filename`, `commit_msg`로 변경
2. **데드락 문제**: `commit_and_push`에서 중복 lock 획득 제거
3. **경로 오류**: 한국어 포스트 경로를 `content/post/`로 수정

## 타이밍 분석 예시

```
Git pull: ~2.3초
파일 작성: ~1ms
Git commit: ~42ms
Git push: ~2.5초
총 요청 시간: ~4.8초
```

## 결론

상세 로깅을 통해 API 요청의 각 단계를 명확히 추적할 수 있게 되었으며, 문제 발생 시 원인 파악이 용이해졌습니다.