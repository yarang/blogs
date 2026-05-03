+++
title = "VS Code 커밋 메시지에 'Co-Authored-by'가 자동 삽입될 때 해결 방법"
date = 2026-05-03T12:52:59+09:00
draft = false
tags = ["VSCode", "Git", "Copilot", "Troubleshooting", "Development"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

안녕하세요! 최근 개발자 커뮤니티와 Hacker News에서 뜨거운 감자로 오르고 있는 이슈가 하나 있습니다. 바로 **VS Code가 사용자의 의도와 무관하게 Git 커밋 메시지에 'Co-Authored-by: Your Name <email@github.com>' 태그를 자동으로 삽입한다는 문제**입니다.

이 문제는 단순히 GitHub Copilot을 사용할 때만 발생하는 것이 아니라, Copilot을 비활성화했거나 심지어 설조차 하지 않은 환경에서도 발생하고 있어 많은 개발자들의 혼란을 가중시키고 있습니다. 특히 기여 기록(Contributions)이나 저작권 명시가 엄격한 오픈소스 프로젝트나 기업 환경에서는 원치 않는 혼란을 야기할 수 있습니다.

오늘은 이 이슈의 원인을 간단히 짚어보고, 당장 내 프로젝트에서 이 자동 삽입 동작을 막을 수 있는 **실용적인 해결 방법**을 공유해 드리겠습니다.

---

### 원인: VS Code의 'AI GitHub Contributor' 기능

이 현상의 원인은 VS Code 내부의 **'AI GitHub Contributor'** 기능에 있습니다. 이 기능은 사용자가 코드를 작성할 때 AI(Copilot)가 어느 정도 도움을 주었는지 파악하여, 일정 임계값을 넘으면 자동으로 공동 저자(Co-Authored-by)를 추가하려는 의도로 설계되었습니다.

하지만 최근 업데이트 과정에서 이 로직이 과도하게 작동하거나, Copilot을 끈 상태에서도 백그라운드 프로세스가 활성화되어 있으면 의도치 않게 태그가 붙는 버그가 발생한 것으로 보입니다. 사용자 입장에서는 내가 쓴 코드인데 메타데이터가 조작되는 느낌을 받아 불쾌할 수밖에 없습니다.

### 해결 방법: 설정 변경으로 차단하기

이 문제는 VS Code의 사용자 설정(User Settings)이나 작업 영역 설정(Settings.json)을 통해 명확하게 차단할 수 있습니다. 가장 확실한 방법은 관련 기능을 끄는 것입니다.

#### 1. 설정 메뉴에서 끄기 (GUI)

가장 간단한 방법은 설정 창에서 관련 옵션을 찾아 비활성화하는 것입니다.

1.  VS Code를 실행하고 `Ctrl + ,` (맥/리눅스는 `Cmd + ,`)를 눌러 **Settings**를 엽니다.
2.  검색창에 `github.copilot.enable`을 입력합니다.
3.  **GitHub Copilot** 관련 설정이 나오지만, 우리가 찾아야 할 것은 **AI 기능의 커밋 참여**와 관련된 부분입니다.
4.  검색창에 `source control` 또는 `ai contribution`을 검색합니다.
5.  **'Editor: Inline Suggest'**와 관련된 항목들을 확인하거나, 더 확실하게는 `settings.json`을 직접 수정하는 것을 권장합니다.

#### 2. settings.json으로 명확하게 차단하기 (권장)

GUI 설정은 버전에 따라 메뉴 이름이 바뀔 수 있으므로, 설정 파일(JSON)에 직접 명시하여 제어하는 것이 가장 안전하고 확실합니다.

1.  `Ctrl + Shift + P` (맥은 `Cmd + Shift + P`)를 눌러 **Command Palette**를 엽니다.
2.  `Preferences: Open User Settings (JSON)`을 입력하고 실행합니다.
3.  열리는 `settings.json` 파일의 `{}` 중괄호 사이에 아래 내용을 추가합니다.

```json
{
  "github.copilot.enable": {
    "*": false
  },
  "editor.inlineSuggest.enabled": false,
  "github.copilot.advanced": {
    "inlineSuggestPolicy": "manual"
  }
}
```

**설정 값 설명:**
*   `"github.copilot.enable": { "*": false }`: Copilot 자체를 껐을 때 가장 확실하게 삽입이 멈춥니다. (하지만 Copilot을 계속 쓰고 싶다면 아래 설정만 추가하세요)
*   **Copilot은 쓰되 삽입만 막고 싶다면?** 최신 VS Code 버전에서는 이 동작을 제어하는 별도의 플래그가 생길 수 있습니다. 현재로서는 Copilot의 자동 완성 기능이 커밋 트리거가 되므로, **"editor.inlineSuggest.enabled": false**로 설정하여 인라인 제안을 끄거나, Copilot 확장 프로그램을 일시 비활성화하는 것이 가장 확실한 예방책입니다.

#### 3. Git Hooks로 강제 방어하기 (하드코어 방법)

만약 팀 프로젝트라서 팀원 모두가 VS Code 설정을 바꿀 수 없는 상황이라면, Git Hook을 사용하는 방법도 있습니다. 프로젝트 루트의 `.git/hooks/commit-msg` 파일을 수정하여(또는 `pre-commit` 훅을 사용하여), 커밋 메시지에 'Co-Authored-by'가 포함되어 있는지 감지하고 제거하는 스크립트를 작성할 수 있습니다.

간단한 Node.js 기반의 `husky`와 `lint-staged` 설정 예시를 들어보겠습니다.

```javascript
// .husky/pre-commit (간단 예시)
const fs = require('fs');

// 현재 브랜치의 커밋 메시지를 가져오는 로직은 복잡하므로,
// 실제로는 commit-msg 훅에서 처리하는 것이 일반적입니다.
// 아래는 commit-msg 훅 스크립트의 간단한 쉘 예시입니다.
``n
```bash
# .git/hooks/commit-msg
#!/bin/sh

COMMIT_MSG_FILE=$1

# Co-Authored-by가 포함되어 있는지 확인
grep -q "Co-Authored-by:" "$COMMIT_MSG_FILE"

if [ $? -eq 0 ]; then
    echo "[WARN] Detected 'Co-Authored-by' tag. Removing it automatically."
    # 해당 라인 삭제 (sed는 OS마다 문법이 다를 수 있음)
    sed -i '' '/Co-Authored-by:/d' "$COMMIT_MSG_FILE"
fi
```

이 스크립트를 저장하고 실행 권한(`chmod +x .git/hooks/commit-msg`)을 주면, 앞으로 커밋을 할 때마다 자동으로 Co-Authored-by 태그를 제거해 줍니다.

### 요약

VS Code와 GitHub의 긴밀한 통합은 편리하지만, 때때로 사용자의 의도를 벗어난 동작을 하기도 합니다. 만약 내 커밋 메시지에 이상한 태그가 붙어 있다면 **`settings.json`에서 인라인 제안을 끄거나 Copilot 설정을 점검**해 보세요.

도움이 되셨다면 댓글과 공유 부탁드립니다! 오늘도 편안한 코딩 하시길 바랍니다.