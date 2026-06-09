---
name: test
description: this is a test
argument-hint: <decision-context>
model: haiku
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          if: Bash("pytest *)
          command: "echo $ >> test.log"
          timeout: 120
---

Call @"Explore (agent)" and say hello! Note Agent not Skill. Instruct it to not do any work. This is a test.
