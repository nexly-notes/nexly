export const meta = {
  name: 'implement',
  description:
    'End-to-end, parallelized implementation lifecycle for ANY task on ANY project: explore the codebase + research the latest docs, draft a DECOMPOSED plan (a DAG of independently-buildable work units), gate it on a reviewer confidence score (and a TDD decision), then build it with maximum safe parallelism — RED tests written per-unit in parallel and reviewed by multiple lenses in parallel, GREEN implemented in dependency/file-disjoint waves, an integration gate, parallel refactor — and finish with a multi-dimension final review (design, functionality, complexity, tests, naming, comments, style, documentation) plus security and requirements reviews.',
  whenToUse:
    'Run to take a feature or bugfix from idea to reviewed code through one gated, heavily-parallel pipeline. Pass the task as args (string, or { task, ... }). It runs in TWO steps around a single human checkpoint: the FIRST run explores, researches, drafts a decomposed plan, and gates it on a reviewer confidence score (default 80, with a revise loop) — then PAUSES and returns the plan for you to review (status "awaiting-plan-approval"); NO code is written yet. To build it, relaunch the SAME run with resumeFromRunId and args.proceed=true: the explore/plan/review phases replay from cache (no re-spend) and only the implementation runs live (RED + per-unit test review, GREEN/refactor waves, integration, final review). Pass proceed=true on the first run to skip the pause and go end-to-end. IMPORTANT: the implement phase writes to the working tree — run it on a clean branch; resume is same-session. Optional args: { task, proceed, scoreThreshold, maxPlanRevisions, maxTestRevisions, testReviewers, planReviewers, maxExplorers, maxResearchers, forceTDD, testCommand, slug, models }.',
  phases: [
    {
      title: 'Scope',
      detail:
        'One explorer reads the repo + task: what to explore, what to research, the test command, the requirements',
    },
    {
      title: 'Explore & Research',
      detail:
        'Parallel: codebase explorers by area + doc researchers (context7/web) per library — barrier before planning',
    },
    {
      title: 'Plan',
      detail:
        'Planner drafts a decomposed plan: a DAG of work units with disjoint files + contracts (revised here on a low score)',
    },
    {
      title: 'Plan Review',
      detail:
        'Reviewer panel scores confidence 0-100 and decides TDD; <threshold loops a revise, >=threshold proceeds',
    },
    {
      title: 'Tests (RED) & Review',
      detail:
        'Parallel per unit: write failing tests; each unit reviewed by N lenses in parallel; barrier before GREEN',
    },
    {
      title: 'Implement',
      detail:
        'GREEN in dependency/file-disjoint waves (parallel within a wave), or a parallel direct build when TDD is off',
    },
    {
      title: 'Integration',
      detail:
        'One agent runs the full suite + build to catch cross-unit regressions; bounded fix loop',
    },
    {
      title: 'Refactor',
      detail:
        'Parallel per file-disjoint unit: clean up, keep tests green, no behavior change (TDD only)',
    },
    {
      title: 'Final Review',
      detail:
        'Parallel: design+complexity, functionality, tests, naming+comments+style+docs, security, requirements',
    },
    {
      title: 'Report',
      detail:
        'Consolidate plan, scores, TDD decision, parallelism, and all findings into a report under .claude/plans/',
    },
  ],
};

// ---------------------------------------------------------------------------
// DESIGN NOTES / JUDGMENT CALLS (per the request to not blindly follow project
// skills/commands/agents):
//
// - PORTABILITY OVER REUSE. Every behavioral instruction below is SELF-CONTAINED
//   in the prompts. The workflow does NOT depend on this repo's /plan, /tdd,
//   /code-review skills or their templates/hooks existing — so it runs unchanged
//   on any project. The prompts (not the agents' built-in assumptions) govern
//   output, and project files are referenced only as "if present".
//
// - COMPANION AGENTS (tool-scoped, since we no longer rely on hooks). Each phase
//   runs a purpose-built subagent whose `.claude/agents/*.md` `tools:` allowlist
//   is the ONLY tool restriction. Read-only roles physically cannot write:
//     Scope/Explore -> Explore · Research -> Researcher · Plan -> Plan
//     Plan review -> Plan Reviewer · Test review + tests dim -> Test Reviewer
//     Design/Functionality/Readability dims -> Code Reviewer · Security -> Security Auditor
//     Requirements -> QA Specialist
//   Write-capable roles are scoped to exactly what they need (no web/MCP):
//     RED/test-revise -> Test Author · GREEN/build/refactor -> Frontend|Backend
//     Developer (routed by unit.domain via devFor) · Integration -> Debugger
//     Report -> Report Writer (no Bash).
//   These agents must ship alongside this workflow; on a project that lacks them,
//   swap the agentType back to 'general-purpose' (it has all tools).
//   NOTE: a `tools:` allowlist is tool-granular, not path-granular — it cannot stop
//   a writer from editing the wrong file. Per-unit file isolation is upheld by the
//   disjoint-file wave scheduler + the prompts + running on a clean branch.
//
// - PARALLELISM MODEL. Speed comes from a decomposed plan. The planner emits a
//   DAG of work units, each declaring the files it owns + a public contract.
//   * RED + per-unit test review run as a pipeline (each unit flows
//     independently; no inter-stage barrier within the phase).
//   * Test review is "bumped": each unit's tests are judged by N lenses in
//     parallel (correctness / coverage / anti-patterns), configurable.
//   * A barrier after RED+review enforces "all tests reviewed before GREEN".
//   * GREEN runs in WAVES: within a wave, units are dependency-ready AND
//     file-disjoint, so concurrent agents never edit the same file. Waves are
//     scheduled by scheduleWaves() below.
//   * Refactor reuses those file-disjoint waves; final review fans out per
//     dimension. Explore/research fan out per scope target.
//
// - HUMAN CHECKPOINT (the only one). The first run stops after the plan is
//   reviewed/approved and returns it (status 'awaiting-plan-approval') — nothing
//   is written. Resume the SAME run with args.proceed=true to build; the
//   explore/plan/review prefix replays from cache (no re-spend), only the
//   implement phases run live. The proceed flag gates the branch BELOW the plan,
//   so it never alters an upstream prompt and the cache stays intact.
//   Same-session only; pass proceed=true on the first run to skip the pause.
// ---------------------------------------------------------------------------

const input = typeof args === 'string' ? { task: args } : args || {};
const task = (input.task || input.feature || input.instruction || '').trim();
if (!task) {
  throw new Error(
    'implement requires a task. Pass args as a string, or as { task: "..." }.',
  );
}

const num = (v, d) => (Number.isFinite(v) ? v : d);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const CFG = {
  threshold: num(input.scoreThreshold, 80),
  maxPlanRevisions: num(input.maxPlanRevisions, 3),
  maxTestRevisions: num(input.maxTestRevisions, 2),
  maxIntegrationFixes: num(input.maxIntegrationFixes, 1),
  maxExplorers: clamp(num(input.maxExplorers, 5), 1, 8),
  maxResearchers: clamp(num(input.maxResearchers, 4), 0, 6),
  // how many test-review lenses per unit (the "bumped" reviewer count)
  testReviewers: clamp(num(input.testReviewers, 2), 1, 3),
  // plan-review panel size (distinct lenses); 1 = single holistic reviewer
  planReviewers: clamp(num(input.planReviewers, 1), 1, 3),
  forceTDD: typeof input.forceTDD === 'boolean' ? input.forceTDD : undefined,
  testCommand: (input.testCommand || '').trim(),
};
const slug =
  (input.slug || task)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .split('-')
    .slice(0, 6)
    .join('-') || 'task';

// Per-agent model tiers — minimize cost by reserving Opus for the high-leverage
// reasoning gates (plan, plan review, the deep final-review lenses), running the
// coding + most reviews on Sonnet, and pushing cheap/mechanical work (doc
// research, refactor, report) to Haiku. Override any key via args.models, e.g.
// { models: { developer: 'opus', refactor: 'sonnet' } }. Values: 'opus'|'sonnet'|'haiku'.
const MODELS = {
  scope: 'sonnet',
  explore: 'sonnet',
  research: 'haiku',
  plan: 'opus',
  planReview: 'opus',
  testAuthor: 'sonnet', // Test Author — RED + test-revise
  testReview: 'sonnet', // Test Reviewer — pre-GREEN test review
  developer: 'sonnet', // Frontend/Backend Developer — GREEN + direct build
  integration: 'sonnet', // Debugger — integration fix loop
  refactor: 'haiku', // Frontend/Backend Developer — refactor pass
  review_design: 'opus',
  review_functionality: 'opus',
  review_tests: 'sonnet',
  review_readability: 'sonnet',
  review_security: 'opus',
  review_requirements: 'sonnet',
  report: 'haiku', // Report Writer
  ...(input.models || {}),
};

// Route a work unit to the right domain developer. Frontend = client/UI/browser;
// everything else (incl. non-web projects) goes to the Backend Developer.
const devFor = (u) =>
  u && u.domain === 'frontend' ? 'Frontend Developer' : 'Backend Developer';

const dedupe = (a) => Array.from(new Set((a || []).filter(Boolean)));
const clip = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : s || '');
const sanitize = (s) =>
  (s || '')
    .toString()
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .slice(0, 28);

// ---------------------------------------------------------------------------
// Wave scheduler: order units by their dependency DAG; within a wave keep them
// file-disjoint so parallel GREEN agents never touch the same file. Units with
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
// Review lenses
// ---------------------------------------------------------------------------

const TEST_LENSES = [
  {
    key: 'correctness',
    focus:
      'CORRECTNESS & BEHAVIOR — assertions encode the intended behavior (not inverted, not tautological); tests exercise REAL behavior, not mock interactions or private internals; failure messages are diagnosable.',
  },
  {
    key: 'coverage',
    focus:
      'COVERAGE & EDGE CASES — every behavior/acceptance-criterion for this unit is covered, including negative paths, boundaries, and empty/single/large/malformed inputs. List anything missing.',
  },
  {
    key: 'anti-patterns',
    focus:
      'ANTI-PATTERNS & RELIABILITY — over-mocking that hides real behavior, time/order dependence, shared mutable state, hidden coupling, flakiness, asserting on incidental output, or test-only hooks leaking into production.',
  },
];
const PLAN_LENSES = [
  {
    key: 'overall',
    focus:
      'HOLISTIC quality across completeness, clarity, feasibility, risk management, and alignment with the task + requirements.',
  },
  {
    key: 'requirements',
    focus:
      'REQUIREMENTS ALIGNMENT — trace EVERY requirement/acceptance criterion to a concrete step/unit; flag any that is unaddressed or only implied.',
  },
  {
    key: 'decomposition',
    focus:
      'DECOMPOSITION & PARALLEL-SAFETY — are work units well-bounded with DISJOINT files and a correct depends_on DAG (no cycles)? Are the declared contracts sufficient to build units independently? Flag units that secretly share files or hide an ordering dependency.',
  },
];
const testLenses = TEST_LENSES.slice(0, CFG.testReviewers);
const planLenses = PLAN_LENSES.slice(0, CFG.planReviewers);

const REVIEW_DIMENSIONS = [
  {
    key: 'design',
    agent: 'Code Reviewer',
    model: MODELS.review_design,
    covers:
      'DESIGN & COMPLEXITY — module boundaries, separation of concerns, soundness of the design decisions, and complexity: over/under-engineering, premature abstraction, dead code, KISS/YAGNI/DRY (and their over-application).',
  },
  {
    key: 'functionality',
    agent: 'Code Reviewer',
    model: MODELS.review_functionality,
    covers:
      'FUNCTIONALITY & RELIABILITY — does the code do what the plan/requirements demand? Logic correctness (off-by-one, null/undefined, races, wrong types, error propagation), and edge cases (empty/single/large/malformed input, boundary values, failure modes, idempotency).',
  },
  {
    key: 'tests',
    agent: 'Test Reviewer',
    model: MODELS.review_tests,
    covers:
      'TESTS — new behavior has tests (unit/integration/e2e as fit); assertions actually verify behavior; negative & edge cases present; isolation is correct; no anti-patterns (testing mocks not behavior, tautologies, time/order-dependence, over-mocking); failures are diagnosable.',
  },
  {
    key: 'readability',
    agent: 'Code Reviewer',
    model: MODELS.review_readability,
    covers:
      'NAMING, COMMENTS, STYLE & DOCUMENTATION — names communicate intent; comments explain WHY not WHAT and none are stale/redundant; conformance to the project STYLE GUIDE / conventions / linter (consult CLAUDE.md and .claude/rules/ if present); documentation (docstrings, README, doc rules) is present and accurate.',
  },
  {
    key: 'security',
    agent: 'Security Auditor',
    model: MODELS.review_security,
    covers:
      'SECURITY — injection (SQL/command/template/header/XSS), authn/authz flaws & IDOR/privilege escalation, secret & PII exposure (logs, errors), input validation & output encoding, CSRF, insecure/vulnerable dependencies, and cryptography (correct primitives, key handling, secure randomness, TLS).',
  },
  {
    key: 'requirements',
    agent: 'QA Specialist',
    model: MODELS.review_requirements,
    covers:
      'REQUIREMENTS — verify EVERY acceptance criterion / requirement is satisfied by the implementation, each with file:line evidence. Flag any unmet/partial criterion in unmet_requirements. RUN the tests; zero tolerance for failures.',
  },
];

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const SCOPE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'restated_task',
    'stack',
    'test_command',
    'explore_targets',
    'research_topics',
    'requirements',
    'open_questions',
  ],
  properties: {
    restated_task: { type: 'string' },
    stack: {
      type: 'string',
      description: 'Languages/frameworks/tools in play, detected from the repo',
    },
    test_command: {
      type: 'string',
      description:
        'Best-guess command to run the test suite (e.g. `npm test`, `pytest`). Empty if none exists.',
    },
    explore_targets: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['area', 'why'],
        properties: { area: { type: 'string' }, why: { type: 'string' } },
      },
    },
    research_topics: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['library', 'focus'],
        properties: { library: { type: 'string' }, focus: { type: 'string' } },
      },
    },
    requirements: {
      type: 'array',
      items: { type: 'string' },
      description:
        'Concrete, testable acceptance criteria distilled from the task + specs',
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
};

// Improved, decomposition-first plan schema. The work_units DAG is the engine
// that drives parallel RED/GREEN; the rest gives reviewers + implementers the
// context they need without guessing.
const PLAN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'objective',
    'in_scope',
    'out_of_scope',
    'approach',
    'interfaces',
    'data_model_changes',
    'work_units',
    'test_strategy',
    'integration_check',
    'risks',
    'rollback',
    'acceptance_criteria',
    'open_questions',
    'plan_markdown',
  ],
  properties: {
    objective: {
      type: 'string',
      description: 'One or two sentences: what this change accomplishes',
    },
    in_scope: { type: 'array', items: { type: 'string' } },
    out_of_scope: { type: 'array', items: { type: 'string' } },
    approach: {
      type: 'string',
      description:
        'The concrete technical approach, grounded in the real modules/APIs found during exploration/research',
    },
    interfaces: {
      type: 'array',
      description:
        'Public contracts (functions/types/endpoints/schemas) introduced or changed — the boundaries units agree on so they can be built independently',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'signature', 'description'],
        properties: {
          name: { type: 'string' },
          signature: { type: 'string' },
          description: { type: 'string' },
        },
      },
    },
    data_model_changes: { type: 'array', items: { type: 'string' } },
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
          'domain',
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
          domain: {
            type: 'string',
            enum: ['frontend', 'backend'],
            description:
              'frontend = client/UI/browser work; backend = everything else (services, data, logic, libraries, CLI, infra). Non-web projects: always backend.',
          },
          description: { type: 'string' },
          files: {
            type: 'array',
            items: { type: 'string' },
            description:
              'Repo-relative production files THIS unit creates/modifies. Must be disjoint from other units to enable parallel builds.',
          },
          test_files: {
            type: 'array',
            items: { type: 'string' },
            description: 'Repo-relative test files for THIS unit',
          },
          public_contract: {
            type: 'string',
            description:
              'The interface other units depend on (so they can be built against it without seeing the implementation)',
          },
          behaviors: {
            type: 'array',
            items: { type: 'string' },
            description:
              'Testable behaviors this unit must exhibit — these drive its RED tests',
          },
          depends_on: {
            type: 'array',
            items: { type: 'string' },
            description:
              'ids of units that must be implemented before this one',
          },
        },
      },
    },
    test_strategy: {
      type: 'string',
      description:
        'Levels (unit/integration/e2e), frameworks, and what the key tests assert',
    },
    integration_check: {
      type: 'string',
      description:
        'The command(s) that validate the whole change together (full test suite + build/lint)',
    },
    risks: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['risk', 'impact', 'likelihood', 'mitigation'],
        properties: {
          risk: { type: 'string' },
          impact: { type: 'string', enum: ['low', 'medium', 'high'] },
          likelihood: { type: 'string', enum: ['low', 'medium', 'high'] },
          mitigation: { type: 'string' },
        },
      },
    },
    rollback: {
      type: 'string',
      description: 'How to back the change out if it goes wrong',
    },
    acceptance_criteria: { type: 'array', items: { type: 'string' } },
    open_questions: { type: 'array', items: { type: 'string' } },
    plan_markdown: {
      type: 'string',
      description: 'Human-readable rendering of the whole plan for the report',
    },
  },
};

const PLAN_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'confidence_score',
    'quality_score',
    'dimension_scores',
    'tdd_required',
    'tdd_rationale',
    'verdict',
    'strengths',
    'weaknesses',
    'required_changes',
    'parallelization_risks',
  ],
  properties: {
    confidence_score: {
      type: 'integer',
      minimum: 0,
      maximum: 100,
      description:
        'Confidence the plan, as written, will succeed. THIS is the gate.',
    },
    quality_score: { type: 'integer', minimum: 0, maximum: 100 },
    dimension_scores: {
      type: 'object',
      additionalProperties: false,
      required: [
        'completeness',
        'clarity',
        'feasibility',
        'risk_management',
        'alignment',
        'decomposition',
      ],
      properties: {
        completeness: { type: 'integer', minimum: 0, maximum: 100 },
        clarity: { type: 'integer', minimum: 0, maximum: 100 },
        feasibility: { type: 'integer', minimum: 0, maximum: 100 },
        risk_management: { type: 'integer', minimum: 0, maximum: 100 },
        alignment: { type: 'integer', minimum: 0, maximum: 100 },
        decomposition: {
          type: 'integer',
          minimum: 0,
          maximum: 100,
          description:
            'Quality of the work-unit DAG: bounded units, disjoint files, correct deps, sufficient contracts',
        },
      },
    },
    tdd_required: { type: 'boolean' },
    tdd_rationale: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'revise'] },
    strengths: { type: 'array', items: { type: 'string' } },
    weaknesses: { type: 'array', items: { type: 'string' } },
    required_changes: { type: 'array', items: { type: 'string' } },
    parallelization_risks: {
      type: 'array',
      items: { type: 'string' },
      description:
        'Units that secretly share files, hidden ordering deps, or contracts too thin to build against in parallel',
    },
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

const TEST_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'lens',
    'verdict',
    'confidence_score',
    'findings',
    'missing_cases',
    'summary',
  ],
  properties: {
    lens: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'revise'] },
    confidence_score: { type: 'integer', minimum: 0, maximum: 100 },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'file', 'issue', 'fix'],
        properties: {
          severity: {
            type: 'string',
            enum: ['critical', 'high', 'medium', 'low'],
          },
          file: { type: 'string' },
          issue: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
    missing_cases: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
};

const GREEN_SCHEMA = {
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
      description: 'MUST be false — tests are frozen during GREEN',
    },
    notes: { type: 'string' },
  },
};

const REFACTOR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'unit_id',
    'files_touched',
    'tests_still_green',
    'changes_summary',
  ],
  properties: {
    unit_id: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    tests_still_green: { type: 'boolean' },
    changes_summary: {
      type: 'string',
      description: 'What was cleaned up; NO behavior added',
    },
  },
};

const IMPLEMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'unit_id',
    'files_touched',
    'ran_command',
    'validation_passed',
    'validation_output',
    'notes',
  ],
  properties: {
    unit_id: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    ran_command: { type: 'string' },
    validation_passed: { type: 'boolean' },
    validation_output: { type: 'string' },
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
        required: ['severity', 'location', 'issue', 'fix'],
        properties: {
          severity: {
            type: 'string',
            enum: ['critical', 'high', 'medium', 'low'],
          },
          location: { type: 'string' },
          issue: { type: 'string' },
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

function scopePrompt() {
  return `You are a tech lead scoping a piece of work before a team plans and builds it. Read the repository to ground every claim — do not guess.

TASK:
"""
${task}
"""

Produce a precise scope:
1. restated_task — restate the task sharply in one or two sentences.
2. stack — the languages, frameworks, and tooling actually in this repo that the work touches (detect from package.json / pyproject / config files / source).
3. test_command — the command that runs this repo's test suite (e.g. \`npm test\`, \`npx vitest run\`, \`pytest\`). ${CFG.testCommand ? `The caller supplied "${CFG.testCommand}" — verify it fits and use it.` : 'Infer it from the repo; empty string if there is no test setup.'}
4. explore_targets — up to ${CFG.maxExplorers} areas of THIS codebase a developer must read before changing it (modules/dirs the task touches, conventions to match, tests to mirror). Each { area, why }. No overlap between areas.
5. research_topics — up to ${CFG.maxResearchers} external libraries/frameworks/APIs whose LATEST documentation should be fetched to build this correctly. Each { library, focus }. Omit if the work needs no external docs.
6. requirements — the concrete, TESTABLE acceptance criteria this work must satisfy. Trace to the task and to any spec the repo defines (e.g. CLAUDE.md, project/specs/**). These gate the requirements review.
7. open_questions — genuine ambiguities; do not paper over them.

Return the structured scope.`;
}

function explorePrompt(target) {
  return `You are exploring an existing codebase to prepare a precise, decomposed implementation plan. Do NOT propose a design — report what EXISTS.

OVERALL TASK:
"""
${task}
"""

YOUR AREA: ${target.area}
WHY IT MATTERS: ${target.why}

Read the relevant files and report, with concrete \`path:line\` references:
- The key modules/functions/types in this area and how they fit together.
- The conventions and patterns new code must match (naming, structure, error handling, state, styling).
- The existing tests covering this area and how they are written (framework, helpers, fixtures) — so new tests can mirror them.
- Natural SEAMS for decomposition: where could the work be split into independent units that touch DISJOINT files?
- Integration points/constraints the change must respect, and any gotcha a naive implementation would hit.

Be specific and cite files. Your report feeds the planner; it is not shown to the user directly.`;
}

function researchPrompt(topic) {
  return `You are fetching the LATEST documentation to ground an implementation. Use Context7 first (resolve the library id, then query docs); supplement with web search only if needed.

OVERALL TASK:
"""
${task}
"""

LIBRARY / API: ${topic.library}
FOCUS: ${topic.focus}

Report:
- The current, version-correct API surface for this task (signatures, options, required setup).
- Idiomatic, working code patterns from the official docs for exactly this use case.
- Version caveats, deprecations, migration notes — flag mismatches with the version installed in this repo (check package.json / lockfile).
- Pitfalls the docs call out.

Keep it tight and actionable. Your findings feed the planner.`;
}

function findingsBlock(exploreFindings, researchFindings) {
  const ex =
    exploreFindings
      .map((f) => `### Codebase — ${f.area}\n${f.text}`)
      .join('\n\n') || '(no codebase findings)';
  const rs =
    researchFindings
      .map((f) => `### Docs — ${f.topic}\n${f.text}`)
      .join('\n\n') || '(no external research)';
  return `CODEBASE EXPLORATION:\n${ex}\n\nDOCUMENTATION RESEARCH:\n${rs}`;
}

function decompositionRules() {
  return `DECOMPOSE the work into independently-buildable work_units forming a DAG — this is what lets the team build in parallel:
- Each unit OWNS a set of production files. Keep file sets DISJOINT across units that could run at the same time; two units that must edit the same file should be merged or chained with depends_on (the scheduler runs file-disjoint, dependency-ready units concurrently and serializes the rest).
- Give each unit a public_contract (the interface others rely on) so a unit can be built against another's contract without seeing its implementation.
- List depends_on ONLY for real ordering constraints (a unit needs another's code to exist first). Avoid false dependencies — they kill parallelism. The graph must be acyclic.
- Each unit lists testable behaviors (drive its tests) and its own test_files (disjoint from other units').
- Classify each unit's domain: "frontend" (client/UI/browser — components, view state, styling, navigation, accessibility) or "backend" (everything else — services, APIs, data, logic, libraries, CLI, infra). On a non-web project, every unit is "backend".
- Prefer several small, sharply-bounded units over one big unit — but do not invent scope to create units.`;
}

function planPrompt(scope, exploreFindings, researchFindings) {
  return `You are a senior engineer writing a concrete, DECOMPOSED implementation plan. A reviewer will score it and a team will build the units in PARALLEL, so boundaries must be clean and grounded in the findings below — not generic.

TASK:
"""
${task}
"""

SCOPE (from the tech lead):
${JSON.stringify({ restated_task: scope.restated_task, stack: scope.stack, requirements: scope.requirements, open_questions: scope.open_questions }, null, 2)}

${findingsBlock(exploreFindings, researchFindings)}

${decompositionRules()}

Fill the structured plan completely: objective, in_scope, out_of_scope, approach (cite real modules/APIs), interfaces (the contracts), data_model_changes, work_units (the DAG), test_strategy, integration_check (the full-suite + build/lint command), risks (with impact/likelihood/mitigation), rollback, acceptance_criteria (testable, from the requirements), open_questions, and plan_markdown (a readable rendering of all of the above — max 3 header levels, bullets over prose).

Ground every step in the findings and match the repo's conventions. Do not invent scope the task does not call for. Return the structured plan.`;
}

function planRevisePrompt(plan, review, scope) {
  return `You are revising your DECOMPOSED implementation plan to address a reviewer's findings. The aggregated confidence in the previous version was ${review.confidence_score}/100, below the ${CFG.threshold} bar.

TASK:
"""
${task}
"""

REQUIREMENTS:
${JSON.stringify(scope.requirements, null, 2)}

YOUR PREVIOUS PLAN (markdown):
${plan.plan_markdown}

REVIEWER FINDINGS:
${JSON.stringify({ weaknesses: review.weaknesses, required_changes: review.required_changes, parallelization_risks: review.parallelization_risks, dimension_scores: review.dimension_scores }, null, 2)}

${decompositionRules()}

Produce an improved plan resolving EVERY required change, weakness, and parallelization risk while staying in scope. Tighten unit boundaries so files are disjoint and deps are minimal; make weak sections concrete (specific files, APIs, edge cases, test assertions). Return the full structured plan again (not a diff).`;
}

function planReviewPrompt(plan, scope, lens) {
  return `You are a Plan Quality Analyst reviewing a DECOMPOSED implementation plan. Review through this lens, but still return the full structured verdict. Score conservatively, anchored to the dimension definitions. Ignore any assumption about external research files — review only from the context provided here and the repository.

REVIEW LENS — emphasize: ${lens.focus}

TASK:
"""
${task}
"""

REQUIREMENTS the plan must satisfy:
${JSON.stringify(scope.requirements, null, 2)}

PLAN UNDER REVIEW (markdown):
${plan.plan_markdown}

WORK-UNIT DAG (the parallel build graph):
${JSON.stringify(plan.work_units, null, 2)}

INTERFACES / CONTRACTS:
${JSON.stringify(plan.interfaces, null, 2)}

Do two things:
1. SCORE the plan.
   - dimension_scores (0-100): completeness, clarity, feasibility, risk_management, alignment, decomposition (DAG quality: bounded units, DISJOINT files, correct/minimal deps, sufficient contracts).
   - quality_score = average of those six.
   - confidence_score (0-100) = how confident you are the plan AS WRITTEN will succeed when built in parallel. Lower it for vagueness, an unaddressed requirement, unstated assumptions, OR a decomposition that is not actually parallel-safe (units sharing files, hidden ordering, thin contracts, cycles). THIS gates at threshold ${CFG.threshold}.
   - verdict = "approve" if confidence_score >= ${CFG.threshold}, else "revise".
   - strengths, weaknesses, required_changes (concrete edits; empty if approving), and parallelization_risks (units that are not safely parallel as drawn).
2. DECIDE TDD. Set tdd_required + tdd_rationale. Require TDD for new features, bug fixes, behavior changes, and non-trivial testable logic; do NOT require it for pure config/scaffolding/generated/throwaway code. Decide from the nature of THIS work, independent of the score.

Return the structured review.`;
}

function aggregateReviews(reviews) {
  const avg = (f) =>
    Math.round(reviews.reduce((s, r) => s + (f(r) || 0), 0) / reviews.length);
  const ds = (k) => avg((r) => r.dimension_scores[k]);
  const tddVotes = reviews.filter((r) => r.tdd_required).length;
  return {
    confidence_score: avg((r) => r.confidence_score),
    quality_score: avg((r) => r.quality_score),
    dimension_scores: {
      completeness: ds('completeness'),
      clarity: ds('clarity'),
      feasibility: ds('feasibility'),
      risk_management: ds('risk_management'),
      alignment: ds('alignment'),
      decomposition: ds('decomposition'),
    },
    tdd_required: tddVotes * 2 >= reviews.length,
    tdd_rationale: reviews
      .map((r) => `[${r.lensKey || 'lens'}] ${r.tdd_rationale}`)
      .join(' '),
    verdict:
      avg((r) => r.confidence_score) >= CFG.threshold ? 'approve' : 'revise',
    strengths: dedupe(reviews.flatMap((r) => r.strengths)),
    weaknesses: dedupe(reviews.flatMap((r) => r.weaknesses)),
    required_changes: dedupe(reviews.flatMap((r) => r.required_changes)),
    parallelization_risks: dedupe(
      reviews.flatMap((r) => r.parallelization_risks),
    ),
    perLens: reviews.map((r) => ({
      lens: r.lensKey,
      confidence: r.confidence_score,
      tdd: r.tdd_required,
    })),
  };
}

const IRON_LAW =
  'TDD Iron Law: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. One behavior per test, clear names, real code over mocks. Watch each test FAIL for the right reason before any implementation exists.';

function redPrompt(unit, plan, testCommand) {
  return `You are in the RED phase of TDD for ONE work unit. Write ONLY this unit's failing tests — no production/implementation code at all.

${IRON_LAW}

OVERALL TASK:
"""
${task}
"""

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, domain: unit.domain, description: unit.description, public_contract: unit.public_contract, behaviors: unit.behaviors, test_files: unit.test_files, files: unit.files }, null, 2)}

OVERALL TEST STRATEGY: ${plan.test_strategy}

Do this:
1. From the repo root (\`git rev-parse --show-toplevel\`), find the existing test setup and MIRROR its conventions (framework, layout, helpers, fixtures).
2. Write minimal, behavior-focused tests for THIS unit's behaviors — one behavior per test, clear names, real code over mocks, covering key edge cases. Write ONLY to this unit's test_files (${JSON.stringify(unit.test_files)}); do NOT touch other units' files. Test against the public_contract; do not assume internals that do not exist yet.
3. RUN the tests scoped to this unit's test files: \`${testCommand || 'the repo test command'}\`. Capture the output.
4. Confirm every new test FAILS for the RIGHT reason (feature missing) — NOT a typo/import/syntax error. If a test errors instead of failing cleanly, fix the test and re-run until it fails correctly.

Set unit_id="${unit.id}". Return the structured result with observed_failure = the actual failing output.`;
}

function testReviewPrompt(unit, plan, red, lens) {
  return `You are reviewing the TESTS for ONE work unit BEFORE any implementation is written (GREEN is BLOCKED on this review). Read the actual test files from disk.

REVIEW LENS — focus on: ${lens.focus}

OVERALL TASK:
"""
${task}
"""

UNIT ${unit.id} — ${unit.name}
BEHAVIORS the tests must encode:
${JSON.stringify(unit.behaviors, null, 2)}
ACCEPTANCE CRITERIA (project-level, for context):
${JSON.stringify(plan.acceptance_criteria, null, 2)}

TESTS JUST WRITTEN (RED result):
${JSON.stringify(red, null, 2)}

Through your lens, judge whether these are the RIGHT tests. Every finding needs { severity, file, issue, fix }. List uncovered behaviors/edge cases in missing_cases. Set verdict="revise" if anything critical/high is wrong or a required behavior is uncovered; else "approve". Set lens="${lens.key}". Return the structured review.`;
}

function testRevisePrompt(unit, red, findings, missing, testCommand) {
  return `You are revising ONE unit's FAILING tests to address a test review, still in the RED phase. Do NOT write production code.

${IRON_LAW}

UNIT ${unit.id} — ${unit.name}
CURRENT TESTS:
${JSON.stringify(red, null, 2)}

REVIEW FINDINGS:
${JSON.stringify(findings, null, 2)}
MISSING CASES TO ADD:
${JSON.stringify(missing, null, 2)}

Fix every finding and close the gaps, writing only to this unit's test_files. Re-run \`${testCommand || 'the repo test command'}\` (scoped) and confirm the tests still FAIL for the right reason. Set unit_id="${unit.id}". Return the updated structured RED result.`;
}

function greenPrompt(unit, plan, red, testCommand) {
  return `You are in the GREEN phase of TDD for ONE work unit, running CONCURRENTLY with other units that own DIFFERENT files. Write the MINIMAL production code that makes THIS unit's failing tests pass.

${IRON_LAW}

OVERALL TASK:
"""
${task}
"""

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, domain: unit.domain, description: unit.description, public_contract: unit.public_contract, files: unit.files, behaviors: unit.behaviors }, null, 2)}

APPROACH (context): ${clip(plan.approach, 1500)}

FAILING TESTS to satisfy (do NOT modify them):
${red ? JSON.stringify(red.tests_added, null, 2) : '(tests for this unit were not captured — implement to the behaviors above and run the unit tests)'}
Test files (FROZEN): ${JSON.stringify((red && red.test_files) || unit.test_files)}

Rules:
1. Edit ONLY this unit's production files (${JSON.stringify(unit.files)}). Do NOT touch other units' files or any test file (set modified_tests=false). If a test is genuinely wrong, STOP and explain in notes rather than editing it.
2. Implement the smallest code that passes the tests; match repo conventions (CLAUDE.md / .claude/rules/ if present).
3. RUN ONLY this unit's tests, scoped to ${JSON.stringify((red && red.test_files) || unit.test_files)}: \`${testCommand || 'the repo test command'}\`. Do NOT run a repo-wide format/lint (other agents are editing in parallel — the integration step handles the full suite). Confirm this unit's tests pass.

Set unit_id="${unit.id}". Return the structured result with the test_output tail.`;
}

function implementPrompt(unit, plan, testCommand) {
  return `You are implementing ONE work unit from an approved plan directly (TDD was judged unnecessary for this work), running CONCURRENTLY with units that own DIFFERENT files.

OVERALL TASK:
"""
${task}
"""

THIS UNIT:
${JSON.stringify({ id: unit.id, name: unit.name, domain: unit.domain, description: unit.description, public_contract: unit.public_contract, files: unit.files, behaviors: unit.behaviors }, null, 2)}

APPROACH (context): ${clip(plan.approach, 1500)}

Rules:
1. Implement ONLY this unit's files (${JSON.stringify(unit.files)}), matching repo conventions (CLAUDE.md / .claude/rules/ if present). Do not touch other units' files. Stay within scope.
2. Validate this unit narrowly: ${testCommand ? `run \`${testCommand}\` scoped to this unit where possible, plus ` : ''}any quick local check. Do NOT run repo-wide format/lint (parallel agents are editing; integration handles the full pass).
3. Confirm this unit's behaviors are met.

Set unit_id="${unit.id}". Return the structured result.`;
}

function integrationPrompt(plan, testCommand, changedFiles, prior) {
  const head = prior
    ? `A previous integration run FAILED. Diagnose and FIX the cross-unit issues (edit production code only — never weaken tests), then re-run.\nPREVIOUS FAILURES:\n${JSON.stringify(prior.failures, null, 2)}\n`
    : 'The work units were built in parallel. Run the WHOLE change together to catch cross-unit regressions.\n';
  return `You are the integration gate. Operate from the repo root.

${head}
CHANGED FILES:
${changedFiles.map((f) => '- ' + f).join('\n') || '(use `git status`/`git diff` to discover them)'}

Run the integration check — the full test suite AND the build/lint the plan specifies: ${plan.integration_check ? `\`${plan.integration_check}\`` : testCommand ? `\`${testCommand}\` plus the repo build/lint` : 'the repo test + build commands'}.
- If anything fails, ${prior ? 'fix the production code minimally and re-run until green (do not modify tests to pass).' : 'list each failure precisely.'}
- Output must be pristine (no new errors/warnings).

Return the structured result: all_tests_pass, build_ok, the output tail, and a precise failures list.`;
}

function refactorPrompt(unit, testCommand) {
  return `You are in the REFACTOR phase for ONE work unit, running CONCURRENTLY with units that own DIFFERENT files. Tests are green. Improve clarity/structure WITHOUT changing behavior and WITHOUT touching any test.

UNIT ${unit.id} — ${unit.name}
FILES (edit only these): ${JSON.stringify(unit.files)}

Do this:
1. Clean up this unit's production code: remove duplication/dead code, sharpen names, flatten nesting, keep functions small and cohesive. Match the project's style (CLAUDE.md / .claude/rules/ if present). Add NO behavior.
2. Touch no test and no other unit's files.
3. Re-run this unit's scoped tests (\`${testCommand || 'the repo test command'}\`) and confirm still green. Do NOT run repo-wide format/lint.

If nothing meaningfully needs refactoring, say so and leave the code. Set unit_id="${unit.id}". Return the structured result.`;
}

function reviewDimensionPrompt(dim, plan, scope, changedFiles) {
  const target = changedFiles.length
    ? `Review these changed files (and their immediate context):\n${changedFiles.map((f) => '- ' + f).join('\n')}`
    : 'No explicit file list was captured — use `git diff`/`git status` from the repo root to find what this run changed, and review that.';
  return `You are reviewing the implementation just produced for the task below. Review ONLY this change and its context — do not expand scope.

TASK:
"""
${task}
"""

REQUIREMENTS / ACCEPTANCE CRITERIA:
${JSON.stringify(scope.requirements && scope.requirements.length ? scope.requirements : plan.acceptance_criteria, null, 2)}

PLAN that was implemented (markdown):
${clip(plan.plan_markdown, 6000)}

${target}

YOUR REVIEW DIMENSION — focus exclusively here:
${dim.covers}

Read the actual files from disk. Return findings as { severity, location, issue, fix } with concrete \`file:line\` (or the requirement text for the requirements dimension), ordered by severity. verdict="fail" if any critical/high (or medium-worth-fixing) finding exists in your dimension, else "pass". If clean, return an empty findings array and say so. ${dim.key === 'requirements' ? 'List every unmet/partial criterion in unmet_requirements and RUN the tests as part of your check.' : ''}

Return the structured review.`;
}

function reportPrompt(
  scope,
  plan,
  review,
  useTDD,
  waves,
  impl,
  reviews,
  integration,
  changedFiles,
) {
  const reviewDigest = reviews.map((r) => ({
    dimension: r.key,
    verdict: r.verdict,
    confidence: r.confidence_score,
    findings: r.findings,
    unmet_requirements: r.unmet_requirements || [],
  }));
  return `You are a release engineer writing a consolidated lifecycle report and persisting it. Operate from the repo root.

WRITE a markdown report to \`.claude/plans/lifecycle-${slug}.md\` (create the directory if needed; if that exact file already exists, append \`-2\`, \`-3\`, … until free). Follow the project's documentation rules if present (no emojis; bullets over prose; max 3 header levels; bold for emphasis). Include, in order:
1. Title + the task.
2. Scope summary (stack, requirements, open questions).
3. The plan (embed plan_markdown) and the work-unit DAG.
4. Plan review: aggregated confidence ${review.confidence_score}/100 (threshold ${CFG.threshold}), quality ${review.quality_score}/100, dimension scores, per-lens votes, and the TDD decision (used: ${useTDD ? 'TDD' : 'direct build'}).
5. Build summary: parallel ${useTDD ? 'RED/review/GREEN/refactor' : 'direct build'} across ${waves.length} wave(s) [${waves.map((w) => w.map((u) => u.id).join('+')).join(' , ')}], the integration result, and the changed files.
6. Final review: a table of the ${reviews.length} dimensions (verdict + confidence), then all findings grouped by severity, then any unmet requirements.
7. Verdict & next steps.

DATA (JSON):
${JSON.stringify({ requirements: scope.requirements, open_questions: scope.open_questions, plan_markdown: plan.plan_markdown, work_units: plan.work_units, plan_review: { confidence_score: review.confidence_score, quality_score: review.quality_score, dimension_scores: review.dimension_scores, tdd_required: review.tdd_required, used_tdd: useTDD, per_lens: review.perLens }, integration: integration, changed_files: changedFiles, final_reviews: reviewDigest }, null, 2)}

After writing, set: report_path = the file you wrote; overall_verdict = "fail" if any dimension has a critical finding, an unmet requirement, or integration is red; "needs-work" if any high/medium findings remain; else "pass". blocking_findings = the critical/high items + any integration failure that must be fixed before merge. summary = 2-3 sentences. Return the structured result.`;
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

phase('Scope');
log(`Scoping: ${clip(task, 120)}`);
const scope = await agent(scopePrompt(), {
  agentType: 'Explore',
  model: MODELS.scope,
  schema: SCOPE_SCHEMA,
  phase: 'Scope',
  label: 'scope',
});
const testCommand = CFG.testCommand || scope.test_command || '';
let exploreTargets = (scope.explore_targets || []).slice(0, CFG.maxExplorers);
if (!exploreTargets.length)
  exploreTargets = [
    {
      area: 'overall structure',
      why: 'no targets identified — survey the codebase the task touches',
    },
  ];
const researchTopics = (scope.research_topics || []).slice(
  0,
  CFG.maxResearchers,
);
log(
  `Stack: ${clip(scope.stack, 90)} · test: ${testCommand || '(none)'} · ${exploreTargets.length} explore + ${researchTopics.length} research (parallel) · ${scope.requirements.length} requirements`,
);

phase('Explore & Research');
// Barrier: the planner legitimately needs the COMPLETE picture before planning.
const findings = (
  await parallel([
    ...exploreTargets.map(
      (t) => () =>
        agent(explorePrompt(t), {
          agentType: 'Explore',
          model: MODELS.explore,
          phase: 'Explore & Research',
          label: `explore:${sanitize(t.area)}`,
        }).then((text) => ({ area: t.area, text })),
    ),
    ...researchTopics.map(
      (r) => () =>
        agent(researchPrompt(r), {
          agentType: 'Researcher',
          model: MODELS.research,
          phase: 'Explore & Research',
          label: `research:${sanitize(r.library)}`,
        }).then((text) => ({ topic: r.library, text })),
    ),
  ])
).filter(Boolean);
const exploreFindings = findings.filter((f) => f.area);
const researchFindings = findings.filter((f) => f.topic);

phase('Plan');
log('Drafting the decomposed implementation plan');
let plan = await agent(planPrompt(scope, exploreFindings, researchFindings), {
  agentType: 'Plan',
  model: MODELS.plan,
  schema: PLAN_SCHEMA,
  phase: 'Plan',
  label: 'plan:v1',
});

async function reviewPlan(planObj, version) {
  const raw = (
    await parallel(
      planLenses.map(
        (lens) => () =>
          agent(planReviewPrompt(planObj, scope, lens), {
            agentType: 'Plan Reviewer',
            model: MODELS.planReview,
            schema: PLAN_REVIEW_SCHEMA,
            phase: 'Plan Review',
            label: `review:v${version}:${lens.key}`,
          }).then((r) => ({ ...r, lensKey: lens.key })),
      ),
    )
  ).filter(Boolean);
  return aggregateReviews(raw);
}

phase('Plan Review');
let review = await reviewPlan(plan, 1);
let revisions = 0;
while (
  review.confidence_score < CFG.threshold &&
  revisions < CFG.maxPlanRevisions
) {
  revisions++;
  log(
    `Plan confidence ${review.confidence_score}/100 < ${CFG.threshold} — revising (${revisions}/${CFG.maxPlanRevisions})`,
  );
  phase('Plan');
  plan = await agent(planRevisePrompt(plan, review, scope), {
    agentType: 'Plan',
    model: MODELS.plan,
    schema: PLAN_SCHEMA,
    phase: 'Plan',
    label: `plan:v${revisions + 1}`,
  });
  phase('Plan Review');
  review = await reviewPlan(plan, revisions + 1);
}

const approved = review.confidence_score >= CFG.threshold;
const useTDD =
  typeof CFG.forceTDD === 'boolean' ? CFG.forceTDD : !!review.tdd_required;
log(
  `Plan review: confidence ${review.confidence_score}/100 (${planLenses.length} lens) — ${approved ? 'APPROVED' : 'NOT approved'}. TDD ${useTDD ? 'REQUIRED' : 'not required'}${CFG.forceTDD !== undefined ? ' (forced)' : ''}.`,
);

if (!approved) {
  log(
    `Halting before implementation — plan never reached confidence ${CFG.threshold} after ${revisions} revision(s). Returning plan + last review.`,
  );
  return {
    status: 'plan-not-approved',
    task,
    scope,
    plan,
    review,
    threshold: CFG.threshold,
    revisions,
    useTDD,
  };
}

// ---- HUMAN CHECKPOINT (the only one) -------------------------------------
// The plan is approved by review. Pause here so a human can read it before any
// code is written. Resume the SAME run to build:
//   Workflow({ scriptPath, resumeFromRunId: <runId>, args: { ...args, proceed: true } })
// On resume everything above replays from cache (no re-spend); only the
// implement phases below run live. `proceed` does not affect any prompt above,
// so the cached prefix stays intact. Pass proceed=true on the first run to skip.
const proceed = input.proceed === true || input.approvePlan === true;
if (!proceed) {
  log(
    'Plan approved by review — PAUSING for human review before implementation. Resume the same run with args.proceed=true to build.',
  );
  return {
    status: 'awaiting-plan-approval',
    task,
    useTDD,
    threshold: CFG.threshold,
    planConfidence: review.confidence_score,
    planQuality: review.quality_score,
    planRevisions: revisions,
    planMarkdown: plan.plan_markdown,
    workUnits: (plan.work_units || []).map((u) => ({
      id: u.id,
      name: u.name,
      domain: u.domain,
      files: u.files,
      depends_on: u.depends_on,
    })),
    openQuestions: (scope.open_questions || []).concat(plan.open_questions || []),
    plan,
    review,
    scope,
    resume:
      'Relaunch Workflow({ scriptPath, resumeFromRunId: <runId from this run> }) with args.proceed=true to build the plan unchanged. The explore/plan/review phases replay from cache (no extra cost); only implementation runs live. To change the plan instead, re-run from scratch with adjusted args.',
  };
}

// Build the work units + parallel schedule.
let units = (plan.work_units || []).filter((u) => u && u.id);
if (!units.length)
  units = [
    {
      id: 'U1',
      name: 'implementation',
      domain: 'backend',
      description: plan.objective || task,
      files: [],
      test_files: [],
      public_contract: '',
      behaviors: plan.acceptance_criteria || [],
      depends_on: [],
    },
  ];
const waves = scheduleWaves(units);
log(
  `${units.length} work unit(s) → ${waves.length} wave(s): ${waves.map((w) => w.map((u) => u.id).join('+')).join(' , ')}`,
);

let redByUnit = new Map();
let changedFiles = [];
let implResults = [];

if (useTDD) {
  // RED + per-unit test review as a pipeline: each unit flows independently,
  // no inter-stage barrier. The pipeline's completion IS the barrier that
  // guarantees every unit's tests are written AND reviewed before any GREEN.
  phase('Tests (RED) & Review');
  log(
    `Writing failing tests for ${units.length} unit(s) in parallel; ${testLenses.length} review lens(es) each`,
  );
  const reviewed = (
    await pipeline(
      units,
      // Stage 1: RED — write this unit's failing tests
      (unit) =>
        agent(redPrompt(unit, plan, testCommand), {
          agentType: 'Test Author',
          model: MODELS.testAuthor,
          schema: RED_SCHEMA,
          phase: 'Tests (RED) & Review',
          label: `red:${unit.id}`,
        }).then((red) => ({ unit, red })),
      // Stage 2: multi-lens test review + bounded revise loop (all before GREEN)
      async ({ unit, red }) => {
        let cur = red;
        let tr = 0;
        let lensReviews = [];
        while (true) {
          lensReviews = (
            await parallel(
              testLenses.map(
                (lens) => () =>
                  agent(testReviewPrompt(unit, plan, cur, lens), {
                    agentType: 'Test Reviewer',
                    model: MODELS.testReview,
                    schema: TEST_REVIEW_SCHEMA,
                    phase: 'Tests (RED) & Review',
                    label: `test-review:${unit.id}:${lens.key}`,
                  }),
              ),
            )
          ).filter(Boolean);
          const needsRevise = lensReviews.some((rv) => rv.verdict === 'revise');
          if (!needsRevise || tr >= CFG.maxTestRevisions) break;
          tr++;
          const findings = lensReviews.flatMap((rv) => rv.findings);
          const missing = dedupe(lensReviews.flatMap((rv) => rv.missing_cases));
          cur = await agent(
            testRevisePrompt(unit, cur, findings, missing, testCommand),
            {
              agentType: 'Test Author',
              model: MODELS.testAuthor,
              schema: RED_SCHEMA,
              phase: 'Tests (RED) & Review',
              label: `red:${unit.id}:rev${tr}`,
            },
          );
        }
        const approvedTests = !lensReviews.some(
          (rv) => rv.verdict === 'revise',
        );
        if (!approvedTests)
          log(
            `Unit ${unit.id}: tests still flagged after ${tr} revision(s) — proceeding; see report`,
          );
        return {
          unit,
          red: cur,
          reviews: lensReviews,
          approvedTests,
          testRevisions: tr,
        };
      },
    )
  ).filter(Boolean);
  reviewed.forEach((r) => redByUnit.set(r.unit.id, r.red));

  // GREEN — dependency/file-disjoint waves (parallel within each wave).
  phase('Implement');
  const greens = [];
  for (let i = 0; i < waves.length; i++) {
    const wave = waves[i];
    log(
      `GREEN wave ${i + 1}/${waves.length}: ${wave.map((u) => u.id).join(', ')} (parallel)`,
    );
    const res = (
      await parallel(
        wave.map(
          (u) => () =>
            agent(greenPrompt(u, plan, redByUnit.get(u.id), testCommand), {
              agentType: devFor(u),
              model: MODELS.developer,
              schema: GREEN_SCHEMA,
              phase: 'Implement',
              label: `green:${u.id}:${u.domain || 'backend'}`,
            }),
        ),
      )
    ).filter(Boolean);
    greens.push(...res);
  }
  implResults = greens;
  if (greens.some((g) => g.modified_tests))
    log(
      'WARNING: a GREEN agent reported modifying tests — TDD violated; check the report',
    );
  changedFiles = dedupe([
    ...reviewed.flatMap((r) => r.red.test_files || []),
    ...greens.flatMap((g) => g.files_touched || []),
  ]);
} else {
  // Direct build — also parallel by wave.
  phase('Implement');
  const builds = [];
  for (let i = 0; i < waves.length; i++) {
    const wave = waves[i];
    log(
      `Build wave ${i + 1}/${waves.length}: ${wave.map((u) => u.id).join(', ')} (parallel)`,
    );
    const res = (
      await parallel(
        wave.map(
          (u) => () =>
            agent(implementPrompt(u, plan, testCommand), {
              agentType: devFor(u),
              model: MODELS.developer,
              schema: IMPLEMENT_SCHEMA,
              phase: 'Implement',
              label: `build:${u.id}:${u.domain || 'backend'}`,
            }),
        ),
      )
    ).filter(Boolean);
    builds.push(...res);
  }
  implResults = builds;
  changedFiles = dedupe(builds.flatMap((b) => b.files_touched || []));
}

// Integration gate — run the whole change together once; bounded fix loop.
phase('Integration');
log('Running the full suite + build to catch cross-unit regressions');
let integration = await agent(
  integrationPrompt(plan, testCommand, changedFiles, null),
  {
    agentType: 'Debugger',
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
    integrationPrompt(plan, testCommand, changedFiles, integration),
    {
      agentType: 'Debugger',
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

// REFACTOR — TDD only; parallel across the same file-disjoint waves.
if (useTDD) {
  phase('Refactor');
  for (let i = 0; i < waves.length; i++) {
    const wave = waves[i];
    const res = (
      await parallel(
        wave.map(
          (u) => () =>
            agent(refactorPrompt(u, testCommand), {
              agentType: devFor(u),
              model: MODELS.refactor,
              schema: REFACTOR_SCHEMA,
              phase: 'Refactor',
              label: `refactor:${u.id}:${u.domain || 'backend'}`,
            }),
        ),
      )
    ).filter(Boolean);
    changedFiles = dedupe([
      ...changedFiles,
      ...res.flatMap((r) => r.files_touched || []),
    ]);
  }
}

// FINAL REVIEW — fan out across dimensions (incl. security + requirements).
phase('Final Review');
log(
  `Reviewing across ${REVIEW_DIMENSIONS.length} dimensions in parallel (incl. security + requirements)`,
);
const reviews = (
  await parallel(
    REVIEW_DIMENSIONS.map(
      (dim) => () =>
        agent(reviewDimensionPrompt(dim, plan, scope, changedFiles), {
          agentType: dim.agent,
          model: dim.model,
          schema: DIMENSION_REVIEW_SCHEMA,
          phase: 'Final Review',
          label: `review:${dim.key}`,
        }).then((r) => ({ ...r, key: dim.key })),
    ),
  )
).filter(Boolean);
const failedDims = reviews
  .filter((r) => r.verdict === 'fail')
  .map((r) => r.key);
log(
  failedDims.length
    ? `Review flagged: ${failedDims.join(', ')}`
    : 'All review dimensions passed',
);

phase('Report');
const report = await agent(
  reportPrompt(
    scope,
    plan,
    review,
    useTDD,
    waves,
    implResults,
    reviews,
    integration,
    changedFiles,
  ),
  {
    agentType: 'Report Writer',
    model: MODELS.report,
    schema: REPORT_SCHEMA,
    phase: 'Report',
    label: 'report',
  },
);
log(
  `Lifecycle complete — overall: ${report.overall_verdict}. Report: ${report.report_path}`,
);

return {
  status: 'complete',
  task,
  useTDD,
  threshold: CFG.threshold,
  planConfidence: review.confidence_score,
  planRevisions: revisions,
  units: units.length,
  models: MODELS,
  waves: waves.map((w) => w.map((u) => u.id)),
  integrationGreen: integration.all_tests_pass && integration.build_ok,
  changedFiles,
  reviews: reviews.map((r) => ({
    dimension: r.key,
    verdict: r.verdict,
    confidence: r.confidence_score,
    findings: r.findings.length,
  })),
  overallVerdict: report.overall_verdict,
  blockingFindings: report.blocking_findings,
  reportPath: report.report_path,
};
