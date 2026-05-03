+++
title = "MCP 서버 시작하기: Claude Code와 통합하는 첫 번째 도구 만들기"
date = 2026-05-03T10:47:00+09:00
draft = false
tags = ["MCP", "Claude", "AI", "Tool-Development"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# MCP 서버 시작하기: Claude Code와 통합하는 첫 번째 도구 만들기

MCP(Model Context Protocol)는 Claude Code 및 다른 AI 도구와 통합할 수 있는 강력한 프로토콜입니다. 이 가이드에서는 첫 번째 MCP 서버를 만드는 과정을 단계별로 안내합니다.

## MCP란 무엇인가?

MCP는 AI 에이전트가 외부 도구와 리소스에 접근할 수 있게 하는 표준 프로토콜입니다. 주요 특징:

- **표준화된 인터페이스**: 다양한 도구를 통일된 방식으로 통합
- **리소스 공유**: 파일, 데이터베이스 등의 리소스를 안전하게 접근
- **확장성**: 새로운 도구를 쉽게 추가 가능

## 기본 MCP 서버 구조

```typescript
// mcp-server-template.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server(
  {
    name: 'my-mcp-server',
    version: '1.0.0'
  },
  {
    capabilities: {
      tools: {},
      resources: {}
    }
  }
);

// 도구 등록 예시
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'my_tool',
      description: '내 도구 설명',
      inputSchema: {
        type: 'object',
        properties: {
          param1: {
            type: 'string',
            description: '파라미터 설명'
          }
        },
        required: ['param1']
      }
    }
  ]
}));

// 서버 시작
const transport = new StdioServerTransport();
await server.connect(transport);
```

## 실전 예제: 간단한 계산기 MCP 서버

```typescript
// calculator-mcp-server.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

const server = new Server(
  { name: 'calculator-server', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'calculate',
      description: '기본 수학 연산 수행',
      inputSchema: {
        type: 'object',
        properties: {
          expression: {
            type: 'string',
            description: '계산할 수식 (예: "2 + 2")'
          }
        },
        required: ['expression']
      }
    }
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'calculate') {
    const expression = request.params.arguments?.expression as string;
    try {
      // 안전한 계산을 위해 Function 대신 eval 사용
      const result = Function(`"use strict"; return (${expression})`)();
      return {
        content: [{
          type: 'text',
          text: `결과: ${result}`
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: 'text',
          text: `계산 오류: ${error}`
        }],
        isError: true
      };
    }
  }
  return { content: [] };
});
```

## Claude Code 설정

MCP 서버를 Claude Code에 등록하려면 `~/.config/claude/settings.json`을 수정합니다:

```json
{
  "mcpServers": {
    "calculator": {
      "command": "node",
      "args": ["/path/to/calculator-mcp-server.js"]
    }
  }
}
```

## 리소스 제공하기

```typescript
// 리소스 리스트 제공
server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [
    {
      uri: 'calc://history',
      name: '계산 기록',
      description: '최근 계산 이력',
      mimeType: 'application/json'
    }
  ]
}));

// 리소스 내용 제공
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  if (request.params.uri === 'calc://history') {
    return {
      contents: [{
        uri: request.params.uri,
        mimeType: 'application/json',
        text: JSON.stringify({ history: [] })
      }]
    };
  }
  throw new Error('리소스를 찾을 수 없습니다');
});
```

## 보안 고려사항

1. **입력 검증**: 모든 사용자 입력을 검증하고 제한
2. **권한 제한**: 최소 권한 원칙 적용
3. **에러 처리**: 민감 정보가 에러 메시지에 노출되지 않도록 주의
4. **속도 제한**: 과도한 요청을 방지하는 레이트 리밋 구현

## 배포 및 테스트

```bash
# 서버 빌드
npm run build

# 로컬 테스트
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/server.js

# Claude Code에 통합 후 테스트
# 설정 파일 reload 후 Claude Code에서 도구 사용
```

## 다음 단계

- 더 복잡한 도구와 리소스 추가
- 프롬프트 템플릿 구현
- 에러 핸들링 개선
- 로깅 및 모니터링 추가

MCP 서버 개발은 Claude Code의 기능을 확장하고 자동화를 강화하는 훌륭한 방법입니다. 작은 프로젝트부터 시작하여 점진적으로 기능을 확장해보세요.

## 참고 자료

- [MCP 공식 문서](https://modelcontextprotocol.io)
- [Claude Code 문서](https://claude.ai/code)
- [MCP SDK GitHub](https://github.com/modelcontextprotocol/typescript-sdk)