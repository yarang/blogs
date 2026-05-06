+++
title = "Computer Use API vs Structured Output: 비용 효율적인 LLM 구현 전략"
date = 2026-05-06T09:00:48+09:00
draft = false
tags = ["LLM", "AI", "CostOptimization", "AgentArchitecture", "Python"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Computer Use API vs Structured Output: 비용 효율적인 LLM 구현 전략

최근 Hacker News에서 흥미로운 기사를 접했습니다. **[Computer Use is 45x more expensive than structured APIs]**라는 제목의 글입니다. Anthropic의 최신 기능인 'Computer Use'는 AI가 컴퓨터 화면을 보고 마우스와 키보드를 조작하여 사용자 대신 작업을 수행할 수 있게 해줍니다. 마치 철권(Tekken) 게임에서 AI가 플레이어를 대신해 콤보를 입력하는 것처럼 매우 매력적입니다.

하지만 이 기능의 구현 비용은 기존의 **Structured Output(JSON 모드 등)**을 사용할 때보다 무려 **45배**나 높다는 분석이 나왔습니다.

이번 포스트에서는 왜 이런 격차가 발생하는지, 그리고 우리가 개발하는 **Multi-Agent 시스템(예: ZeroClaw)**에서 이 비용 문제를 어떻게 지혜롭게 해결할 수 있을지 현실적인 코드와 함께 분석해 보겠습니다.

---

## 1. 비용 격차의 원인 분석

### Computer Use (GUI 기반 접근)
'Computer Use'는 본질적으로 **VNC(RDP) 원격 제어**와 유사합니다. AI는 매 턴마다 다음을 수행해야 합니다.

1.  **화면 캡처:** 고해상도 이미지를 다운로드합니다. (토큰 비용 급증)
2.  **시각적 처리:** 이미지를 이해하기 위해 대규모 Vision 모델을 실행합니다.
3.  **좌표 계산:** 버튼의 위치를 픽셀 단위로 계산합니다.
4.  **액션 실행:** 마우스 클릭/키보드 입력을 전송합니다.

이 과정에서 단순한 텍스트 응답 대신 수백만 개의 '시각적 토큰'이 소모됩니다.

### Structured Output (API 기반 접근)
반면, 우리가 블로그 API 서버나 MCP(Model Context Protocol)를 통해 구성하는 전통적인 방식은 훨씬 효율적입니다.

1.  **텍스트 입력:** 시스템 상태나 사용자 의도가 텍스트로 전달됩니다.
2.  **논리적 추론:** LLM이 텍스트를 파싱하여 의사결정을 내립니다.
3.  **직접 호출:** `tool_use` 블록을 통해 함수를 직접 실행합니다. (이미지 처리 불필요)

---

## 2. 실용적인 해결책: 하이브리드 아키텍처

모든 작업을 Computer Use로 처리하는 것은 낭비입니다. 우리는 **ZeroClaw**나 **MCP 블로그 자동화** 프로젝트에서 배운 **'도구 분리의 원칙'**을 적용해야 합니다.

### 전략: 도구 사용 우선순위

1.  **1순위: Native API (Structured Output)**
    *   데이터베이스 조회, API 호출, 파일 생성 등 명확한 로직은 항상 함수 호출로 처리.
2.  **2순위: Browser Automation (Playwright/Selenium)**
    *   복잡한 DOM 조작이 필요하나, 백엔드 API가 없는 경우. (이미지보다 HTML 트리를 파싱하는 것이 저렴)
3.  **최후의 수단: Computer Use (Vision)**
    *   캡차가 있거나, 동영상 편집 프로그램처럼 DOM 접근이 불가능한 오래된 레거시 소프트웨어만 대상으로 함.

---

## 3. 코드 예제: 비용 최적화된 Agent 구현

Python을 사용하여 LLM이 API 호출(Structured)과 브라우저 제어(Browser)를 선택적으로 사용하도록 만드는 예제를 작성해 보겠습니다. Computer Use는 아직 특정 클라우드 환경에 종속되어 있으므로, 가장 현실적인 대안인 **Playwright(HTML 기반)**와 **API 호출**을 비교하는 코드를 소개합니다.

### 시나리오: 블로그 게시글 자동 발행

LLM 에이전트에게 "최신 기술 뉴스를 요약하고 내 블로그에 발행해"라고 요청한다고 가정해 봅시다.

#### 구조적 접근 (Structured Output + API)

```python
import json
from typing import Literal

# 1. 도구 정의 (API 방식)
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_blog_post",
            "description": "블로그에 새 글을 발행합니다. (가장 저렴하고 빠름)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web_browser",
            "description": "웹 브라우저를 제어하여 정보를 검색합니다. (API가 없을 때 사용)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    }
]

# 2. 에이전트 실행 로직 (시뮬레이션)
def run_agent(user_query: str):
    # 단계 1: LLM에게 도구 사용 요청 (실제로는 OpenAI/Anthropic API 호출)
    # LLM 응답 시뮬레이션: create_blog_post 도구 선택
    llm_response = {
        "tool": "create_blog_post",
        "arguments": {
            "title": "Gemma 4 가속화 기술",
            "content": "구글의 최신 모델 Gemma은 멀티-토큰 예측을 통해...",
            "tags": ["AI", "Google"]
        }
    }

    # 단계 2: 로컬 함수 실행 (Vision 필요 없음)
    if llm_response['tool'] == 'create_blog_post':
        print(f"[API 실행] 블로그 글 발행: {llm_response['arguments']['title']}")
        # 실제로는 여기서 requests.post('https://blog-api.com/posts', ...) 호출
        return {"status": "success", "cost": "0.0001 USD"}

print(run_agent("블로그에 글 써줘"))
```

이 방식은 텍스트만 주고받으므로 매우 저렴합니다.

#### 비구조적 접근 (Computer Use 시뮬레이션 - 비용 상승)

만약 우리가 블로그 API를 사용하지 않고 Computer Use로 웹 브라우저를 띄워 글을 쓴다고 상상해 보세요.

```python
# Computer Use 방식의 의사코드 (비용 폭발 구간)
def run_computer_use_agent():
    # 1. 화면 캡처 (1024x768 이미지 -> 약 1,100 토큰 소모)
    screenshot = capture_screen()
    print(f"[Vision] 화면 분석 중... (토큰 1,100개 소모)")

    # 2. LLM 추론: "로그인 버튼을 찾아라"
    action = llm_vision_inference(screenshot, prompt="Find the login button")
    # 결과: {"x": 500, "y": 300, "action": "click"}
    print(f"[Action] 마우스 이동 및 클릭: {action}")

    # 3. 다시 화면 캡처 및 입력 필드 분석
    screenshot = capture_screen()
    print(f"[Vision] 입력 필드 분석 중... (토큰 1,100개 소모)")
    
    # ... (반복적인 캡처와 추론)
    return {"status": "success", "cost": "0.05 USD"} 
    # API 방식(0.0001 USD) 대비 약 500배 비용 발생 가능
```

---

## 4. ZeroClaw 및 MCP 아키텍처 적용 가이드

우리가 진행 중인 **ZeroClaw(고성능 Rust 에이전트)**나 **Discord MCP** 프로젝트에서 이 원칙을 적용하면 다음과 같은 설계가 나옵니다.

1.  **MCP (Model Context Protocol) 표준 준수:**
    *   가능한 모든 자원(파일 시스템, 데이터베이스, 클라우드 리소스)을 **MCP Server**로 노출시켜 LLM이 **Structured JSON**으로 제어하게 하십시오.
    *   예: Discord 메시지를 보낼 때, 브라우저를 띄우는 것이 아니라 `discord_mcp.send_message()` 함수를 호출하도록 유도합니다.

2.  **Prompt Engineering:**
    *   시스템 프롬프트에 명확히 선언하십시오.
    *   > "당신은 화면을 보는 것이 아니라 도구를 호출해야 합니다. 사용자의 요청을 처리하기 위해 먼저 `available_tools` 리스트를 확인하고, 함수 호출이 가능한지 우선 확인하십시오."

3.  **Fallback 메커니즘:**
    *   `MCP Server`나 API가 죽었을 때만, 혹은 반드시 시각적 확인이 필요할 때만 'Computer Use' 또는 'Browser Automation' 에이전트를 깨우는 2단계 구조를 만드십시오.

## 5. 결론

AI 에이전트를 개발할 때 'Computer Use'는 마치 '스위스 군용 칼'과 같습니다. 모든 것을 할 수 있지만, 나사를 하나 조일 때마다 거대한 칼을 꺼내면(화면을 캡처면) 비용이 막대합니다.

우리는 **'적재적소'**의 도구를 사용해야 합니다. 대부분의 작업은 **Structured Output(API)**으로 해결하고, 정말 어쩔 수 없는 상황에만 **Vision/GUI** 기능을 사용하는 전략을 취한다면, **45배의 비용 차이**를 우리의 이익으로 돌릴 수 있을 것입니다.

앞으로 진행될 **ZeroClaw** 프로젝트의 통신 프로토콜 설계에서도 이 비용 효율성을 최우선 가이드라인으로 삼겠습니다.