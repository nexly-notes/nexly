export const meta = {
  name: 'initial-backlog',
  description: 'Developers + a Product Owner collaborate to design the LEAN (ungroomed) product backlog and write it to project/backlog.json (scope -> survey -> design -> critique -> finalize -> render -> verify). This is phase 1 of the two-workflow backlog flow: a Scope pass discovers the project name, scope contract and developer domains from .github/config.json and the project specs; domain developers then survey and adversarially critique while the Product Owner designs a LEAN SELECTION of stories (each story: title/description/priority only). Stories carry NO id — identity is the GitHub issue number minted later by convert, and the title is the stable re-link key (unique across stories). The build order is committed HERE as a foundation-first sequence: the ORDER of the stories IS the build order (carried by array position). The workflow RENDERS the selection into project/backlog.json as an UNGROOMED file (3-key stories — title/description/priority), VALIDATES it with the lenient projects validator (lean backlogs pass; titles must be unique), regenerates project/backlog.md, and adversarially VERIFIES the written file is faithful to the lean design (repairing on drift). The separate final-backlog workflow grooms this output in place into the full backlog — it never mints ids itself but PRESERVES any issue numbers a convert wrote back, and it authors dependencies (blocked_by) during grooming once issue numbers exist (otherwise they are added via the convert two-pass flow). Optional args: { instruction, phase, domains, dates } — all optional; with none, it auto-discovers everything.',
  whenToUse: 'Run the FIRST half of the /backlog flow as a multi-agent collaboration on any project: produce the LEAN, ungroomed product backlog at project/backlog.json so a human can review/edit it before grooming. Pair it with the final-backlog workflow (phase 2) which reads this lean backlog and grooms it in place. Use this when you want the story selection (titles, descriptions, priorities) in committed foundation-first build order, without the buildable grooming detail yet.',
  phases: [
    { title: 'Scope', detail: 'Tech lead discovers project, scope contract, developer domains, dates' },
    { title: 'Survey', detail: 'Developer agents digest the specs by domain (candidate work, hard dependencies, scope traps)' },
    { title: 'Design', detail: 'Product Owner drafts the LEAN selection — title/description/priority only, in foundation-first order (no ids)' },
    { title: 'Critique', detail: 'Developers adversarially review the lean draft (missing, scope-creep, priority, ordering, duplicates)' },
    { title: 'Finalize', detail: 'Product Owner finalizes the lean selection — the approved deliverable' },
    { title: 'Render', detail: 'Engineer writes the LEAN project/backlog.json (3-key stories), runs the lenient validator, regenerates backlog.md' },
    { title: 'Verify', detail: 'Adversarial QA confirms the lean file is faithful to the design and validates; repairs on drift' },
  ],
}

// ---------------------------------------------------------------------------
// Project-agnostic. Nothing about a specific product is hardcoded. Everything
// project-specific (name, in/out-of-scope contract, developer domains, dates)
// is discovered at runtime in the Scope phase from .github/config.json and the
// project's own specs, OR supplied via args.
//
// This is the UNGROOMED (lean) half of the backlog flow. It writes a lean
// project/backlog.json that is a pure SELECTION of stories (title/description/
// priority) — NO ids. Stories are never assigned an id: identity is the GitHub
// issue number minted by convert, and the title is the stable re-link key
// (unique across stories). The foundation-first build order is COMMITTED here —
// the order of the stories IS the build order (carried by array position). The
// separate final-backlog workflow grooms each story in place; it preserves any
// issue numbers a convert wrote back and authors dependencies (blocked_by)
// during grooming once those numbers exist (else via the convert two-pass flow).
//
// Optional args (all optional):
//   args.instruction : a <backlog-focus> / direction that governs scope + sources
//                      (takes precedence over default spec discovery)
//   args.phase       : specs phase folder under project/specs/<phase>/ (default 'mvp')
//   args.domains     : force the developer domains [{key, role}, ...]
//   args.dates       : force the window { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' }
// ---------------------------------------------------------------------------

const instruction = (args && args.instruction) || ''
const specPhase = (args && args.phase) || 'mvp'
const domainsOverride = args && args.domains
const datesOverride = args && args.dates

const PRIORITY = { type: 'string', enum: ['P0', 'P1', 'P2'] }

// Generic fallback if the Scope pass yields no domains.
const DEFAULT_DOMAINS = [
  { key: 'frontend', role: 'Frontend / UI engineer (client application, screens, state, styling, navigation)' },
  { key: 'backend', role: 'Backend / Data engineer (services, data model, persistence, validation)' },
  { key: 'integration', role: 'Integration / API engineer (API contracts, external services, auth wiring)' },
  { key: 'platform', role: 'Platform / Delivery & QA engineer (build, CI, testing, performance, deploy)' },
]

// ---------------------------------------------------------------------------
// Shared, reusable grounding text — parameterised by the discovered scope.
// ---------------------------------------------------------------------------

// The foundation-first build order. In the lean phase it is used to COMMIT the
// story ORDER (array position == build order): each group unblocks the ones
// after it, so the backlog reads top-to-bottom in the order the work is built.
function buildOrderRules() {
  return `FOUNDATION-FIRST BUILD ORDER (groups, each unblocking the ones after it; within a group, order by priority):
1 Project setup -> 2 App structure -> 3 Database & models -> 4 API contracts -> 5 Backend skeleton ->
6 Frontend screens (mock data) -> 7 Feature implementation -> 8 Frontend<->backend integration ->
9 Auth & permissions -> 10 Test & debug -> 11 Polish & optimize -> 12 Deploy & release.
- Skip groups the specs do not justify; never invent scope to fill one. A group may map to several stories.
- Map each story to the EARLIEST group it genuinely belongs to.
- A real hard dependency may override the natural group order (e.g. a security model like per-user RLS before any data feature) — commit that order here, state the reason in the story description, and flag non-obvious moves in open_questions.`
}

// Lean field rules. Used by survey/design/critique/finalize. The lean backlog is
// a pure SELECTION: title/description/priority, with NO id. Identity is the
// GitHub issue number (minted later by convert); the title is the stable re-link
// key (unique across stories). The foundation-first build order is committed here
// (array position == build order). Grooming and dependencies come later.
function leanRules() {
  return `LEAN BACKLOG (the ungroomed selection — this stage ONLY) — each story carries EXACTLY:
- title     : short imperative title; this is the stable RE-LINK KEY, so it must be UNIQUE across stories
- description: one or two sentences of context (enough to judge priority; no implementation detail)
- priority  : P0 / P1 / P2 (case-sensitive)
NO id — a story is NEVER assigned an id; identity is the GitHub issue number minted later by convert. NO grooming fields yet: the separate final-backlog workflow grooms each story in place (goal / notes / tasks / acceptance_criteria / labels / size / points) and authors dependencies (blocked_by) once a convert has minted issue numbers (else via the convert two-pass flow). COMMIT the foundation-first build order NOW: the ORDER of the stories IS the build order (carried by array position) — list them in that order.

${buildOrderRules()}`
}

function grounding(scope, rules = leanRules()) {
  const sources = (scope.sources || []).map((s) => '- ' + s).join('\n')
  return `PROJECT: ${scope.project_name}

SCOPE CONTRACT (distilled from THIS project's specs — the source of truth, NOT any code scaffold):
${scope.scope_summary}

SOURCES (read in full for detail):
${sources}

${rules}`
}

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const SCOPE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['project_name', 'dates', 'sources', 'scope_summary', 'domains', 'open_questions'],
  properties: {
    project_name: { type: 'string' },
    dates: {
      type: 'object', additionalProperties: false, required: ['start', 'end'],
      properties: { start: { type: 'string' }, end: { type: 'string' } },
    },
    sources: { type: 'array', items: { type: 'string' } },
    scope_summary: { type: 'string' },
    domains: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['key', 'role'],
        properties: { key: { type: 'string' }, role: { type: 'string' } },
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
}

const DIGEST_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['domain', 'candidate_stories', 'hard_dependencies', 'scope_warnings'],
  properties: {
    domain: { type: 'string' },
    candidate_stories: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['working_title', 'spec_refs', 'rationale', 'suggested_group', 'suggested_priority'],
        properties: {
          working_title: { type: 'string' },
          spec_refs: { type: 'array', items: { type: 'string' } },
          rationale: { type: 'string' },
          suggested_group: { type: 'string' },
          suggested_priority: PRIORITY,
        },
      },
    },
    hard_dependencies: { type: 'array', items: { type: 'string' } },
    scope_warnings: { type: 'array', items: { type: 'string' } },
  },
}

// LEAN backlog schema: a pure selection. Story items carry only
// title/description/priority — NO id (stories are never assigned an id).
const LEAN_BACKLOG_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['project', 'description', 'dates', 'stories', 'open_questions'],
  properties: {
    project: { type: 'string' },
    description: { type: 'string' },
    dates: {
      type: 'object', additionalProperties: false, required: ['start', 'end'],
      properties: { start: { type: 'string' }, end: { type: 'string' } },
    },
    stories: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'description', 'priority'],
        properties: {
          title: { type: 'string' },
          description: { type: 'string' },
          priority: PRIORITY,
        },
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
}

// Adversarial review schema for the LEAN phase. This pass reviews the lean
// selection, scope, priority, and the committed foundation-first ORDER (which is
// a lean-phase decision now — array position carries the build order). Grooming
// detail is NOT reviewed here (it is a final-backlog concern).
const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['reviewer_domain', 'missing_stories', 'scope_creep', 'priority_issues', 'ordering_issues', 'other', 'overall_assessment'],
  properties: {
    reviewer_domain: { type: 'string' },
    missing_stories: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['working_title', 'spec_refs', 'why'],
        properties: { working_title: { type: 'string' }, spec_refs: { type: 'array', items: { type: 'string' } }, why: { type: 'string' } },
      },
    },
    scope_creep: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['target', 'why'],
        properties: { target: { type: 'string' }, why: { type: 'string' } },
      },
    },
    priority_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['target', 'current', 'suggested', 'why'],
        properties: { target: { type: 'string' }, current: { type: 'string' }, suggested: { type: 'string' }, why: { type: 'string' } },
      },
    },
    ordering_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['target', 'problem', 'suggested_fix'],
        properties: { target: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    other: { type: 'array', items: { type: 'string' } },
    overall_assessment: { type: 'string' },
  },
}

// Result of the Render / Repair agent that actually writes the LEAN
// project/backlog.json. The lean backlog IS validated — the projects validator
// is lenient (title/description/priority pass) and enforces title uniqueness.
const RENDER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['wrote_path', 'story_count', 'validator_passed', 'validator_output', 'md_generated', 'notes'],
  properties: {
    wrote_path: { type: 'string' },
    story_count: { type: 'integer' },
    validator_passed: { type: 'boolean' },
    validator_output: { type: 'string' },
    md_generated: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

// Result of the adversarial Verify agent that reads the written LEAN file back.
// Stories have no id, so a mismatch locates the story by its title.
const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file_exists', 'story_count', 'validator_passed', 'mismatches', 'structural_issues', 'md_generated', 'faithful'],
  properties: {
    file_exists: { type: 'boolean' },
    story_count: { type: 'integer' },
    validator_passed: { type: 'boolean' },
    mismatches: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['story', 'field', 'issue'],
        properties: { story: { type: 'string' }, field: { type: 'string' }, issue: { type: 'string' } },
      },
    },
    structural_issues: { type: 'array', items: { type: 'string' } },
    md_generated: { type: 'boolean' },
    faithful: { type: 'boolean' },
  },
}

// ---------------------------------------------------------------------------
// Prompt builders
// ---------------------------------------------------------------------------

function scopePrompt() {
  const instr = instruction
    ? `A USER INSTRUCTION was given and TAKES PRECEDENCE over default spec discovery — it governs the backlog's scope, focus, and which sources to read:\n"""\n${instruction}\n"""\n`
    : 'No user instruction was given — fall back to the phase specs.\n'
  return `You are a pragmatic tech lead establishing the shared grounding a team will use to select a LEAN backlog (the ungroomed selection of stories; a separate workflow grooms it in place later). Read the repository and report a precise scope.
${instr}
Do all of the following by reading the repo:
1. PROJECT. Its name and a one-line product goal.
2. SOURCES. ${instruction
    ? 'The sources the user instruction points to (read them).'
    : `The active-phase specs under project/specs/${specPhase}/ — typically prd.md, design.md, tech-specs.md — plus project/roadmap.md and CLAUDE.md when present. If prd.md is missing and no instruction was given, record that in open_questions rather than guessing.`}
3. SCOPE CONTRACT. Read those sources and distill a compact but COMPLETE contract with two explicit halves:
   - IN-SCOPE: the features/requirements that must become stories, each tagged with its spec id(s)/section(s).
   - OUT-OF-SCOPE: anything present in the code scaffold or adjacent phases that must NOT get a story (this is what prevents scope creep).
   This contract is what every downstream agent will share — make it self-sufficient.
4. DOMAINS. Propose 3-5 developer domains that TOGETHER cover this project's whole surface, tailored to THIS project's actual stack and shape (not a fixed template). ${domainsOverride
    ? `Use exactly: ${JSON.stringify(domainsOverride)}.`
    : 'Each domain is a {key, role}: key is a short slug; role names the area plus its key technologies/responsibilities. Avoid overlap; cover the full stack.'}
5. DATES. ${datesOverride
    ? `Use start "${datesOverride.start}", end "${datesOverride.end}".`
    : 'Derive the delivery window (YYYY-MM-DD) from the specs/roadmap. If the specs do not pin dates, propose a sensible window and note the assumption in open_questions.'}

Return the structured scope. Be specific and trace claims to the specs.`
}

function surveyPrompt(d, scope) {
  return `You are a senior ${d.role}, helping a Product Owner build a product backlog for ${scope.project_name}. The backlog is selected LEAN first (this workflow) and then groomed into full detail later (the separate final-backlog workflow); this survey feeds the lean selection.
${grounding(scope)}

TASK (SURVEY phase) — from YOUR domain lens only, read the source specs in full, then report:
- candidate_stories: each buildable piece of work that should become a backlog story. For each: the spec id(s)/section(s) it traces to, a one-line rationale, the build-order GROUP it belongs to (use the group names above), and a suggested P0/P1/P2.
- hard_dependencies: real ordering constraints in your domain (e.g. "the auth/security model must exist before any data feature"). Be concrete — these ground the foundation-first ORDER committed in this lean phase, and the blocked_by edges added later during grooming.
- scope_warnings: anything in your domain that LOOKS in-scope from the code scaffold but is out-of-scope per the scope contract and must NOT get a story.

Stay in your domain. Trace every candidate to a spec line — drop anything you cannot. Do NOT author grooming detail here (tasks/acceptance_criteria/labels/size/points) — that comes in the separate grooming workflow; this survey feeds the lean selection.`
}

function designPrompt(scope, digests) {
  return `You are the PRODUCT OWNER. Select the LEAN product backlog for ${scope.project_name} — the ungroomed selection of stories, in committed foundation-first build order. The main agent will render your output into JSON verbatim, so your design IS the source of truth for content. Later these SAME stories will be groomed in place by the separate final-backlog workflow — so focus on WHICH stories exist, their priority, and their build ORDER (not on tasks/criteria/labels/size).
${grounding(scope)}

Ground your design in the specs (read the sources above) AND in the developer survey digests below. The digests are advisory technical input — you own every final content decision.

DEVELOPER SURVEY DIGESTS (JSON):
${JSON.stringify(digests, null, 2)}

Produce the lean backlog:
- One flat list of user stories, each just enough to prioritize. Cover EVERY in-scope spec item with at least one story; reject anything the specs do not justify; create NO stories for out-of-scope work.
- Each story carries ONLY: a short imperative title, a 1-2 sentence description, and P0/P1/P2. NO id and NO other fields — the grooming fields and dependencies are all added later.
- Keep every title UNIQUE — the title is the stable re-link key that convert uses to match issues, so two stories may never share a title.
- COMMIT the foundation-first build order: LIST the stories in build order (array position IS the build order), grounded in the build-order groups and the developers' hard_dependencies. Within a group, order by priority. A real hard dependency may override the natural group order — state the reason in that story's description.
- dates: ${datesOverride ? `start "${datesOverride.start}", end "${datesOverride.end}".` : `use the scope's window (start "${scope.dates.start}", end "${scope.dates.end}") unless the specs pin different dates; record any assumption in open_questions.`}
- open_questions: capture any ambiguity rather than silently choosing for the user.

Return the structured backlog.`
}

function critiquePrompt(d, scope, draft) {
  return `You are a senior ${d.role}, doing an ADVERSARIAL review of the Product Owner's DRAFT lean backlog for ${scope.project_name}, from your domain lens. This pass reviews the LEAN SELECTION — which stories exist, scope, priority, and the committed foundation-first ORDER (array position is the build order). Grooming detail (tasks/criteria/labels/size/points) is NOT in scope here. Your job is to find what is wrong, not to praise.
${grounding(scope)}

DRAFT BACKLOG (JSON):
${JSON.stringify(draft, null, 2)}

Hunt, scoped to your domain (${d.role}):
- missing_stories: in-scope spec work that has NO story (cite the spec id(s)/section(s)).
- scope_creep: stories that build out-of-scope work, or that smuggle in grooming detail (tasks/criteria/labels/size/points) PREMATURELY — this pass reviews the LEAN selection only.
- priority_issues: P0/P1/P2 that is wrong vs the MVP critical path and the spec priorities.
- ordering_issues: stories placed out of foundation-first build order (array position is the build order) — name the story by title and a concrete fix (e.g. "X must come before Y because …"), grounded in the build-order groups and hard dependencies.
- other: duplicate or non-unique TITLES (the title is the re-link key and must be unique), overlapping stories, vague descriptions, dates issues.
Cite spec evidence for every finding — no vague complaints. If a dimension is genuinely clean, return it as an empty array. End with a one-line overall_assessment.`
}

function finalizePrompt(scope, draft, critiques) {
  return `You are the PRODUCT OWNER. Revise your draft lean backlog for ${scope.project_name} into the FINAL lean version, incorporating the developers' critique where it is correct and defensible against the specs. This is the END of the lean phase.
${grounding(scope)}

YOUR DRAFT (JSON):
${JSON.stringify(draft, null, 2)}

DEVELOPER CRITIQUES (JSON):
${JSON.stringify(critiques, null, 2)}

Revision rules:
- Accept critique the specs support; reject critique that conflicts with the specs or scope, and record any real disagreement (and your resolution) in open_questions.
- Keep the backlog LEAN — only title, description, priority per story; NO id and no grooming fields (those are all added later in grooming).
- Keep every title UNIQUE (the title is the re-link key) and keep the stories in committed foundation-first build ORDER (array position is the build order).
- Re-verify that every story traces to a spec item, there is zero out-of-scope leakage, no duplicate titles, and dates are set.
Return the FINAL structured backlog. This is the approved LEAN selection; the workflow will now RENDER it to project/backlog.json (ungroomed, no ids), validate it, and the separate final-backlog workflow grooms it in place.`
}

// The render/verify agents need filesystem + shell tools (Write, Bash, Read),
// which the workflow SCRIPT itself does not have — so this work is delegated to
// general-purpose subagents. This phase writes a LEAN (ungroomed) backlog: a
// pure selection with no ids. The projects validator is LENIENT — a lean backlog
// (title/description/priority) passes — and it enforces title uniqueness, so it
// IS run here. The markdown generator renders lean stories cleanly, with the
// groomed sections simply omitted.
function renderLeanRules() {
  return `Operate from the repository ROOT (run \`git rev-parse --show-toplevel\` and work there).

WRITE project/backlog.json as a LEAN (ungroomed) backlog — the deliverable of this workflow:
- Top-level keys, in order: project, description, dates { start, end }, stories. Include NO other top-level key — in particular do NOT write open_questions.
- Each story object has EXACTLY these 3 keys, IN THIS ORDER: title, description, priority.
  - copy CHARACTER-FOR-CHARACTER from the lean design below. Do NOT reword, summarize, re-punctuate, normalize quotes/dashes, or reorder anything. Preserve em-dashes, parentheses, slashes, and spec ids verbatim.
  - Add NO id, NO status, NO issue_number, and NO groomed field (goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points) — this backlog is intentionally UNGROOMED; the separate final-backlog workflow adds the detail (and never assigns an id).
- Preserve the story order EXACTLY as given — the order IS the committed foundation-first build order (array position carries the build order); do NOT reshuffle it.
- Pretty-print with 2-space indentation; end with a trailing newline.

THEN validate with the projects validator: run \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`. It must print "Backlog validation passed". The validator is LENIENT — a lean backlog (title/description/priority only) passes — and it ALSO enforces that every title is UNIQUE (the title is the re-link key) and that priority is a correctly-cased enum. If it errors, fix the JSON and re-run until it passes. Set validator_passed and validator_output from its actual stdout/stderr. (If that validator does not exist in this repo, set validator_passed=false and explain in notes.)

THEN regenerate the readable view: if .claude/skills/backlog/scripts/backlog-to-md.py exists, run \`python3 .claude/skills/backlog/scripts/backlog-to-md.py\` (it writes project/backlog.md and renders lean stories cleanly, with the groomed sections simply omitted); set md_generated accordingly. If it does not exist, set md_generated=false and note it.`
}

function renderLeanPrompt(leanFinal) {
  return `You are a release engineer. Render the FINAL lean backlog (provided as JSON below) into the deliverable file project/backlog.json as an UNGROOMED backlog, validate it with the projects validator, then regenerate the markdown view. Do NOT assign ids and do NOT groom.

${renderLeanRules()}

FINAL lean backlog to render (JSON — note: ignore its open_questions field, it does NOT go in the file):
${JSON.stringify(leanFinal, null, 2)}

Return the structured render result.`
}

function verifyLeanPrompt(leanFinal) {
  return `You are an adversarial QA reviewer. project/backlog.json was just written from the CANONICAL lean design below as an UNGROOMED backlog. Assume it is WRONG until proven right — your job is to catch any drift or invalidity.

From the repository root:
1. Read project/backlog.json FROM DISK (the actual file — do not trust memory).
2. Re-run the validator: \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`; record whether it passes in validator_passed.
3. Compare the file against the CANONICAL lean design below (match stories by position, confirming the title agrees):
   - story_count must equal the canonical story count.
   - For EACH canonical story, report any drift as a mismatch { story, field, issue } where "story" is the title:
     - title, description, priority — IDENTICAL character-for-character (any rewording, truncation, added/removed/normalized punctuation, changed dash/quote, or altered spec id is a mismatch).
   - Structural checks (report as structural_issues):
     - Every story has EXACTLY these 3 keys, IN THIS ORDER: title, description, priority.
     - NO id, status, issue_number, or groomed field (goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points) appears on any story.
     - priority is a valid, correctly-cased enum (P0, P1, P2).
     - Every title is UNIQUE across stories (the title is the re-link key — duplicates are a structural issue).
     - The story order in the file matches the canonical order (the committed foundation-first build order must not be reshuffled at render time).
     - Top-level project, description, and dates { start, end } match the canonical.
     - The file does NOT contain an open_questions key, nor any top-level key beyond project/description/dates/stories.
   - Confirm project/backlog.md was regenerated (set md_generated).
Put per-story field drift in mismatches; put everything from the structural checks in structural_issues. Set faithful=true ONLY when there are zero mismatches AND zero structural_issues AND the validator passes.

CANONICAL lean design (JSON):
${JSON.stringify(leanFinal, null, 2)}

Return the structured verification.`
}

function repairPrompt(leanFinal, verify) {
  return `You are a release engineer fixing project/backlog.json. A QA pass found it is not yet a faithful, valid render of the canonical lean design. Fix it.

QA FINDINGS (JSON):
${JSON.stringify({ validator_passed: verify.validator_passed, mismatches: verify.mismatches, structural_issues: verify.structural_issues }, null, 2)}

Re-render project/backlog.json from scratch so it EXACTLY matches the canonical lean design, applying every rule precisely (the 3 lean keys per story in order — title, description, priority — with NO id, NO status, NO issue_number, and NO groomed fields), and make it pass the validator:

${renderLeanRules()}

CANONICAL lean design (JSON — ignore its open_questions field, it does NOT go in the file):
${JSON.stringify(leanFinal, null, 2)}

Return the structured render result.`
}

// ---------------------------------------------------------------------------
// Orchestration. Barriers between phases are deliberate: each Product Owner
// pass needs the COMPLETE set of prior-stage outputs (all digests / all
// critiques) to synthesize across domains — the legitimate barrier case.
// ---------------------------------------------------------------------------

phase('Scope')
log(instruction ? 'Scoping from the user instruction' : `Scoping from project/specs/${specPhase}/ + repo config`)
const scope = await agent(scopePrompt(), { schema: SCOPE_SCHEMA, phase: 'Scope', label: 'scope' })

let domains = (domainsOverride && domainsOverride.length ? domainsOverride : scope.domains) || []
if (!domains.length) domains = DEFAULT_DOMAINS
domains = domains.slice(0, 6)
log(`Project "${scope.project_name}" · ${domains.length} developer domains (no ids — identity is the issue number)`)

phase('Survey')
const digests = (await parallel(
  domains.map((d) => () => agent(surveyPrompt(d, scope), { schema: DIGEST_SCHEMA, phase: 'Survey', label: `survey:${d.key}` })),
)).filter(Boolean)

phase('Design')
log(`Product Owner drafting the lean selection from ${digests.length} digests`)
const draft = await agent(designPrompt(scope, digests), {
  agentType: 'Product Owner', schema: LEAN_BACKLOG_SCHEMA, phase: 'Design', label: 'po:draft',
})
log(`Lean draft has ${draft.stories.length} stories`)

phase('Critique')
log('Developers adversarially reviewing the lean draft')
const critiques = (await parallel(
  domains.map((d) => () => agent(critiquePrompt(d, scope, draft), { schema: CRITIQUE_SCHEMA, phase: 'Critique', label: `critique:${d.key}` })),
)).filter(Boolean)

phase('Finalize')
log(`Product Owner finalizing the lean selection with ${critiques.length} critiques`)
const leanFinal = await agent(finalizePrompt(scope, draft, critiques), {
  agentType: 'Product Owner', schema: LEAN_BACKLOG_SCHEMA, phase: 'Finalize', label: 'po:final',
})
log(`Lean backlog finalized: ${leanFinal.stories.length} stories, ${leanFinal.open_questions.length} open questions`)

// Render the LEAN design into project/backlog.json (ungroomed, no ids), validate
// it with the lenient projects validator, then adversarially verify the written
// file is faithful to the design, repairing on drift (up to 2 attempts).
// Delegated to general-purpose agents because the script has no FS/shell access.
phase('Render')
log('Rendering the final lean backlog into project/backlog.json (ungroomed, no ids)')
let render = await agent(renderLeanPrompt(leanFinal), {
  agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: 'render',
})

phase('Verify')
log('Adversarially verifying the written lean backlog.json is faithful and valid')
let verify = await agent(verifyLeanPrompt(leanFinal), {
  agentType: 'general-purpose', schema: VERIFY_SCHEMA, phase: 'Verify', label: 'verify',
})

let repairs = 0
while (
  verify &&
  (!verify.faithful || !verify.validator_passed || verify.mismatches.length || verify.structural_issues.length) &&
  repairs < 2
) {
  repairs++
  log(`Repairing lean backlog.json (attempt ${repairs}) — ${verify.mismatches.length} mismatch(es), ${verify.structural_issues.length} structural issue(s)`)
  render = await agent(repairPrompt(leanFinal, verify), {
    agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: `repair:${repairs}`,
  })
  verify = await agent(verifyLeanPrompt(leanFinal), {
    agentType: 'general-purpose', schema: VERIFY_SCHEMA, phase: 'Verify', label: `verify:${repairs}`,
  })
}

log(
  verify && verify.faithful
    ? `lean backlog.json written, validated & verified: ${verify.story_count} stories. Run the final-backlog workflow to groom it.`
    : 'lean backlog.json written but verification flagged issues — see result.verify',
)

return { leanFinal, draft, critiques, digests, scope, render, verify }
