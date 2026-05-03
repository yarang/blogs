+++

+++

# A Tool to Boost Server Management Efficiency: Introducing the Server Status Checker Skill

Are the number of servers you manage increasing?

Connecting to each server individually via SSH to check its status is a waste of time. If you could grasp the CPU, memory, and disk usage of multiple servers at a glance, your work efficiency would improve significantly.

I also faced that problem. So I created it.

## Problem: Repetitive Tasks in Server Monitoring

If you are a DevOps engineer or system administrator, this is a situation you have likely encountered at least once:

1. Repeated SSH connections for each server
2. Manually running top, htop, df commands
3. Manually recording status in Excel or Notion
4. Modifying management scripts every time servers increase

This process is a waste of time and a repetitive task that can cause mistakes.

## Solution: Server Status Checker Skill

**Server Status Checker** is a skill for Claude Code that checks the status of all servers in parallel based on the SSH config file.

### Key Features

| Feature | Description |
|---------|-------------|
| **SSH config auto-parsing** | Auto-discovery of server list from `~/.ssh/config` file |
| **Real-time status check** | Collecting CPU, Memory, Disk, Uptime, Load information |
| **Parallel connection** | Fast status check via asyncssh (in seconds) |
| **Grouping** | Automatic categorization by GCP, OCI, GitHub, Blog, Local, etc. |
| **Online/Offline status** | Intuitive status display with ✓ / ✗ |

### Usage

```bash
# Check status of all servers
/server-status-checker

# Check only specific servers
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

It parses the `~/.ssh/config` file to automatically extract the following information:

- Host (Hostname)
- HostName (IP address or domain)
- User (Username)
- Port (Port number)
- IdentityFile (SSH key path)

### Asynchronous Parallel Processing

It connects to all servers simultaneously using the Python `asyncssh` library:

```python
async def check_server(host: str):
    # SSH connection and command execution
    result = await asyncssh.connect(...)
    return status
```

Checking 30 servers sequentially takes 5 minutes, but with parallel processing, it completes within 30 seconds.

### Automatic Group Classification

It automatically classifies based on server name patterns:

| Group | Pattern | Example |
|-------|---------|---------|
| **GCP** | `gcp-` prefix | gcp-ajou-ec1, gcp-fcoinfup-ec1 |
| **OCI Ajou** | `oci-ajou-` prefix | oci-ajou-ec1 |
| **OCI Fcoinfup** | `oci-fcoinfup-` prefix | oci-fcoinfup-ec1 |
| **GitHub** | `github-as-` prefix | github-as-actions |
| **Blog** | `blog` | blog |
| **Local** | `mini`, `mac` | mini01, macbook-pro |

### System Metrics Collection

It collects the following information from each server:

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

| Aspect | Improvement Effect |
|--------|-------------------|
| **Time Saving** | 90% reduction in server check time (5 min → 30 sec) |
| **Real-time Monitoring** | Immediate grasp of server status |
| **Centralized Management** | Manage all servers with a single SSH config file |
| **Automation** | Minimize human error by removing repetitive tasks |

## Use Cases

### 1. Daily Server Health Check

Check the status of all servers with a single `/server-status-checker` command every morning.

### 2. Incident Response

Immediately identify offline servers and take action when an incident occurs.

### 3. Capacity Planning

Monitor disk usage trends to plan capacity expansion in advance.

### 4. Performance Monitoring

Track CPU and memory usage to identify bottlenecks.

## Conclusion

Server Status Checker is not just a simple server status checking tool. It is a productivity tool that helps DevOps engineers and system administrators escape repetitive tasks and focus on core work.

It utilizes the standardized configuration file, SSH config, and provides quick results through parallel processing. Now, there is no need to connect to each server one by one; grasp the health status of all servers with a single command.

Increase the efficiency of system management through AI and automation, and let us focus on more important problems.

---

**Related Projects:**
- [domain-checker](https://github.com/yarang/skill-domain-checker) - Domain availability checker

**Tags:** #DevOps #ServerMonitoring #OpenSource #Claude #AI #Productivity #SSH

**English Version:** [English Version](/post/2026-03-09-002-server-status-checker-skill-introduction/)