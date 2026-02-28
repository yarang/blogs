+++
title = "MCP를 활용한 블로그 자동화 시스템 구축"
slug = "2026-02-21-004-mcp-blog-automation"
date = 2026-02-21T21:30:00+09:00
draft = false
tags = ["mcp", "automation", "claude", "blog"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

## 들어가며

Model Context Protocol(MCP)을 활용하여 Claude가 직접 블로그 포스트를 관리할 수 있는 시스템을 구축했습니다. 이 글에서는 구현 내용과 활용 방법을 소개합니다.

## MCP란?

MCP(Model Context Protocol)는 Anthropic에서 개발한 프로토콜로, Claude와 외부 도구/데이터 소스 간의 표준화된 통신을 가능하게 합니다.

```
┌─────────────┐      MCP      ┌─────────────┐
│   Claude    │ ◄──────────► │  MCP Server │
└─────────────┘               └─────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │   Blog      │
                              │   Files     │
                              └─────────────┘
```

## 아키텍처

### 시스템 구성

```
blogs/
├── .claude/
│   ├── mcp_server.py      # MCP 서버 구현
│   ├── requirements.txt   # Python 의존성
│   ├── README.md          # 사용 문서
│   └── claude_desktop_config.json
├── content/
│   └── posts/             # 블로그 포스트
└── static/
    └── images/            # 이미지 파일
```

### MCP 서버 구조

```python
class BlogManager:
    """블로그 관리 클래스"""

    def create_post(self, title, content, tags, categories):
        """새 포스트 생성"""

    def list_posts(self, limit, offset):
        """포스트 목록 조회"""

    def get_post(self, filename):
        """특정 포스트 조회"""

    def update_post(self, filename, **kwargs):
        """포스트 수정"""

    def delete_post(self, filename):
        """포스트 삭제"""

    def search_posts(self, query):
        """포스트 검색"""
```

## 제공 도구

### 1. blog_create_post

새 블로그 포스트를 생성합니다.

```json
{
  "title": "포스트 제목",
  "content": "Markdown 내용...",
  "tags": ["tag1", "tag2"],
  "categories": ["Development"],
  "draft": false
}
```

### 2. blog_list_posts

포스트 목록을 조회합니다.

```json
{
  "limit": 20,
  "offset": 0
}
```

### 3. blog_get_post

특정 포스트의 상세 내용을 조회합니다.

```json
{
  "filename": "2026-02-21-004-example.md"
}
```

### 4. blog_update_post

기존 포스트를 수정합니다.

```json
{
  "filename": "2026-02-21-004-example.md",
  "content": "수정된 내용...",
  "draft": false
}
```

### 5. blog_search_posts

내용으로 포스트를 검색합니다.

```json
{
  "query": "Docker"
}
```

## 자동화된 파일 명명

포스트 파일명은 다음 규칙으로 자동 생성됩니다:

```
YYYY-MM-DD-NNN-slug.md
```

- `YYYY-MM-DD`: 작성일
- `NNN`: 일련번호 (001, 002, ...)
- `slug`: 제목에서 생성된 URL 친화적 문자열

예: `2026-02-21-004-mcp-blog-automation.md`

## 활용 시나리오

### 1. 빠른 포스트 작성

```
사용자: "Python 리스트 컴프리헨션에 대한 짧은 팁 포스트를 작성해줘"

Claude: blog_create_post 도구를 사용하여 포스트 생성
→ 파일 생성: 2026-02-21-005-python-list-comprehension.md
```

### 2. 기존 포스트 검색 및 수정

```
사용자: "Docker 관련 포스트를 찾아서 최신 버전 정보로 업데이트해줘"

Claude: blog_search_posts("Docker") → 결과 확인 → blog_update_post
```

### 3. 시리즈 포스트 관리

```
사용자: "지금까지 작성한 에이전트 관련 포스트 목록을 보여줘"

Claude: blog_search_posts("agent") → 관련 포스트 나열
```

## 구현상의 고려사항

### Front Matter 파싱

Hugo의 TOML 형식 front matter를 파싱합니다:

```python
def _parse_front_matter(self, content: str) -> Dict[str, Any]:
    """TOML front matter 파싱"""
    if not content.startswith("+++"):
        return {}

    parts = content.split("+++", 2)
    # ... 파싱 로직
```

### 동시성 처리

파일명 충돌을 방지하기 위해 기존 파일 수를 확인합니다:

```python
existing_count = len(list(self.content_dir.glob("*.md")))
filename = self._generate_filename(title, existing_count + 1)
```

## 확장 가능성

### 1. 이미지 처리

```
blog_upload_image: 이미지 업로드 및 최적화
```

### 2. 자동 태그 추천

```
blog_suggest_tags: 내용 분석 기반 태그 추천
```

### 3. SEO 최적화

```
blog_optimize_seo: 메타 설명, 키워드 최적화
```

### 4. 배포 자동화

```
blog_publish: git commit, push, 배포 트리거
```

## 결론

MCP를 활용한 블로그 자동화 시스템을 통해:

1. **생산성 향상**: 자연어로 포스트 작성 가능
2. **일관성 유지**: 파일 명명 규칙 자동 적용
3. **접근성 개선**: Claude를 통한 직관적인 블로그 관리

이 시스템은 지속적으로 확장 가능하며, 이미지 처리, SEO 최적화, 자동 배포 등의 기능을 추가할 수 있습니다.

## 참고 자료

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Hugo Documentation](https://gohugo.io/documentation/)
