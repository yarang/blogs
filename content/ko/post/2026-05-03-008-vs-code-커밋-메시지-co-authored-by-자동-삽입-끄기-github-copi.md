+++
title = "VS Code 커밋 메시지 'Co-Authored-by' 자동 삽입 끄기: GitHub Copilot 설정 정리"
date = 2026-05-03T14:11:23+09:00
draft = false
tags = ["VSCode", "GitHub", "Copilot", "Git", "Settings"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# VS Code 커밋 메시지 'Co-Authored-by' 자동 삽입 끄기: GitHub Copilot 설정 정리

최근 VS Code를 사용하여 Git을 커밋할 때, 내가 작업하지 않은 코드나 Copilot의 도움을 받지 않았음에도 불구하고 커밋 메시지에 자동으로 `Co-Authored-by: GitHub Copilot ...` 구문이 삽입되는 현상을 겪으셨나요? Hacker News 등에서도 이 문제가 논란이 되고 있으며, 의도치 않은 공저자 표기는 프로젝트의 기여도 집계를 흐리거나 불필요한 기록을 남기는 원인이 됩니다.

이번 포스트에서는 이 문제의 원인을 간단히 짚어보고, VS Code와 GitHub Copilot 확장 프로그램의 설정을 통해 이 자동 삽입 기능을 끄는 방법을 정리해 드리겠습니다.

## 문제의 원인: Copilot의 'Attribution' 기능

GitHub Copilot 확장 프로그램은 특정 설정이 켜져 있을 경우, 사용자가 코드를 작성할 때 Copilot이 제안한 내용이 포함되어 있다고 판단하면 커밋 메시지에 자동으로 저자 정보(Co-Authored-by)를 추가하려 합니다. 이는 투명성을 위한 기능이지만, 실제 코드 작성 비중에 따라 불편함을 느끼는 개발자들이 많습니다.

## 해결 방법 1: VS Code 설정 변경 (settings.json)

가장 확실한 방법은 VS Code의 사용자 설정(JSON) 파일을 직접 수정하는 것입니다. 이 방법은 모든 워크스페이스에 적용되므로 한 번만 설정하면 편리합니다.

1. VS Code를 실행하고 명령 팔레트를 엽니다 (`Ctrl + Shift + P` 또는 `Cmd + Shift + P`).
2. `Preferences: Open User Settings (JSON)`을 입력하고 실행합니다.
3. 열려있는 `settings.json` 파일의 최상위 중괄호 `{ ... }` 안에 아래 코드를 추가합니다.

```json
{
  "github.copilot.enableCommitCompletion": false
}
```

이 설정은 Copilot이 커밋 메시지를 자동으로 완성하거나 수정하는 기능을 꺼줍니다.

## 해결 방법 2: GUI 설정 메뉴에서 끄기

JSON 파일을 직접 건드리는 것이 부담스럽다면, 설정 메뉴에서 마우스 클릭만으로 해결할 수 있습니다.

1. VS Code의 왼쪽 하단 톱니바퀴 아이콘을 클릭하고 **[Settings]**를 선택합니다.
2. 검색창에 `copilot commit`을 입력합니다.
3. **GitHub Copilot: Enable Commit Completion** 항목을 찾습니다.
4. 체크박스를 클릭하여 **체크 해제(Off)** 상태로 만듭니다.

## 해결 방법 3: Git 구성으로 자동 서명 방지 (추가 팁)

만약 Copilot이 아닌 다른 도구나 Git 자체의 설정 때문에 `Co-Authored-by`가 들어가는 것을 방지하고 싶다면, Git의 훅(Hook)이나 커밋 템플릿을 점검해야 합니다. 하지만 최근 보고되는 대부분의 사례는 위에서 언급한 VS Code의 Copilot 설정 문제입니다.

## 설정 확인 및 테스트

설정을 변경한 후, 간단한 코드를 수정하고 다시 커밋 메시지 창을 열어보세요. 더 이상 `Co-Authored-by: GitHub Copilot ...` 문구가 자동으로 생성되지 않는 것을 확인할 수 있습니다.

## 마치며

AI 도구는 개발 생산성을 높여주지만, 때로는 사용자의 의도와 다르게 작동하기도 합니다. 본인의 코드 기여도를 명확히 하고 싶거나, 깔끔한 커밋 히스토리를 유지하고 싶다면 위의 설정을 적용해 보시기 바랍니다.

기술 블로그에서는 이러한 개발 도구의 팁 외에도 Next.js, MCP 서버 구축, 그리고 AI 에이전트 팀 설계 등 다양한 실용적인 주제를 다루고 있습니다. 궁금한 점이 있거나 도움이 필요하신 부분이 있다면 언제든지 댓글을 남겨주세요.

Happy Coding!
