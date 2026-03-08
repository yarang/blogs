---
title: "Boosting Server Management Efficiency: Introducing Server Status Checker Skill"
date: 2026-03-09T00:30:00+09:00
draft: false
tags: ["DevOps", "ServerMonitoring", "OpenSource", "Claude", "AI", "Productivity", "SSH"]
categories: ["DevTools"]
---

# Boosting Server Management Efficiency: Introducing Server Status Checker Skill

Are you managing an increasing number of servers?

Individually connecting via SSH to check the status of each server is a waste of time. If you could grasp the CPU, memory, and disk usage of all servers at a glance, your work efficiency would improve significantly.

I faced this problem too, so I built a solution.

## The Problem: Repetitive Server Monitoring Tasks

If you're a DevOps engineer or system administrator, you've likely faced this situation:

1. Repeated SSH connections to each server
2. Manually running commands like `top`, `htop`, `df`
3. Manually recording status in Excel or Notion
4. Modifying management scripts as servers increase

This process wastes time and is repetitive work that can lead to mistakes.

## The Solution: Server Status Checker Skill

**Server Status Checker** is a skill for Claude Code that checks the status of all servers in parallel based on your SSH config file.

### Key Features

| Feature | Description |
|---------|-------------|
| **Automatic SSH Config Parsing** | Automatically discovers server list from `~/.ssh/config` |
| **Real-time Status Check** | Collects CPU, Memory, Disk, Uptime, Load information |
| **Parallel Connections** | Fast status checking with asyncssh (in seconds) |
| **Group Classification** | Automatically categorizes by GCP, OCI, GitHub, Blog, Local, etc. |
| **Online/Offline Status** | Intuitive status display with ✓ / ✗ |

### Usage

```bash
# Check all server status
/server-status-checker

# Check specific server only
/server-status-checker --server mini01

# Output in JSON format
/server-status-checker --json

# Verbose error messages
/server-status-checker --verbose
```

### Output Example

```
=== Server Status Report ===

[GCP Servers]
✗ gcp-ajou-ec1 - Offline (Authentication failed)
✗ gcp-fcoinfup-ec1 - Offline (Authentication failed)

[OCI Ajou]
✓ oci-ajou-ec1 - Online
  CPU: 15.2% | Memory: 62.3% | Disk: 45.8%
  Uptime: 15 days | Load: 1.23 1.45 1.38
  OS: Ubuntu 22.04 LTS

[Local Servers]
✓ mini01 - Online
  CPU: 6.7% | Memory: 45.2% | Disk: 5.0%
  Uptime: 2 days | Load: 2.17 2.11 1.94
  OS: macOS 26.3.1
```

## Technical Details

### SSH Config Parsing

Parses `~/.ssh/config` file to automatically extract:

- Host (hostname)
- HostName (IP address or domain)
- User (username)
- Port (port number)
- IdentityFile (SSH key path)

### Asynchronous Parallel Processing

Uses Python's `asyncssh` library to connect to all servers simultaneously:

```python
async def check_server(host: str):
    # SSH connection and command execution
    result = await asyncssh.connect(...)
    return status
```

Checking 30 servers sequentially takes 5 minutes, but parallel processing completes in under 30 seconds.

### Automatic Group Classification

Automatically classifies based on server name patterns:

| Group | Pattern | Examples |
|-------|---------|----------|
| **GCP** | `gcp-` prefix | gcp-ajou-ec1, gcp-fcoinfup-ec1 |
| **OCI Ajou** | `oci-ajou-` prefix | oci-ajou-ec1 |
| **OCI Fcoinfup** | `oci-fcoinfup-` prefix | oci-fcoinfup-ec1 |
| **GitHub** | `github-as-` prefix | github-as-actions |
| **Blog** | `blog` | blog |
| **Local** | `mini`, `mac` | mini01, macbook-pro |

### System Metrics Collection

Collects the following information from each server:

**Linux:**
- CPU: `/proc/stat` or `psutil.cpu_percent()`
- Memory: `/proc/meminfo` or `psutil.virtual_memory()`
- Disk: `psutil.disk_usage()`
- Uptime: `/proc/uptime` or `psutil.boot_time()`
- Load: `/proc/loadavg` or `os.getloadavg()`

**macOS:**
- CPU: `psutil.cpu_percent()`
- Memory: `psutil.virtual_memory()`
- Disk: `psutil.disk_usage()`
- Uptime: `psutil.boot_time()`
- Load: `os.getloadavg()`

## GitHub Release

This skill is released as open source.

🔗 **GitHub:** https://github.com/yarang/skill-server-status-checker

### Installation

```bash
git clone https://github.com/yarang/skill-server-status-checker.git
cp -r skill-server-status-checker ~/.claude/skills/server-status-checker
```

## Business Value

| Aspect | Improvement |
|--------|-------------|
| **Time Savings** | 90% reduction in server check time (5 min → 30 sec) |
| **Real-time Monitoring** | Immediate server status awareness |
| **Centralized Management** | Manage all servers with single SSH config file |
| **Automation** | Minimize human errors by eliminating repetitive tasks |

## Use Cases

### 1. Daily Server Health Check

Every morning, check all server status with a single `/server-status-checker` command.

### 2. Incident Response

When an incident occurs, immediately identify offline servers and take action.

### 3. Capacity Planning

Monitor disk usage trends to plan capacity expansion in advance.

### 4. Performance Monitoring

Track CPU and memory usage to identify bottlenecks.

## Conclusion

Server Status Checker is more than a simple server status checking tool. It's a productivity tool that helps DevOps engineers and system administrators focus on core tasks by eliminating repetitive work.

By leveraging the standardized SSH config file and providing fast results through parallel processing, you no longer need to connect to each server individually. Check the health status of all servers with a single command.

Through AI and automation, let's improve system management efficiency and focus on more important problems.

---

**Related Projects:**
- [domain-checker](https://github.com/yarang/skill-domain-checker) - Domain availability checker tool

**Tags:** #DevOps #ServerMonitoring #OpenSource #Claude #AI #Productivity #SSH

**Translation:** [한국어 버전](/ko/post/2026-03-09-002-서버-관리의-효율을-높이는-도구-server-status-checker-skill-소개/)
