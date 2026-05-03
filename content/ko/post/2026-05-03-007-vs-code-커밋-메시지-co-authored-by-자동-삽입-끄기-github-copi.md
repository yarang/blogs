+++
title = "VS Code 커밋 메시지 'Co-Authored-by' 자동 삽입 끄기: GitHub Copilot 설정 정리"
date = 2026-05-03T14:04:28+09:00
draft = false
tags = ["VSCode", "Git", "GitHub Copilot", "Troubleshooting", "DevelopmentEnvironment"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# VS Code 커밋 메시지 'Co-Authored-by' 자동 삽입 끄기

최근 VS Code를 사용해 Git 커밋을 생성할 때, 의도치 않게 `Co-Authored-by: GitHub Copilot <copilot@github.com>`와 같은 메시지가 커밋 메시지 하단에 자동으로 삽입되는 현상을 겪으셨을 것입니다. Hacker News 등에서도 "VS Code inserting 'Co-Authored-by Copilot' into commits regardless of usage"라는 이슈로 화제가 되었습니다.

AI가 코드를 작성하지 않았거나, 단순히 문법만 확인했음에도 불구하고 이 메시지가 들어가면, 커밋 히스토리가 지저분해질 수 있고 **공로(Credit)** 관리가 모호해질 수 있습니다. 

이번 포스트에서는 이 기능의 원인과 VS Code 설정을 통해 이를 깔끔하게 해제하는 방법을 단계별로 설명합니다.

## 현상 확인

VS Code의 소스 제어(Source Control) 패널에서 커밋 메시지를 입력하고 커밋을 생성하면, 실제 `.git/COMMIT_EDITMSG`나 푸시된 히스토리에는 다음과 같은 줄이 추가되어 있습니다.

```git
feat: update user authentication logic

Co-Authored-by: GitHub Copilot <copilot@github.com>
```

## 원인 분석

이 현상은 주로 **GitHub Copilot 확장 프로그램**과 VS Code의 **Smart Commit(스마트 커밋)** 기능이 연동되면서 발생합니다. Copilot이 IDE 내에서 활성화되어 있고, 코드 생성이나 완성을 제안한 맥락이 있으면 확장 프로그램이 자신을 공동 저자로 추가하려고 시도합니다.

사용자 입장에서는 단순히 변수명 자동 완성을 받았을 뿐인데, 이 기능이 모든 커밋에 적용되는 것은 과도한 행동일 수 있습니다.

## 해결 방법: VS Code 설정 변경

가장 확실한 해결책은 VS Code의 사용자 설정(`settings.json`)을 수정하여, 커밋 작성 시 Copilot이 개입하지 않도록 막는 것입니다.

### 1. 설정 열기

VS Code에서 `Ctrl + Shift + P` (맥: `Cmd + Shift + P`)를 눌러 명령 팔레트를 엽니다. **`Preferences: Open User Settings (JSON)`**을 입력하여 설정 파일을 엽니다.

### 2. 설정 코드 추가

열린 `settings.json` 파일의 중괄호 `{}` 안에 아래 내용을 추가합니다. 만약 `github.copilot` 관련 설정이 이미 있다면 병합하세요.

```json
{
  "github.copilot.enableInlineCompletions": true,
  "github.copilot.advanced": {
    "inlineSuggest.count": 3
  },
  
  // [핵심 수정 사항] 커밋 메시지에 Co-Authored-by 자동 삽입 비활성화
  "github.copilot.inlineSuggest.enable": false,
  
  // 또는 Copilot 자체의 공동 저자 표시 기능 끄기 (최신 버전 지원 시)
  "github.copilot.commitMessage": "off"
}
```

> **참고:** VS Code와 Copilot 확장 프로그램의 버전에 따라 옵션 키가 다를 수 있습니다. 가장 일반적인 방법은 커밋을 생성하는 순간 Copilot과의 통신을 최소화하는 것입니다.

### 3. 대체 방법: Git 훅(Hook) 사용 (선택 사항)

만약 설정만으로 해결되지 않는다면, Git의 `prepare-commit-msg` 훅을 사용하여 강제로 해당 줄을 제거할 수 있습니다. 프로젝트 루트의 `.git/hooks/prepare-commit-msg` 파일(확장자 없음)을 생성하거나 수정합니다.

```bash
#!/bin/sh

# 커밋 메시지 파일 경로 가져오기
COMMIT_MSG_FILE=$1

# 파일 내용에서 'Co-Authored-by: GitHub Copilot' 줄 제거
# macOS/BSD sed (macOS 기본)
sed -i '' '/Co-Authored-by: GitHub Copilot/d' "$COMMIT_MSG_FILE"

# Linux sed (WSL, Linux 서버 등)
# sed -i '/Co-Authored-by: GitHub Copilot/d' "$COMMIT_MSG_FILE"
```

이 스크립트를 저장하고 실행 권한(`chmod +x .git/hooks/prepare-commit-msg`)을 부여하면, 앞으로 커밋을 생성할 때마다 자동으로 해당 라인이 삭제됩니다.

## 검증

이제 다시 소스 제어 패널로 돌아가서 간단한 수정(예: 주석 추가) 후 커밋을 생성해 보세요.

```bash
# 커밋 로그 확인
git log -1
```

결과에 `Co-Authored-by: GitHub Copilot` 문구가 보이지 않는다면 성공입니다.

## 요약

개발 도구가 편리함을 제공하는 것은 좋지만, 커밋 메시지는 개발자의 작업 내역을 대변하는 중요한 기록입니다. 불필요한 텍스트가 섞이는 것을 방지하기 위해 위 설정을 적용하여 더 깔끔한 Git 관리 환경을 만들어 보시기 바랍니다.
