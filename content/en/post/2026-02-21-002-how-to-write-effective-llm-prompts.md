+++
title = "[LLM] How to Write Effective Prompts"
slug = "2026-02-21-002-llm-prompt-guide"
date = 2026-02-21T20:40:00+09:00
draft = false
tags = ["llm", "prompt-engineering", "ai"]
categories = ["AI"]
ShowToc = true
TocOpen = true
+++

## Introduction

Writing effective prompts is essential for getting the most out of LLMs (Large Language Models). This article summarizes key principles and practical patterns of prompt engineering.

## Core Principles of Good Prompts

### 1. Clarity

Avoid ambiguous expressions and be specific.

**Bad Example:**
```
Write good code
```

**Good Example:**
```
Implement a binary search tree in Python.
Include insert, search, and delete methods,
with time complexity of O(log n).
```

### 2. Provide Context

Give background information needed for the LLM to understand the task.

```
I'm a React beginner.
Explain the difference between useState and useEffect
with example code.
```

### 3. Role Playing

Set up responses from a specific expert's perspective.

```
You are a senior backend developer with 10 years of experience.
Explain the pros and cons of microservices architecture.
```

### 4. Specify Output Format

Explicitly state the desired response format.

```
Summarize the following in a markdown table:
- Language features
- Pros and cons
- Use cases
```

## Prompt Patterns

### Chain of Thought

Guide step-by-step thinking for complex problems.

```
Let's think through this problem step by step:
1. First analyze the problem
2. Consider solutions
3. Write the final answer
```

### Few-Shot Learning

Provide examples to teach the desired format.

```
Summarize in the following format:

Input: "The weather is nice today"
Output: Positive, Weather

Input: "The meeting was too long"
Output: Negative, Work

Input: "Started a new project"
Output: ?
```

### Structured Prompts

Divide complex tasks into sections.

```
## Goal
Design a user authentication API

## Requirements
- Use JWT tokens
- Refresh token rotation
- Apply rate limiting

## Output
1. API endpoint specification
2. Sequence diagram
3. Security considerations
```

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Too long prompts | Key points get lost | Keep it concise |
| Ambiguous instructions | Unexpected results | Provide specific examples |
| Missing context | Inaccurate answers | Add background info |
| Unspecified format | Poor readability | Specify output format |

## Practical Checklist

Check before writing your prompt:

- [ ] Is the goal clear?
- [ ] Included necessary context?
- [ ] Specified output format?
- [ ] Stated constraints?
- [ ] Would examples help?

## Conclusion

Good prompts are clear, specific, and provide necessary context. Practice to improve your prompt writing skills.

## References

- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Claude Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)


---

**Korean Version:** [한국어 버전](/ko/post/2026-02-21-002-llm-prompt-guide/)