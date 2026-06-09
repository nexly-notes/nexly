---
name: code-review
description: Invoke the CodeReviewer agent to review code quality and correctness.
argument-hint: <optional-additional-context>
model: sonnet
---

## Overview

Invoke 1 `CodeReviewer` agent to evaluate the implementation across 8 aspects (correctness, tests, performance, security, readability, style & standards, maintainability, edge cases & reliability) and gate advancement on a Pass/Fail verdict. Findings drive any required revision; Confidence Score is reported alongside but does not gate.

## Instructions

1. Launch 1 `CodeReviewer` agent with:
   - The code files written in the `/implement` phase
   - The implementation plan for context
   - Explicit instruction to evaluate all 8 aspects
   - Explicit instruction to emit `Verdict` (Pass | Fail) in the Summary and end the response with a `Confidence Score`
2. Parse the reviewer's output for `Verdict` and `Confidence Score`. The expected format:
   ```
   Verdict: Pass | Fail
   ...
   Confidence Score: [0-100]
   ```
3. If `Verdict` or `Confidence Score` is missing or malformed, **continue the same reviewer subagent** (via `SendMessage` with the existing agent ID) and ask it to re-emit its review with the missing field added in the correct format. Do **not** spawn a fresh `CodeReviewer` — the existing subagent already has the review context loaded; a new one would re-do all the analysis and produce uncorrelated findings. Allow up to 2 course-correction attempts; if the third response is still malformed, halt and escalate.
4. Act on the verdict:
   - **Pass** → approve the code; advance to the next phase
   - **Fail** → refactor the affected code per the findings, then re-review
   - **Pass + Confidence < 60** → surface a yellow flag in the phase summary; do not block advance
5. If a re-review is required, repeat step 1 with the revised code. Stop after 3 total review iterations.

## Rules

- Code must be written before invoking this phase
- When refactoring on `Fail`, only edit the code files referenced in the findings — no new files, no scope expansion
- The verdict alone signals _whether_ to revise; the reviser must consult the findings list (severity + line refs) to decide _what_ to revise
- `Confidence Score` is reported, not gated on — do not auto-trigger re-review purely because confidence is low (re-running the same model on the same code is correlated noise)
- Maximum 3 review iterations; halt and escalate if Fail persists after the third pass
- Do not modify the reviewer's output; pass findings through to the reviser verbatim
- When the reviewer's output is missing `Verdict` or `Confidence Score`, course-correct by continuing the **same** subagent via `SendMessage`. Never spawn a fresh `CodeReviewer` to retry — the original subagent already has the review context and a fresh one would discard it
- Course-correction is capped at 2 attempts (3 total responses from the same subagent) before halting and escalating

## Acceptance Criteria

- Reviewer output contains both a `Verdict` line and a trailing `Confidence Score` line
- If either field was missing on first emit, course-correction continued the same subagent (not a fresh one) and resolved within ≤ 2 attempts
- All 8 aspects are addressed in the reviewer's output (findings or explicit "no issues found in scope")
- On `Pass`: phase advances and the next phase is invoked
- On `Fail`: affected code is refactored per the findings, then a re-review is launched
- On `Pass` with `Confidence Score < 60`: a yellow-flag note appears in the phase summary
- Review loop terminates within 3 iterations regardless of outcome
- Reviser edits stay scoped to the findings — no unrelated changes introduced during refactor
