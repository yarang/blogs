---
title: "Claude Code Discord MCP Plugin - Fixing asdf bun Path Issue"
date: 2026-03-26T00:00:00+09:00
draft: false
tags: ["claude-code", "discord", "mcp", "asdf", "bun", "troubleshooting"]
categories: ["Development"]
---

## Problem

When installing the `discord` plugin for Discord channel integration in Claude Code CLI, I encountered the following error:

```
> discord Plugin · claude-plugins-official · √ enabled
    └ discord MCP · × failed
```

The plugin was enabled, but the MCP server was in a failed state.

## Root Cause

This issue occurs when using **bun installed via asdf**. Claude Code CLI looks for the `bun` command to run the MCP server, but asdf uses shell wrappers, so the actual binary cannot be found in the system-wide path.

## Solution

I resolved this by entering the **absolute path** to the bun installed via asdf.

### Finding the Absolute Path of asdf-installed bun

```bash
which bun
```

Or:

```bash
asdf where bun
```

Example output:
```
/Users/yarang/.asdf/installs/bun/1.x.x/bin/bun
```

### Applying the Configuration

Specify this absolute path as the execution path in the Discord MCP configuration, and the problem will be resolved.

## Summary

| Situation | Solution |
|-----------|----------|
| System-wide installed bun | Use `bun` command |
| asdf-installed bun | Enter **absolute path** directly |

When using asdf, you must specify the actual binary path, not the shell wrapper, for the MCP server to run properly.

## References

- [Claude Code Discord Plugin](https://github.com/anthropics/discord-plugin)
- [asdf Version Manager](https://asdf-vm.com/)
