+++
title = "Show HN: Semble – Token-Efficient Code Search Engine Implementation for Agents"
date = "2026-05-18T09:00:38+09:00"
draft = "false"
tags = ["Rust", "ZeroClaw", "CodeSearch", "MCP", "LLM", "Agent"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

Recently, while developing agent systems utilizing LLMs (Large Language Models), one of the biggest bottlenecks has been 'code search'. Simply searching source code with a `grep` command and dumping it into the LLM's context led to an explosive increase in Input Tokens and slow search speeds, hindering the real-time responsiveness required by agents.

The 'Show HN: Semble' project, discussed on Hacker News, presents a fascinating approach to solving this problem. It claims to search code using **98% fewer tokens** compared to general grep tools. In this post, we will explore Semble's core ideas and how to maximize performance by integrating them into our high-performance Rust agent runtime, **ZeroClaw**, and the **MCP (Model Context Protocol)** server.

### The Problem with Existing Search Methods: The Mismatch Between grep and LLMs

When searching code in existing tools like `blog-api-server` or various MCP tools, we primarily used `grep` libraries based on regular expressions. However, this method has a critical drawback when used with LLM agents.

1.  **Token Waste**: `grep` returns the entire line containing the search term. If a long line or unnecessary comments are included, the LLM has to process more noise than actual code.
2.  **Lack of Semantic Understanding**: As it's simple string matching, it doesn't understand nuances like 'camel case' or 'snake case'. For example, searching for `getUser` might miss `get_user`.
3.  **Increased Costs**: LLM API call costs are proportional to the number of input tokens. Including unnecessary code in the context increases costs accordingly.

### Semble's Approach: Separating Structure and Meaning

The secret to Semble's ability to reduce token usage by 98% is that it **pre-processes code into structured AST (Abstract Syntax Tree) or semantic tokens** and then reassembles them at search time. The core idea is **'treating code as data, not strings'**.

We've extended this concept to design a `CodeIndexer` module within the ZeroClaw architecture.

### ZeroClaw Integration: Implementing a High-Performance Indexer

Since ZeroClaw is Rust-based, it guarantees memory safety and speed. Here, we will implement an indexer inspired by Semble.

#### 1. Defining Data Structures

First, let's define the structure to store code. Instead of storing the entire content of a file, we'll only store symbols and metadata.

```rust
use std::collections::HashMap;
use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CodeSymbol {
    pub id: String,
    pub name: String,
    pub kind: SymbolKind, // Function, Struct, Variable, etc.
    pub file_path: String,
    pub start_line: usize,
    pub end_line: usize,
    pub signature: String, // Function signature or type definition
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum SymbolKind {
    Function,
    Struct,
    Enum,
    Variable,
    Module,
}

// In-memory index (for actual production, using a DB or Vector Store is recommended)
pub struct CodeIndex {
    symbols: Vec<CodeSymbol>,
    // Map for fast lookups
    name_map: HashMap<String, Vec<usize>>,
}
```

#### 2. Indexing Logic (Parsing)

While Semble actually uses a much more complex parser, here we will simulate line-by-line parsing with simple logic to implement a token-saving approach. It removes comments and whitespace and captures only essential definitions.

```rust
impl CodeIndex {
    pub fn new() -> Self {
        Self {
            symbols: Vec::new(),
            name_map: HashMap::new(),
        }
    }

    // Simple parsing logic (in reality, use tree-sitter etc.)
    pub fn index_file(&mut self, content: &str, path: &str) {
        for (line_num, line) in content.lines().enumerate() {
            // Example pattern for function definition: "fn name(...)"
            if line.trim().starts_with("fn ") {
                let signature = line.split('{').next().unwrap_or(line).trim();
                let name = signature
                    .strip_prefix("fn ")
                    .unwrap()
                    .split('(')
                    .next()
                    .unwrap()
                    .trim();

                let symbol = CodeSymbol {
                    id: format!("{}:{}", path, line_num),
                    name: name.to_string(),
                    kind: SymbolKind::Function,
                    file_path: path.to_string(),
                    start_line: line_num,
                    end_line: line_num + 10, // Approximate range estimation
                    signature: signature.to_string(),
                };

                self.add_symbol(symbol);
            }
            // Patterns for Struct, impl, etc. can be added...
        }
    }

    fn add_symbol(&mut self, symbol: CodeSymbol) {
        let idx = self.symbols.len();
        self.symbols.push(symbol);
        self.name_map
            .entry(symbol.name.clone())
            .or_insert_with(Vec::new)
            .push(idx);
    }
}
```

#### 3. Search Interface for MCP Tools

Now, let's create a search function that MCP clients can call. This function saves tokens by returning only the `signature` and `key ID` instead of the entire code.

```rust
impl CodeIndex {
    pub fn search(&self, query: &str) -> Vec<CodeSymbol> {
        self.symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&query.to_lowercase()))
            .cloned()
            .collect()
    }

    // Converts to an optimized format for LLM context
    pub fn to_llm_context(&self, results: Vec<CodeSymbol>) -> String {
        results
            .iter()
            .map(|s| format!(
                "File: {}, Line: {}\nSymbol: {}\nDefinition: {}\n",
                s.file_path, s.start_line, s.name, s.signature
            ))
            .collect::<Vec<_>>()
            .join("\n---\n")
    }
}
```

### Performance Comparison and Token Saving Effect

For example, let's assume we are looking for a function named `get_post` in `blog-api-server`.

*   **Traditional grep Method**: Returns all 20 lines containing the function from `main.rs` (including comments, logic, etc.).
*   **ZeroClaw Indexer Method**: Returns only `File: src/main.rs, Line: 45, Symbol: get_post, Definition: async fn get_post(id: i32) -> Result<Post>`.

Consequently, the LLM receives only the necessary metadata, allowing it to either be re-queried with "show me the internal implementation of this function" or perform sufficient reasoning with just the metadata. Token usage is drastically reduced as unnecessary code is not processed.

### Conclusion: Optimization for the Agent Ecosystem

This Semble-inspired approach goes beyond simply improving search speed; it **optimizes the communication costs and efficiency between LLM agents and codebases**. This is particularly essential in environments dealing with large codebases, such as improving logging for `blog-api-server` or for monitoring systems.

As a next step, we plan to extend ZeroClaw's communication protocol to enable semantic search by incorporating **Vector Embedding**, going beyond simple text matching. This will allow agents to flexibly find functions like `login`, `verify`, and `session` when searching for "user authentication related logic," even if the keyword `auth` is not present.

If you are building a high-performance agent runtime, consider building an indexer that 'understands' code, rather than just reading files. You can achieve both token cost savings and improved response times.

### References
*   [Show HN: Semble – Code search for agents that uses 98% fewer tokens than grep](https://news.ycombinator.com/item?id=41981234)
*   ZeroClaw Architecture Documentation
*   Rust Tree-sitter Binding Guide
```