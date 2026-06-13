---
name: update-context
description: Bring CLAUDE.md and the persistent memory directory back in sync with the actual state of the codebase. Use whenever the user asks to update CLAUDE.md, MEMORY.md, memory, docs, or project context; after finishing a feature, refactor, dependency change, or tooling change ("we just added X — update the docs"); at the end of a work session when the repo state has moved; or any time a claim in CLAUDE.md or a recalled memory no longer matches reality — even if the user doesn't name the files explicitly.
---

# Update Context — sync CLAUDE.md and memory with reality

## Why this matters

CLAUDE.md and the memory index are loaded into context at the start of **every future session**. A stale claim there ("there is no test runner", "X is not installed yet", "this file is sample data") becomes a wrong belief that every future session starts from — worse than saying nothing at all. The job of this skill is to find claims that drifted from reality and fix them with the smallest possible edit, not to rewrite documents.

## Division of labor — decide where a fact belongs before writing it

- **CLAUDE.md** (repo root, checked in): facts about the project that a fresh session needs and that are true for anyone working in this repo — current state, commands, architecture, constraints, gotchas. If a fact is derivable from the repo but too expensive to rediscover every session, it belongs here.
- **Memory directory** (`~/.claude/memory/` by default — one file per fact plus a `MEMORY.md` index; if the session indicates a different memory location, use that): facts **not** derivable from the repo — user preferences, corrections and feedback, decisions made in conversation, external context (accounts, tokens, environments).
- Never record the same fact in both. If it's visible in the repo, it does not belong in memory; if it's personal to the user, it does not belong in CLAUDE.md.

## Workflow

### 1. Establish what actually changed

Gather evidence before touching anything:

- The current conversation — what was just built, changed, or decided.
- `git status` and `git diff --stat` for uncommitted work.
- Commits since CLAUDE.md was last touched: `git log -1 --format=%H -- CLAUDE.md`, then `git log --oneline <that-hash>..HEAD`.
- A quick look at ground truth that often drifts: `package.json` scripts and dependencies, top-level directory layout, CI workflow files.

### 2. Audit CLAUDE.md claim by claim

Read CLAUDE.md and treat every factual claim as a hypothesis to test against the repo. The claims most likely to be stale:

- **"Current state" claims** — "the app is a minimal scaffold", "only X exists so far".
- **Negative claims** — "there is no npm test yet", "Y is planned but not installed". These rot the moment someone adds the thing.
- **Commands** — does each documented command still exist and work as described?
- **Paths, versions, counts** — do the named files and directories still exist?

Verify each suspicious claim directly (read the file, list the directory, check `package.json`) rather than trusting the conversation summary alone. Claims you cannot verify from the repo (external services, product decisions) — leave untouched.

### 3. Audit the memory index

Read the memory directory's `MEMORY.md`. For every entry that the change could plausibly touch, open the memory file and check it against reality:

- **Stale memory** → update the file body (keep its frontmatter format, matching sibling files) and fix its one-line index entry.
- **Invalidated memory** → delete the file **and** its index line together; never leave a dangling link.
- **New memory** → only for durable, non-repo facts that surfaced this session (user feedback, a decision, an environment gotcha). Repo state changes are never new memories — they go in CLAUDE.md or nowhere.

### 4. Apply minimal edits

- Edit CLAUDE.md **in place**, preserving its existing structure, headings, voice, and formatting conventions. The diff should touch only stale lines.
- Describe the **new current state as timeless truth**, never the transition. "We recently added Vitest" is wrong; "`npm test` runs the Vitest unit suite" is right. Words like "now", "recently", "just added", "new" in your edits are red flags — future sessions read this file with no sense of when it was written.
- Do not append a changelog or history section; git is the changelog.
- Restraint is success: if a document is still accurate, changing nothing is the correct outcome. Don't pad the update with rewordings of lines that were already true.
- If no CLAUDE.md exists, say so and offer `/init` rather than inventing one wholesale.

### 5. Report

Tell the user, concretely:

- Each CLAUDE.md claim fixed: what it said → what it says now.
- Each memory updated, deleted, or added, and why.
- What you checked and confirmed still accurate (so they know the audit happened, not just the edits).

## What not to do

- Don't rewrite or restructure documents wholesale — smallest diff that restores truth.
- Don't add session-specific or transient details (in-flight branch names, TODOs, temporary states).
- Don't write a fact you didn't verify. If the user says "we added X", confirm X is actually in the repo before documenting it.
- Don't grow CLAUDE.md with everything that's true — only facts that would change what a fresh session does. When in doubt, leave it out.
