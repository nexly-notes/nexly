export const meta = {
  name: 'final-backlog',
  description: 'Developers + a Product Owner GROOM the lean (ungroomed) backlog IN PLACE into the final groomed backlog and write project/backlog.json in the full schema (scope -> survey -> load -> groom -> groom-critique -> groom-finalize -> resolve-deps -> render -> verify). This is phase 2 of the two-workflow backlog flow: a Scope pass re-discovers the project name, scope contract and developer domains; domain developers survey (their hard_dependencies ground the build order and the blocked_by edges); the workflow LOADS the project/backlog.json written by the initial-backlog workflow (title/description/priority) AND any issue numbers a prior convert wrote back, then the Product Owner grooms EVERY story IN PLACE — adding goal/notes/tasks/acceptance_criteria/labels (incl. >=1 work-type label)/size/points, and naming each story’s hard dependencies BY TITLE (blocked_by_titles) — with a developer critique + PO finalize sub-loop. Title, priority, and the committed foundation-first ORDER (array position) are FROZEN; no story is added, dropped, or reordered. The workflow PRESERVES each story’s issue_number (the GitHub identity minted by convert) and resolves the title-named dependencies to issue NUMBERS deterministically in code (matched by title; backward-only in build order, so the dependency graph is acyclic by construction). If issue numbers are not present yet (grooming ran before a convert), blocked_by falls back to [] and the intended dependencies are recorded by title in open_questions. The workflow then RENDERS the groomed backlog into project/backlog.json in the canonical groomed schema (key order per sample_structure.json), runs the projects validator (.github/scripts/projects/cli.py validate — lenient, but it enforces title uniqueness, the work-type-label rule, and that blocked_by entries resolve to in-file issue numbers), regenerates project/backlog.md, and adversarially VERIFIES the written file is faithful to the GROOMED design and validates (repairing if it drifted). Optional args: { instruction, phase, domains, dates, backlogPath, leanBacklog, scope, digests } — all optional; with none, it auto-discovers everything and reads the backlog from project/backlog.json.',
  whenToUse: 'Run the SECOND half of the /backlog flow after the initial-backlog workflow has produced project/backlog.json (and, in the convert-first flow, after a convert has minted issue numbers into it). It reads that selection and grooms it in place into the full, validated groomed backlog — keeping titles, priorities, and the committed foundation-first order unchanged, preserving any issue numbers, and authoring blocked_by from title-named dependencies whenever issue numbers are present. To chain it directly after initial-backlog without re-discovery, pass args.leanBacklog / args.scope / args.digests from that run.',
  phases: [
    { title: 'Scope', detail: 'Tech lead re-discovers project, scope contract, developer domains, dates' },
    { title: 'Survey', detail: 'Developer agents digest the specs by domain (hard dependencies ground the order + blocked_by edges)' },
    { title: 'Load', detail: 'Read project/backlog.json (title/description/priority + any issue numbers a convert wrote back)' },
    { title: 'Groom', detail: 'PO grooms EVERY story in place: goal/notes/tasks/acceptance_criteria/labels/size/points + blocked_by_titles (title + order frozen)' },
    { title: 'Groom Critique', detail: 'Developers adversarially review the groomed detail + dependencies per domain' },
    { title: 'Groom Finalize', detail: 'Product Owner revises the grooming into the final GROOMED backlog' },
    { title: 'Render', detail: 'Engineer writes project/backlog.json (issue numbers preserved, blocked_by resolved from titles), runs the validator, regenerates backlog.md' },
    { title: 'Verify', detail: 'Adversarial QA confirms the groomed file is faithful to the design and validates; repairs on drift' },
  ],
}

// ---------------------------------------------------------------------------
// Project-agnostic. Nothing about a specific product is hardcoded. Everything
// project-specific (name, in/out-of-scope contract, developer domains, dates)
// is discovered at runtime in the Scope phase from .github/config.json and the
// project's own specs, OR supplied via args.
//
// This is the GROOM half of the backlog flow. It reads project/backlog.json
// produced by the initial-backlog workflow (a selection: title/description/
// priority, in committed foundation-first order) — plus any issue_number a
// prior convert wrote back — and grooms every story IN PLACE into the full
// groomed backlog, then runs the validator. It does NOT reorder (the array
// position IS the build order) and it PRESERVES each story's issue_number (the
// GitHub identity minted by convert). The Product Owner names each story's hard
// dependencies BY TITLE (blocked_by_titles); the orchestration resolves those
// titles to issue NUMBERS deterministically (matched by title), enforcing that
// every blocker is EARLIER in the build order — so the dependency graph is a DAG
// by construction (no cycles). When issue numbers are not present yet (grooming
// ran before a convert), blocked_by falls back to [] and the intended
// dependencies are recorded by title in open_questions for a later convert pass.
//
// Optional args (all optional):
//   args.instruction : a <backlog-focus> / direction that governs scope + sources
//                      (takes precedence over default spec discovery)
//   args.phase       : specs phase folder under project/specs/<phase>/ (default 'mvp')
//   args.domains     : force the developer domains [{key, role}, ...]
//   args.dates       : force the window { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' }
//   args.backlogPath : path to the backlog to groom (default 'project/backlog.json')
//   args.leanBacklog : pass the backlog object directly (skip the disk Load)
//   args.scope       : pass the scope object directly (skip the Scope phase)
//   args.digests     : pass the developer survey digests directly (skip the Survey phase)
// ---------------------------------------------------------------------------

const instruction = (args && args.instruction) || ''
const specPhase = (args && args.phase) || 'mvp'
const domainsOverride = args && args.domains
const datesOverride = args && args.dates
const backlogPath = (args && args.backlogPath) || 'project/backlog.json'
const leanOverride = args && args.leanBacklog
const scopeOverride = args && args.scope
const digestsOverride = args && args.digests

const PRIORITY = { type: 'string', enum: ['P0', 'P1', 'P2'] }
const STATUS = { type: 'string', enum: ['Backlog', 'In Progress', 'Done'] }
const SIZE = { type: 'string', enum: ['XS', 'S', 'M', 'L', 'XL'] }

// Stories carry no id, so the work-type label is the SOLE carrier of issue type.
// Every groomed story's labels must include >=1 of these (validation.py
// WORK_TYPE_LABELS). Domain labels (backend/frontend/…) are allowed extras but
// do NOT satisfy the rule.
const WORK_TYPE_LABELS = ['feature', 'tech', 'bug', 'spike', 'chore', 'docs', 'review']

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

// The foundation-first build order. The lean backlog already COMMITS this order
// via array position; grooming preserves it. The survey uses it to classify
// candidate work into groups and to ground each story's dependencies.
function buildOrderRules() {
  return `FOUNDATION-FIRST BUILD ORDER (groups, each unblocking the ones after it; within a group, order by priority) — the lean backlog already commits this order via array position:
1 Project setup -> 2 App structure -> 3 Database & models -> 4 API contracts -> 5 Backend skeleton ->
6 Frontend screens (mock data) -> 7 Feature implementation -> 8 Frontend<->backend integration ->
9 Auth & permissions -> 10 Test & debug -> 11 Polish & optimize -> 12 Deploy & release.
- Skip groups the specs do not justify; never invent scope to fill one. A group may map to several stories.
- Map each story to the EARLIEST group it genuinely belongs to.
- A real hard dependency may override the natural group order (e.g. a security model like per-user RLS before any data feature) — the lean backlog already reflects that in its order; PRESERVE the order and ground each story's dependencies in it.`
}

// Lean field rules. Used by surveyPrompt's grounding, so the survey reasons about
// the selection (title/description/priority, in committed order) that this
// workflow grooms in place.
function leanRules() {
  return `BACKLOG (the selection this workflow grooms IN PLACE) — each story carries AT LEAST:
- title     : short imperative title; the stable RE-LINK KEY (unique across stories)
- description: one or two sentences of context (enough to judge priority; no implementation detail)
- priority  : P0 / P1 / P2 (case-sensitive)
- issue_number (when a convert has already run): the GitHub issue number — the story's IDENTITY. PRESERVE it; never change or invent it.
Its story ORDER is the committed foundation-first build order (array position). This workflow PRESERVES title/priority/order and the issue_number, and adds the grooming fields (goal / notes / tasks / acceptance_criteria / labels / size / points) plus each story's hard dependencies named BY TITLE.

${buildOrderRules()}`
}

// Groom field rules. Used by groom/groom-critique/groom-finalize. Grooming adds
// the buildable detail in place; it does NOT reorder and it works in TITLES, never
// issue numbers (the workflow attaches numbers deterministically by title).
function groomRules() {
  return `GROOMED BACKLOG SCHEMA — grooming turns the selection into the fully-detailed backlog IN PLACE. It does NOT reorder, and it NEVER sets issue numbers (the workflow attaches each story's GitHub issue number by title).
FROZEN (carry over verbatim from the selection, never change): title, description, priority, AND the story ORDER (array position is the committed foundation-first build order). Add NO story; drop NO story; do NOT reorder.
ADD to EVERY story (the groomed fields the validator checks when present):
- goal               : one non-empty sentence — the outcome this story delivers (distinct from the description's context).
- notes              : free-form string; MAY be "" (empty string) when there is nothing extra to say. Do NOT write the literal word "none".
- tasks              : list of >=1 concrete implementation steps (strings).
- acceptance_criteria: list of >=1 testable, observable pass conditions (strings) — each independently verifiable, no vague "works well".
- labels             : list of >=1 string labels. MUST include >=1 WORK-TYPE label from {${WORK_TYPE_LABELS.join(', ')}} — this is the SOLE carrier of issue type, so every story needs exactly one work type (feature for product work, tech for infra/refactor, spike for time-boxed investigation, chore/docs/review/bug as fitting). Domain labels (backend, frontend, …) are allowed EXTRAS but do NOT satisfy the work-type rule.
- size               : one of XS / S / M / L / XL (case-sensitive).
- points             : a number (story points). Keep it consistent with size.
- blocked_by_titles  : list of the EXACT titles (verbatim — the re-link key) of the stories this story DIRECTLY, HARD-depends on (the ones that MUST be built first). Use [] when there is no hard prerequisite. RULES: (1) every blocker MUST appear EARLIER in the build order (a lower array position) than this story — a foundation a story rests on is always built before it; never name a later story; (2) never name the story itself; (3) list only HARD blockers, omit soft/nice-to-have ordering; (4) ground each dependency in the survey hard_dependencies and the build order, and keep a one-line rationale for it in notes or open_questions. You work ONLY in titles — the workflow resolves these to GitHub issue numbers deterministically (and drops/flags any that point forward or to an unknown title).
status stays "Backlog". Do NOT set or mention issue numbers — the workflow attaches each story's issue_number by title (preserved from the convert).

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

// Schema for the backlog loaded from disk. Stories carry title/description/
// priority and, once a convert has run, an issue_number (the identity this
// workflow PRESERVES). Captures those plus the top-level project/description/
// dates carried forward into the groomed file.
const LOAD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['project', 'description', 'dates', 'stories'],
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
          // Present only after a convert has written numbers back; 0/absent otherwise.
          issue_number: { type: 'integer' },
        },
      },
    },
  },
}

// GROOMED (Product Owner output): story items carry the groomed content fields
// plus blocked_by_titles (dependencies named BY TITLE — the PO never handles
// issue numbers). JSON Schema enforces presence/type/enums and minItems on the
// lists, but it CANNOT express "title is unique", "labels contains >=1 work-type
// label", or "every blocker is an earlier story" — those are enforced by the
// groom prompts, the groom-critique, the deterministic dependency resolver, and
// (authoritatively) the python validator at Render. The workflow attaches
// issue_number and resolves blocked_by_titles -> blocked_by (numbers) before the
// file is written; neither appears in this PO-facing schema.
const GROOMED_BACKLOG_SCHEMA = {
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
        required: [
          'title', 'description', 'status', 'priority', 'goal', 'notes',
          'tasks', 'acceptance_criteria', 'labels', 'blocked_by_titles', 'size', 'points',
        ],
        properties: {
          title: { type: 'string', minLength: 1 },
          description: { type: 'string', minLength: 1 },
          status: STATUS,
          priority: PRIORITY,
          goal: { type: 'string', minLength: 1 },
          notes: { type: 'string' },
          tasks: { type: 'array', items: { type: 'string' }, minItems: 1 },
          acceptance_criteria: { type: 'array', items: { type: 'string' }, minItems: 1 },
          labels: { type: 'array', items: { type: 'string' }, minItems: 1 },
          // Dependencies named BY TITLE (the re-link key); resolved to issue numbers in code.
          blocked_by_titles: { type: 'array', items: { type: 'string' }, default: [] },
          size: SIZE,
          points: { type: 'number' },
        },
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
}

// Adversarial review schema for the GROOM phase (quality of the per-story
// detail AND the title-named dependencies). Each finding cites the story TITLE
// it targets and why it is wrong. Ordering is NOT reviewed (frozen from the lean
// phase), but dependencies ARE (they are authored here, by title).
const GROOM_CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'reviewer_domain', 'weak_tasks', 'weak_acceptance_criteria', 'label_issues',
    'sizing_issues', 'dependency_issues', 'empty_field_issues', 'other', 'overall_assessment',
  ],
  properties: {
    reviewer_domain: { type: 'string' },
    weak_tasks: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'problem', 'suggested_fix'],
        properties: { title: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    weak_acceptance_criteria: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'problem', 'suggested_fix'],
        properties: { title: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    label_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'problem', 'suggested_fix'],
        properties: { title: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    sizing_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'problem', 'suggested_fix'],
        properties: { title: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    dependency_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'problem', 'suggested_fix'],
        properties: { title: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    empty_field_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'field', 'problem'],
        properties: { title: { type: 'string' }, field: { type: 'string' }, problem: { type: 'string' } },
      },
    },
    other: { type: 'array', items: { type: 'string' } },
    overall_assessment: { type: 'string' },
  },
}

// Result of the Render / Repair agent that actually writes project/backlog.json.
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

// Result of the adversarial Verify agent that reads the written file back.
// Stories have no id, so a mismatch locates the story by its title.
const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file_exists', 'story_count', 'validator_passed', 'mismatches', 'structural_issues', 'faithful'],
  properties: {
    file_exists: { type: 'boolean' },
    story_count: { type: 'integer' },
    validator_passed: { type: 'boolean' },
    mismatches: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['title', 'field', 'issue'],
        properties: { title: { type: 'string' }, field: { type: 'string' }, issue: { type: 'string' } },
      },
    },
    structural_issues: { type: 'array', items: { type: 'string' } },
    faithful: { type: 'boolean' },
  },
}

// ---------------------------------------------------------------------------
// Deterministic dependency resolver. The Product Owner names dependencies BY
// TITLE (blocked_by_titles); this code is the SINGLE place issue numbers are
// handled. It (1) attaches each story's preserved issue_number by title, (2)
// resolves blocked_by_titles -> blocked_by issue numbers, dropping any edge that
// is a self-reference, names an unknown title, or points FORWARD in the build
// order (a blocker must be an earlier story) — every dropped edge is logged and
// recorded in open_questions, and the backward-only rule guarantees the graph is
// acyclic. When no issue numbers are present yet (grooming ran before a convert)
// it leaves blocked_by [] and records the intended dependencies by title in
// open_questions for a later convert pass. Returns the stories in canonical key
// order plus warnings + open-question additions.
// ---------------------------------------------------------------------------
function resolveDependencies(groomed, lean) {
  const titleToNumber = {}
  for (const s of (lean.stories || [])) titleToNumber[s.title] = s.issue_number || 0
  const haveNumbers = Object.values(titleToNumber).some((n) => n > 0)

  const indexByTitle = {}
  groomed.stories.forEach((s, i) => { indexByTitle[s.title] = i })

  const warnings = []
  const openQuestionsAdd = []

  const stories = groomed.stories.map((s, i) => {
    const num = titleToNumber[s.title] || 0
    const wanted = s.blocked_by_titles || []
    let blocked = []

    if (haveNumbers) {
      for (const t of wanted) {
        if (t === s.title) {
          warnings.push(`Dropped self-dependency on "${s.title}".`)
          continue
        }
        if (!(t in indexByTitle)) {
          warnings.push(`Dropped dependency "${s.title}" -> unknown title "${t}".`)
          openQuestionsAdd.push(`"${s.title}" was groomed to depend on "${t}", which is not a story title — review.`)
          continue
        }
        if (indexByTitle[t] >= i) {
          warnings.push(`Dropped forward dependency "${s.title}" -> "${t}" (blocker is not earlier in the build order).`)
          openQuestionsAdd.push(`"${s.title}" was groomed to depend on later/same-position story "${t}" — review the build order.`)
          continue
        }
        const bn = titleToNumber[t]
        if (!bn) {
          warnings.push(`Dropped dependency "${s.title}" -> "${t}" (blocker has no issue number yet).`)
          openQuestionsAdd.push(`"${s.title}" depends on "${t}", which has no issue number yet — author after the next convert.`)
          continue
        }
        blocked.push(bn)
      }
    } else if (wanted.length) {
      // No issue numbers yet: cannot author blocked_by; preserve intent by title.
      for (const t of wanted) {
        openQuestionsAdd.push(`"${s.title}" is blocked by "${t}" — author as an issue number after the first convert.`)
      }
    }

    blocked = [...new Set(blocked)]

    // Canonical key order, matching .claude/skills/backlog/sample_structure.json.
    return {
      title: s.title,
      description: s.description,
      status: s.status,
      priority: s.priority,
      goal: s.goal,
      notes: s.notes,
      tasks: s.tasks,
      acceptance_criteria: s.acceptance_criteria,
      labels: s.labels,
      blocked_by: blocked,
      size: s.size,
      points: s.points,
      issue_number: num,
    }
  })

  return { stories, warnings, openQuestionsAdd, haveNumbers }
}

// ---------------------------------------------------------------------------
// Prompt builders
// ---------------------------------------------------------------------------

function scopePrompt() {
  const instr = instruction
    ? `A USER INSTRUCTION was given and TAKES PRECEDENCE over default spec discovery — it governs the backlog's scope, focus, and which sources to read:\n"""\n${instruction}\n"""\n`
    : 'No user instruction was given — fall back to the phase specs.\n'
  return `You are a pragmatic tech lead re-establishing the shared grounding a team will use to GROOM an already-selected, already-ordered backlog into full detail. Read the repository and report a precise scope.
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
  return `You are a senior ${d.role}, helping a Product Owner GROOM a product backlog for ${scope.project_name}. The backlog was selected LEAN first (the initial-backlog workflow — title/description/priority, in committed foundation-first order) and is now being groomed into full detail in place; this survey grounds the grooming detail and the dependencies the grooming authors.
${grounding(scope)}

TASK (SURVEY phase) — from YOUR domain lens only, read the source specs in full, then report:
- candidate_stories: each buildable piece of work that should become a backlog story. For each: the spec id(s)/section(s) it traces to, a one-line rationale, the build-order GROUP it belongs to (use the group names above), and a suggested P0/P1/P2.
- hard_dependencies: real ordering constraints in your domain (e.g. "the auth/security model must exist before any data feature"). Be concrete — these confirm the committed ORDER and ground the blocked_by edges the grooming authors (named by title, resolved to issue numbers).
- scope_warnings: anything in your domain that LOOKS in-scope from the code scaffold but is out-of-scope per the scope contract and must NOT get a story.

Stay in your domain. Trace every candidate to a spec line — drop anything you cannot. The story selection and its order are already settled; this survey's main job is to ground the grooming detail and the dependencies (hard_dependencies).`
}

function loadLeanPrompt(backlogPath) {
  return `You are a release engineer. Read the backlog from disk so it can be groomed in place.

From the repository root:
1. Read ${backlogPath} FROM DISK (the actual file — do not trust memory). This is the selection written by the initial-backlog workflow (stories carry title/description/priority, in committed foundation-first build order) and may ALSO carry an issue_number per story if a convert has already run.
2. Return its parsed contents mapped to the schema: the top-level project, description, and dates { start, end }, and for EACH story extract title, description, priority, AND issue_number when present (PRESERVE it — it is the story's GitHub identity; if a story has no issue_number, omit it or set 0). Preserve the story order EXACTLY as given (it is the committed build order) and copy every string CHARACTER-FOR-CHARACTER (preserve em-dashes, parentheses, slashes, and spec ids verbatim). Ignore any other groomed fields that may already be present (goal/tasks/etc.) — they will be re-derived; only title/description/priority/issue_number are carried forward here.
3. If the file is missing, unreadable, or has no stories, return project and description as empty strings "", dates { start: "", end: "" }, and stories: [] — the workflow will detect this and stop.

Return the structured backlog.`
}

function groomPrompt(scope, leanFinal, digests) {
  return `You are the PRODUCT OWNER. GROOM the approved selection for ${scope.project_name} IN PLACE. The stories carry title/description/priority (and, when a convert has run, an issue_number) and are already in committed foundation-first build order — you ENRICH every story with its full buildable detail while keeping title, priority, and the story order FROZEN. You do NOT reorder and you NEVER set or mention issue numbers (the workflow attaches them by title). The main agent will render your output into JSON, so your output IS the source of truth for content and for the title-named dependencies.
${grounding(scope, groomRules())}

The developer survey digests are below — use their hard_dependencies to ground each story's grooming AND each story's blocked_by_titles.

DEVELOPER SURVEY DIGESTS (JSON):
${JSON.stringify(digests, null, 2)}

APPROVED SELECTION to groom (JSON — each story has title/description/priority and maybe issue_number; the order is the committed build order):
${JSON.stringify(leanFinal, null, 2)}

Groom rules:
- FREEZE title, description, priority AND the story ORDER exactly as given — do NOT reword them, do NOT reorder, do NOT add a story, do NOT drop a story. Do NOT output issue numbers.
- For EVERY story, ADD: goal, notes (may be ""), tasks (>=1), acceptance_criteria (>=1), labels (>=1, INCLUDING >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}), size (XS|S|M|L|XL), points (number), and blocked_by_titles.
- blocked_by_titles: the EXACT titles of the stories each story DIRECTLY, HARD-depends on. Every blocker MUST be EARLIER in the build order (a lower array position); never name the story itself; use [] when there is no hard prerequisite. Ground each in the survey hard_dependencies and keep a one-line rationale in notes or open_questions. (The workflow resolves these titles to issue numbers and will DROP any that point forward or to an unknown title — so name them precisely.)
- acceptance_criteria must be testable and observable; tasks must be concrete steps; size and points must be mutually consistent.
- Keep dates and the top-level project/description as in the approved backlog; carry forward / extend open_questions for any grooming ambiguity or dependency rationale.

Return the structured GROOMED backlog (every story now carries the full field set incl. blocked_by_titles, in the unchanged build order).`
}

function groomCritiquePrompt(d, scope, groomedDraft) {
  return `You are a senior ${d.role}, doing an ADVERSARIAL review of the Product Owner's GROOMED backlog for ${scope.project_name}, from your domain lens. This pass reviews the QUALITY of the per-story grooming AND the title-named dependencies — NOT the lean selection (settled) and NOT the order (frozen from the lean phase). Assume the grooming is weak until proven sound.
${grounding(scope, groomRules())}

GROOMED BACKLOG (JSON):
${JSON.stringify(groomedDraft, null, 2)}

Hunt, scoped to your domain (${d.role}). For every finding cite the story TITLE and concrete spec evidence — no vague complaints:
- weak_tasks: stories whose tasks are missing, too thin, non-actionable, or do not cover the work to satisfy the acceptance criteria.
- weak_acceptance_criteria: criteria that are vague, non-testable, unobservable, or do not actually prove the story is done.
- label_issues: stories MISSING a work-type label (every story MUST carry >=1 of {${WORK_TYPE_LABELS.join(', ')}}), carrying the WRONG work type, or with misleading labels.
- sizing_issues: size/points that is mis-scaled vs the work, or size and points that disagree.
- dependency_issues: problems in blocked_by_titles — a HARD blocker that is missing, a named blocker that is spurious/soft, a self-reference, a blocker that does NOT exist as a story title, or a blocker that is NOT earlier in the build order (forward dependency). Cite the depending story's title and name the offending blocker.
- empty_field_issues: required fields left blank where they must be non-empty (goal, tasks, acceptance_criteria, labels) — note that notes MAY be "" and blocked_by_titles MAY be [].
- other: anything else that would fail the validator or harm buildability — e.g. a reworded/renamed title (titles are FROZEN and must stay unique).
If a dimension is genuinely clean, return it as an empty array. End with a one-line overall_assessment.`
}

function groomFinalizePrompt(scope, groomedDraft, groomCritiques) {
  return `You are the PRODUCT OWNER. Revise your GROOMED backlog for ${scope.project_name} into the FINAL GROOMED version, incorporating the developers' groom critique where it is correct and defensible against the specs.
${grounding(scope, groomRules())}

YOUR GROOMED DRAFT (JSON):
${JSON.stringify(groomedDraft, null, 2)}

DEVELOPER GROOM CRITIQUES (JSON):
${JSON.stringify(groomCritiques, null, 2)}

Revision rules:
- Accept critique the specs support; reject critique that conflicts with them, and record any real disagreement (and your resolution) in open_questions.
- Keep title, description, priority, AND the story ORDER FROZEN (carried verbatim from the selection); add no story, drop no story, do not reorder, and do not output issue numbers. Titles must stay UNIQUE.
- Ensure EVERY story carries all groomed fields with non-empty goal/tasks/acceptance_criteria/labels (notes may be ""), >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}, a valid size (XS|S|M|L|XL), and a numeric points.
- Ensure blocked_by_titles is correct: only HARD blockers, each an EXACT existing story title that is EARLIER in the build order, no self-reference; use [] when there is none.
Return the FINAL structured GROOMED backlog. This fully groomed backlog is the deliverable the workflow will resolve, render into project/backlog.json, and validate.`
}

// The render/verify agents need filesystem + shell tools (Write, Bash, Read),
// which the workflow SCRIPT itself does not have — so this work is delegated to
// general-purpose subagents. The canonical file shape lives in
// .claude/skills/backlog/sample_structure.json; the validator and markdown
// generator are the same ones the /backlog skill uses. Note: blocked_by and
// issue_number in the design below were resolved deterministically by the
// workflow (the PO worked in titles) — the render agent copies them verbatim.
function renderRules() {
  return `Operate from the repository ROOT (run \`git rev-parse --show-toplevel\` and work there).

WRITE project/backlog.json so it matches the canonical key order in .claude/skills/backlog/sample_structure.json EXACTLY:
- Top-level keys, in order: project, description, dates { start, end }, stories. Include NO other top-level key — in particular do NOT write open_questions (sample_structure.json has none).
- Each story object has EXACTLY these 13 keys, IN THIS ORDER: title, description, status, priority, goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points, issue_number. There is NO id key — stories are never assigned an id.
  - title, description, priority, goal, notes, tasks, acceptance_criteria, labels, size, points — copy CHARACTER-FOR-CHARACTER from the design below. Do NOT reword, summarize, re-punctuate, normalize quotes/dashes, reorder list entries, or "improve" anything. Preserve em-dashes, parentheses, slashes, and spec ids verbatim. tasks/acceptance_criteria/labels are JSON ARRAYS — copy each entry and its order exactly.
  - notes — copy the design's string exactly; it MAY be the empty string "" (write "", never the literal word "none").
  - blocked_by — copy the array of issue NUMBERS from the design EXACTLY (same integers, same order). It is already resolved (the workflow converted the PO's title-named dependencies to numbers); do NOT add, drop, reorder, or invent entries, and do NOT put titles here. It MAY be [].
  - status — the literal string "Backlog" for every story (unless the design sets a different valid status).
  - issue_number — copy the integer from the design EXACTLY (it is the story's preserved GitHub identity; it is 0 only when the design has 0). Never renumber.
- Preserve story ORDER exactly as given (order encodes the committed foundation-first build sequence — array position IS the build order).
- Pretty-print with 2-space indentation; end with a trailing newline.

THEN validate: run \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`. It must print "Backlog validation passed". The validator is LENIENT (required = title/description/priority; groomed fields checked only when present) but it ALSO enforces that every title is UNIQUE (the re-link key), that every story's labels include >=1 work-type label, and that every blocked_by entry is an issue number that RESOLVES to an in-file issue_number (and a story may not block itself). If it errors, fix the JSON and re-run until it passes. (If that validator does not exist in this repo, set validator_passed=false and explain in notes.)

THEN regenerate the readable view: if .claude/skills/backlog/scripts/backlog-to-md.py exists, run \`python3 .claude/skills/backlog/scripts/backlog-to-md.py\` (it writes project/backlog.md); set md_generated accordingly. If it does not exist, set md_generated=false and note it.

Set validator_output to the validator's actual stdout/stderr.`
}

function renderPrompt(finalBacklog) {
  return `You are a release engineer. Render the FINAL GROOMED backlog (provided as JSON below) into the deliverable file project/backlog.json, then validate it and regenerate the markdown view. Copy issue_number and blocked_by from the design verbatim (they are already resolved — do not change them).

${renderRules()}

FINAL GROOMED backlog to render (JSON — note: ignore its open_questions field, it does NOT go in the file):
${JSON.stringify(finalBacklog, null, 2)}

Return the structured render result.`
}

function verifyPrompt(finalBacklog) {
  return `You are an adversarial QA reviewer. project/backlog.json was just written from the CANONICAL GROOMED design below. Assume it is WRONG until proven right — your job is to catch any drift or invalidity.

From the repository root:
1. Read project/backlog.json FROM DISK (the actual file — do not trust memory).
2. Re-run the validator: \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`; record whether it passes.
3. Compare the file against the CANONICAL design below (match stories by TITLE):
   - story_count must equal the canonical story count.
   - For EACH canonical story, every field in the file must match the canonical exactly — report any drift as a mismatch { title, field, issue }:
     - title, description, priority, goal, notes, size, points — IDENTICAL character-for-character (for points, the same number). Any rewording, truncation, added/removed/normalized punctuation, changed dash/quote, or altered spec id is a mismatch.
     - tasks, acceptance_criteria — the SAME entries in the SAME order and count, each char-for-char.
     - labels — the SAME set of labels (including the work-type label).
     - blocked_by — the SAME issue numbers in the SAME order as the canonical (an added/dropped/reordered/renumbered entry is a mismatch).
     - issue_number — the SAME integer as the canonical (the preserved identity — any change is a mismatch).
   - Structural checks (report as structural_issues):
     - Every story has EXACTLY these 13 keys, IN THIS ORDER: title, description, status, priority, goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points, issue_number. There is NO id key on any story.
     - Every title is UNIQUE across stories (the title is the re-link key — duplicates are a structural issue).
     - Every story's labels include >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}.
     - blocked_by is an array of integers; every entry resolves to some in-file story's issue_number; no story lists its own issue_number.
     - Enums are valid and correctly cased: status in {Backlog, In Progress, Done}, priority in {P0,P1,P2}, size in {XS,S,M,L,XL}.
     - Every story has status === "Backlog".
     - The story order in the file matches the canonical order (the committed build order must not be reshuffled).
     - Top-level project, description, and dates { start, end } match the canonical.
     - The file does NOT contain an open_questions key, nor any top-level key beyond project/description/dates/stories.
Put per-story field drift in mismatches; put everything from the structural checks in structural_issues. Set faithful=true ONLY when there are zero mismatches AND zero structural_issues AND the validator passes.

CANONICAL GROOMED design (JSON):
${JSON.stringify(finalBacklog, null, 2)}

Return the structured verification.`
}

function repairPrompt(finalBacklog, verify) {
  return `You are a release engineer fixing project/backlog.json. A QA pass found it is not yet a faithful, valid render of the canonical GROOMED design. Fix it.

QA FINDINGS (JSON):
${JSON.stringify({ validator_passed: verify.validator_passed, mismatches: verify.mismatches, structural_issues: verify.structural_issues }, null, 2)}

Re-render project/backlog.json from scratch so it EXACTLY matches the canonical GROOMED design, applying every rule precisely (re-emit ALL 13 fields per story in order with NO id, keep >=1 work-type label, keep titles unique, and copy blocked_by + issue_number from the design verbatim):

${renderRules()}

CANONICAL GROOMED design (JSON — ignore its open_questions field, it does NOT go in the file):
${JSON.stringify(finalBacklog, null, 2)}

Return the structured render result.`
}

// ---------------------------------------------------------------------------
// Orchestration. Barriers between phases are deliberate: each Product Owner
// pass needs the COMPLETE set of prior-stage outputs (all digests / all
// critiques) to synthesize across domains — the legitimate barrier case.
// ---------------------------------------------------------------------------

phase('Scope')
log(scopeOverride ? 'Using supplied scope' : (instruction ? 'Scoping from the user instruction' : `Scoping from project/specs/${specPhase}/ + repo config`))
const scope = scopeOverride || await agent(scopePrompt(), { schema: SCOPE_SCHEMA, phase: 'Scope', label: 'scope' })

let domains = (domainsOverride && domainsOverride.length ? domainsOverride : scope.domains) || []
if (!domains.length) domains = DEFAULT_DOMAINS
domains = domains.slice(0, 6)
log(`Project "${scope.project_name}" · ${domains.length} developer domains`)

phase('Survey')
const digests = (digestsOverride && digestsOverride.length)
  ? digestsOverride
  : (await parallel(
      domains.map((d) => () => agent(surveyPrompt(d, scope), { schema: DIGEST_SCHEMA, phase: 'Survey', label: `survey:${d.key}` })),
    )).filter(Boolean)

phase('Load')
log(leanOverride ? 'Using supplied backlog' : `Loading the backlog from ${backlogPath}`)
const leanFinal = leanOverride || await agent(loadLeanPrompt(backlogPath), {
  agentType: 'general-purpose', schema: LOAD_SCHEMA, phase: 'Load', label: 'load-lean',
})
if (!leanFinal || !leanFinal.stories || !leanFinal.stories.length) {
  log(`No backlog found at ${backlogPath} — run the initial-backlog workflow first.`)
  return { error: 'backlog not found', backlogPath, scope }
}
const loadedWithNumbers = leanFinal.stories.filter((s) => s.issue_number > 0).length
log(`Loaded selection: ${leanFinal.stories.length} stories (order is the committed build order; ${loadedWithNumbers} carry issue numbers)`)

// ── Groom (detail in place) -> groom-critique -> groom-finalize ──
phase('Groom')
log('Product Owner grooming every story in place (title + order frozen; dependencies named by title)')
const groomedDraft = await agent(groomPrompt(scope, leanFinal, digests), {
  agentType: 'Product Owner', schema: GROOMED_BACKLOG_SCHEMA, phase: 'Groom', label: 'po:groom',
})
log(`Groomed draft has ${groomedDraft.stories.length} stories (fully detailed, dependencies named by title)`)

phase('Groom Critique')
log('Developers adversarially reviewing the groomed detail and dependencies')
const groomCritiques = (await parallel(
  domains.map((d) => () => agent(groomCritiquePrompt(d, scope, groomedDraft), { schema: GROOM_CRITIQUE_SCHEMA, phase: 'Groom Critique', label: `groom-critique:${d.key}` })),
)).filter(Boolean)

phase('Groom Finalize')
log(`Product Owner finalizing the groomed backlog with ${groomCritiques.length} groom critiques`)
const groomedFinal = await agent(groomFinalizePrompt(scope, groomedDraft, groomCritiques), {
  agentType: 'Product Owner', schema: GROOMED_BACKLOG_SCHEMA, phase: 'Groom Finalize', label: 'po:groom-final',
})
log(`Groomed backlog finalized: ${groomedFinal.stories.length} stories, ${groomedFinal.open_questions.length} open questions`)

// Resolve the PO's title-named dependencies to issue NUMBERS deterministically,
// preserving each story's issue_number. This is the single place numbers are
// handled (the PO only ever worked in titles); forward/unknown/self edges are
// dropped + recorded, leaving an acyclic, in-file-resolvable blocked_by graph.
const resolved = resolveDependencies(groomedFinal, leanFinal)
resolved.warnings.forEach((w) => log(`  ⚠ ${w}`))
const edgeCount = resolved.stories.reduce((n, s) => n + s.blocked_by.length, 0)
log(resolved.haveNumbers
  ? `Resolved dependencies: ${edgeCount} blocked_by edge(s) across ${resolved.stories.length} stories (issue numbers preserved)`
  : `No issue numbers present yet — blocked_by left [] and ${resolved.openQuestionsAdd.length} intended dependency(ies) recorded by title for a later convert`)

// The canonical design the render + verify agents work from: groomed content
// with issue_number preserved and blocked_by resolved to numbers.
const groomedForRender = {
  project: groomedFinal.project,
  description: groomedFinal.description,
  dates: groomedFinal.dates,
  stories: resolved.stories,
  open_questions: [...(groomedFinal.open_questions || []), ...resolved.openQuestionsAdd],
}

// Render the GROOMED design into project/backlog.json, then adversarially
// verify the written file is faithful + valid against the validator, repairing
// on drift (up to 2 attempts). Delegated to general-purpose agents because the
// script has no FS/shell access.
phase('Render')
log('Rendering the final groomed backlog into project/backlog.json (issue numbers preserved; blocked_by resolved)')
let render = await agent(renderPrompt(groomedForRender), {
  agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: 'render',
})

phase('Verify')
log('Adversarially verifying the written groomed backlog.json is faithful and valid')
let verify = await agent(verifyPrompt(groomedForRender), {
  agentType: 'general-purpose', schema: VERIFY_SCHEMA, phase: 'Verify', label: 'verify',
})

let repairs = 0
while (
  verify &&
  (!verify.faithful || !verify.validator_passed || verify.mismatches.length || verify.structural_issues.length) &&
  repairs < 2
) {
  repairs++
  log(`Repairing groomed backlog.json (attempt ${repairs}) — ${verify.mismatches.length} mismatch(es), ${verify.structural_issues.length} structural issue(s)`)
  render = await agent(repairPrompt(groomedForRender, verify), {
    agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: `repair:${repairs}`,
  })
  verify = await agent(verifyPrompt(groomedForRender), {
    agentType: 'general-purpose', schema: VERIFY_SCHEMA, phase: 'Verify', label: `verify:${repairs}`,
  })
}

log(
  verify && verify.faithful && verify.validator_passed
    ? (resolved.haveNumbers
        ? `groomed backlog.json written, validated & verified: ${verify.story_count} stories (issue numbers preserved, blocked_by authored). Convert again to push bodies/fields and set the GitHub "blocked by" edges.`
        : `groomed backlog.json written, validated & verified: ${verify.story_count} stories. Convert to mint issue numbers, then re-run grooming (or a convert pass) to author blocked_by.`)
    : 'groomed backlog.json written but verification flagged issues — see result.verify',
)

return { groomedForRender, groomedFinal, groomedDraft, groomCritiques, leanFinal, digests, scope, render, verify, depWarnings: resolved.warnings }
