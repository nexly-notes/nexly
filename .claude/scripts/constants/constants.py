"""Shared constants used across hooks, guards, validators, and the async batcher.

Layout overview:
    * ``CODE_EXTENSIONS`` — file extensions treated as "source code" by guards.
    * Regex patterns (``PR_COMMAND_PATTERNS``, ``TEST_RUN_PATTERNS``,
      ``CI_CHECK_PATTERNS``, ``STORY_ID_PATTERN``, ``SCORE_PATTERNS``,
      ``TABLE_PATTERN``) — used by hooks to classify Bash invocations and parse
      structured agent output.
    * Command lists (``PR_COMMANDS``, ``CI_COMMANDS``, ``TEST_COMMANDS``,
      ``READ_ONLY_COMMANDS``, ``WRITE_COMMANDS``) — keyed by phase via
      ``COMMANDS_MAP`` to gate which shell commands a phase may run.
    * File patterns (``TEST_FILE_PATTERNS``) — heuristics for locating
      test files.
"""

CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".rb",
    ".sh",
}


PR_COMMAND_PATTERNS = [r"\bgh\s+pr\s+create\b", r"\bgit\s+push\b"]
TEST_RUN_PATTERNS = [
    r"\bpytest\b",
    r"\bnpm\s+test\b",
    r"\byarn\s+test\b",
    r"\bgo\s+test\b",
    r"\bjest\b",
    r"\bvitest\b",
]
CI_CHECK_PATTERNS = [r"\bgh\s+pr\s+checks\b", r"\bgh\s+run\s+view\b"]

# ---------------------------------------------------------------------------
# Skill / story ID patterns
# ---------------------------------------------------------------------------
STORY_ID_PATTERN = r"\b([A-Z]{2,}-\d+)\b"

# All ``/implement`` CLI flags; used by arg/prompt parsers to strip non-prose tokens.
BUILD_FLAGS = [
    "--skip-explore",
    "--skip-research",
    "--skip-all",
    "--tdd",
    "--reset",
    "--takeover",
    "--test",
]

SCORE_PATTERNS = [
    r"{label}\s*(?:score|rating)?\s*(?:\*\*)?\s*[:=\-]?\s*(?:\*\*)?\s*(\d+)(?:\s*/\s*100)?",
    r"{label}\s*(?:score|rating)?\s+(?:is\s+)?(?:\*\*)?\s*(\d+)(?:\s*/\s*100)?",
]

TABLE_PATTERN = r"^(\|.+\|[ \t]*\n)(\|[ \t]*[-:]+.*\|[ \t]*\n)((?:\|.+\|[ \t]*\n?)*)"


# ---------------------------------------------------------------------------
# Valid PR commands
# ---------------------------------------------------------------------------


PR_COMMANDS = [
    "git push",
    "git commit",
    "git add",
    "gh pr create",
    "gh pr merge",
    "gh pr close",
    "gh pr edit",
    "gh pr review",
    "gh pr comment",
]

CI_COMMANDS = [
    "gh run view",
    "gh run list",
    "gh run watch",
    "gh pr checks",
    "gh pr status",
]

TEST_COMMANDS = [
    "pytest",
    "python -m pytest",
    "npm test",
    "npm run test",
    "yarn test",
    "yarn run test",
    "pnpm test",
    "go test",
    "jest",
    "vitest",
    "cargo test",
    "ruby -Itest",
    "rspec",
]

READ_ONLY_COMMANDS = [
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "wc",
    "file",
    "which",
    "whoami",
    "printenv",
    "date",
    "uname",
    "hostname",
    "df",
    "du",
    "free",
    "ps",
    "git status",
    "git log",
    "git diff",
    "git show",
    "git blame",
    "tree",
    "grep",
    "rg",
    "ag",
    "fd",
    "stat",
    "realpath",
    "dirname",
    "basename",
]

COMMANDS_MAP = {
    "write-tests": TEST_COMMANDS,
    "write-code": TEST_COMMANDS,
}

TEST_FILE_PATTERNS = [
    # JS / TS style
    "*.test.js",
    "*.test.ts",
    "*.test.jsx",
    "*.test.tsx",
    # Python style
    "test_*.py",
    "*_test.py",
    # Optional: JS test prefix style
    "test_*.js",
    "test_*.ts",
    "test_*.jsx",
    "test_*.tsx",
]


WRITE_COMMANDS = [
    "touch",
    "mkdir",
    "echo",
    "cat",
    "cp",
    "mv",
    "rm",
]

READ_ONLY_PHASES = ["explore", "decision", "plan"]

LINTER_COMMANDS_MAP = {
    "ruff": ["ruff", "check", "."],
    "black": ["black", "."],
    "isort": ["isort", "."],
    "mypy": ["mypy", "."],
    "flake8": ["flake8", "."],
    "eslint": ["eslint", "."],
    "pyright": ["pyright", "."],
}

FORMATTER_COMMANDS_MAP = {
    "black": ["black", "."],
    "isort": ["isort", "."],
    "prettier": ["prettier", "."],
    "stylelint": ["stylelint", "."],
    "tsc": ["tsc", "."],
    "dartfmt": ["dartfmt", "."],
    "dart analyze": ["dart", "analyze", "."],
    "dart format": ["dart", "format", "."],
    "dart fix": ["dart", "fix", "."],
    "dart analyze": ["dart", "analyze", "."],
}
