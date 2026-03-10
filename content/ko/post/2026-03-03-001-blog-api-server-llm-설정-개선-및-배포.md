+++
title = "[blog-api-server] LLM 설정 개선 및 배포"
date = 2026-03-03T13:01:48+09:00
draft = false
tags = ["blog-api-server", "LLM", "\ubc30\ud3ec", "\uac1c\ubc1c"]
categories = ["\uac1c\ubc1c"]
ShowToc = true
TocOpen = true
+++

## 개요

blog-api-server 프로젝트의 LLM 설정을 개선하고 서버에 배포했다.

## LLM 설정 개선

### 기존 문제
- 여러 개의 API Key 환경 변수 (`ZAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Provider 분기 로직이 복잡함
- 모델 설정이 분산되어 있음

### 변경 사항

#### 환경 변수 단순화

```bash
# 기존
ZAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
ZAI_MODEL=gpt-4o-mini
LLM=ZAI

# 변경 후
LLM=ZAI                    # Provider (ZAI, OPENAI, ANTHROPIC)
LLM_API_KEY=xxx           # 단일 API Key
LLM_MODEL=glm-4.7         # 기본 모델
LLM_TIMEOUT=120           # 타임아웃 (초)
```

#### BASE_URL 자동 설정

```python
LLM_BASE_URLS = {
    "ZAI": "https://api.z.ai/api/coding/paas/v4",
    "OPENAI": "https://api.openai.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1"
}
```

#### 코드 구조 개선

```python
class Translator:
    """LLM 기반 번역기"""
    
    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL  # 자동 선택
        self.model = LLM_MODEL
        self.timeout = LLM_TIMEOUT
```

## 모델 설정

### 기본 모델
- **glm-4.7** (기본값)
- max_tokens: 8192

### 지원 모델

| 모델 | max_tokens |
|------|------------|
| glm-4 | 8192 |
| glm-4.7 | 8192 |
| gpt-4o-mini | 4096 |
| gpt-4o | 8192 |
| claude-3-5-haiku | 8192 |

## 팀 구성

blog-api-server 개발 팀을 구성했다.

| 역할 | 이름 | 담당 |
|------|------|------|
| 팀 리드 | team-lead | 전체 관리 |
| 개발자 | developer | 코드 작성, 기능 구현 |
| 배포 관리자 | deployer | 서버 배포, 인프라 |
| 모니터링 | monitor | 로그 분석, 성능 모니터링 |

## 서버 배포

### 배포 대상
- **서버**: blog.fcoinfup.com (130.162.133.47)
- **경로**: `/var/www/blog-api`

### 배포 내용
- `translator.py` 업데이트
- systemd 서비스 재시작

### 배포 결과
```
● blog-api.service - Blog API Server
     Active: active (running)
```

## 다음 단계

1. 번역 API 테스트
2. 모니터링 대시보드 구축
3. 로그 파일 롤오버 정책 적용

---

**영어 버전:** [English Version](/post/2026-03-03-001-blog-api-server-llm-config-improvement-and-deployment/)