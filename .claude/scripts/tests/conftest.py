import sys
import types
from pathlib import Path

# Make scripts_v2/ importable so `code_review`, `utils.*`, `lib.*` resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# scripts_v2/lib has no subprocess_agents; conformance_check imports it from
# the older scripts/lib tree. Stub it so code_review imports cleanly without
# pulling in that tree.
if "lib.subprocess_agents" not in sys.modules:
    stub = types.ModuleType("lib.subprocess_agents")
    stub.invoke_headless_agent = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["lib.subprocess_agents"] = stub


def pytest_configure(config):
    # `live` tests actually invoke the claude/codex CLIs. They are opt-in via
    # RUN_LIVE_TESTS=1 and skipped by default to avoid waste/auth requirements.
    config.addinivalue_line(
        "markers", "live: hits real claude/codex CLIs; opt-in via RUN_LIVE_TESTS=1"
    )
