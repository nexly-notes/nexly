---
name: rules
description: Phase between /design and /backlog. Synthesize prd.md and design.md into one rule file per detected topic under .claude/rules/.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
argument-hint: <optional-extra-focus>
model: sonnet
---

**Goal**: Translate `prd.md` and `design.md` into a set of Claude Code rule files under `.claude/rules/` — one path-scoped file per detected topic — so future implementation work loads enforceable, traceable constraints automatically.

## Context

Phase between `/design` and `/backlog` in the `/specs` pipeline. Each rule file translates spec content into concrete, verifiable instructions that load into Claude's context per the Claude Code memory model (see <https://code.claude.com/docs/en/memory>). Rules with `paths:` YAML frontmatter only load when Claude works on matching files; rules without it load unconditionally. **One topic = one file**, so a single run typically produces several files.

| Depends on | Path                      |
| :--------- | :------------------------ |
| PRD        | `project/specs/prd.md`    |
| Design     | `project/specs/design.md` |

## Instructions

1. **Verify dependencies exist**. If either `prd.md` or `design.md` is missing, stop and report the missing dependency to the user — do not proceed.
2. **Ensure `.claude/rules/` exists**. Create the directory if missing.
3. **Read both spec files** in full. Treat their accepted decisions, conventions, accessibility requirements, naming/structure constraints, and stack choices (PRD §5 Constraints) as the authoritative source for rule content. `$ARGUMENTS` (if non-empty) narrows the focus but never invents content the specs don't already imply.
4. **Identify topics**. Cluster spec content into distinct rule topics (e.g. `api-design`, `database-access`, `auth`, `accessibility`, `testing`, `python-style`, `react-components`, `naming`). Each topic must be self-contained (~3–8 verifiable bullets) and map cleanly to either a path/extension scope or to "applies everywhere".
5. **Decide path-scoping per topic** without re-asking:
   - If a topic clearly belongs to a directory or extension (e.g. React components → `src/components/**/*.{tsx,jsx}`), emit `paths:` frontmatter with verified globs.
   - Verify every glob with `Glob` against the repo. Drop or rewrite any glob that matches zero files.
   - Topics that genuinely span the whole repo (e.g. naming, commit conventions) carry no frontmatter.
6. **Resolve filename collisions**. For every existing `.claude/rules/<topic>.md`, use `AskUserQuestion` to choose overwrite / merge / skip. Never silently overwrite.
7. **Show the topic plan** via `AskUserQuestion` before writing anything: list every proposed filename, its scope (glob list or "unconditional"), the rule count, and a one-line topic summary. Get user approval.
8. **Write each approved rule file** to `.claude/rules/<topic>.md` with `Write`. Each file: optional `paths:` frontmatter, H1 title, bulleted body, ≤40 lines total.
9. **Validate** every written file: re-read it, confirm valid YAML (when present), an H1, and an imperative bulleted body — no leftover placeholders, no prose paragraphs.
10. **Report** to the user: each file path, scope, rule count, and which spec sections sourced each topic.

## Rules

- NEVER create rule files if any dependency spec is missing — guardrails enforce phase order.
- NEVER write outside `.claude/rules/`.
- NEVER silently overwrite an existing rule file; resolve collisions via `AskUserQuestion`.
- NEVER attach `paths:` frontmatter unless the topic genuinely scopes to a path/extension.
- NEVER commit a glob to `paths:` without verifying it matches real files via `Glob`.
- NEVER fabricate rules; every bullet must trace to a specific section or decision in prd/design.
- One topic per file. If two concerns blur into one bullet list, split them into separate files.
- Rule bullets must be specific, imperative, and verifiable ("Use 2-space indentation", not "Format code nicely").
- Cap each rule file at ~40 lines.
- Use `AskUserQuestion` for every clarification — never plain-text questions.

## Acceptance Criteria

- All three dependency specs were read in full.
- `.claude/rules/` exists and contains one file per approved topic.
- Each file has a kebab-case filename, valid frontmatter (when path-scoped), an H1, and an imperative-bulleted body.
- Every glob in any `paths:` field was verified via `Glob` to match at least one file.
- No rule file exceeds ~40 lines.
- User approved the topic plan via `AskUserQuestion` before any write.
- Report enumerates each new/updated file with its source spec section(s).

## References

- **Claude Code rules docs**: <https://code.claude.com/docs/en/memory#organize-rules-with-claude-rules>
- **PRD input**: `project/specs/prd.md`
- **Design input**: `project/specs/design.md`
- **Project rules dir**: `.claude/rules/`
