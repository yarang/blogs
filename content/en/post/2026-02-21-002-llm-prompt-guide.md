+++
title = ""
slug = "2026-02-21-002-llm-prompt-guide"
date = "2026-02-21T20:40:00+09:00"
draft = "false"
tags = ["llm", "prompt-engineering", "ai"]
categories = ["AI"]
ShowToc = "true"
TocOpen = "true"
+++

## Introduction

To effectively utilize an LLM (Large Language Model), writing a good prompt is essential. This article summarizes the core principles of prompt engineering and practical patterns.

## Core Principles of a Good Prompt

### 1. Clarity

Avoid ambiguous expressions and be specific.

**Bad Example:**
```
Write good code
```

**Good Example:**
```
Implement a Binary Search Tree in Python.
Include insert, search, and delete methods,
and ensure the time complexity is O(log n).
```

### 2. Providing Context

Provide background information necessary for the LLM to understand the task.

```
I am a React beginner.
Explain the differences between useState and useEffect with example code.
```

### 3. Role Playing

Set the response to come from the perspective of a specific expert.

```
You are a Senior Backend Developer with 10 years of experience.
Explain the pros and cons of microservices architecture.
```

### 4. Specifying Output Format

Specify the desired response format.

```
Summarize the following into a markdown table:
- Characteristics by language
- Pros and cons
- Use cases
```

## Prompt Patterns

### Chain of Thought

Guide the model to think step-by-step for complex problems.

```
Let's think about this problem step by step:
1. First, analyze the problem
2. Then, consider the solution
3. Finally, write the answer
```

### Few-Shot Learning

Provide examples to teach the desired format.

```
Summarize in the following format:

Input: "The weather is good today"
Output: Positive, Weather

Input: "The meeting was too long"
Output: Negative, Work

Input: "Started a new project"
Output: ?
```

### Structured Prompt

Break down complex tasks into sections.

```
## Goal
Design a User Authentication API

## Requirements
- Use JWT tokens
- Refresh token rotation
- Apply Rate limiting

## Output
1. API endpoint specification
2. Sequence diagram
3. Security considerations
```

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Too long prompt | Main point gets blurred | Keep only the core points concisely |
| Ambiguous instructions | Results different from expectations | Provide specific examples |
| Missing context | Inaccurate answer | Add background information |
| Unspecified format | Poor readability | Specify output format |

## Practical Checklist

Check before writing a prompt:

- [ ] Is the goal clear?
- [ ] Did you include necessary context?
- [ ] Did you specify the output format?
- [ ] Did you state constraints?
- [ ] Would examples be helpful?

## Conclusion

A good prompt is clear, specific, and provides necessary context. Improve your prompt writing skills through practice.

## References

- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Claude Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)


---

**English Version:** [English Version](/post/2026-02-21-002-how-to-write-effective-llm-prompts/)