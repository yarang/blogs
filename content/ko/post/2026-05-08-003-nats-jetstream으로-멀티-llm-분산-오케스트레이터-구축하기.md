+++
title = "NATS JetStream으로 멀티-LLM 분산 오케스트레이터 구축하기"
date = 2026-05-08T21:57:11+09:00
draft = false
tags = ["agentforge", "nats", "jetstream", "architecture", "llm", "python", "systemd"]
categories = ["AI", "Architecture"]
ShowToc = true
TocOpen = true
+++

1편에서는 Claude, ZAI, Codex, Gemini 네 가지 AI를 같은 태스크에 동시에 돌리면서 발견한 모델별 제한 사항을 다뤘다. 이번 편은 "어떻게 그게 가능하도록 만들었나"—시스템 설계와 구현 이야기다.

---

## 시스템 개요

AgentForge는 세 가지 요소로 이루어진다.

```
[태스크 발행자]
       │  NATS JetStream publish
       ▼
[NATS 브로커] ─── af.worker.{id}.inbox
       │  JetStream consume (워커별 독립 스트림)
       ▼
[워커 폴러] × N  (poller.py × 18개)
       │  LLM CLI 실행 (claude / codex / gemini)
       ▼
[결과 반환]   af.task.{task_id}.completed
```

발행자가 NATS에 태스크를 올리면, 각 워커가 독립적으로 구독하고 있다가 자신의 inbox로 들어온 메시지를 받아 LLM CLI를 실행한다. 결과는 완료 주제로 다시 publish된다.

---

## 왜 NATS JetStream인가

메시지 브로커 선택지는 여러 개였다: Redis Streams, Kafka, RabbitMQ, NATS JetStream.

**NATS JetStream을 선택한 이유:**

1. **단일 바이너리** — 별도의 런타임 없이 `nats-server` 하나로 동작한다. Kafka의 ZooKeeper나 RabbitMQ의 Erlang/OTP 의존성이 없다.

2. **내장 영속성** — JetStream은 NATS 위에 올라가는 스트리밍 레이어로, 메시지를 파일시스템에 저장한다. 워커가 재시작되어도 처리 안 된 태스크가 유실되지 않는다.

3. **NKey 기반 인증** — 워커별로 독립된 Ed25519 keypair를 발급할 수 있다. 한 워커가 침해되어도 다른 워커의 자격증명은 유효하다.

4. **경량** — 단일 서버에서 메모리 사용량 ~30MB. 18개 워커를 연결해도 브로커 부하가 거의 없다.

---

## 핵심: poller.py의 백엔드 어댑터

워커의 핵심은 `poller.py`다. 이 파일 하나가 NATS 구독, LLM CLI 실행, 결과 반환을 모두 담당한다.

LLM별 실행 방식이 다르기 때문에, 백엔드 어댑터 딕셔너리로 분리했다.

```python
_BACKENDS: dict[str, dict] = {
    "claude": {
        "bin":   os.environ.get("CLAUDE_BIN",  "/usr/local/bin/claude"),
        "tools": os.environ.get("ALLOWED_TOOLS", "Read,Edit,Write,Glob,Grep"),
        "model": os.environ.get("CLAUDE_MODEL", ""),
    },
    "codex": {
        "bin":     os.environ.get("CODEX_BIN",     "/usr/bin/codex"),
        "model":   os.environ.get("CODEX_MODEL",   ""),
        "sandbox": os.environ.get("CODEX_SANDBOX", "read-only"),
    },
    "gemini_cli": {
        "bin":   os.environ.get("GEMINI_BIN",   "/usr/bin/gemini"),
        "model": os.environ.get("GEMINI_MODEL", ""),
    },
}
```

`MODEL_BACKEND` 환경변수로 어떤 LLM을 쓸지 결정한다. 덕분에 동일한 `poller.py` 코드로 18개 워커가 각자 다른 LLM을 실행한다.

### Claude 백엔드

```python
async def run_claude(instructions: str, task_id: str) -> tuple[int, str]:
    cfg = _BACKENDS["claude"]
    cmd = [cfg["bin"], "--print", "--allowedTools", cfg["tools"]]
    if cfg.get("model"):
        cmd += ["--model", cfg["model"]]
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
```

`--print` 플래그가 핵심이다. Claude Code가 대화 모드가 아닌 비대화형 모드로 실행되어 stdout으로 결과를 반환하게 만든다.

### ZAI 백엔드

ZAI는 Anthropic API 호환 엔드포인트를 제공하기 때문에 별도 백엔드가 없다. 환경변수 두 개로 라우팅을 바꾼다.

```ini
# /etc/agentforge/cc-zai-high-dev-01.env
ANTHROPIC_BASE_URL=<ZAI endpoint>
ANTHROPIC_AUTH_TOKEN=<ZAI API key>
```

systemd `EnvironmentFile=` 지시어로 이 파일을 주입하면, claude 바이너리가 ZAI 엔드포인트로 요청을 보낸다. 코드 변경 없이 환경변수만으로 다른 LLM 공급자를 연결하는 셈이다.

---

## 선언적 관리: fleet.yaml × servers.yaml

18개 워커를 수동으로 관리하는 건 비현실적이다. 두 개의 YAML 파일로 전체 인프라를 선언적으로 정의했다.

### servers.yaml — 서버 인벤토리

```yaml
servers:
  - name: worker-node-1
    role: worker-host
    services: [agentforge-worker, tunnel-arm1]

  - name: broker-host
    role: broker-host
    services: [nats-jetstream, postgres]

  - name: worker-node-2
    role: worker-host
    services: [agentforge-worker, tunnel-arm1]
```

### fleet.yaml — 워커 배치

```yaml
workers:
  - worker_id: cc-go-dev-01
    llm: claude-code
    model: claude-sonnet-4-6
    lang: go
    role: developer
    host: worker-node-1
    enabled: true
    create_pr: true

  - worker_id: codex-py-dev-01
    llm: codex
    model: gpt-5.5
    lang: python
    role: developer
    host: worker-node-1
    enabled: true
    create_pr: false
```

`host` 필드 하나를 바꾸면 워커가 다른 서버로 이동한다. `enabled: false`로 설정하면 배포 스크립트가 해당 워커를 중지한다.

---

## 워커 템플릿 시스템: provision_worker.py

워커를 새로 추가할 때마다 systemd 유닛 파일을 직접 작성하는 건 오류가 생기기 쉽다. Jinja2 템플릿 + 프로비저닝 스크립트로 자동화했다.

### 템플릿 구조

```
templates/
  systemd/
    claude.service.j2    # claude-code, ZAI 공용
    codex.service.j2     # OpenAI Codex
    gemini.service.j2    # Google Gemini CLI
```

`claude.service.j2`의 핵심 부분:

```jinja2
Environment=MODEL_BACKEND=claude
Environment=CLAUDE_BIN={{ claude_bin }}
{% if claude_model %}
Environment=CLAUDE_MODEL={{ claude_model }}
{% endif %}
{% if env_file %}
EnvironmentFile={{ env_file }}
{% endif %}
Environment=WORK_BASE={{ work_base }}
Environment=WORK_DIR={{ work_base }}/repo
Environment="{{ 'ALLOWED_TOOLS=' + allowed_tools }}"
Environment=CREATE_PR={{ 'true' if create_pr else 'false' }}
{% if create_pr and github_remote %}
Environment=GITHUB_REMOTE={{ github_remote }}
{% endif %}
```

ZAI 워커는 `env_file` 블록이 활성화되어 EnvironmentFile이 추가된다. PR 생성 워커는 `github_remote`가 주입된다. 나머지는 기본값을 쓴다.

### provision_worker.py 사용법

```bash
# 미리보기 (실제 배포 없음)
python3 scripts/provision_worker.py --worker new-worker-id --dry-run

# 실제 배포 (NATS creds 발급 포함)
python3 scripts/provision_worker.py --worker new-worker-id --issue-creds

# fleet.yaml 전체 일괄 배포
python3 scripts/provision_worker.py --all
```

내부적으로 수행하는 작업:

1. `fleet.yaml`에서 워커 항목 읽기
2. `servers.yaml`에서 대상 호스트 읽기
3. Jinja2 템플릿 렌더링
4. SSH로 `/etc/systemd/system/{worker_id}-poller.service` 배포
5. 워크 디렉터리 생성
6. `systemctl daemon-reload && enable --now`
7. (선택) `nsc add user`로 NATS NKey 발급 → creds 배포 → `auth.conf` 재생성

---

## 분산 호스트: 두 번째 서버에 워커 추가

모든 워커를 한 서버에서 돌리면 단일 장애점이 된다. 두 번째 호스트에 Claude 워커를 추가했다.

두 번째 호스트에서 NATS 브로커에 연결하는 방법은 autossh 터널이다.

```ini
[Unit]
Description=NATS 브로커 터널
After=network-online.target

[Service]
ExecStart=/usr/bin/autossh -N \
    -L 4222:127.0.0.1:4222 \
    -i /home/ubuntu/.ssh/id_ed25519 \
    broker-host
Restart=always
RestartSec=10
```

이 설정이 활성화된 상태에서 워커는 항상 `nats://127.0.0.1:4222`로 연결한다. 브로커 호스트 주소를 몰라도 된다. 터널만 살아있으면 어느 호스트에서든 동일하게 동작한다.

---

## NATS 자격증명 운영 경험

구현 중 가장 복잡했던 부분은 NATS NKey 관리다.

NATS JetStream의 인증 구조는 계층적이다.

```
Operator (최상위 서명 기관)
  └── Account: SYS    (시스템 계정)
  └── Account: Services  (워커 계정)
        ├── User: cc-dev-01
        ├── User: cc-go-dev-01
        ├── User: codex-py-dev-01
        └── ...
```

각 워커는 독립된 User NKey를 가지고, Services 계정의 권한 범위(`af.>`, `_INBOX.>`, `$JS.>`) 내에서만 publish/subscribe할 수 있다.

신규 워커를 추가할 때 Operator의 signing key가 필요하다. 초기에 이 키의 백업을 만들지 않았다가 분실하는 사고가 있었다. 결과적으로 Operator를 전부 재생성하고 모든 워커의 creds를 일괄 교체했다. 서비스 다운타임은 약 60초.

```bash
# 재생성 절차
nsc add operator AgentForge
nsc add account SYS
nsc add account Services
for worker in cc-dev-01 cc-go-dev-01 ...; do
    nsc add user --account Services --name $worker \
        --allow-pub "af.>,_INBOX.>,$JS.>" \
        --allow-sub "af.>,_INBOX.>,$JS.>"
done
nsc generate config --mem-resolver --sys-account SYS > auth.new.conf
```

---

## 새 워커 추가: 전체 절차

이 시스템이 완성된 이후 새 워커를 추가하는 절차는 단순하다.

**1단계**: `fleet.yaml`에 항목 추가

```yaml
- worker_id: my-new-worker
  llm: claude-code
  model: claude-haiku-4-5
  lang: multi
  role: developer
  host: worker-node-1
  enabled: true
  create_pr: false
```

**2단계**: 미리보기

```bash
python3 scripts/provision_worker.py --worker my-new-worker --dry-run
```

**3단계**: 실제 배포

```bash
python3 scripts/provision_worker.py --worker my-new-worker --issue-creds
```

끝이다. 템플릿 렌더링, SSH 배포, NATS 자격증명 발급, 서비스 등록까지 한 명령으로 처리된다.

---

## 다음 단계

현재 시스템은 워커가 태스크를 독립적으로 처리하는 구조다. 앞으로 만들고 싶은 것:

- **라우팅 정책**: 태스크 특성에 따라 적합한 워커를 자동 선택 (Go 코드 → claude-go-dev, 비용 최우선 → ZAI 경량 티어)
- **결과 비교 대시보드**: fan-out 결과를 나란히 보여주는 UI
- **비용 추적**: 워커별 API 호출 비용 집계

코드는 GitHub에 공개되어 있다.