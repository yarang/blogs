---
title: "Claude Code Discord MCP Plugin - asdf bun 경로 문제 해결"
date: 2026-03-26T00:00:00+09:00
draft: false
tags: ["claude-code", "discord", "mcp", "asdf", "bun", "troubleshooting"]
categories: ["Development"]
---

## 문제 상황

Claude Code CLI에서 Discord 채널 연결을 위해 `discord` 플러그인을 설치했는데 다음과 같은 에러가 발생했습니다.

```
> discord Plugin · claude-plugins-official · √ enabled
    └ discord MCP · × failed
```

플러그인은 활성화되었지만, MCP 서버는 실패 상태였습니다.

## 원인

이 문제는 **asdf로 설치한 bun**을 사용할 때 발생합니다. Claude Code CLI는 MCP 서버 실행을 위해 `bun` 명령어를 찾지만, asdf는 셸 래퍼를 사용하므로 시스템 전역 경로에서 실제 바이너리를 찾지 못합니다.

## 해결 방법

asdf로 설치한 bun의 **절대 경로**를 직접 입력하여 해결했습니다.

### asdf로 설치한 bun 절대 경로 찾기

```bash
which bun
```

또는:

```bash
asdf where bun
```

출력 예시:
```
/Users/yarang/.asdf/installs/bun/1.x.x/bin/bun
```

### 설정 적용

이 절대 경로를 Discord MCP 설정의 실행 경로로 지정하면 문제가 해결됩니다.

## 핵심 정리

| 상황 | 해결 방법 |
|------|----------|
| 시스템 전역 설치된 bun | `bun` 명령어 사용 |
| asdf로 설치한 bun | **절대 경로** 직접 입력 |

asdf를 사용하는 경우, 셸 래퍼가 아닌 실제 바이너리 경로를 지정해야 MCP 서버가 정상적으로 실행됩니다.

## 참고 자료

- [Claude Code Discord Plugin](https://github.com/anthropics/discord-plugin)
- [asdf 버전 관리자](https://asdf-vm.com/)
