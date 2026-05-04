# 블로그 글 작성 가이드

**갱신일**: 2026-05-03

## 개요

arm1의 Claude Code가 ec1의 Blog API를 통해 블로그 포스트를 관리한다.
직접 파일을 편집하지 않고, API 호출로 모든 작업을 수행한다.

## API 접속 설정

```bash
API_KEY=$(cat /etc/auto-comment-worker/credentials/blog-api-key)
BASE="https://blog.fcoinfup.com/api"
H_KEY="X-API-Key: $API_KEY"
H_JSON="Content-Type: application/json"
```

## 포스트 작성 절차

### 1. 기존 포스트 확인

```bash
curl -s -H "$H_KEY" "$BASE/posts?limit=5&language=ko" | python3 -m json.tool
```

### 2. 포스트 생성

```bash
curl -s -X POST -H "$H_KEY" -H "$H_JSON" "$BASE/posts" \
  -d '{"title":"제목","content":"본문","tags":["tag1"],"categories":["Development"],"draft":false,"auto_push":true,"language":"ko"}'
```

**파라미터:**
- `title` (필수): 포스트 제목
- `content` (필수): 마크다운 본문 (frontmatter 제외, API가 자동 생성)
- `tags`: 태그 목록
- `categories`: 카테고리 목록
- `draft`: true면 드래프트
- `auto_push`: true면 Git에 자동 push
- `language`: "ko" 또는 "en"

### 3. 번역 (ko -> en)

```bash
curl -s -X POST -H "$H_KEY" -H "$H_JSON" "$BASE/translate" \
  -d '{"content":"번역할 마크다운","source":"ko","target":"en"}'

# 미번역 포스트 일괄 번역
curl -s -X POST -H "$H_KEY" "$BASE/translate/sync"
```

### 4. 포스트 수정

```bash
curl -s -H "$H_KEY" "$BASE/posts/{filename}?language=ko"

curl -s -X PUT -H "$H_KEY" -H "$H_JSON" "$BASE/posts/{filename}?language=ko" \
  -d '{"content":"수정된 마크다운","auto_push":true}'
```

### 5. 포스트 삭제

```bash
curl -s -X DELETE -H "$H_KEY" "$BASE/posts/{filename}?language=ko"
```

## Hugo 포스트 규칙

1. **slug 필수**: 제목에 특수문자 포함 시 permalink 깨짐. frontmatter에 slug 명시
2. **날짜**: 현재 시간 이전으로 설정. Hugo는 미래 포스트를 기본 빌드에서 제외
3. **시리즈**: `series = ["시리즈명"]`으로 시리즈 묶기
4. **카테고리**: 기존 패턴 따르기 (Development, AI, DevOps, Security 등)

## 검색 및 동기화

```bash
curl -s -H "$H_KEY" "$BASE/search?q=검색어"
curl -s -X POST -H "$H_KEY" "$BASE/sync"
curl -s -H "$H_KEY" "$BASE/status"
```
