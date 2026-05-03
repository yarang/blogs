+++
title = ""
date = "2026-05-03T10:47:00+09:00"
draft = "false"
tags = ["MCP", "Claude", "AI", "Tool-Development"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

```

# Getting Started with MCP Servers: Creating Your First Tool Integrated with Claude Code

MCP (Model Context Protocol) is a powerful protocol that can be integrated with Claude Code and other AI tools. This guide will walk you through the process of creating your first MCP server step-by-step.

## What is MCP?

MCP is a standard protocol that allows AI agents to access external tools and resources. Key features:

- **Standardized Interface**: Integrate various tools in a unified manner
- **Resource Sharing**: Safely access resources such as files and databases
- **Extensibility**: Easily add new tools

## Basic MCP Server Structure

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

// Example of tool registration
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'my_tool',
      description: 'Description of my tool',
      inputSchema: {
        type: 'object',
        properties: {
          param1: {
            type: 'string',
            description: 'Parameter description'
          }
        },
        required: ['param1']
      }
    }
  ]
}));

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
```

## Practical Example: Simple Calculator MCP Server

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
      description: 'Perform basic mathematical operations',
      inputSchema: {
        type: 'object',
        properties: {
          expression: {
            type: 'string',
            description: 'Expression to calculate (e.g., "2 + 2")'
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
      // Use Function instead of eval for safer calculation
      const result = Function(`"use strict"; return (${expression})`)();
      return {
        content: [{
          type: 'text',
          text: `Result: ${result}`
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: 'text',
          text: `Calculation error: ${error}`
        }],
        isError: true
      };
    }
  }
  return { content: [] };
});
```

## Claude Code Configuration

To register an MCP server with Claude Code, modify `~/.config/claude/settings.json`:

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

## Providing Resources

```typescript
// Provide resource list
server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [
    {
      uri: 'calc://history',
      name: 'Calculation History',
      description: 'Recent calculation history',
      mimeType: 'application/json'
    }
  ]
}));

// Provide resource content
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
  throw new Error('Resource not found');
});
```

## Security Considerations

1. **Input Validation**: Validate and restrict all user input
2. **Access Control**: Apply the principle of least privilege
3. **Error Handling**: Ensure sensitive information is not exposed in error messages
4. **Rate Limiting**: Implement rate limiting to prevent excessive requests

## Deployment and Testing

```bash
# Build server
npm run build

# Local test
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/server.js

# Test after integrating with Claude Code
# Use tool in Claude Code after reloading config file
```

## Next Steps

- Add more complex tools and resources
- Implement prompt templates
- Improve error handling
- Add logging and monitoring

Developing MCP servers is a great way to extend Claude Code's functionality and enhance automation. Start with small projects and gradually expand your features.

## References

- [MCP Official Documentation](https://modelcontextprotocol.io)
- [Claude Code Documentation](https://claude.ai/code)
- [MCP SDK GitHub](https://github.com/modelcontextprotocol/typescript-sdk)
```