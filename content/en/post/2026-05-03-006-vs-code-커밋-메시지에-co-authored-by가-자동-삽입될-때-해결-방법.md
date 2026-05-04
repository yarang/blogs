+++
title = "How to Fix Automatic 'Co-Authored-by' Insertion in VS Code Commit Messages"
date = "2026-05-03T12:52:59+09:00"
draft = "false"
tags = ["VSCode", "Git", "Copilot", "Troubleshooting", "Development"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

Hello! There is currently a hot issue rising in developer communities and Hacker News. Specifically, the problem where **VS Code automatically inserts a 'Co-Authored-by: Your Name <email@github.com>' tag into Git commit messages regardless of the user's intent**.

This issue does not occur only when using GitHub Copilot; it is happening even when Copilot is disabled or not even installed, causing confusion for many developers. Especially in open-source projects or corporate environments where contribution records and copyright attributions are strict, this can cause unwanted confusion.

Today, I will briefly examine the cause of this issue and share **practical solutions** to immediately block this automatic insertion behavior in your projects.

---

### Cause: VS Code's 'AI GitHub Contributor' Feature

The cause of this phenomenon lies within VS Code's internal **'AI GitHub Contributor'** feature. This feature is designed to detect how much the AI (Copilot) helped when writing code and automatically add a co-author (Co-Authored-by) if a certain threshold is exceeded.

However, it appears that during recent updates, this logic is acting excessively, or a bug occurs where the tag is attached unintentionally if the background process is active even with Copilot turned off. From the user's perspective, it feels like their metadata is being manipulated for code they wrote themselves, which is inevitably unpleasant.

### Solution: Blocking via Settings Changes

This problem can be clearly blocked through VS Code's User Settings or Workspace Settings (Settings.json). The surest way is to turn off the related feature.

#### 1. Turn off in Settings Menu (GUI)

The simplest method is to find the related option in the settings window and disable it.

1.  Run VS Code and press `Ctrl + ,` (`Cmd + ,` for Mac/Linux) to open **Settings**.
2.  Type `github.copilot.enable` in the search bar.
3.  Although **GitHub Copilot** settings will appear, what we need to find is the section related to **AI feature commit participation**.
4.  Search for `source control` or `ai contribution` in the search bar.
5.  Check items related to **'Editor: Inline Suggest'**, or it is recommended to directly modify `settings.json` for more certainty.

#### 2. Clearly Block via settings.json (Recommended)

Since GUI menu names may change depending on the version, specifying directly in the settings file (JSON) is the safest and most certain method.

1.  Press `Ctrl + Shift + P` (`Cmd + Shift + P` on Mac) to open the **Command Palette**.
2.  Type and run `Preferences: Open User Settings (JSON)`.
3.  Add the following content between the `{}` curly braces in the `settings.json` file that opens.

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

**Description of Settings Values:**
*   `"github.copilot.enable": { "*": false }`: Insertion stops most reliably when Copilot itself is turned off. (However, if you want to keep using Copilot, just add the settings below.)
*   **Want to use Copilot but block only the insertion?** In the latest VS Code versions, a separate flag to control this behavior may appear. As of now, since Copilot's auto-completion feature acts as the commit trigger, setting **"editor.inlineSuggest.enabled": false** to turn off inline suggestions or temporarily disabling the Copilot extension is the most definite preventive measure.

#### 3. Force Defense with Git Hooks (Hardcore Method)

If it is a team project where not all team members can change their VS Code settings, you can also use Git Hooks. You can modify the `.git/hooks/commit-msg` file in the project root (or use a `pre-commit` hook) to write a script that detects and removes 'Co-Authored-by' if it is included in the commit message.

Let's look at a simple example using `husky` and `lint-staged` based on Node.js.

```javascript
// .husky/pre-commit (Simple example)
const fs = require('fs');

// Since the logic to get the commit message of the current branch is complex,
// it is common to handle it in the commit-msg hook.
// Below is a simple shell example of the commit-msg hook script.
```
```bash
# .git/hooks/commit-msg
#!/bin/sh

COMMIT_MSG_FILE=$1

# Check if Co-Authored-by is included
grep -q "Co-Authored-by:" "$COMMIT_MSG_FILE"

if [ $? -eq 0 ]; then
    echo "[WARN] Detected 'Co-Authored-by' tag. Removing it automatically."
    # Delete the relevant line (sed syntax may vary by OS)
    sed -i '' '/Co-Authored-by:/d' "$COMMIT_MSG_FILE"
fi
```

If you save this script and give it execution permissions (`chmod +x .git/hooks/commit-msg`), it will automatically remove the Co-Authored-by tag whenever you commit in the future.

### Summary

The tight integration of VS Code and GitHub is convenient, but sometimes it behaves in ways that deviate from user intent. If you see strange tags attached to your commit messages, **try checking inline suggestions in `settings.json` or inspecting Copilot settings**.

If this was helpful, please leave a comment and share! Happy coding today as well.