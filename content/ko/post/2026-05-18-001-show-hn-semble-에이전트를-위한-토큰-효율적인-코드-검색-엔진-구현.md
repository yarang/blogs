+++
title = "Show HN: Semble – 에이전트를 위한 토큰 효율적인 코드 검색 엔진 구현"
date = 2026-05-18T09:00:38+09:00
draft = false
tags = ["Rust", "ZeroClaw", "CodeSearch", "MCP", "LLM", "Agent"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

최근 LLM(Large Language Model)을 활용한 에이전트 시스템을 개발하면서 가장 큰 병목 현상 중 하나는 바로 '코드 검색'이었습니다. 단순히 `grep` 명령어로 소스 코드를 검색하여 LLM 컨텍스트에 던져주는 것만으로는 입력 토큰(Input Tokens)이 폭발적으로 증가하고, 검색 속도 또한 느려져 실시간성을 요구하는 에이전트의 응답 속도를 저해했습니다.

Hacker News에서 논의된 'Show HN: Semble' 프로젝트는 이러한 문제를 해결하는 아주 흥미로운 접근 방식을 제시합니다. 일반적인 grep 도구 대비 **98%나 적은 토큰**을 사용하여 코드를 검색한다는 것인데요. 이번 포스트에서는 Semble의 핵심 아이디어와 이를 우리의 고성능 Rust 에이전트 런타임인 **ZeroClaw** 및 **MCP(Model Context Protocol)** 서버에 통합하여 성능을 극대화하는 방법을 살펴보겠습니다.

### 기존 검색 방식의 문제점: grep과 LLM의 궁합

기존의 `blog-api-server`나 여러 MCP 도구에서 코드를 검색할 때 주로 정규표현식 기반의 `grep` 라이브러리를 사용했습니다. 하지만 이 방식은 LLM 에이전트와 함께 사용할 때 치명적인 단점이 있습니다.

1.  **토큰 낭비**: `grep`은 검색어가 포함된 전체 라인을 반환합니다. 긴 라인이나 불필요한 주석이 포함된 경우, LLM은 실제 코드보다 잡음(Noise)을 더 많이 처리해야 합니다.
2.  **의미 이해 부족**: 단순 문자열 매칭이므로 '카멜 케이스', '스네이크 케이스' 등의 뉘앙스를 이해하지 못합니다. 예를 들어 `getUser`를 검색했을 때 `get_user`는 놓칠 수 있습니다.
3.  **비용 증가**: LLM API 호출 비용은 입력 토큰 수에 비례합니다. 불필요한 코드가 컨텍스트에 포함되면 비용이 그만큼 증가합니다.

### Semble의 접근 방식: 구조와 의미의 분리

Semble이 토큰 사용량을 98%나 줄일 수 있는 비결은 **코드를 구조화된 AST(Abstract Syntax Tree)나 의미론적 토큰으로 사전 처리**하고, 검색 시점에 이를 재조합하기 때문입니다. 핵심은 **'코드를 문자열이 아닌 데이터로 다룬다'**는 것입니다.

우리는 이 개념을 확장하여 ZeroClaw 아키텍처 내에 `CodeIndexer` 모듈을 설계했습니다.

### ZeroClaw 통합: 고성능 인덱서 구현

ZeroClaw는 Rust 기반이므로 메모리 안전성과 속도를 보장합니다. 여기에 Semble 영감을 받은 인덱서를 구현해 보겠습니다.

#### 1. 데이터 구조 정의

먼저 코드를 저장할 구조를 정의합니다. 파일의 내용 전체를 저장하는 대신, 심볼(Symbol)과 메타데이터만 저장합니다.

```rust
use std::collections::HashMap;
use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CodeSymbol {
    pub id: String,
    pub name: String,
    pub kind: SymbolKind, // Function, Struct, Variable 등
    pub file_path: String,
    pub start_line: usize,
    pub end_line: usize,
    pub signature: String, // 함수 시그니처나 타입 정의
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum SymbolKind {
    Function,
    Struct,
    Enum,
    Variable,
    Module,
}

// 인메모리 인덱스 (실제 운영에서는 DB나 Vector Store 사용 권장)
pub struct CodeIndex {
    symbols: Vec<CodeSymbol>,
    // 빠른 룩업을 위한 맵
    name_map: HashMap<String, Vec<usize>>, 
}
```

#### 2. 인덱싱 로직 (Parsing)

실제 Semble은 훨씬 복잡한 파서를 사용하겠지만, 여기서는 간단한 로직으로 라인 단위 파싱을 흉내 내어 토큰을 절약하는 방식을 구현합니다. 주석이나 공백을 제거하고 핵심 정의만 캡처합니다.

```rust
impl CodeIndex {
    pub fn new() -> Self {
        Self {
            symbols: Vec::new(),
            name_map: HashMap::new(),
        }
    }

    // 간단한 파싱 로직 (실제로는 tree-sitter 등 활용)
    pub fn index_file(&mut self, content: &str, path: &str) {
        for (line_num, line) in content.lines().enumerate() {
            // 함수 정의 패턴 예시: "fn name(...)"
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
                    end_line: line_num + 10, // 대략적인 범위 추정
                    signature: signature.to_string(),
                };

                self.add_symbol(symbol);
            }
            // Struct, impl 등에 대한 패턴 매칭 추가 가능...
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

#### 3. MCP 도구를 위한 검색 인터페이스

이제 MCP 클라이언트가 호출할 수 있는 검색 함수를 만듭니다. 이 함수는 전체 코드가 아닌 `signature`와 `핵심 ID`만 반환하도록 하여 토큰을 아낍니다.

```rust
impl CodeIndex {
    pub fn search(&self, query: &str) -> Vec<CodeSymbol> {
        self.symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&query.to_lowercase()))
            .cloned()
            .collect()
    }

    // LLM 컨텍스트를 위해 최적화된 포맷으로 변환
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

### 성능 비교 및 토큰 절약 효과

예를 들어, `blog-api-server`에서 `get_post`라는 함수를 찾는다고 가정해 봅시다.

*   **기존 grep 방식**: `main.rs`의 100줄 중 해당 함수가 포함된 20줄을 모두 반환. (주석, 로직 등 포함)
*   **ZeroClaw 인덱서 방식**: `File: src/main.rs, Line: 45, Symbol: get_post, Definition: async fn get_post(id: i32) -> Result<Post>`만 반환.

결과적으로, LLM은 필요한 메타데이터만 전달받으므로 **"이 함수의 내부 구현을 보여줘"**라고 재요청하거나, 메타데이터만으로도 충분한 추론을 수행할 수 있습니다. 불필요한 코드를 읽지 않기 때문에 토큰 사용량이 획기적으로 줄어듭니다.

### 결론: 에이전트 생태계를 위한 최적화

Semble에서 영감을 받은 이 접근 방식은 단순히 검색 속도를 높이는 것을 넘어, **LLM 에이전트와 코드베이스 간의 통신 비용과 효율성을 최적화**합니다. 특히 `blog-api-server`의 로깅 개선이나 모니터링 시스템처럼 대규모 코드베이스를 다루는 환경에서는 필수적입니다.

다음 단계로, 단순 텍스트 매칭을 넘어 **Vector Embedding(벡터 임베딩)**을 결합하여 의미론적 검색(Semantic Search)이 가능하도록 `ZeroClaw`의 통신 프로토콜을 확장할 예정입니다. 이를 통해 에이전트가 "사용자 인증 관련 로직"을 검색했을 때, `auth`라는 키워드가 없어도 `login`, `verify`, `session` 등의 함수를 유연하게 찾아낼 수 있게 될 것입니다.

고성능 에이전트 런타임을 구축하신다면, 단순히 파일을 읽는 것에서 벗어나 코드를 '이해'하는 인덱서 구축을 고려해 보세요. 토큰 비용 절감과 응답 속도 개선이라는 두 마리 토끼를 잡을 수 있습니다.

### 참고 자료
*   [Show HN: Semble – Code search for agents that uses 98% fewer tokens than grep](https://news.ycombinator.com/item?id=41981234)
*   ZeroClaw Architecture Documentation
*   Rust Tree-sitter Binding Guide