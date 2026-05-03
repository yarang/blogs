+++
title = ""
date = "2026-05-03T14:11:23+09:00"
draft = "false"
tags = ["VSCode", "GitHub", "Copilot", "Git", "Settings"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Disabling Automatic 'Co-Authored-by' Insertion in VS Code Commit Messages: GitHub Copilot Settings Guide

Have you recently experienced the issue where the phrase `Co-Authored-by: GitHub Copilot ...` is automatically inserted into your commit messages when committing with Git in VS Code, even for code you wrote yourself or without Copilot's assistance? This issue has been controversial on platforms like Hacker News, and unintended co-author attribution can obscure project contribution metrics or leave unnecessary records.

In this post, we will briefly examine the cause of this problem and summarize how to disable this automatic insertion feature through the settings of VS Code and the GitHub Copilot extension.

## The Root Cause: Copilot's 'Attribution' Feature

When a specific setting is enabled, the GitHub Copilot extension attempts to automatically add author information (Co-Authored-by) to the commit message if it determines that the user's code includes suggestions from Copilot. While this feature aims for transparency, many developers feel uncomfortable with it depending on the actual proportion of code written.

## Solution 1: Change VS Code Settings (settings.json)

The most definitive method is to directly modify VS Code's user settings (JSON) file. Since this applies to all workspaces, it is convenient as you only need to set it up once.

1. Launch VS Code and open the Command Palette (`Ctrl + Shift + P` or `Cmd + Shift + P`).
2. Type and execute `Preferences: Open User Settings (JSON)`.
3. Add the following code inside the top-level curly braces `{ ... }` of the opened `settings.json` file.

```json
{
  "github.copilot.enableCommitCompletion": false
}
```

This setting disables Copilot's ability to automatically complete or modify commit messages.

## Solution 2: Disable via the GUI Settings Menu

If editing the JSON file directly feels burdensome, you can resolve this with just a few mouse clicks in the settings menu.

1. Click the gear icon in the bottom left corner of VS Code and select **[Settings]**.
2. Enter `copilot commit` in the search box.
3. Find the **GitHub Copilot: Enable Commit Completion** item.
4. Click the checkbox to turn it to the **unchecked (Off)** state.

## Solution 3: Preventing Automatic Attribution via Git Configuration (Additional Tip)

If you want to prevent `Co-Authored-by` from being added due to other tools besides Copilot or Git's own settings, you should check your Git hooks or commit templates. However, most recently reported cases are due to the VS Code Copilot settings mentioned above.

## Verifying Settings and Testing

After changing the settings, try modifying a simple code and opening the commit message window again. You will see that the `Co-Authored-by: GitHub Copilot ...` text is no longer automatically generated.

## Conclusion

While AI tools improve development productivity, they sometimes operate differently from the user's intent. If you want to clarify your own code contributions or maintain a clean commit history, try applying the settings above.

On this technical blog, we cover various practical topics such as these development tool tips, Next.js, building MCP servers, and designing AI agent teams. If you have any questions or need help, please leave a comment at any time.

Happy Coding!