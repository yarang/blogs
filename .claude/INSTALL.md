# Claude Code에 MCP 서버 설치 가이드

## 1. 사전 요구사항

- Python 3.10+
- Git
- Claude Desktop 앱

## 2. 설치 단계

### Step 1: 저장소 클론

```bash
cd ~/workspaces
git clone https://github.com/yarang/blogs.git
cd blogs
```

### Step 2: MCP 의존성 설치

```bash
cd .claude
pip install -r requirements.txt
```

### Step 3: Claude Desktop 설정

**macOS:**
```bash
# 설정 파일 열기
open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

### Step 4: 설정 내용 추가

```json
{
  "mcpServers": {
    "blog-manager": {
      "command": "python3",
      "args": ["/Users/yarang/workspaces/agent_dev/blogs/.claude/mcp_server.py"],
      "env": {
        "BLOG_ROOT": "/Users/yarang/workspaces/agent_dev/blogs"
      }
    }
  }
}
```

> 경로를 본인 환경에 맞게 수정하세요.

### Step 5: Claude Desktop 재시작

Claude Desktop 앱을 완전히 종료하고 다시 실행합니다.

## 3. 확인

Claude Desktop에서 다음과 같이 물어보세요:

```
"사용 가능한 MCP 도구가 있어?"
```

또는 바로 사용:

```
"블로그 포스트 목록 보여줘"
```

## 4. 사용 예시

### 포스트 작성

```
"Python 가상환경 설정법에 대한 블로그 포스트 작성해줘"
```

### 포스트 검색

```
"Docker 관련 포스트 검색해줘"
```

### Git 상태 확인

```
"블로그 Git 상태 확인해줘"
```

## 5. 문제 해결

### MCP 서버가 로드되지 않을 때

```bash
# MCP 서버 직접 실행 테스트
cd /Users/yarang/workspaces/agent_dev/blogs/.claude
python3 mcp_server.py

# 의존성 확인
pip list | grep mcp
```

### Git 권한 문제

```bash
# Git credential 설정
git config --global credential.helper store

# 또는 SSH 키 사용
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### 경로 문제

설정 파일의 경로가 절대 경로인지 확인:
- ❌ `./.claude/mcp_server.py`
- ✅ `/Users/yarang/workspaces/agent_dev/blogs/.claude/mcp_server.py`

## 6. 여러 MCP 서버 사용

```json
{
  "mcpServers": {
    "blog-manager": {
      "command": "python3",
      "args": ["/path/to/blogs/.claude/mcp_server.py"],
      "env": {"BLOG_ROOT": "/path/to/blogs"}
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

## 7. 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `BLOG_ROOT` | 블로그 저장소 경로 | `..` (상위 디렉토리) |

## 8. 업데이트

```bash
cd /path/to/blogs
git pull
cd .claude
pip install -r requirements.txt --upgrade

# Claude Desktop 재시작
```
