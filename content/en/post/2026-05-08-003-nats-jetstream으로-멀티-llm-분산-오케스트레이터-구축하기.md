+++
title = "Building a Multi-LLM Distributed Orchestrator with NATS JetStream"
date = "2026-05-08T21:57:11+09:00"
draft = "false"
tags = ["agentforge", "nats", "jetstream", "architecture", "llm", "python", "systemd"]
categories = ["AI", "Architecture"]
ShowToc = "true"
TocOpen = "true"
+++

Part 1 discussed the model-specific limitations discovered while running four AIs—Claude, ZAI, Codex, and Gemini—concurrently on the same tasks. This part is about "how we made it possible"—the system design and implementation story.

---

## System Overview

AgentForge consists of three components.

```
[Task Publisher]
       │  NATS JetStream publish
       ▼
[NATS Broker] ─── af.worker.{id}.inbox
       │  JetStream consume (independent streams per worker)
       ▼
[Worker Pollers] × N  (poller.py × 18 instances)
       │  LLM CLI Execution (claude / codex / gemini)
       ▼
[Result Return]   af.task.{task_id}.completed
```

When a publisher posts a task to NATS, each worker, which is independently subscribed, receives the message on its inbox and executes the LLM CLI. The result is then published back to a completion topic.

---

## Why NATS JetStream?

We considered several message broker options: Redis Streams, Kafka, RabbitMQ, and NATS JetStream.

**Reasons for choosing NATS JetStream:**

1.  **Single Binary** — Operates with a single `nats-server` without requiring separate runtimes. It has no dependencies like Kafka's ZooKeeper or RabbitMQ's Erlang/OTP.

2.  **Built-in Persistence** — JetStream is a streaming layer on top of NATS, storing messages to the filesystem. This ensures that unprocessed tasks are not lost even if a worker restarts.

3.  **NKey-based Authentication** — We can issue independent Ed25519 key pairs for each worker. If one worker is compromised, the credentials of other workers remain valid.

4.  **Lightweight** — Memory usage is around 30MB on a single server. Even with 18 workers connected, the broker load is minimal.

---

## The Core: Backend Adapter in `poller.py`

The heart of the worker is `poller.py`. This single file handles NATS subscriptions, LLM CLI execution, and result returns.

Since LLMs have different execution methods, we separated them into a backend adapter dictionary.

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

The `MODEL_BACKEND` environment variable determines which LLM to use. This allows the same `poller.py` code to run different LLMs across 18 workers.

### Claude Backend

```python
async def run_claude(instructions: str, task_id: str) -> tuple[int, str]:
    cfg = _BACKENDS["claude"]
    cmd = [cfg["bin"], "--print", "--allowedTools", cfg["tools"]]
    if cfg.get("model"):
        cmd += ["--model", cfg["model"]]
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
```

The `--print` flag is key. It runs Claude Code in non-interactive mode instead of conversational mode, ensuring the results are returned via stdout.

### ZAI Backend

ZAI offers an Anthropic API-compatible endpoint, so it doesn't require a separate backend. Routing is handled by two environment variables.

```ini
# /etc/agentforge/cc-zai-high-dev-01.env
ANTHROPIC_BASE_URL=<ZAI endpoint>
ANTHROPIC_AUTH_TOKEN=<ZAI API key>
```

By injecting this file using systemd's `EnvironmentFile=` directive, the `claude` binary sends requests to the ZAI endpoint. This allows us to connect to a different LLM provider simply by changing environment variables, without altering the code.

---

## Declarative Management: `fleet.yaml` × `servers.yaml`

Manually managing 18 workers is impractical. We declaratively defined the entire infrastructure using two YAML files.

### `servers.yaml` — Server Inventory

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

### `fleet.yaml` — Worker Placement

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

Changing just the `host` field moves a worker to a different server. Setting `enabled: false` stops the deployment script from starting that worker.

---

## Worker Templating System: `provision_worker.py`

Manually writing systemd unit files for each new worker is prone to errors. We automated this using Jinja2 templates and a provisioning script.

### Template Structure

```
templates/
  systemd/
    claude.service.j2    # For claude-code and ZAI alike
    codex.service.j2     # OpenAI Codex
    gemini.service.j2    # Google Gemini CLI
```

The core part of `claude.service.j2`:

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

For ZAI workers, the `env_file` block is activated, adding the `EnvironmentFile`. For PR creation workers, `github_remote` is injected. Other settings use defaults.

### `provision_worker.py` Usage

```bash
# Preview (no actual deployment)
python3 scripts/provision_worker.py --worker new-worker-id --dry-run

# Actual deployment (including NATS creds issuance)
python3 scripts/provision_worker.py --worker new-worker-id --issue-creds

# Bulk deployment for the entire fleet.yaml
python3 scripts/provision_worker.py --all
```

Internal operations:

1. Reads worker entries from `fleet.yaml`.
2. Reads target hosts from `servers.yaml`.
3. Renders Jinja2 templates.
4. Deploys `/etc/systemd/system/{worker_id}-poller.service` via SSH.
5. Creates the working directory.
6. Executes `systemctl daemon-reload && enable --now`.
7. (Optional) Issues NATS NKey with `nsc add user` → deploys creds → regenerates `auth.conf`.

---

## Distributed Hosting: Adding Workers to a Second Server

Running all workers on a single server creates a single point of failure. We added Claude workers to a second host.

The method for workers on the second host to connect to the NATS broker is via an autossh tunnel.

```ini
[Unit]
Description=NATS Broker Tunnel
After=network-online.target

[Service]
ExecStart=/usr/bin/autossh -N \
    -L 4222:127.0.0.1:4222 \
    -i /home/ubuntu/.ssh/id_ed25519 \
    broker-host
Restart=always
RestartSec=10
```

With this configuration active, workers always connect to `nats://127.0.0.1:4222`. They don't need to know the broker host's address. As long as the tunnel is alive, it works the same way from any host.

---

## NATS Credential Operations Experience

NATS NKey management was the most complex part of the implementation.

NATS JetStream's authentication structure is hierarchical.

```
Operator (Root Signing Authority)
  └── Account: SYS    (System Account)
  └── Account: Services  (Worker Account)
        ├── User: cc-dev-01
        ├── User: cc-go-dev-01
        ├── User: codex-py-dev-01
        └── ...
```

Each worker has an independent User NKey and can publish/subscribe within the permissions scope (`af.>`, `_INBOX.>`, `$JS.>`) of the Services account.

Adding a new worker requires the Operator's signing key. We initially made the mistake of not backing up this key, leading to its loss. Consequently, we had to regenerate the entire Operator and replace all worker credentials en masse. The service downtime was approximately 60 seconds.

```bash
# Regeneration procedure
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

## Adding a New Worker: The Full Procedure

Since the completion of this system, adding a new worker is straightforward.

**Step 1**: Add an entry to `fleet.yaml`

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

**Step 2**: Preview

```bash
python3 scripts/provision_worker.py --worker my-new-worker --dry-run
```

**Step 3**: Actual Deployment

```bash
python3 scripts/provision_worker.py --worker my-new-worker --issue-creds
```

That's it. Template rendering, SSH deployment, NATS credential issuance, and service registration are all handled by a single command.

---

## Next Steps

The current system is structured such that workers process tasks independently. Future plans include:

-   **Routing Policies**: Automatically selecting the appropriate worker based on task characteristics (e.g., Go code → `claude-go-dev`, cost-first → ZAI lightweight tier).
-   **Results Comparison Dashboard**: A UI to display fan-out results side-by-side.
-   **Cost Tracking**: Aggregating API call costs per worker.

The code is publicly available on GitHub.
```