export const meta = {
  name: 'backlog-collab',
  description: 'Developers + a Product Owner collaborate to design a lean backlog (phase 1), then groom EVERY story in place into a fully GROOMED backlog (phase 2), then write & validate project/backlog.json against the strict full-schema validator (scope -> survey -> design -> critique -> finalize -> groom -> groom-critique -> groom-finalize -> render -> verify)',
  whenToUse: 'Run the /backlog skill as a multi-agent collaboration on any project. A Scope pass discovers the project name, issue-id prefix, scope contract and developer domains from .github/config.json and the project specs; domain developers then survey and adversarially critique while a Product Owner owns the content across two stages. STAGE 1 (lean): the PO designs a LEAN backlog (each story: id/title/description/priority, plus status="Backlog" and issue_number=0), developers critique it, the PO finalizes it. STAGE 2 (groom): the PO grooms EVERY story IN PLACE — adding goal/notes/tasks/acceptance_criteria/labels (incl. >=1 work-type label)/blocked_by/size/points — with its own developer critique + PO finalize sub-loop; no story is added or dropped and ids never change. The workflow then RENDERS the final GROOMED backlog into project/backlog.json in the FULL groomed schema (canonical key order id..issue_number per sample_structure.json), runs the STRICT full-schema validator (.github/scripts/projects/cli.py validate, backed by validation.py), regenerates project/backlog.md, and adversarially VERIFIES the written file is faithful to the GROOMED design and passes the strict validator (repairing if it drifted). Optional args: { instruction, phase, idPrefix, domains, dates } — all optional; with none, it auto-discovers everything.',
  phases: [
    { title: 'Scope', detail: 'Tech lead discovers project, id prefix, scope contract, developer domains, dates' },
    { title: 'Survey', detail: 'Developer agents digest the specs by domain (candidate work, hard dependencies, scope traps)' },
    { title: 'Design', detail: 'Product Owner drafts the LEAN backlog — id/title/description/priority only' },
    { title: 'Critique', detail: 'Developers adversarially review the lean draft (missing, scope-creep, ordering, priority)' },
    { title: 'Finalize', detail: 'Product Owner finalizes the lean backlog — the approved phase-1 deliverable' },
    { title: 'Groom', detail: 'PO Stage 2 grooms EVERY story in place: goal/notes/tasks/acceptance_criteria/labels/blocked_by/size/points; no add/drop, ids unchanged' },
    { title: 'Groom Critique', detail: 'Developers adversarially review the groomed detail per domain (tasks, criteria, labels, dependencies, sizing)' },
    { title: 'Groom Finalize', detail: 'Product Owner revises the grooming into the final GROOMED backlog' },
    { title: 'Render', detail: 'Engineer writes project/backlog.json in the FULL groomed schema, runs the STRICT validator, regenerates backlog.md' },
    { title: 'Verify', detail: 'Adversarial QA confirms the groomed file is faithful to the design and passes the strict validator; repairs on drift' },
  ],
}

// ---------------------------------------------------------------------------
// Project-agnostic. Nothing about a specific product is hardcoded. Everything
// project-specific (name, issue-id prefix, in/out-of-scope contract, developer
// domains, dates) is discovered at runtime in the Scope phase from
// .github/config.json and the project's own specs, OR supplied via args.
//
// Optional args (all optional):
//   args.instruction : a <backlog-focus> / direction that governs scope + sources
//                      (takes precedence over default spec discovery)
//   args.phase       : specs phase folder under project/specs/<phase>/ (default 'mvp')
//   args.idPrefix    : force the issue-id prefix (else derived from .github/config.json)
//   args.domains     : force the developer domains [{key, role}, ...]
//   args.dates       : force the window { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' }
// ---------------------------------------------------------------------------

const instruction = (args && args.instruction) || ''
const specPhase = (args && args.phase) || 'mvp'
const prefixOverride = args && args.idPrefix
const domainsOverride = args && args.domains
const datesOverride = args && args.dates

const PRIORITY = { type: 'string', enum: ['P0', 'P1', 'P2'] }
const STATUS = { type: 'string', enum: ['Backlog', 'In Progress', 'Done'] }
const SIZE = { type: 'string', enum: ['XS', 'S', 'M', 'L', 'XL'] }

// The id is type-agnostic, so the work-type label is the SOLE carrier of issue
// type. Every groomed story's labels must include >=1 of these (validation.py
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

// The foundation-first build order is shared by BOTH phases: ids are assigned
// once in the lean phase and frozen, and grooming must respect the same order
// when reasoning about blocked_by dependencies.
function buildOrderRules() {
  return `FOUNDATION-FIRST BUILD ORDER (ids are assigned sequentially down this; within a group, order by priority):
1 Project setup -> 2 App structure -> 3 Database & models -> 4 API contracts -> 5 Backend skeleton ->
6 Frontend screens (mock data) -> 7 Feature implementation -> 8 Frontend<->backend integration ->
9 Auth & permissions -> 10 Test & debug -> 11 Polish & optimize -> 12 Deploy & release.
- Skip groups the specs do not justify; never invent scope to fill one. A group may map to several stories.
- Map each story to the EARLIEST group it genuinely belongs to.
- A real hard dependency may override the order (e.g. a security model like per-user RLS before any data feature) — state the reason in that story's description and flag non-obvious moves in open_questions.`
}

// Phase-1 (lean) field rules. Used by survey/design/critique/finalize.
function leanRules(prefix) {
  return `LEAN BACKLOG SCHEMA (PHASE 1 — this stage ONLY) — each story carries EXACTLY:
- id        : ${prefix}-NNN, matching ^${prefix}-\\d{3}$ (exactly 3 digits), unique, sequential DOWN the build order, no gaps/reuse
- title     : short imperative title
- description: one or two sentences of context (enough to judge priority; no implementation detail)
- priority  : P0 / P1 / P2 (case-sensitive)
DO NOT author goal / notes / tasks / acceptance_criteria / labels / blocked_by / size / points — those are added in the GROOM phase (phase 2) of THIS workflow.

${buildOrderRules()}`
}

// Phase-2 (groom) field rules. Used by groom/groom-critique/groom-finalize.
function groomRules(prefix) {
  return `GROOMED BACKLOG SCHEMA (PHASE 2) — grooming happens IN PLACE on the approved lean backlog:
FROZEN (copy verbatim, never change): id, title, description, priority, and the STORY ORDER. Add NO story; drop NO story; renumber NOTHING. Match each story by its ${prefix}-NNN id.
ADD to EVERY story (these are the groomed fields the strict validator requires):
- goal               : one non-empty sentence — the outcome this story delivers (distinct from the description's context).
- notes              : free-form string; MAY be "" (empty string) when there is nothing extra to say. Do NOT write the literal word "none".
- tasks              : list of >=1 concrete implementation steps (strings).
- acceptance_criteria: list of >=1 testable, observable pass conditions (strings) — each independently verifiable, no vague "works well".
- labels             : list of >=1 string labels. MUST include >=1 WORK-TYPE label from {${WORK_TYPE_LABELS.join(', ')}} — this is the SOLE carrier of issue type, so every story needs exactly one work type (feature for product work, tech for infra/refactor, spike for time-boxed investigation, chore/docs/review/bug as fitting). Domain labels (backend, frontend, …) are allowed EXTRAS but do NOT satisfy the work-type rule.
- blocked_by         : list of ${prefix}-NNN ids this story hard-depends on; MAY be [] for a root/foundational story. EVERY id must resolve to a story id present in THIS backlog. No cycles. Ground dependencies in the build order and the developers' hard_dependencies — do not invent them.
- size               : one of XS / S / M / L / XL (case-sensitive).
- points             : a number (story points). Keep it consistent with size.
status stays "Backlog" and issue_number stays 0 (the render step sets these on the file).`
}

function grounding(scope, prefix, rules = leanRules(prefix)) {
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
  required: ['project_name', 'id_prefix', 'dates', 'sources', 'scope_summary', 'domains', 'open_questions'],
  properties: {
    project_name: { type: 'string' },
    id_prefix: { type: 'string' },
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

// Built at runtime once the id prefix is known, so the id pattern matches the project.
// PHASE 1 (lean): story items carry only id/title/description/priority.
function makeLeanBacklogSchema(idPattern) {
  return {
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
          required: ['id', 'title', 'description', 'priority'],
          properties: {
            id: { type: 'string', pattern: idPattern },
            title: { type: 'string' },
            description: { type: 'string' },
            priority: PRIORITY,
          },
        },
      },
      open_questions: { type: 'array', items: { type: 'string' } },
    },
  }
}

// PHASE 2 (groom): story items carry the FULL canonical groomed field set, in
// the same key order as .claude/skills/backlog/sample_structure.json. JSON
// Schema enforces presence/type/enums and minItems on the lists, but it CANNOT
// express "labels contains >=1 work-type label" nor "blocked_by ids resolve
// in-file / no cycles" — those are enforced by the groom prompts, the
// groom-critique, and (authoritatively) the strict python validator at Render.
function makeGroomedBacklogSchema(idPattern) {
  return {
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
            'id', 'title', 'description', 'status', 'priority', 'goal', 'notes',
            'tasks', 'acceptance_criteria', 'labels', 'blocked_by', 'size', 'points', 'issue_number',
          ],
          properties: {
            id: { type: 'string', pattern: idPattern },
            title: { type: 'string', minLength: 1 },
            description: { type: 'string', minLength: 1 },
            status: STATUS,
            priority: PRIORITY,
            goal: { type: 'string', minLength: 1 },
            notes: { type: 'string' },
            tasks: { type: 'array', items: { type: 'string' }, minItems: 1 },
            acceptance_criteria: { type: 'array', items: { type: 'string' }, minItems: 1 },
            labels: { type: 'array', items: { type: 'string' }, minItems: 1 },
            blocked_by: { type: 'array', items: { type: 'string' }, default: [] },
            size: SIZE,
            points: { type: 'number' },
            issue_number: { type: 'integer' },
          },
        },
      },
      open_questions: { type: 'array', items: { type: 'string' } },
    },
  }
}

// Adversarial review schema for the LEAN phase (selection / ordering / priority).
const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['reviewer_domain', 'missing_stories', 'scope_creep', 'ordering_issues', 'priority_issues', 'other', 'overall_assessment'],
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
    ordering_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['target', 'problem', 'suggested_fix'],
        properties: { target: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    priority_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['target', 'current', 'suggested', 'why'],
        properties: { target: { type: 'string' }, current: { type: 'string' }, suggested: { type: 'string' }, why: { type: 'string' } },
      },
    },
    other: { type: 'array', items: { type: 'string' } },
    overall_assessment: { type: 'string' },
  },
}

// Adversarial review schema for the GROOM phase (quality of the per-story
// detail). Each finding cites the story id it targets and why it is wrong.
const GROOM_CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'reviewer_domain', 'weak_tasks', 'weak_acceptance_criteria', 'label_issues',
    'dependency_issues', 'sizing_issues', 'empty_field_issues', 'other', 'overall_assessment',
  ],
  properties: {
    reviewer_domain: { type: 'string' },
    weak_tasks: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'problem', 'suggested_fix'],
        properties: { id: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    weak_acceptance_criteria: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'problem', 'suggested_fix'],
        properties: { id: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    label_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'problem', 'suggested_fix'],
        properties: { id: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    dependency_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'problem', 'suggested_fix'],
        properties: { id: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    sizing_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'problem', 'suggested_fix'],
        properties: { id: { type: 'string' }, problem: { type: 'string' }, suggested_fix: { type: 'string' } },
      },
    },
    empty_field_issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'field', 'problem'],
        properties: { id: { type: 'string' }, field: { type: 'string' }, problem: { type: 'string' } },
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
        type: 'object', additionalProperties: false, required: ['id', 'field', 'issue'],
        properties: { id: { type: 'string' }, field: { type: 'string' }, issue: { type: 'string' } },
      },
    },
    structural_issues: { type: 'array', items: { type: 'string' } },
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
  return `You are a pragmatic tech lead establishing the shared grounding a team will use to build a backlog — designed lean first, then groomed into full detail. Read the repository and report a precise scope.
${instr}
Do all of the following by reading the repo:
1. ID PREFIX. ${prefixOverride
    ? `Use "${prefixOverride}".`
    : 'Read .github/config.json and uppercase the repo name (the segment after "/", e.g. "owner/foo" -> "FOO"). If that file is absent, uppercase the project directory name. Strip non-alphanumeric characters.'}
2. PROJECT. Its name and a one-line product goal.
3. SOURCES. ${instruction
    ? 'The sources the user instruction points to (read them).'
    : `The active-phase specs under project/specs/${specPhase}/ — typically prd.md, design.md, tech-specs.md — plus project/roadmap.md and CLAUDE.md when present. If prd.md is missing and no instruction was given, record that in open_questions rather than guessing.`}
4. SCOPE CONTRACT. Read those sources and distill a compact but COMPLETE contract with two explicit halves:
   - IN-SCOPE: the features/requirements that must become stories, each tagged with its spec id(s)/section(s).
   - OUT-OF-SCOPE: anything present in the code scaffold or adjacent phases that must NOT get a story (this is what prevents scope creep).
   This contract is what every downstream agent will share — make it self-sufficient.
5. DOMAINS. Propose 3-5 developer domains that TOGETHER cover this project's whole surface, tailored to THIS project's actual stack and shape (not a fixed template). ${domainsOverride
    ? `Use exactly: ${JSON.stringify(domainsOverride)}.`
    : 'Each domain is a {key, role}: key is a short slug; role names the area plus its key technologies/responsibilities. Avoid overlap; cover the full stack.'}
6. DATES. ${datesOverride
    ? `Use start "${datesOverride.start}", end "${datesOverride.end}".`
    : 'Derive the delivery window (YYYY-MM-DD) from the specs/roadmap. If the specs do not pin dates, propose a sensible window and note the assumption in open_questions.'}

Return the structured scope. Be specific and trace claims to the specs.`
}

function surveyPrompt(d, scope, prefix) {
  return `You are a senior ${d.role}, helping a Product Owner build a product backlog for ${scope.project_name}. The backlog is designed LEAN first (phase 1) and then groomed into full detail (phase 2); this survey feeds the lean design.
${grounding(scope, prefix)}

TASK (SURVEY phase) — from YOUR domain lens only, read the source specs in full, then report:
- candidate_stories: each buildable piece of work that should become a backlog story. For each: the spec id(s)/section(s) it traces to, a one-line rationale, the build-order GROUP it belongs to (use the group names above), and a suggested P0/P1/P2.
- hard_dependencies: real ordering constraints in your domain (e.g. "the auth/security model must exist before any data feature"). Be concrete — these will ground the blocked_by edges in phase-2 grooming.
- scope_warnings: anything in your domain that LOOKS in-scope from the code scaffold but is out-of-scope per the scope contract and must NOT get a story.

Stay in your domain. Trace every candidate to a spec line — drop anything you cannot. Do NOT author grooming detail here (tasks/acceptance_criteria/labels/size/points) — that comes in the GROOM phase (phase 2); this survey feeds the lean design.`
}

function designPrompt(scope, prefix, digests) {
  return `You are the PRODUCT OWNER. Design the LEAN product backlog for ${scope.project_name} — Stage 1 (lean design), phase 1 of a TWO-PHASE flow. The main agent will render your output into JSON verbatim, so your design IS the source of truth for content. In phase 2 these SAME stories will be groomed IN PLACE — the ids and order you set here are FROZEN for grooming, so set them deliberately.
${grounding(scope, prefix)}

Ground your design in the specs (read the sources above) AND in the developer survey digests below. The digests are advisory technical input — you own every final content decision.

DEVELOPER SURVEY DIGESTS (JSON):
${JSON.stringify(digests, null, 2)}

Produce the lean backlog:
- One flat list of user stories, each just enough to prioritize. Cover EVERY in-scope spec item with at least one story; reject anything the specs do not justify; create NO stories for out-of-scope work.
- Each story carries ONLY: id (${prefix}-NNN), short imperative title, 1-2 sentence description, P0/P1/P2. No other fields — grooming fields are added in phase 2.
- Order stories foundation-first per the build sequence; within a group, order by priority. Assign ${prefix}-001, ${prefix}-002, … sequentially DOWN that order — no gaps, no reuse, exactly 3 digits, so id order == build order.
- If a hard dependency forces a story earlier than its natural group, say why in that story's description.
- dates: ${datesOverride ? `start "${datesOverride.start}", end "${datesOverride.end}".` : `use the scope's window (start "${scope.dates.start}", end "${scope.dates.end}") unless the specs pin different dates; record any assumption in open_questions.`}
- open_questions: capture any ambiguity rather than silently choosing for the user.

Return the structured backlog.`
}

function critiquePrompt(d, scope, prefix, draft) {
  return `You are a senior ${d.role}, doing an ADVERSARIAL review of the Product Owner's DRAFT lean backlog for ${scope.project_name}, from your domain lens. This pass reviews the LEAN backlog only (phase 1) — story selection, ordering, and priority. Your job is to find what is wrong, not to praise.
${grounding(scope, prefix)}

DRAFT BACKLOG (JSON):
${JSON.stringify(draft, null, 2)}

Hunt, scoped to your domain (${d.role}):
- missing_stories: in-scope spec work that has NO story (cite the spec id(s)/section(s)).
- scope_creep: stories that build out-of-scope work, or that smuggle in phase-2 grooming detail (tasks/criteria/labels/size/points) PREMATURELY — this pass reviews the LEAN backlog only; grooming happens in phase 2.
- ordering_issues: stories out of foundation-first order, or that violate a hard build dependency — name the dependency and a concrete fix (e.g. "move ${prefix}-007 before ${prefix}-004").
- priority_issues: P0/P1/P2 that is wrong vs the MVP critical path and the spec priorities.
- other: duplicate/overlapping stories, vague descriptions, non-sequential or malformed ${prefix}-NNN ids, dates issues.
Cite spec evidence for every finding — no vague complaints. If a dimension is genuinely clean, return it as an empty array. End with a one-line overall_assessment.`
}

function finalizePrompt(scope, prefix, draft, critiques) {
  return `You are the PRODUCT OWNER. Revise your draft lean backlog for ${scope.project_name} into the FINAL lean version, incorporating the developers' critique where it is correct and defensible against the specs. This is the END of phase 1.
${grounding(scope, prefix)}

YOUR DRAFT (JSON):
${JSON.stringify(draft, null, 2)}

DEVELOPER CRITIQUES (JSON):
${JSON.stringify(critiques, null, 2)}

Revision rules:
- Accept critique the specs support; reject critique that conflicts with the specs or scope, and record any real disagreement (and your resolution) in open_questions.
- Keep the backlog LEAN — only id, title, description, priority per story; no grooming fields (those are added in phase 2).
- Re-verify foundation-first ordering and that ${prefix}-NNN ids are sequential down the FINAL order, no gaps/reuse, exactly 3 digits.
- Ensure every story traces to a spec item, there is zero out-of-scope leakage, and dates are set.
Return the FINAL structured backlog. This is the approved LEAN backlog (phase 1); the workflow will now GROOM every story in place (phase 2) before rendering project/backlog.json.`
}

function groomPrompt(scope, prefix, leanFinal, digests) {
  return `You are the PRODUCT OWNER. GROOM the approved lean backlog for ${scope.project_name} — Stage 2 (grooming), phase 2 of the flow. You enrich EVERY story IN PLACE with its full buildable detail. The main agent will render your output into JSON verbatim, so your grooming IS the source of truth for content.
${grounding(scope, prefix, groomRules(prefix))}

The developer survey digests are below again — use their hard_dependencies to ground each story's blocked_by so dependencies are sourced, not invented.

DEVELOPER SURVEY DIGESTS (JSON):
${JSON.stringify(digests, null, 2)}

APPROVED LEAN BACKLOG to groom IN PLACE (JSON — match each story by id):
${JSON.stringify(leanFinal, null, 2)}

Groom rules:
- For EVERY story (matched by id), ADD: goal, notes (may be ""), tasks (>=1), acceptance_criteria (>=1), labels (>=1, INCLUDING >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}), blocked_by (in-file ${prefix}-NNN ids, [] for roots, no cycles, grounded in the build order + hard_dependencies), size (XS|S|M|L|XL), points (number).
- FREEZE id, title, description, priority, and the story ORDER exactly as given — do NOT reword them, do NOT add a story, do NOT drop a story.
- acceptance_criteria must be testable and observable; tasks must be concrete steps; size and points must be mutually consistent.
- Keep dates and the top-level project/description as in the approved backlog; carry forward / extend open_questions for any grooming ambiguity.

Return the structured GROOMED backlog (every story now carries the full field set).`
}

function groomCritiquePrompt(d, scope, prefix, groomedDraft) {
  return `You are a senior ${d.role}, doing an ADVERSARIAL review of the Product Owner's GROOMED backlog for ${scope.project_name}, from your domain lens. This pass reviews the QUALITY of the per-story grooming (phase 2), NOT the lean selection (that is settled). Assume the grooming is weak until proven sound.
${grounding(scope, prefix, groomRules(prefix))}

GROOMED BACKLOG (JSON):
${JSON.stringify(groomedDraft, null, 2)}

Hunt, scoped to your domain (${d.role}). For every finding cite the story id and concrete spec/dependency evidence — no vague complaints:
- weak_tasks: stories whose tasks are missing, too thin, non-actionable, or do not cover the work to satisfy the acceptance criteria.
- weak_acceptance_criteria: criteria that are vague, non-testable, unobservable, or do not actually prove the story is done.
- label_issues: stories MISSING a work-type label (every story MUST carry >=1 of {${WORK_TYPE_LABELS.join(', ')}}), carrying the WRONG work type, or with misleading labels.
- dependency_issues: blocked_by that is wrong, dangling (an id not in this backlog), CYCLIC, missing a real hard dependency from the build order / survey, or pointing at a later story (a story may only depend on EARLIER ids).
- sizing_issues: size/points that is mis-scaled vs the work, or size and points that disagree.
- empty_field_issues: required fields left blank where they must be non-empty (goal, tasks, acceptance_criteria, labels) — note that notes MAY be "".
- other: anything else that would fail the strict validator or harm buildability.
If a dimension is genuinely clean, return it as an empty array. End with a one-line overall_assessment.`
}

function groomFinalizePrompt(scope, prefix, groomedDraft, groomCritiques) {
  return `You are the PRODUCT OWNER. Revise your GROOMED backlog for ${scope.project_name} into the FINAL GROOMED version, incorporating the developers' groom critique where it is correct and defensible against the specs and the build order.
${grounding(scope, prefix, groomRules(prefix))}

YOUR GROOMED DRAFT (JSON):
${JSON.stringify(groomedDraft, null, 2)}

DEVELOPER GROOM CRITIQUES (JSON):
${JSON.stringify(groomCritiques, null, 2)}

Revision rules:
- Accept critique the specs/build-order support; reject critique that conflicts with them, and record any real disagreement (and your resolution) in open_questions.
- Keep id, title, description, priority, and the story ORDER FROZEN — grooming is in place; add no story, drop no story.
- Ensure EVERY story carries all groomed fields with non-empty goal/tasks/acceptance_criteria/labels (notes may be ""), >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}, blocked_by whose every id resolves to an in-file ${prefix}-NNN id with NO cycles, a valid size (XS|S|M|L|XL), and a numeric points.
Return the FINAL structured GROOMED backlog. This FULLY GROOMED backlog is the deliverable the workflow will render into project/backlog.json and validate with the strict validator.`
}

// The render/verify agents need filesystem + shell tools (Write, Bash, Read),
// which the workflow SCRIPT itself does not have — so this work is delegated to
// general-purpose subagents. The canonical file shape lives in
// .claude/skills/backlog/sample_structure.json; the validator and markdown
// generator are the same ones the /backlog skill uses.
function renderRules() {
  return `Operate from the repository ROOT (run \`git rev-parse --show-toplevel\` and work there).

WRITE project/backlog.json so it matches .claude/skills/backlog/sample_structure.json EXACTLY:
- Top-level keys, in order: project, description, dates { start, end }, stories. Include NO other top-level key — in particular do NOT write open_questions (sample_structure.json has none).
- Each story object has EXACTLY these 14 keys, IN THIS ORDER: id, title, description, status, priority, goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points, issue_number.
  - id, title, description, priority, goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points — copy CHARACTER-FOR-CHARACTER from the groomed design below. Do NOT reword, summarize, re-punctuate, normalize quotes/dashes, reorder list entries, or "improve" anything. Preserve em-dashes, parentheses, slashes, and spec ids verbatim. tasks/acceptance_criteria/labels/blocked_by are JSON ARRAYS — copy each entry and its order exactly.
  - notes — copy the design's string exactly; it MAY be the empty string "" (write "", never the literal word "none").
  - blocked_by — copy the design's array exactly; it MAY be [] for a root story. Do NOT drop or invent dependency ids.
  - status — the literal string "Backlog" for every story (unless the design sets a different valid status).
  - issue_number — the integer 0 for every story (unless already populated by a prior convert).
- Preserve story ORDER exactly as given (order encodes the foundation-first build sequence).
- Pretty-print with 2-space indentation; end with a trailing newline.

THEN validate with the STRICT full-schema validator: run \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`. It must print "Backlog validation passed". This validator additionally enforces that every story's labels include >=1 work-type label and that every blocked_by id resolves to an id in this file — so do NOT strip labels or break dependency ids. If it errors, fix the JSON and re-run until it passes. (If that validator does not exist in this repo, set validator_passed=false and explain in notes.)

THEN regenerate the readable view: if .claude/skills/backlog/scripts/backlog-to-md.py exists, run \`python3 .claude/skills/backlog/scripts/backlog-to-md.py\` (it writes project/backlog.md); set md_generated accordingly. If it does not exist, set md_generated=false and note it.

Set validator_output to the validator's actual stdout/stderr.`
}

function renderPrompt(finalBacklog) {
  return `You are a release engineer. Render the FINAL GROOMED backlog (provided as JSON below) into the deliverable file project/backlog.json, then validate it with the strict validator and regenerate the markdown view.

${renderRules()}

FINAL GROOMED backlog to render (JSON — note: ignore its open_questions field, it does NOT go in the file):
${JSON.stringify(finalBacklog, null, 2)}

Return the structured render result.`
}

function verifyPrompt(finalBacklog) {
  return `You are an adversarial QA reviewer. project/backlog.json was just written from the CANONICAL GROOMED design below. Assume it is WRONG until proven right — your job is to catch any drift or invalidity.

From the repository root:
1. Read project/backlog.json FROM DISK (the actual file — do not trust memory).
2. Re-run the STRICT validator: \`python3 .github/scripts/projects/cli.py validate project/backlog.json\`; record whether it passes.
3. Compare the file against the CANONICAL design below:
   - story_count must equal the canonical story count.
   - For EACH canonical story (matched by id), every GROOMED field in the file must match the canonical exactly — report any drift as a mismatch { id, field, issue }:
     - title, description, priority, goal, notes, size, points — IDENTICAL character-for-character (for points, the same number). Any rewording, truncation, added/removed/normalized punctuation, changed dash/quote, or altered spec id is a mismatch.
     - tasks, acceptance_criteria — the SAME entries in the SAME order and count, each char-for-char.
     - labels — the SAME set of labels (including the work-type label).
     - blocked_by — the SAME set of dependency ids.
   - Structural checks (report as structural_issues):
     - Every story has ALL 14 fields: id, title, description, status, priority, goal, notes, tasks, acceptance_criteria, labels, blocked_by, size, points, issue_number.
     - Every story's labels include >=1 work-type label from {${WORK_TYPE_LABELS.join(', ')}}.
     - Every blocked_by id resolves to an id present in the file (no dangling); no dependency cycle.
     - Enums are valid and correctly cased: status in {Backlog, In Progress, Done}, priority in {P0,P1,P2}, size in {XS,S,M,L,XL}.
     - Every story has status === "Backlog" and issue_number === 0.
     - Every canonical id appears exactly once; flag missing, extra, duplicated, or malformed ids.
     - Top-level project, description, and dates { start, end } match the canonical.
     - The file does NOT contain an open_questions key, nor any top-level key beyond project/description/dates/stories.
Put per-story field drift in mismatches; put everything from the structural checks in structural_issues. Set faithful=true ONLY when there are zero mismatches AND zero structural_issues AND the strict validator passes.

CANONICAL GROOMED design (JSON):
${JSON.stringify(finalBacklog, null, 2)}

Return the structured verification.`
}

function repairPrompt(finalBacklog, verify) {
  return `You are a release engineer fixing project/backlog.json. A QA pass found it is not yet a faithful, valid render of the canonical GROOMED design. Fix it.

QA FINDINGS (JSON):
${JSON.stringify({ validator_passed: verify.validator_passed, mismatches: verify.mismatches, structural_issues: verify.structural_issues }, null, 2)}

Re-render project/backlog.json from scratch so it EXACTLY matches the canonical GROOMED design, applying every rule precisely (re-emit ALL 14 groomed fields per story, keep >=1 work-type label, and keep every blocked_by id resolving in-file):

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
log(instruction ? 'Scoping from the user instruction' : `Scoping from project/specs/${specPhase}/ + repo config`)
const scope = await agent(scopePrompt(), { schema: SCOPE_SCHEMA, phase: 'Scope', label: 'scope' })

const prefix = ((prefixOverride || scope.id_prefix || 'PROJ') + '').toUpperCase().replace(/[^A-Z0-9]/g, '')
const idPattern = '^' + prefix + '-\\d{3}$'
const LEAN_BACKLOG_SCHEMA = makeLeanBacklogSchema(idPattern)
const GROOMED_BACKLOG_SCHEMA = makeGroomedBacklogSchema(idPattern)
let domains = (domainsOverride && domainsOverride.length ? domainsOverride : scope.domains) || []
if (!domains.length) domains = DEFAULT_DOMAINS
domains = domains.slice(0, 6)
log(`Project "${scope.project_name}" · id prefix ${prefix} · ${domains.length} developer domains`)

phase('Survey')
const digests = (await parallel(
  domains.map((d) => () => agent(surveyPrompt(d, scope, prefix), { schema: DIGEST_SCHEMA, phase: 'Survey', label: `survey:${d.key}` })),
)).filter(Boolean)

// ── PHASE 1: lean design -> critique -> finalize ───────────────────────────
phase('Design')
log(`Product Owner drafting the lean backlog from ${digests.length} digests`)
const draft = await agent(designPrompt(scope, prefix, digests), {
  agentType: 'Product Owner', schema: LEAN_BACKLOG_SCHEMA, phase: 'Design', label: 'po:draft',
})
log(`Lean draft has ${draft.stories.length} stories`)

phase('Critique')
log('Developers adversarially reviewing the lean draft')
const critiques = (await parallel(
  domains.map((d) => () => agent(critiquePrompt(d, scope, prefix, draft), { schema: CRITIQUE_SCHEMA, phase: 'Critique', label: `critique:${d.key}` })),
)).filter(Boolean)

phase('Finalize')
log(`Product Owner finalizing the lean backlog with ${critiques.length} critiques`)
const leanFinal = await agent(finalizePrompt(scope, prefix, draft, critiques), {
  agentType: 'Product Owner', schema: LEAN_BACKLOG_SCHEMA, phase: 'Finalize', label: 'po:final',
})
log(`Lean backlog finalized (phase 1): ${leanFinal.stories.length} stories, ${leanFinal.open_questions.length} open questions`)

// ── PHASE 2: groom -> groom-critique -> groom-finalize (in place) ──────────
phase('Groom')
log('Product Owner grooming every lean story in place (phase 2)')
const groomedDraft = await agent(groomPrompt(scope, prefix, leanFinal, digests), {
  agentType: 'Product Owner', schema: GROOMED_BACKLOG_SCHEMA, phase: 'Groom', label: 'po:groom',
})
log(`Groomed draft has ${groomedDraft.stories.length} stories (fully detailed)`)

phase('Groom Critique')
log('Developers adversarially reviewing the groomed detail')
const groomCritiques = (await parallel(
  domains.map((d) => () => agent(groomCritiquePrompt(d, scope, prefix, groomedDraft), { schema: GROOM_CRITIQUE_SCHEMA, phase: 'Groom Critique', label: `groom-critique:${d.key}` })),
)).filter(Boolean)

phase('Groom Finalize')
log(`Product Owner finalizing the groomed backlog with ${groomCritiques.length} groom critiques`)
const groomedFinal = await agent(groomFinalizePrompt(scope, prefix, groomedDraft, groomCritiques), {
  agentType: 'Product Owner', schema: GROOMED_BACKLOG_SCHEMA, phase: 'Groom Finalize', label: 'po:groom-final',
})
log(`Groomed backlog finalized (phase 2): ${groomedFinal.stories.length} stories, ${groomedFinal.open_questions.length} open questions`)

// Render the GROOMED design into project/backlog.json, then adversarially
// verify the written file is faithful + valid against the STRICT validator,
// repairing on drift (up to 2 attempts). Delegated to general-purpose agents
// because the script has no FS/shell access.
phase('Render')
log('Rendering the final groomed backlog into project/backlog.json')
let render = await agent(renderPrompt(groomedFinal), {
  agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: 'render',
})

phase('Verify')
log('Adversarially verifying the written groomed backlog.json is faithful and valid')
let verify = await agent(verifyPrompt(groomedFinal), {
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
  render = await agent(repairPrompt(groomedFinal, verify), {
    agentType: 'general-purpose', schema: RENDER_SCHEMA, phase: 'Render', label: `repair:${repairs}`,
  })
  verify = await agent(verifyPrompt(groomedFinal), {
    agentType: 'general-purpose', schema: VERIFY_SCHEMA, phase: 'Verify', label: `verify:${repairs}`,
  })
}

log(
  verify && verify.faithful && verify.validator_passed
    ? `groomed backlog.json written, validated & verified: ${verify.story_count} stories`
    : 'groomed backlog.json written but verification flagged issues — see result.verify',
)

return { groomedFinal, leanFinal, groomedDraft, groomCritiques, draft, digests, critiques, scope, prefix, render, verify }
