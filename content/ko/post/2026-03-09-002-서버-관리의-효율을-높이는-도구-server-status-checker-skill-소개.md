---
title: "서버 관리의 효율을 높이는 도구: Server Status Checker Skill 소개"
date: 2026-03-09T00:30:00+09:00
draft: false
tags: ["DevOps", "서버모니터링", "오픈소스", "Claude", "AI", "생산성", "SSH"]
categories: ["개발도구"]
---

# 서버 관리의 효율을 높이는 도구: Server Status Checker Skill 소개

관리하는 서버가 점점 늘어나고 있나요?

서버마다 일일이 SSH로 접속하여 상태를 확인하는 일은 시간 낭비입니다. 여러 서버의 CPU, 메모리, 디스크 사용량을 한눈에 파악할 수 있다면 업무 효율이 크게 향상될 것입니다.

저도 그런 문제를 겪었습니다. 그래서 만들었습니다.

## 문제: 서버 모니터링의 반복 작업

DevOps 엔지니어나 시스템 관리자라면 한 번쯤 겪는 상황입니다:

1. 서버별 SSH 접속 반복
2. top, htop, df 명령어 일일이 실행
3. 엑셀이나 노션에 수동으로 상태 기록
4. 서버 증가시 마다 관리 스크립트 수정

이 과정은 시간 낭비이자, 실수를 유발할 수 있는 반복 작업입니다.

## 해결책: Server Status Checker Skill

**Server Status Checker**는 Claude Code용 스킬로, SSH config 파일을 기반으로 모든 서버의 상태를 병렬로 확인합니다.

### 주요 기능

| 기능 | 설명 |
|------|------|
| **SSH config 자동 파싱** | `~/.ssh/config` 파일에서 서버 목록 자동 발견 |
| **실시간 상태 확인** | CPU, Memory, Disk, Uptime, Load 정보 수집 |
| **병렬 연결** | asyncssh로 빠른 상태 확인 (초 단위) |
| **그룹별 분류** | GCP, OCI, GitHub, Blog, Local 등으로 자동 분류 |
| **온라인/오프라인 상태** | ✓ / ✗ 로 직관적인 상태 표시 |

### 사용법

```bash
# 전체 서버 상태 확인
/server-status-checker

# 특정 서버만 확인
/server-status-checker --server mini01

# JSON 형식으로 출력
/server-status-checker --json

# 상세 에러 메시지
/server-status-checker --verbose
```

### 출력 예시

```
=== Server Status Report ===

[GCP 서버]
✗ gcp-ajou-ec1 - Offline (Authentication failed)
✗ gcp-fcoinfup-ec1 - Offline (Authentication failed)

[OCI Ajou]
✓ oci-ajou-ec1 - Online
  CPU: 15.2% | Memory: 62.3% | Disk: 45.8%
  Uptime: 15 days | Load: 1.23 1.45 1.38
  OS: Ubuntu 22.04 LTS

[로컬 서버]
✓ mini01 - Online
  CPU: 6.7% | Memory: 45.2% | Disk: 5.0%
  Uptime: 2 days | Load: 2.17 2.11 1.94
  OS: macOS 26.3.1
```

## 기술적 세부사항

### SSH Config 파싱

`~/.ssh/config` 파일을 파싱하여 다음 정보를 자동 추출합니다:

- Host (호스트명)
- HostName (IP 주소 또는 도메인)
- User (사용자명)
- Port (포트번호)
- IdentityFile (SSH 키 경로)

### 비동기 병렬 처리

Python `asyncssh` 라이브러리를 활용하여 모든 서버에 동시에 접속합니다:

```python
async def check_server(host: str):
    # SSH 접속 및 명령 실행
    result = await asyncssh.connect(...)
    return status
```

30대의 서버를 순차적으로 확인하면 5분이 걸리지만, 병렬 처리시 30초 내에 완료됩니다.

### 그룹 자동 분류

서버 이름 패턴을 기반으로 자동 분류합니다:

| 그룹 | 패턴 | 예시 |
|------|------|------|
| **GCP** | `gcp-` 접두사 | gcp-ajou-ec1, gcp-fcoinfup-ec1 |
| **OCI Ajou** | `oci-ajou-` 접두사 | oci-ajou-ec1 |
| **OCI Fcoinfup** | `oci-fcoinfup-` 접두사 | oci-fcoinfup-ec1 |
| **GitHub** | `github-as-` 접두사 | github-as-actions |
| **Blog** | `blog` | blog |
| **Local** | `mini`, `mac` | mini01, macbook-pro |

### 시스템 메트릭 수집

각 서버에서 다음 정보를 수집합니다:

**Linux:**
- CPU: `/proc/stat` 또는 `psutil.cpu_percent()`
- Memory: `/proc/meminfo` 또는 `psutil.virtual_memory()`
- Disk: `psutil.disk_usage()`
- Uptime: `/proc/uptime` 또는 `psutil.boot_time()`
- Load: `/proc/loadavg` 또는 `os.getloadavg()`

**macOS:**
- CPU: `psutil.cpu_percent()`
- Memory: `psutil.virtual_memory()`
- Disk: `psutil.disk_usage()`
- Uptime: `psutil.boot_time()`
- Load: `os.getloadavg()`

## GitHub 공개

이 스킬은 오픈소스로 공개되어 있습니다.

🔗 **GitHub:** https://github.com/yarang/skill-server-status-checker

### 설치 방법

```bash
git clone https://github.com/yarang/skill-server-status-checker.git
cp -r skill-server-status-checker ~/.claude/skills/server-status-checker
```

## 비즈니스 가치

| 측면 | 개선 효과 |
|------|----------|
| **시간 절약** | 서버 확인 시간 90% 단축 (5분 → 30초) |
| **실시간 모니터링** | 즉각적인 서버 상태 파악 |
| **중앙화된 관리** | SSH config 단일 파일로 모든 서버 관리 |
| **자동화** | 반복 작업 제거로 인적 실수 최소화 |

## 활용 사례

### 1. 일일 서버 건강 확인

매일 아침 `/server-status-checker` 명령 하나로 모든 서버 상태를 확인합니다.

### 2. 장애 대응

장애 발생시 즉시 오프라인 서버를 식별하고 조치를 취합니다.

### 3. 용량 계획

디스크 사용량 추이를 모니터링하여 미리 용량 확보를 계획합니다.

### 4. 성능 모니터링

CPU와 메모리 사용량을 추적하여 병목 지점을 파악합니다.

## 결론

Server Status Checker는 단순한 서버 상태 확인 도구가 아닙니다. DevOps 엔지니어와 시스템 관리자가 반복 작업에서 벗어나 핵심 업무에 집중할 수 있도록 돕는 생산성 도구입니다.

SSH config라는 표준화된 설정 파일을 활용하고, 병렬 처리를 통해 빠르게 결과를 제공합니다. 이제 서버 한 대 한 대에 접속할 필요 없이, 한 번의 명령으로 모든 서버의 건강 상태를 파악하세요.

AI와 자동화를 통해 시스템 관리의 효율성을 높이고, 우리는 더 중요한 문제에 집중할 수 있습니다.

---

**관련 프로젝트:**
- [domain-checker](https://github.com/yarang/skill-domain-checker) - 도메인 등록 가능 여부 확인 도구

**태그:** #DevOps #서버모니터링 #오픈소스 #Claude #AI #생산성 #SSH

**영어 버전:** [English Version](/post/2026-03-09-002-server-status-checker-skill-introduction/)
