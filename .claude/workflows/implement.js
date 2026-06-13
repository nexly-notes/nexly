export const meta = {
  name: 'implement',
  description:
    'Tight build pipeline for ANY task on ANY project: one intake agent reads the plan (if given) and the repo, decides TDD (follows the plan if it states a testing approach, otherwise assesses the task), then builds in file-disjoint waves — RED tests first when TDD is on — runs an integration gate, and finishes with a small adversarial review panel (correctness+tests, security, requirements) that tries to REFUTE the change. With no task/plan args, intake works from the project handoff (project/handoffs/handoff.md).',
  whenToUse:
    'Run to build a feature or bugfix without the explore/research/plan/plan-review pipeline — bring your own plan, just a task, or nothing at all: with NO task/plan args the intake agent MUST work from the project handoff (project/handoffs/handoff.md, searching the repo if it moved), and if no handoff exists the run returns status "needs-input" so the caller can ask the user what to implement. Pass args as a string task, or { task, plan, planPath, ... }. If the plan/handoff explicitly states a testing approach (TDD required or waived) or the task size/difficulty, the workflow follows it; otherwise the intake agent assesses them from the task and the project preferences (CLAUDE.md). Every phase is capped small (intake 1, RED/build <= maxUnits [default 4, max 6], integration <= 2, review 3, report 1). The intake agent also sizes the task (xs/s/m/l/xl/xxl), which picks the developer tier: xs sonnet@high, s sonnet@max, m opus@high, l opus@xhigh, xl/xxl opus@max; reviewers run on Fable 5. IMPORTANT: writes to the working tree — run on a clean branch. Optional args: { task, plan (inline markdown), planPath (file the intake agent reads), forceTDD, taskSize (xs|s|m|l|xl|xxl, overrides intake sizing), testCommand, maxUnits, maxIntegrationFixes, slug, models }.',
  phases: [
    {
      title: 'Intake',
      detail:
        'One agent reads the plan — or the project handoff when no args were given — plus the repo: work units, test command, requirements, and the TDD + size decisions (plan/handoff-stated, else assessed)',
    },
    {
      title: 'Tests (RED)',
      detail: 'TDD only: failing tests per unit, written in parallel',
    },
    {
      title: 'Implement',
      detail:
        'GREEN (minimal code + a same-agent tidy pass) or direct build, in dependency/file-disjoint waves',
    },
    {
      title: 'Integration',
      detail:
        'One agent runs the full suite + build to catch cross-unit regressions; bounded fix loop',
    },
    {
      title: 'Adversarial Review',
      detail:
        'Three reviewers try to REFUTE the change: correctness+design+tests, security, requirements (with file:line evidence)',
    },
    {
      title: 'Report',
      detail: 'Consolidate the run into a report under .claude/plans/',
    },
  ],
};

// ---------------------------------------------------------------------------
// DESIGN NOTES
//
// - NO EXPLORE / NO PLANNING. This workflow starts from a task (and optionally
//   an existing plan via args.plan or args.planPath). The single Intake agent
//   grounds itself in the repo, extracts work units from the plan when one is
//   provided, and derives a minimal decomposition otherwise. There is no plan
//   drafting, no plan-review gate, and no human checkpoint.
//
// - HANDOFF FALLBACK. With NO task and NO plan args, the Intake agent must
//   work from the project handoff — project/handoffs/handoff.md first, then a
//   repo-wide search. A found handoff IS the task + plan; a handoff-stated
//   size/difficulty or TDD directive is followed (explicit args still
//   override). If no handoff exists, the run returns { status: 'needs-input' }
//   so the caller asks the user what to implement — it never invents a task.
//
// - TDD DECISION. If the plan explicitly states a testing approach (TDD
//   required, or explicitly waived), the workflow FOLLOWS the plan. If the plan
//   is silent (or absent), the Intake agent assesses whether TDD fits this task
//   and the project's stated preferences (e.g. CLAUDE.md "Prefer TDD").
//   args.forceTDD overrides everything.
//
// - TIGHT PHASES. Every phase is capped: Intake 1 agent; RED and Implement at
//   most maxUnits agents (default 4, clamped to 6); Integration 1 + at most
//   maxIntegrationFixes (default 1); Adversarial Review exactly 3; Report 1.
//
// - DEVELOPER TIERING. Intake resolves the task size — a plan/handoff-stated
//   size/difficulty is followed, otherwise intake assesses it; args.taskSize
//   overrides both. The size picks the developer model + reasoning effort:
//     xs -> sonnet @ high · s -> sonnet @ max · m -> opus @ high
//     l -> opus @ xhigh · xl/xxl -> opus @ max
//   agent() has no effort parameter, so effort rides in the build prompts via
//   the harness thinking keywords (think hard / think harder / ultrathink).
//
// - ADVERSARIAL REVIEW. Reviewers are skeptics, not checklist-fillers: each is
//   prompted to actively try to refute that the change is correct/secure/
//   complete, and a finding must carry evidence (file:line, a failing command,
//   or a concrete exploit path) to count. All three lenses run on Fable 5
//   (model: 'fable') — the strongest tier is reserved for the review gate.
//
// - AGENT TYPES. Only agents that exist in this registry are used:
//   read-only review/intake -> Explore (has Bash, cannot Write/Edit)
//   security review -> security-auditor
//   write-capable build/integration/report -> general-purpose
//
// - PARALLELISM. Units declare the files they own; scheduleWaves() runs
//   dependency-ready, file-disjoint units concurrently and serializes the rest,
//   so concurrent agents never edit the same file.
// ---------------------------------------------------------------------------

const input = typeof args === 'string' ? { task: args } : args || {};
let task = (input.task || input.feature || input.instruction || '').trim();
const planInline = (input.plan || '').trim();
const planPath = (input.planPath || '').trim();
// No task and no plan → handoff mode: intake must find and build from the
// project handoff (project/handoffs/handoff.md, searched if moved); with no
// handoff found the run stops so the user can be asked what to implement.
const handoffMode = !task && !planInline && !planPath;

const num = (v, d) => (Number.isFinite(v) ? v : d);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const CFG = {
  maxUnits: clamp(num(input.maxUnits, 4), 1, 6),
  maxIntegrationFixes: clamp(num(input.maxIntegrationFixes, 1), 0, 2),
  forceTDD: typeof input.forceTDD === 'boolean' ? input.forceTDD : undefined,
  testCommand: (input.testCommand || '').trim(),
};
// In handoff mode the task is only known after intake, so the report slug is
// resolved post-intake via slugify().
const slugify = (s) =>
  (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .split('-')
    .slice(0, 6)
    .join('-') || 'task';

// Per-agent model tiers — Fable for the adversarial review panel, Sonnet for
// intake/tests/integration, Haiku for the report. The DEVELOPER model + effort
// are picked from the task size after intake (see DEV_TIERS); args.models
// can override any role, e.g. { models: { developer: 'opus' } }.
// Values: 'fable'|'opus'|'sonnet'|'haiku'.
const MODELS = {
  intake: 'sonnet',
  testAuthor: 'sonnet',
  integration: 'sonnet',
  review_correctness: 'fable',
  review_security: 'fable',
  review_requirements: 'fable',
  report: 'haiku',
  ...(input.models || {}),
};

// Developer tier by task size: Opus for medium and up, Sonnet for small/xs,
// with reasoning effort scaled to the size. agent() has no effort parameter,
// so effort is conveyed in-prompt via the harness thinking keywords
// (think hard < think harder < ultrathink).
const SIZES = ['xs', 's', 'm', 'l', 'xl', 'xxl'];
const DEV_TIERS = {
  xs: { model: 'sonnet', effort: 'high' },
  s: { model: 'sonnet', effort: 'max' },
  m: { model: 'opus', effort: 'high' },
  l: { model: 'opus', effort: 'xhigh' },
  xl: { model: 'opus', effort: 'max' },
  xxl: { model: 'opus', effort: 'max' },
};
const EFFORT_LINES = {
  high: 'EFFORT: HIGH. Think hard before you code — trace the affected paths and edge cases, then implement.',
  xhigh:
    'EFFORT: EXTRA HIGH. Think harder before you code — reason through the design, failure modes, and edge cases end-to-end first.',
  max: 'EFFORT: MAXIMUM. Ultrathink before you code — exhaustively reason through the design, alternatives, failure modes, and edge cases first.',
};

const dedupe = (a) => Array.from(new Set((a || []).filter(Boolean)));
const clip = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : s || '');

// ---------------------------------------------------------------------------
// Wave scheduler: order units by their dependency DAG; within a wave keep them
// file-disjoint so parallel build agents never touch the same file. Units with
// no declared files (unknown footprint) are treated as conflicting with all and
// run alone. Dependency cycles degrade gracefully to a serial tail.
// ---------------------------------------------------------------------------

function footprintOf(u) {
  return u.files && u.files.length
    ? { wild: false, files: new Set(u.files) }
    : { wild: true, files: new Set() };
}
function conflicts(a, b) {
  if (a.wild || b.wild) return true;
  for (const f of a.files) if (b.files.has(f)) return true;
  return false;
}
function scheduleWaves(units) {
  const byId = new Map(units.map((u) => [u.id, u]));
  const fp = new Map(units.map((u) => [u.id, footprintOf(u)]));
  const done = new Set();
  const waves = [];
  let remaining = units.slice();
  let guard = 0;
  while (remaining.length && guard++ < 500) {
    const ready = remaining.filter((u) =>
      (u.depends_on || []).every((d) => !byId.has(d) || done.has(d)),
    );
    if (!ready.length) {
      for (const u of remaining) {
        waves.push([u]);
        done.add(u.id);
      }
      remaining = [];
      break;
    }
    const wave = [];
    for (const u of ready) {
      if (wave.every((w) => !conflicts(fp.get(u.id), fp.get(w.id))))
        wave.push(u);
    }
    wave.forEach((u) => done.add(u.id));
    waves.push(wave);
    const inWave = new Set(wave.map((u) => u.id));
    remaining = remaining.filter((u) => !inWave.has(u.id));
  }
  for (const u of remaining) waves.push([u]);
  return waves;
}

// ---------------------------------------------------------------------------
// Adversarial review panel — exactly three lenses, each tasked with REFUTING
// the change rather than approving it.
// ---------------------------------------------------------------------------

const REVIEW_DIMENSIONS = [
  {
    key: 'correctness',
    agent: 'Explore',
    model: MODELS.review_correctness,
    covers:
      'CORRECTNESS, DESIGN & TESTS — try to prove the change does NOT work: logic errors (off-by-one, null/undefined, races, wrong types, error propagation), unhandled edge cases (empty/single/large/malformed input, boundaries, failure modes), design flaws (broken boundaries, over/under-engineering, dead code), and weak tests (tautological assertions, over-mocking, behaviors with no test, tests that would still pass if the feature were broken). RUN the tests as part of your attack.',
  },
  {
    key: 'security',
    agent: 'security-auditor',
    model: MODELS.review_security,
    covers:
      'SECURITY — attack the change: injection (SQL/command/template/header/XSS), authn/authz flaws & IDOR/privilege escalation, secret & PII exposure (logs, errors), missing input validation/output encoding, CSRF, insecure or vulnerable dependencies, and cryptography misuse. A finding must name a concrete exploit path.',
  },
  {
    key: 'requirements',
    agent: 'Explore',
    model: MODELS.review_requirements,
    covers:
      'REQUIREMENTS — try to prove a requirement is NOT met. Check EVERY acceptance criterion against the implementation and demand file:line evidence that it is satisfied; anything you cannot evidence goes in unmet_requirements. RUN the test suite; zero tolerance for failures.',
  },
];

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const INTAKE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'restated_task',
    'task_source',
    'handoff_path',
    'test_command',
    'requirements',
    'plan_found',
    'plan_tdd_directive',
    'use_tdd',
    'tdd_rationale',
    'plan_size_directive',
    'task_size',
    'work_units',
    'integration_check',
    'open_questions',
  ],
  properties: {
    restated_task: { type: 'string' },
    task_source: {
      type: 'string',
      enum: ['args', 'handoff', 'none'],
      description:
        '"args" if the caller supplied the task, "handoff" if it was derived from a handoff file, "none" if no task was given and no handoff could be found',
    },
    handoff_path: {
      type: 'string',
      description:
        'Repo-relative path of the handoff file the task was derived from; empty if none',
    },
    test_command: {
      type: 'string',
      description:
        'Command that runs this repo test suite (e.g. `npm test`, `pytest`). Empty if none exists.',
    },
    requirements: {
      type: 'array',
      items: { type: 'string' },
      description:
        'Concrete, testable acceptance criteria distilled from the plan/task/specs — these gate the requirements review',
    },
    plan_found: { type: 'boolean' },
    plan_tdd_directive: {
      type: 'string',
      enum: ['tdd', 'no-tdd', 'silent'],
      description:
        '"tdd" if the plan explicitly directs test-driven development, "no-tdd" if it explicitly waives it, "silent" if the plan says nothing (or no plan was provided)',
    },
    use_tdd: {
      type: 'boolean',
      description:
        'The final TDD decision: follow the plan directive when not silent; otherwise your assessment of the task + project preferences',
    },
    tdd_rationale: { type: 'string' },
    plan_size_directive: {
      type: 'string',
      enum: ['xs', 's', 'm', 'l', 'xl', 'xxl', 'silent'],
      description:
        'The size/difficulty the plan/handoff EXPLICITLY states (map wording — trivial→xs, small→s, medium→m, large→l, very large/architecturally risky→xl, sweeping→xxl); "silent" if it states none (or no plan/handoff was provided)',
    },
    task_size: {
      type: 'string',
      enum: ['xs', 's', 'm', 'l', 'xl', 'xxl'],
      description:
        'The FINAL size decision: follow plan_size_directive when not silent; otherwise your own assessment of the overall complexity. xs = trivial tweak (one spot, no design), s = small single-file/unit change, m = multi-file feature with some design, l = large feature spanning modules, xl = very large or architecturally risky, xxl = sweeping cross-cutting change',
    },
    work_units: {
      type: 'array',
      description:
        'Independently-buildable units forming a DAG. Keep file sets DISJOINT across units that can run in parallel; declare real ordering via depends_on.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: [
          'id',
          'name',
          'description',
          'files',
          'test_files',
          'public_contract',
          'behaviors',
          'depends_on',
        ],
        properties: {
          id: { type: 'string', description: 'Stable short id, e.g. "U1"' },
          name: { type: 'string' },
          description: { type: 'string' },
          files: {
            type: 'array',
            items: { type: 'string' },
            description:
              'Repo-relative production files THIS unit creates/modifies. Disjoint from other units to enable parallel builds.',
          },
          test_files: {
            type: 'array',
            items: { type: 'string' },
            description: 'Repo-relative test files for THIS unit',
          },
          public_contract: {
            type: 'string',
            description:
              'The interface other units depend on, so they can be built against it without seeing the implementation',
          },
          behaviors: {
            type: 'array',
            items: { type: 'string' },
            description:
              'Testable behaviors this unit must exhibit — these drive its tests',
          },
          depends_on: {
            type: 'array',
            items: { type: 'string' },
            description: 'ids of units that must be implemented first',
          },
        },
      },
    },
    integration_check: {
      type: 'string',
      description:
        'The command(s) that validate the whole change together (full test suite + build/lint)',
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
};

const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'unit_id',
    'test_files',
    'tests_added',
    'ran_command',
    'observed_failure',
    'all_failing_as_expected',
    'notes',
  ],
  properties: {
    unit_id: { type: 'string' },
    test_files: { type: 'array', items: { type: 'string' } },
    tests_added: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'file', 'behavior'],
        properties: {
          name: { type: 'string' },
          file: { type: 'string' },
          behavior: { type: 'string' },
        },
      },
    },
    ran_command: { type: 'string' },
    observed_failure: {
      type: 'string',
      description:
        'Actual failing output proving the tests fail for the RIGHT reason (feature missing — not a typo/import error)',
    },
    all_failing_as_expected: { type: 'boolean' },
    notes: { type: 'string' },
  },
};

const BUILD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'unit_id',
    'files_touched',
    'ran_command',
    'unit_tests_pass',
    'test_output',
    'modified_tests',
    'notes',
  ],
  properties: {
    unit_id: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    ran_command: { type: 'string' },
    unit_tests_pass: { type: 'boolean' },
    test_output: { type: 'string' },
    modified_tests: {
      type: 'boolean',
      description: 'MUST be false under TDD — tests are frozen during GREEN',
    },
    notes: { type: 'string' },
  },
};

const INTEGRATION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'ran_command',
    'all_tests_pass',
    'build_ok',
    'output',
    'failures',
    'notes',
  ],
  properties: {
    ran_command: { type: 'string' },
    all_tests_pass: { type: 'boolean' },
    build_ok: { type: 'boolean' },
    output: { type: 'string' },
    failures: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
};

const DIMENSION_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['dimension', 'verdict', 'confidence_score', 'findings', 'summary'],
  properties: {
    dimension: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    confidence_score: { type: 'integer', minimum: 0, maximum: 100 },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'location', 'issue', 'evidence', 'fix'],
        properties: {
          severity: {
            type: 'string',
            enum: ['critical', 'high', 'medium', 'low'],
          },
          location: { type: 'string' },
          issue: { type: 'string' },
          evidence: {
            type: 'string',
            description:
              'The proof: file:line, failing command output, or a concrete exploit path. No evidence, no finding.',
          },
          fix: { type: 'string' },
        },
      },
    },
    unmet_requirements: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

const REPORT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['report_path', 'overall_verdict', 'blocking_findings', 'summary'],
  properties: {
    report_path: { type: 'string' },
    overall_verdict: { type: 'string', enum: ['pass', 'needs-work', 'fail'] },
    blocking_findings: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

// ---------------------------------------------------------------------------
// Prompt builders
// ---------------------------------------------------------------------------

function planBlock() {
  if (planInline)
    return `PLAN (provided by the caller — this is the plan to build):\n"""\n${planInline}\n"""`;
  if (planPath)
    return `PLAN FILE: \`${planPath}\` — READ this file; it is the plan to build. If it does not exist, say so in open_questions and work from the task alone.`;
  if (handoffMode)
    return `PLAN: the caller provided NO task and NO plan — you MUST work from the project handoff.
1. Read \`project/handoffs/handoff.md\` (the usual location).
2. If it is not there, SEARCH the repo for one (e.g. glob \`**/handoff*.md\`, prefer the most recently modified) before giving up.
3. If a handoff is found: it IS the task and the plan. Set task_source="handoff" and handoff_path to its repo-relative path, derive restated_task, requirements, and work_units from it, and honor any testing approach or size/difficulty it states (see the TDD and SIZE decisions below).
4. If NO handoff exists anywhere: set task_source="none", handoff_path="", leave work_units empty, and return immediately — the user must be ASKED what to implement first. Do NOT invent a task.`;
  return 'PLAN: none provided — work from the task and the repository alone.';
}

function intakePrompt() {
  return `You are a tech lead doing INTAKE for a build that starts immediately — there is no separate planning phase after you. Ground every claim in the repository; do not guess.

TASK:
${task ? `"""\n${task}\n"""` : '(none provided — derive it from the handoff per the PLAN instructions below, and restate it in restated_task)'}

${planBlock()}

Produce the build brief:
1. restated_task — restate the task sharply in one or two sentences. Set task_source ("args"/"handoff"/"none") and handoff_path to match where the task came from.
2. test_command — the command that runs this repo's test suite. ${CFG.testCommand ? `The caller supplied "${CFG.testCommand}" — verify it fits and use it.` : 'Infer it from the repo; empty string if there is no test setup.'}
3. requirements — the concrete, TESTABLE acceptance criteria this work must satisfy. Trace to the plan, the task, and any spec the repo defines (e.g. CLAUDE.md, project/specs/**).
4. THE TDD DECISION:
   - If the plan EXPLICITLY directs test-driven development (or explicitly says to skip tests-first), set plan_tdd_directive to "tdd"/"no-tdd" and FOLLOW it: use_tdd matches the directive.
   - If the plan is silent or absent, set plan_tdd_directive="silent" and ASSESS it yourself: require TDD for new features, bug fixes, behavior changes, and non-trivial testable logic; skip it for pure config/scaffolding/generated/throwaway code. Honor the project's stated preferences (read CLAUDE.md — if it prefers TDD, lean strongly toward it).
   - Explain the decision in tdd_rationale.
5. THE SIZE DECISION:
   - If the plan/handoff EXPLICITLY states the task's size or difficulty (e.g. "Difficulty: Large (size \`l\`)"), set plan_size_directive to it and FOLLOW it: task_size matches the directive.
   - If it is silent or absent, set plan_size_directive="silent" and ASSESS task_size (xs/s/m/l/xl/xxl) yourself from the real footprint of the change: files and modules touched, design judgment required, and risk.
   - This picks the build model, so classify honestly — neither inflate nor downplay.
6. work_units — AT MOST ${CFG.maxUnits} independently-buildable units forming a DAG (merge rather than drop work to stay under the cap; one unit is fine for small tasks). If the plan already breaks the work down, extract its units faithfully. Each unit OWNS disjoint production files, has a public_contract others build against, testable behaviors, its own test_files, and depends_on listing ONLY real ordering constraints (false dependencies kill parallelism; the graph must be acyclic).
7. integration_check — the command(s) that validate the whole change together (full suite + build/lint).
8. open_questions — genuine ambiguities; do not paper over them.

Return the structured brief.`;
}

const IRON_LAW =
  'TDD Iron Law: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. One behavior per test, clear names, real code over mocks. Watch each test FAIL for the right reason before any implementation exists.';

function redPrompt(unit, brief, testCommand) {
  return `You are in the RED phase of TDD for ONE work unit. Write ONLY this unit's failing tests — no production/implementation code at all.

${IRON_LAW}

OVERALL TASK:
"""
${task}
"""

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, description: unit.description, public_contract: unit.public_contract, behaviors: unit.behaviors, test_files: unit.test_files, files: unit.files }, null, 2)}

Do this:
1. From the repo root (\`git rev-parse --show-toplevel\`), find the existing test setup and MIRROR its conventions (framework, layout, helpers, fixtures).
2. Write minimal, behavior-focused tests for THIS unit's behaviors — one behavior per test, clear names, real code over mocks, covering key edge cases. Write ONLY to this unit's test_files (${JSON.stringify(unit.test_files)}); do NOT touch other units' files. Test against the public_contract; do not assume internals that do not exist yet.
3. RUN the tests scoped to this unit's test files: \`${testCommand || 'the repo test command'}\`. Capture the output.
4. Confirm every new test FAILS for the RIGHT reason (feature missing) — NOT a typo/import/syntax error. If a test errors instead of failing cleanly, fix the test and re-run until it fails correctly.

Set unit_id="${unit.id}". Return the structured result with observed_failure = the actual failing output.`;
}

function greenPrompt(unit, brief, red, testCommand) {
  return `You are in the GREEN phase of TDD for ONE work unit, running CONCURRENTLY with other units that own DIFFERENT files. Write the MINIMAL production code that makes THIS unit's failing tests pass, then tidy it.

${IRON_LAW}

OVERALL TASK:
"""
${task}
"""

${effortLine}

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, description: unit.description, public_contract: unit.public_contract, files: unit.files, behaviors: unit.behaviors }, null, 2)}

FAILING TESTS to satisfy (do NOT modify them):
${red ? JSON.stringify(red.tests_added, null, 2) : '(tests for this unit were not captured — implement to the behaviors above and run the unit tests)'}
Test files (FROZEN): ${JSON.stringify((red && red.test_files) || unit.test_files)}

Rules:
1. Edit ONLY this unit's production files (${JSON.stringify(unit.files)}). Do NOT touch other units' files or any test file (set modified_tests=false). If a test is genuinely wrong, STOP and explain in notes rather than editing it.
2. Implement the smallest code that passes the tests; match repo conventions (CLAUDE.md / .claude/rules/ if present).
3. RUN ONLY this unit's tests, scoped to ${JSON.stringify((red && red.test_files) || unit.test_files)}: \`${testCommand || 'the repo test command'}\`. Do NOT run a repo-wide format/lint (other agents are editing in parallel — the integration step handles the full suite). Confirm this unit's tests pass.
4. Once green, do a quick tidy pass on YOUR files only — remove duplication/dead code, sharpen names — with NO behavior change, and confirm the unit's tests are still green.

Set unit_id="${unit.id}". Return the structured result with the test_output tail.`;
}

function buildPrompt(unit, brief, testCommand) {
  return `You are implementing ONE work unit directly (TDD was judged unnecessary for this work), running CONCURRENTLY with units that own DIFFERENT files.

OVERALL TASK:
"""
${task}
"""

${effortLine}

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, description: unit.description, public_contract: unit.public_contract, files: unit.files, behaviors: unit.behaviors }, null, 2)}

Rules:
1. Implement ONLY this unit's files (${JSON.stringify(unit.files)}), matching repo conventions (CLAUDE.md / .claude/rules/ if present). Do not touch other units' files. Stay within scope.
2. Validate this unit narrowly: ${testCommand ? `run \`${testCommand}\` scoped to this unit where possible, plus ` : ''}any quick local check. Do NOT run repo-wide format/lint (parallel agents are editing; integration handles the full pass). Set unit_tests_pass to whether your validation passed, and modified_tests=false unless you added/changed tests deliberately.
3. Confirm this unit's behaviors are met.

Set unit_id="${unit.id}". Return the structured result.`;
}

function integrationPrompt(brief, testCommand, changedFiles, prior) {
  const head = prior
    ? `A previous integration run FAILED. Diagnose and FIX the cross-unit issues (edit production code only — never weaken tests), then re-run.\nPREVIOUS FAILURES:\n${JSON.stringify(prior.failures, null, 2)}\n`
    : 'The work units were built in parallel. Run the WHOLE change together to catch cross-unit regressions.\n';
  return `You are the integration gate. Operate from the repo root.

${head}
CHANGED FILES:
${changedFiles.map((f) => '- ' + f).join('\n') || '(use `git status`/`git diff` to discover them)'}

Run the integration check — the full test suite AND the build/lint: ${brief.integration_check ? `\`${brief.integration_check}\`` : testCommand ? `\`${testCommand}\` plus the repo build/lint` : 'the repo test + build commands'}.
- If anything fails, ${prior ? 'fix the production code minimally and re-run until green (do not modify tests to pass).' : 'list each failure precisely.'}
- Output must be pristine (no new errors/warnings).

Return the structured result: all_tests_pass, build_ok, the output tail, and a precise failures list.`;
}

function reviewDimensionPrompt(dim, brief, changedFiles) {
  const target = changedFiles.length
    ? `The change under attack (changed files, plus their immediate context):\n${changedFiles.map((f) => '- ' + f).join('\n')}`
    : 'No explicit file list was captured — use `git diff`/`git status` from the repo root to find what this run changed, and attack that.';
  return `You are an ADVERSARIAL reviewer. Your job is to REFUTE this change — assume it is broken and hunt for the proof. A change you cannot refute earns a "pass"; do not manufacture findings to look thorough.

TASK the change claims to accomplish:
"""
${task}
"""

REQUIREMENTS / ACCEPTANCE CRITERIA:
${JSON.stringify(brief.requirements, null, 2)}

${target}

YOUR ATTACK SURFACE — focus exclusively here:
${dim.covers}

Read the actual files from disk. EVERY finding must carry evidence — a concrete \`file:line\`, a command you ran with its failing output, or a step-by-step exploit path. A suspicion without evidence is not a finding. Return findings as { severity, location, issue, evidence, fix }, ordered by severity. verdict="fail" if any critical/high finding survives your own scrutiny, else "pass". confidence_score = how confident you are in your verdict. If you genuinely cannot refute the change, return an empty findings array and say so in the summary. Set dimension="${dim.key}".

Return the structured review.`;
}

function reportPrompt(
  brief,
  useTDD,
  devSummary,
  waves,
  integration,
  reviews,
  changedFiles,
) {
  const reviewDigest = reviews.map((r) => ({
    dimension: r.key,
    verdict: r.verdict,
    confidence: r.confidence_score,
    findings: r.findings,
    unmet_requirements: r.unmet_requirements || [],
  }));
  return `You are a release engineer writing a consolidated build report and persisting it. Operate from the repo root.

WRITE a markdown report to \`.claude/plans/build-${slug}.md\` (create the directory if needed; if that exact file already exists, append \`-2\`, \`-3\`, … until free). Follow the project's documentation rules if present (no emojis; bullets over prose; max 3 header levels; bold for emphasis). Include, in order:
1. Title + the task.
2. Intake summary: requirements, open questions, and the TDD decision (directive: ${brief.plan_tdd_directive}; used: ${useTDD ? 'TDD' : 'direct build'}; rationale: ${clip(brief.tdd_rationale, 300)}).
3. Build summary: developer tier ${devSummary}, ${waves.length} wave(s) [${waves.map((w) => w.map((u) => u.id).join('+')).join(' , ')}], the integration result, and the changed files.
4. Adversarial review: a table of the ${reviews.length} dimensions (verdict + confidence), then all findings grouped by severity WITH their evidence, then any unmet requirements.
5. Verdict & next steps.

DATA (JSON):
${JSON.stringify({ requirements: brief.requirements, open_questions: brief.open_questions, work_units: brief.work_units, tdd: { directive: brief.plan_tdd_directive, used: useTDD, rationale: brief.tdd_rationale }, integration: integration, changed_files: changedFiles, reviews: reviewDigest }, null, 2)}

After writing, set: report_path = the file you wrote; overall_verdict = "fail" if any dimension has a critical finding, an unmet requirement, or integration is red; "needs-work" if any high/medium findings remain; else "pass". blocking_findings = the critical/high items + any integration failure that must be fixed before merge. summary = 2-3 sentences. Return the structured result.`;
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

phase('Intake');
log(
  handoffMode
    ? 'Intake: no task/plan args — working from the project handoff'
    : `Intake: ${clip(task, 120)}${planPath ? ` (plan: ${planPath})` : planInline ? ' (inline plan)' : ' (no plan)'}`,
);
const brief = await agent(intakePrompt(), {
  agentType: 'Explore',
  model: MODELS.intake,
  schema: INTAKE_SCHEMA,
  phase: 'Intake',
  label: 'intake',
});
// Handoff gate: with no caller-supplied task, a found handoff IS the task;
// with none found, stop and ask the user rather than inventing work.
if (handoffMode && brief.task_source !== 'handoff') {
  log('No handoff found — stopping; the user must be asked what to implement');
  return {
    status: 'needs-input',
    reason:
      'No task/plan args were given and no handoff file exists (checked project/handoffs/handoff.md and searched the repo). Ask the user what to implement, then re-run with args.',
    openQuestions: brief.open_questions || [],
  };
}
if (!task) task = (brief.restated_task || '').trim() || 'the handoff task';
const slug = slugify(input.slug || task);
if (brief.handoff_path)
  log(`Handoff: ${brief.handoff_path} — ${clip(brief.restated_task, 120)}`);
const testCommand = CFG.testCommand || brief.test_command || '';
const useTDD =
  typeof CFG.forceTDD === 'boolean' ? CFG.forceTDD : !!brief.use_tdd;
const tddSource =
  typeof CFG.forceTDD === 'boolean'
    ? 'forced'
    : brief.plan_tdd_directive !== 'silent'
      ? 'plan'
      : 'assessed';

// Resolve the developer tier from the task size (args.taskSize overrides the
// intake classification; args.models.developer overrides the model).
const sizeArg = (input.taskSize || '').toLowerCase();
const sizeKey = SIZES.includes(sizeArg)
  ? sizeArg
  : SIZES.includes(brief.task_size)
    ? brief.task_size
    : 'm';
const sizeSource = SIZES.includes(sizeArg)
  ? 'forced'
  : brief.plan_size_directive && brief.plan_size_directive !== 'silent'
    ? 'plan'
    : 'assessed';
const devTier = DEV_TIERS[sizeKey];
const developerModel = MODELS.developer || devTier.model;
const effortLine = EFFORT_LINES[devTier.effort];
log(
  `TDD ${useTDD ? 'ON' : 'OFF'} (${tddSource}: ${clip(brief.tdd_rationale, 140)}) · test: ${testCommand || '(none)'} · ${brief.requirements.length} requirement(s)`,
);
log(
  `Task size ${sizeKey.toUpperCase()} (${sizeSource}) → developer: ${developerModel} @ ${devTier.effort} effort`,
);

let units = (brief.work_units || []).filter((u) => u && u.id).slice(0, CFG.maxUnits);
if (!units.length)
  units = [
    {
      id: 'U1',
      name: 'implementation',
      description: brief.restated_task || task,
      files: [],
      test_files: [],
      public_contract: '',
      behaviors: brief.requirements || [],
      depends_on: [],
    },
  ];
const waves = scheduleWaves(units);
log(
  `${units.length} work unit(s) → ${waves.length} wave(s): ${waves.map((w) => w.map((u) => u.id).join('+')).join(' , ')}`,
);

const redByUnit = new Map();
let changedFiles = [];

if (useTDD) {
  // RED — failing tests per unit, in parallel. No production code exists yet,
  // so test files cannot collide with build files.
  phase('Tests (RED)');
  log(`Writing failing tests for ${units.length} unit(s) in parallel`);
  const reds = (
    await parallel(
      units.map(
        (u) => () =>
          agent(redPrompt(u, brief, testCommand), {
            agentType: 'general-purpose',
            model: MODELS.testAuthor,
            schema: RED_SCHEMA,
            phase: 'Tests (RED)',
            label: `red:${u.id}`,
          }),
      ),
    )
  ).filter(Boolean);
  reds.forEach((r) => redByUnit.set(r.unit_id, r));
  changedFiles = dedupe(reds.flatMap((r) => r.test_files || []));
}

// Implement — GREEN (TDD) or direct build, in dependency/file-disjoint waves.
phase('Implement');
const builds = [];
for (let i = 0; i < waves.length; i++) {
  const wave = waves[i];
  log(
    `${useTDD ? 'GREEN' : 'Build'} wave ${i + 1}/${waves.length}: ${wave.map((u) => u.id).join(', ')} (parallel)`,
  );
  const res = (
    await parallel(
      wave.map(
        (u) => () =>
          agent(
            useTDD
              ? greenPrompt(u, brief, redByUnit.get(u.id), testCommand)
              : buildPrompt(u, brief, testCommand),
            {
              agentType: 'general-purpose',
              model: developerModel,
              schema: BUILD_SCHEMA,
              phase: 'Implement',
              label: `${useTDD ? 'green' : 'build'}:${u.id}`,
            },
          ),
      ),
    )
  ).filter(Boolean);
  builds.push(...res);
}
if (useTDD && builds.some((b) => b.modified_tests))
  log(
    'WARNING: a GREEN agent reported modifying tests — TDD violated; check the report',
  );
changedFiles = dedupe([
  ...changedFiles,
  ...builds.flatMap((b) => b.files_touched || []),
]);

// Integration gate — run the whole change together once; bounded fix loop.
phase('Integration');
log('Running the full suite + build to catch cross-unit regressions');
let integration = await agent(
  integrationPrompt(brief, testCommand, changedFiles, null),
  {
    agentType: 'general-purpose',
    model: MODELS.integration,
    schema: INTEGRATION_SCHEMA,
    phase: 'Integration',
    label: 'integration',
  },
);
let fixes = 0;
while (
  !(integration.all_tests_pass && integration.build_ok) &&
  fixes < CFG.maxIntegrationFixes
) {
  fixes++;
  log(
    `Integration red (${integration.failures.length} failure(s)) — fix attempt ${fixes}/${CFG.maxIntegrationFixes}`,
  );
  integration = await agent(
    integrationPrompt(brief, testCommand, changedFiles, integration),
    {
      agentType: 'general-purpose',
      model: MODELS.integration,
      schema: INTEGRATION_SCHEMA,
      phase: 'Integration',
      label: `integration:fix${fixes}`,
    },
  );
}
log(
  integration.all_tests_pass && integration.build_ok
    ? 'Integration green'
    : 'Integration still red — surfaced in the report',
);

// Adversarial review — three skeptics, each trying to refute the change.
phase('Adversarial Review');
log('3 adversarial reviewers attacking the change: correctness+tests, security, requirements');
const reviews = (
  await parallel(
    REVIEW_DIMENSIONS.map(
      (dim) => () =>
        agent(reviewDimensionPrompt(dim, brief, changedFiles), {
          agentType: dim.agent,
          model: dim.model,
          schema: DIMENSION_REVIEW_SCHEMA,
          phase: 'Adversarial Review',
          label: `refute:${dim.key}`,
        }).then((r) => ({ ...r, key: dim.key })),
    ),
  )
).filter(Boolean);
const failedDims = reviews
  .filter((r) => r.verdict === 'fail')
  .map((r) => r.key);
log(
  failedDims.length
    ? `Refuted on: ${failedDims.join(', ')}`
    : 'No reviewer could refute the change',
);

phase('Report');
const report = await agent(
  reportPrompt(
    brief,
    useTDD,
    `${sizeKey.toUpperCase()} (${sizeSource}) → ${developerModel} @ ${devTier.effort} effort`,
    waves,
    integration,
    reviews,
    changedFiles,
  ),
  {
    agentType: 'general-purpose',
    model: MODELS.report,
    schema: REPORT_SCHEMA,
    phase: 'Report',
    label: 'report',
  },
);
log(
  `Build complete — overall: ${report.overall_verdict}. Report: ${report.report_path}`,
);

return {
  status: 'complete',
  task,
  taskSource: brief.task_source,
  handoffPath: brief.handoff_path || '',
  useTDD,
  tddSource,
  tddRationale: brief.tdd_rationale,
  taskSize: sizeKey,
  sizeSource,
  developerModel,
  developerEffort: devTier.effort,
  units: units.length,
  waves: waves.map((w) => w.map((u) => u.id)),
  integrationGreen: integration.all_tests_pass && integration.build_ok,
  changedFiles,
  reviews: reviews.map((r) => ({
    dimension: r.key,
    verdict: r.verdict,
    confidence: r.confidence_score,
    findings: r.findings.length,
  })),
  openQuestions: brief.open_questions,
  overallVerdict: report.overall_verdict,
  blockingFindings: report.blocking_findings,
  reportPath: report.report_path,
};
