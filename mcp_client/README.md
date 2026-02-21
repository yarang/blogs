# Blog MCP Client

Claude Code에서 블로그를 관리하기 위한 MCP 클라이언트입니다.

## 설치

### 자동 설치

```bash
cd mcp_client
./install.sh
```

설치 스크립트가 다음을 수행합니다:
1. uv 설치 (없는 경우)
2. 의존성 설치 (mcp, httpx)
3. API Key 입력
4. .mcp.json 설정 업데이트

### 수동 설치

```bash
# 1. uv로 의존성 설치
cd mcp_client
uv venv
uv pip install mcp httpx

# 2. .mcp.json 설정
# 프로젝트 루트의 .mcp.json을 다음과 같이 수정:
{
  "mcpServers": {
    "blog": {
      "command": "/절대경로/mcp_client/.venv/bin/python",
      "args": ["/절대경로/mcp_client/mcp_blog_client.py"],
      "env": {
        "BLOG_API_URL": "http://130.162.133.47",
        "BLOG_API_KEY": "your_api_key"
      }
    }
  }
}
```

## API Key 발급

블로그 관리자에게 API Key를 요청하세요.

## 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `blog_create` | 새 포스트 작성 (제목, 내용 필수) |
| `blog_list` | 포스트 목록 조회 |
| `blog_get` | 특정 포스트 조회 (파일명 필요) |
| `blog_update` | 포스트 수정 (파일명, 내용 필요) |
| `blog_delete` | 포스트 삭제 (파일명 필요) |
| `blog_search` | 포스트 검색 (검색어 필요) |
| `blog_status` | 서버 상태 확인 |

## 사용 예시

Claude Code에서 다음과 같이 사용할 수 있습니다:

```
블로그에 새 포스트 작성해줘.
제목: "Python으로 MCP 서버 만들기"
내용: MCP 프로토콜 소개와 예제 코드를 포함해.
태그: Python, MCP, Tutorial
```

```
블로그 포스트 목록 보여줘
```

```
"Python" 키워드로 블로그 검색해줘
```

## 파일 구조

```
mcp_client/
├── mcp_blog_client.py   # MCP 클라이언트
├── pyproject.toml       # 패키지 설정
├── install.sh           # 설치 스크립트
├── .venv/               # 가상환경 (설치 후 생성)
└── README.md            # 이 파일
```
