# MCP Server Tests

MCP 서버/클라이언트 테스트 스위트입니다.

## 테스트 구조

```
tests/
├── __init__.py           # 패키지 초기화
├── conftest.py           # Pytest fixtures
├── test_client.py        # BlogAPIClient 단위 테스트
├── test_mcp_tools.py     # MCP 도구 단위 테스트
└── test_integration.py   # 통합 테스트
```

## 실행 방법

### 전체 테스트 실행

```bash
cd .claude/tests
pip install -r requirements.txt
pytest
```

### 특정 테스트 파일

```bash
pytest test_client.py
pytest test_mcp_tools.py
pytest test_integration.py
```

### 커버리지 포함

```bash
pytest --cov=../mcp_server --cov-report=html
open htmlcov/index.html
```

### 마커별 실행

```bash
pytest -m unit          # 단위 테스트만
pytest -m integration   # 통합 테스트만
pytest -m "not slow"    # 빠른 테스트만
```

## 테스트 범위

### 단위 테스트 (test_client.py)
- BlogAPIClient 초기화
- 연결 풀링 동작
- HTTP 메서드 (GET, POST, PUT, DELETE)
- 에러 핸들링 (401, 403, 타임아웃)
- 리소스 정리

### 단위 테스트 (test_mcp_tools.py)
- 8개 MCP 도구 스키마 검증
- 각 도구별 호출 테스트
- 기본값 처리

### 통합 테스트 (test_integration.py)
- 전체 포스트 작업 워크플로우
- 검색 및 목록 조회
- Git 작업
- 에러 처리 시나리오

## 커버리지 목표

- 라인 커버리지: 80% 이상
- 분기 커버리지: 70% 이상

## CI/CD 통합

```yaml
- name: Run tests
  run: |
    cd .claude/tests
    pip install -r requirements.txt
    pytest --cov=../mcp_server --cov-report=xml
```
