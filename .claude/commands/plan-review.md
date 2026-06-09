---
name: plan-review
description: Invoke the PlanReview agent to validate plan quality before implementation.
argument-hint: <optional-additional-context>
model: sonnet
hooks:
  PreToolUse:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/review.py plan"
---

## Overview

Invoke 1 `PlanReview` agent to evaluate the plan across 4 dimensions (clarity, completeness, feasibility, risk) and gate advancement on a Pass/Fail verdict. Findings drive any required plan revision; Confidence Score is reported alongside but does not gate.

## Instructions

1. Launch 1 `PlanReview` agent with:
   - The plan written to `.claude/plans/plan.md`
   - The originating user request / task context
   - Explicit instruction to evaluate all 4 dimensions
   - Explicit instruction to emit `Verdict` (Pass | Fail) in the Summary and end the response with a `Confidence Score`
2. Parse the reviewer's output for `Verdict` and `Confidence Score`. The expected format:
   ```
   Verdict: Pass | Fail
   ...
   Confidence Score: [0-100]
   ```
3. If `Verdict` or `Confidence Score` is missing or malformed, **continue the same reviewer subagent** (via `SendMessage` with the existing agent ID) and ask it to re-emit its review with the missing field added in the correct format. Do **not** spawn a fresh `PlanReview` — the existing subagent already has the review context loaded; a new one would re-do all the analysis and produce uncorrelated findings. Allow up to 2 course-correction attempts; if the third response is still malformed, halt and escalate.
4. Act on the verdict:
   - **Pass** → approve the plan; advance to the `/write-code` phase
   - **Fail** → revise the plan per the findings, then re-review
   - **Pass + Confidence < 60** → surface a yellow flag in the phase summary; do not block advance
5. If a re-review is required, repeat step 1 with the revised plan. Stop after 3 total review iterations.

## Rules

- The plan must be written to `.claude/plans/plan.md` before invoking this phase
- When revising on `Fail`, only edit the plan file referenced in the findings — no new files, no scope expansion
- The verdict alone signals _whether_ to revise; the reviser must consult the findings list (severity + section refs) to decide _what_ to revise
- `Confidence Score` is reported, not gated on — do not auto-trigger re-review purely because confidence is low (re-running the same model on the same plan is correlated noise)
- Maximum 3 review iterations; halt and escalate if Fail persists after the third pass
- Do not modify the reviewer's output; pass findings through to the reviser verbatim
- When the reviewer's output is missing `Verdict` or `Confidence Score`, course-correct by continuing the **same** subagent via `SendMessage`. Never spawn a fresh `PlanReview` to retry — the original subagent already has the review context and a fresh one would discard it
- Course-correction is capped at 2 attempts (3 total responses from the same subagent) before halting and escalating

## Acceptance Criteria

- Reviewer output contains both a `Verdict` line and a trailing `Confidence Score` line
- If either field was missing on first emit, course-correction continued the same subagent (not a fresh one) and resolved within ≤ 2 attempts
- All 4 dimensions are addressed in the reviewer's output (findings or explicit "no issues found in scope")
- On `Pass`: phase advances and `/write-code` is invoked
- On `Fail`: the plan is revised per the findings, then a re-review is launched
- On `Pass` with `Confidence Score < 60`: a yellow-flag note appears in the phase summary
- Review loop terminates within 3 iterations regardless of outcome
- Reviser edits stay scoped to the findings — no unrelated changes introduced during revision
