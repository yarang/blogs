# 블로그 번역 파이프라인 가이드

## 개요

이 문서는 블로그 포스트의 한국어/영어 동기화를 위한 자동 번역 파이프라인 사용법을 설명합니다.

## 시스템 구조

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Korean Posts   │─────▶│  Translation API │─────▶│ English Posts   │
│ content/post/   │      │  (ZAI/Anthropic) │      │content/en/post/ │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Git Commit/Push │
                       └──────────────────┘
```

## 디렉토리 구조

Hugo Stack 테마의 다국어 지원을 따릅니다:

```
content/
├── post/           # 한국어 포스트 (기본 언어)
│   ├── 2026-02-21-001-example.md
│   └── ...
└── en/
    └── post/       # 영어 포스트
        ├── 2026-02-21-001-example.md
        └── ...
```

## 번역 방법

### 1. API를 통한 자동 번역 (권장)

API 서버의 `/translate/sync` 엔드포인트를 사용합니다:

```bash
curl -X POST http://130.162.133.47/translate/sync \
  -H "x-api-key: YOUR_API_KEY"
```

### 2. MCP 도구를 통한 번역

Claude Code에서 MCP 블로그 도구를 사용합니다:

```
# 번역 상태 확인
blog_status

# 포스트 생성 (language="en" 지정)
blog_create(title="English Title", content="...", language="en")
```

### 3. 수동 번역

직접 파일을 생성하는 경우:

1. `content/post/`에서 한국어 원본 찾기
2. 동일한 파일명으로 `content/en/post/` 생성
3. 번역 후 front matter 유지

## 번역 API 설정

### ZAI API (추천)

```bash
# .env 파일
ZAI_API_KEY=your_zai_api_key
ZAI_BASE_URL=https://api.zukijourney.com/v1
ZAI_MODEL=gpt-4o-mini
```

### Anthropic Claude API

```bash
# .env 파일
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## 번역 상태 확인

```bash
curl http://130.162.133.47/translate/status \
  -H "x-api-key: YOUR_API_KEY"
```

응답 예시:
```json
{
  "korean_posts": 6,
  "english_posts": 2,
  "needs_translation": ["2026-02-21-003-example", "..."],
  "needs_translation_count": 4,
  "synced": false
}
```

## 자동 번역 워크플로우

1. 한국어 포스트 작성 (MCP 도구 또는 직접 파일 생성)
2. Git push로 블로그 배포
3. `/translate/sync` API 호출로 자동 번역
4. 번역된 영어 포스트가 `content/en/post/`에 생성
5. Git 자동 커밋/푸시

## 프론트 매터 처리

번역 시 front matter는 자동으로 처리됩니다:

```toml
+++
title = "번역된 제목"        # 제목 자동 번역
date = 2026-02-21T...       # 날짜 유지
draft = false               # 상태 유지
tags = ["tag1", "tag2"]     # 태그 유지
categories = ["Category"]   # 카테고리 유지
+++
```

## 주의사항

1. **코드 블록 보존**: 번역기는 마크다운 형식을 보존합니다
2. **기술 용어**: 적절한 영어 번역 또는 원문 유지
3. **파일명 동기화**: 한국어와 영어 포스트는 동일한 파일명 사용
4. **날짜 유지**: 번역본은 원본의 날짜를 그대로 사용

## 문제 해결

### 번역이 실패하는 경우

1. API Key 확인
2. API 서버 로그 확인 (`/var/www/blog-api-server/logs/`)
3. 네트워크 연결 확인

### 영어 포스트가 노출되지 않는 경우

1. `hugo.toml`의 `defaultContentLanguageInSubdir` 설정 확인
2. 영어 메뉴 URL이 `/en/`으로 시작하는지 확인
3. Hugo 빌드 후 재배포

## 추천 작업 flow

```bash
# 1. 한국어 포스트 작성
cd /Users/yarang/workspaces/agent_dev/blogs
# MCP 도구 또는 직접 파일 생성

# 2. Git 커밋/푸시
git add content/post/
git commit -m "Add new Korean post"
git push

# 3. 번역 API 호출
curl -X POST http://130.162.133.47/translate/sync \
  -H "x-api-key: YOUR_API_KEY"

# 4. GitHub Actions가 자동으로 빌드/배포
```
