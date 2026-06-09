"""Live CLI integration tests for scripts_v2/code_review.py.

These tests actually invoke `claude` and `codex` to verify the argv builders,
parallel runner, session-id extraction, and run_headless_review glue work
against the real CLI surface.

They do NOT ask the agents to perform real work. Each prompt instructs the
model to echo a short canned string so the round trip stays cheap and fast.

Run with:
    RUN_LIVE_TESTS=1 pytest -m live claude-3PO/scripts_v2/tests/

Skipped by default and auto-skipped if `claude` or `codex` is not on PATH.
"""

import json
import os
import shutil

import pytest

import code_review as cr
from utils.agent_cli_v2 import (  # type: ignore
    ClaudeConfig,
    CodexConfig,
    build_argv,
    parse_agent_response,
    run_headless_parallel,
)


# Module-level guard: skip everything unless the user explicitly opts in.
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_TESTS") != "1",
        reason="set RUN_LIVE_TESTS=1 to run live CLI tests",
    ),
]


# Minimal prompt: instruct the model to emit a tiny canned token. We don't
# care what it returns substantively — only that the CLI round-trip works
# and our parsers can pull a session_id out.
MOCK_PROMPT = (
    "Respond with EXACTLY this single token and nothing else: REVIEW_MOCK_OK"
)


def _require_binary(name: str) -> None:
    if shutil.which(name) is None:
        pytest.skip(f"{name} not on PATH")


# ──────────────────────────────────────────────────────────────────
# Single-CLI smoke tests
# ──────────────────────────────────────────────────────────────────


class TestLiveClaude:
    # Use what build_sub_config("claude") produces in production:
    # output_format="json" (NOT json_output=True — claude has no --json flag).
    CLAUDE_CFG = ClaudeConfig(model="haiku", output_format="json")

    def test_round_trip_yields_json_with_session_id(self):
        _require_binary("claude")
        argv = build_argv(MOCK_PROMPT, self.CLAUDE_CFG)
        ok, results = run_headless_parallel([argv])
        assert ok is True, "claude CLI returned non-zero"
        assert len(results) == 1
        # claude --output-format json emits a single JSON object on stdout
        parsed = json.loads(results[0])
        assert "session_id" in parsed
        assert isinstance(parsed["session_id"], str) and parsed["session_id"]

    def test_get_session_id_extracts_real_claude_output(self):
        _require_binary("claude")
        argv = build_argv(MOCK_PROMPT, self.CLAUDE_CFG)
        ok, results = run_headless_parallel([argv])
        assert ok is True
        # exercise the dispatcher with the literal "claude" owner
        sid = cr.get_session_id(results[0], "claude")
        assert isinstance(sid, str) and sid


class TestLiveCodex:
    # codex exec accepts the prompt as a trailing positional, so build_codex_argv
    # passes it directly in argv — no stdin piping required, and the same
    # run_headless_parallel pipeline that drives claude works for codex too.
    def test_build_codex_argv_runs_and_parse_agent_response_handles_output(self):
        _require_binary("codex")
        argv = build_argv(MOCK_PROMPT, CodexConfig(model="codex", json_output=True))
        ok, results = run_headless_parallel([argv])
        assert ok is True, "codex CLI returned non-zero"
        session_id, text, raw = parse_agent_response(results[0])
        # codex emits a JSONL stream with a thread.started event up front
        assert raw == results[0]
        assert session_id, "expected non-empty thread_id from codex JSONL stream"
        assert isinstance(text, str)


# ──────────────────────────────────────────────────────────────────
# End-to-end through run_headless_review with the real claude CLI
# ──────────────────────────────────────────────────────────────────


class TestLiveRunHeadlessReview:
    def test_three_parallel_claude_subprocesses_extract_agent_text(self):
        _require_binary("claude")
        # Mirrors REVIEW_CONFIG_MAP shape but with mock prompts so the model
        # doesn't actually do review work.
        config = {
            "security_review": {"owner": "claude", "prompt": MOCK_PROMPT},
            "code_review": {"owner": "claude", "prompt": MOCK_PROMPT},
            "requirements_review": {"owner": "claude", "prompt": MOCK_PROMPT},
        }
        ok, results = cr.run_headless_review(pr_content="(no PR)", config=config)

        assert ok is True
        assert set(results.keys()) == set(config.keys())
        # slot 1 is the EXTRACTED agent text (no JSON envelope), per the
        # collect_review_results contract — the agent reply must round-trip cleanly.
        for key, (returncode, content, _stderr, session_id) in results.items():
            assert returncode == 0, f"{key} returned {returncode}"
            assert session_id, f"{key} produced empty session_id"
            assert "REVIEW_MOCK_OK" in content, (
                f"{key} content was not the canned token: {content!r}"
            )


# ──────────────────────────────────────────────────────────────────
# Content extraction lock-down for both flavors
# ──────────────────────────────────────────────────────────────────


class TestLiveResultExtraction:
    def test_get_claude_result_extracts_real_envelope(self):
        _require_binary("claude")
        argv = build_argv(MOCK_PROMPT, ClaudeConfig(model="haiku", output_format="json"))
        ok, results = run_headless_parallel([argv])
        assert ok is True
        envelope = results[0]
        # raw envelope must round-trip through json + carry both fields we read
        parsed = json.loads(envelope)
        assert "result" in parsed and "session_id" in parsed
        # the helper must pull the same `result` text out of the live envelope
        assert cr.get_claude_result(envelope) == parsed["result"]
        assert "REVIEW_MOCK_OK" in cr.get_claude_result(envelope)

    def test_get_codex_result_extracts_real_jsonl_stream(self):
        _require_binary("codex")
        argv = build_argv(MOCK_PROMPT, CodexConfig(model="codex", json_output=True))
        ok, results = run_headless_parallel([argv])
        assert ok is True, "codex CLI returned non-zero"
        # codex's JSONL stream: parse_agent_response collapses to (thread_id, text, raw).
        # get_codex_result must return that text — and it must contain the canned token.
        text = cr.get_codex_result(results[0])
        assert "REVIEW_MOCK_OK" in text, f"codex text was: {text!r}"


# ──────────────────────────────────────────────────────────────────
# Full save pipeline: real claude → run_headless_review → save_review_report
# ──────────────────────────────────────────────────────────────────


def _template_prompt(kind: str) -> str:
    """Build a prompt that pins the agent to the real template's heading structure."""
    tpl = (cr.TEMPLATES_DIR / f"{kind}_review_template.md").read_text()
    return (
        f"You are running a {kind.replace('_', ' ')} on a small PR. "
        "Output ONLY a markdown document that EXACTLY matches the heading structure of "
        "the template below. Fill each section with 1-3 short bullets — even if the PR "
        "context is thin, invent plausible placeholder bullets rather than asking for "
        "more information. Do NOT ask clarifying questions. Replace the score values "
        "with integers between 0-100. Do not output anything before or after the "
        "markdown document.\n\n"
        f"TEMPLATE:\n{tpl}\n"
    )


class TestLiveSavePipeline:
    def test_run_headless_review_then_save_writes_md_files(self, tmp_path, monkeypatch):
        """Full e2e: 2 real claude + 1 real codex → extract content → save_review_report → md files."""
        _require_binary("claude")
        _require_binary("codex")
        # redirect persistence so the test stays isolated; templates still come from the repo
        monkeypatch.setattr(cr, "CODE_REVIEW_DIR", tmp_path)

        # Mirrors REVIEW_CONFIG_MAP's owner mix: requirements_review is now codex,
        # so this test exercises both flavors through the same run_headless_review path.
        config = {
            "security_review": {
                "owner": "claude", "prompt": _template_prompt("security"),
            },
            "code_review": {
                "owner": "claude", "prompt": _template_prompt("code"),
            },
            "requirements_review": {
                "owner": "codex", "prompt": _template_prompt("requirements"),
            },
        }
        pr_content = "PR: small refactor — extract helper, fix flag, add result extraction"

        ok, results = cr.run_headless_review(pr_content, config)
        assert ok is True, "real claude calls failed"
        assert set(results.keys()) == set(config.keys())

        for key, (rc, content, _stderr, sid) in results.items():
            assert rc == 0, f"{key} returned non-zero"
            assert sid, f"{key} produced empty session_id"
            cr.save_review_report(key, content)

        # md files actually exist on disk under the patched CODE_REVIEW_DIR
        for key in config:
            md_path = tmp_path / f"{key}.md"
            assert md_path.exists(), f"{md_path} was not written"
            body = md_path.read_text()
            # the agent should have honored the template's top heading
            expected_h1 = {
                "security_review": "# Security Review",
                "code_review": "# Code Review",
                "requirements_review": "# Requirements Review",
            }[key]
            assert expected_h1 in body, f"{key}.md missing expected heading; body was:\n{body[:300]}"
            # score lines drive the validation gate downstream — they must be present
            assert "Confidence Score:" in body
            assert "Quality Score:" in body
