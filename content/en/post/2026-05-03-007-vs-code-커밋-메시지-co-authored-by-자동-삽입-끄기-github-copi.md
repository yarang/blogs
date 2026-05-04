+++
title = "Disabling Automatic 'Co-Authored-by' Insertion in VS Code Commit Messages: GitHub Copilot Settings Guide"
date = "2026-05-03T14:04:28+09:00"
draft = "false"
tags = ["VSCode", "Git", "GitHub Copilot", "Troubleshooting", "DevelopmentEnvironment"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Disabling Automatic 'Co-Authored-by' Insertion in VS Code Commit Messages

Recently, when creating Git commits using VS Code, you may have experienced the phenomenon where a message like `Co-Authored-by: GitHub Copilot <copilot@github.com>` is automatically inserted at the bottom of the commit message unintentionally. This issue was also a hot topic on sites like Hacker News under the title "VS Code inserting 'Co-Authored-by Copilot' into commits regardless of usage".

Even if the AI did not write the code or simply checked the syntax, if this message is included, the commit history can become cluttered and **Credit** attribution can become ambiguous.

In this post, we explain step-by-step the cause of this feature and how to cleanly disable it through VS Code settings.

## Verifying the Issue

When you enter a commit message in VS Code's Source Control panel and create a commit, the following line is added to the actual `.git/COMMIT_EDITMSG` or the pushed history.

```git
feat: update user authentication logic

Co-Authored-by: GitHub Copilot <copilot@github.com>
```

## Cause Analysis

This phenomenon mainly occurs when the **GitHub Copilot extension** and VS Code's **Smart Commit** feature are linked. When Copilot is activated within the IDE and there is a context where code generation or completion was suggested, the extension attempts to add itself as a co-author.

From the user's perspective, they may have simply received variable name auto-completion, so applying this feature to every commit might be considered excessive behavior.

## Solution: Changing VS Code Settings

The most definitive solution is to modify VS Code's user settings (`settings.json`) to prevent Copilot from intervening during commit creation.

### 1. Open Settings

Press `Ctrl + Shift + P` (Mac: `Cmd + Shift + P`) in VS Code to open the Command Palette. Type **`Preferences: Open User Settings (JSON)`** to open the settings file.

### 2. Add Settings Code

Add the following content inside the curly braces `{}` of the opened `settings.json` file. If there are already `github.copilot` related settings, merge them.

```json
{
  "github.copilot.enableInlineCompletions": true,
  "github.copilot.advanced": {
    "inlineSuggest.count": 3
  },
  
  // [Key Modification] Disable automatic Co-Authored-by insertion in commit messages
  "github.copilot.inlineSuggest.enable": false,
  
  // Or turn off Copilot's own co-author indication feature (if supported in latest version)
  "github.copilot.commitMessage": "off"
}
```

> **Note:** Option keys may vary depending on the versions of VS Code and the Copilot extension. The most common method is to minimize communication with Copilot at the moment of creating a commit.

### 3. Alternative Method: Using Git Hooks (Optional)

If the issue is not resolved by settings alone, you can use Git's `prepare-commit-msg` hook to forcibly remove that line. Create or modify the `.git/hooks/prepare-commit-msg` file (no extension) in the project root.

```bash
#!/bin/sh

# Get commit message file path
COMMIT_MSG_FILE=$1

# Remove lines containing 'Co-Authored-by: GitHub Copilot' from file content
# macOS/BSD sed (macOS default)
sed -i '' '/Co-Authored-by: GitHub Copilot/d' "$COMMIT_MSG_FILE"

# Linux sed (WSL, Linux servers, etc.)
# sed -i '/Co-Authored-by: GitHub Copilot/d' "$COMMIT_MSG_FILE"
```

After saving this script and granting execution permissions (`chmod +x .git/hooks/prepare-commit-msg`), that line will be automatically deleted whenever a commit is created in the future.

## Verification

Now go back to the Source Control panel and try creating a commit after a simple modification (e.g., adding a comment).

```bash
# Check commit log
git log -1
```

If the `Co-Authored-by: GitHub Copilot` text does not appear in the result, it is successful.

## Summary

While it is good for development tools to provide convenience, commit messages are important records that represent a developer's work history. To prevent unnecessary text from being mixed in, apply the above settings to create a cleaner Git management environment.