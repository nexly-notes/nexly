"""Tests for scripts_v2/code_review.py.

Focus: the refactored helpers (build_sub_config, start/collect, run_headless_review,
correct_one, run_correction) and regression coverage for three bug fixes:
  - check_review_output now uses the real conformance diff (was always returning a fixed string)
  - generate_pr_review_content calls run_headless_parallel (not the undefined invoke_agents)
  - get_session_id has an explicit return for the claude branch
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import code_review as cr
from utils.agent_cli_v2 import ClaudeConfig, CodexConfig  # type: ignore


# ──────────────────────────────────────────────────────────────────
# view_pr_content
# ──────────────────────────────────────────────────────────────────


class TestViewPrContent:
    def test_returns_subprocess_stdout(self):
        fake = MagicMock(returncode=0, stdout="PR body text", stderr="")
        with patch("code_review.subprocess.run", return_value=fake) as run:
            assert cr.view_pr_content(42) == "PR body text"
        argv = run.call_args.args[0]
        assert argv == ["gh", "pr", "view", "42"]
        assert run.call_args.kwargs == {"check": True, "capture_output": True, "text": True}

    def test_propagates_subprocess_error(self):
        err = subprocess.CalledProcessError(1, ["gh"], stderr="boom")
        with patch("code_review.subprocess.run", side_effect=err):
            with pytest.raises(subprocess.CalledProcessError):
                cr.view_pr_content(1)


# ──────────────────────────────────────────────────────────────────
# get_pr_number
# ──────────────────────────────────────────────────────────────────


class TestGetPrNumber:
    def test_parses_int_from_stdout(self):
        fake = MagicMock(returncode=0, stdout="42\n", stderr="")
        with patch("code_review.subprocess.run", return_value=fake):
            assert cr.get_pr_number() == 42

    def test_strips_whitespace_before_parsing(self):
        fake = MagicMock(returncode=0, stdout="  7  \n", stderr="")
        with patch("code_review.subprocess.run", return_value=fake):
            assert cr.get_pr_number() == 7

    def test_raises_when_stdout_not_numeric(self):
        fake = MagicMock(returncode=0, stdout="not-a-number\n", stderr="")
        with patch("code_review.subprocess.run", return_value=fake):
            with pytest.raises(ValueError):
                cr.get_pr_number()


# ──────────────────────────────────────────────────────────────────
# run_subprocess_popen
# ──────────────────────────────────────────────────────────────────


class TestRunSubprocessPopen:
    def test_starts_popen_with_pipes_and_text_mode(self):
        fake = MagicMock()
        with patch("code_review.subprocess.Popen", return_value=fake) as popen:
            assert cr.run_subprocess_popen(["echo", "hi"]) is fake
        kwargs = popen.call_args.kwargs
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.PIPE
        assert kwargs["text"] is True
        assert popen.call_args.args[0] == ["echo", "hi"]


# ──────────────────────────────────────────────────────────────────
# create_pr_review
# ──────────────────────────────────────────────────────────────────


class TestCreatePrReview:
    def test_returns_false_when_content_generation_fails(self):
        with patch("code_review.generate_pr_review_content", return_value=None), \
             patch("code_review.get_pr_number") as pr_num, \
             patch("code_review.subprocess.run") as run:
            assert cr.create_pr_review() is False
        # short-circuit: no PR lookup, no gh call
        pr_num.assert_not_called()
        run.assert_not_called()

    def test_invokes_gh_pr_review_with_approve_when_action_passes(self):
        fake = MagicMock(returncode=0, stdout="", stderr="")
        with patch("code_review.generate_pr_review_content", return_value="Title here\nBody text"), \
             patch("code_review.decide_pr_review_action", return_value="--approve"), \
             patch("code_review.get_pr_number", return_value=42), \
             patch("code_review.subprocess.run", return_value=fake) as run:
            assert cr.create_pr_review() is True
        argv = run.call_args.args[0]
        assert argv[:3] == ["gh", "pr", "review"]
        assert "42" in argv
        # action flag flows from decide_pr_review_action; no more hardcoded --comment
        assert "--approve" in argv
        assert "--comment" not in argv
        assert "--request-changes" not in argv
        # entire generated content (not just the body line) flows into --body
        assert "--body" in argv and argv[argv.index("--body") + 1] == "Title here\nBody text"

    def test_invokes_gh_pr_review_with_request_changes_when_action_fails(self):
        fake = MagicMock(returncode=0, stdout="", stderr="")
        with patch("code_review.generate_pr_review_content", return_value="body"), \
             patch("code_review.decide_pr_review_action", return_value="--request-changes"), \
             patch("code_review.get_pr_number", return_value=7), \
             patch("code_review.subprocess.run", return_value=fake) as run:
            assert cr.create_pr_review() is True
        argv = run.call_args.args[0]
        assert "--request-changes" in argv
        assert "--approve" not in argv


# ──────────────────────────────────────────────────────────────────
# decide_pr_review_action  (score-threshold gating: approve vs request-changes)
# ──────────────────────────────────────────────────────────────────


class TestDecidePrReviewAction:
    def _seed(self, tmp_path, scores_per_file: dict[str, tuple[int, int]]) -> list:
        paths = []
        for name, (conf, qual) in scores_per_file.items():
            p = tmp_path / f"{name}.md"
            p.write_text(f"# {name}\n\nConfidence Score: {conf}\nQuality Score: {qual}\n")
            paths.append(p)
        return paths

    def test_approves_when_every_review_passes_threshold(self, tmp_path):
        # all >= 80 (the THRESHOLDS in review_scores.py)
        paths = self._seed(tmp_path, {"a": (90, 95), "b": (80, 85), "c": (100, 88)})
        assert cr.decide_pr_review_action(paths) == "--approve"

    def test_requests_changes_when_any_confidence_below_threshold(self, tmp_path):
        paths = self._seed(tmp_path, {"a": (90, 90), "b": (75, 90)})
        assert cr.decide_pr_review_action(paths) == "--request-changes"

    def test_requests_changes_when_any_quality_below_threshold(self, tmp_path):
        paths = self._seed(tmp_path, {"a": (95, 60), "b": (85, 85)})
        assert cr.decide_pr_review_action(paths) == "--request-changes"

    def test_short_circuits_on_first_failing_review(self, tmp_path):
        # second file is unreadable; if we already failed on the first, we never touch it
        first = tmp_path / "first.md"
        first.write_text("Confidence Score: 50\nQuality Score: 50\n")
        missing = tmp_path / "missing.md"  # never .write_text — would raise on read
        assert cr.decide_pr_review_action([first, missing]) == "--request-changes"


# ──────────────────────────────────────────────────────────────────
# check_review_output  (regression: bug where it always returned "Correction needed")
# ──────────────────────────────────────────────────────────────────


class TestCheckReviewOutput:
    def test_returns_template_diff_when_conformance_fails(self):
        with patch("code_review.template_conformance_check", return_value=(False, "DIFF_BODY")):
            ok, msg = cr.check_review_output("output", "tpl")
        assert ok is False
        # the actual diff must flow back to the agent, not a hardcoded "Correction needed"
        assert msg == "DIFF_BODY"

    def test_returns_failure_when_scores_invalid(self):
        with patch("code_review.template_conformance_check", return_value=(True, "")), \
             patch("code_review.extract_scores", return_value={"a": 1}), \
             patch("code_review.scores_valid", return_value=False):
            ok, msg = cr.check_review_output("output", "tpl")
        assert ok is False
        assert "Scores" in msg

    def test_returns_ok_when_template_and_scores_pass(self):
        with patch("code_review.template_conformance_check", return_value=(True, "")), \
             patch("code_review.extract_scores", return_value={"a": 9}), \
             patch("code_review.scores_valid", return_value=True):
            ok, msg = cr.check_review_output("output", "tpl")
        assert ok is True
        assert msg == "Output is valid"


# ──────────────────────────────────────────────────────────────────
# check_validation_output
# ──────────────────────────────────────────────────────────────────


class TestCheckValidationOutput:
    @pytest.mark.parametrize("verdict", ["Pass", "Fail"])
    def test_accepts_valid_verdicts(self, verdict):
        with patch("code_review.extract_verdict", return_value=verdict):
            ok, _ = cr.check_validation_output("any")
        assert ok is True

    def test_rejects_unknown_verdict(self):
        with patch("code_review.extract_verdict", return_value="Maybe"):
            ok, _ = cr.check_validation_output("any")
        assert ok is False


# ──────────────────────────────────────────────────────────────────
# build_sub_config
# ──────────────────────────────────────────────────────────────────


class TestBuildSubConfig:
    def test_codex_owner_returns_codex_config(self):
        cfg = cr.build_sub_config("codex")
        assert isinstance(cfg, CodexConfig)
        assert cfg.json_output is True

    def test_claude_owner_returns_claude_config(self):
        cfg = cr.build_sub_config("claude")
        assert isinstance(cfg, ClaudeConfig)
        assert cfg.model == "haiku"

    def test_unknown_owner_raises(self):
        with pytest.raises(ValueError, match="Unknown owner"):
            cr.build_sub_config("gemini")


# ──────────────────────────────────────────────────────────────────
# get_session_id  (regression: previously had no explicit claude return)
# ──────────────────────────────────────────────────────────────────


class TestGetSessionId:
    def test_codex_path(self):
        with patch("code_review.parse_agent_response", return_value=("codex-sid", "x", "y")):
            assert cr.get_session_id("stdout", "codex") == "codex-sid"

    def test_claude_path_returns_string_not_none(self):
        # bug regression: function used to fall through with no return, yielding None
        stdout = '{"session_id": "claude-sid"}'
        assert cr.get_session_id(stdout, "claude") == "claude-sid"


# ──────────────────────────────────────────────────────────────────
# start_review_processes
# ──────────────────────────────────────────────────────────────────


class TestStartReviewProcesses:
    def test_spawns_one_proc_per_config_entry(self):
        config = {
            "code_review": {"owner": "claude", "prompt": "/code-review"},
            "security_review": {"owner": "claude", "prompt": "/security-review"},
        }
        fake_proc = MagicMock()
        with patch("code_review.run_subprocess_popen", return_value=fake_proc) as popen, \
             patch("code_review.build_argv", side_effect=lambda p, c: ["argv", p]):
            procs = cr.start_review_processes("PR_BODY", config)
        assert set(procs.keys()) == {"code_review", "security_review"}
        assert popen.call_count == 2
        for key, (proc, owner) in procs.items():
            assert proc is fake_proc
            assert owner == "claude"

    def test_includes_pr_content_in_prompt(self):
        config = {"k": {"owner": "claude", "prompt": "/cmd"}}
        captured = {}

        def fake_build_argv(prompt, _):
            captured["prompt"] = prompt
            return ["argv"]

        with patch("code_review.run_subprocess_popen", return_value=MagicMock()), \
             patch("code_review.build_argv", side_effect=fake_build_argv):
            cr.start_review_processes("PR_BODY", config)
        assert captured["prompt"] == "/cmd PR_BODY"


# ──────────────────────────────────────────────────────────────────
# collect_review_results
# ──────────────────────────────────────────────────────────────────


class TestCollectReviewResults:
    def test_extracts_content_and_session_id_into_per_key_tuple(self):
        proc = MagicMock()
        proc.communicate.return_value = ("RAW_ENVELOPE", "STDERR")
        proc.returncode = 0
        procs = {"code_review": (proc, "claude")}
        with patch("code_review.get_session_id", return_value="sid-1") as gsid, \
             patch("code_review.get_result", return_value="REVIEW_TEXT") as gres:
            results = cr.collect_review_results(procs)
        # slot 1 is the extracted agent text, NOT the raw envelope
        assert results == {"code_review": (0, "REVIEW_TEXT", "STDERR", "sid-1")}
        gsid.assert_called_once_with("RAW_ENVELOPE", "claude")
        gres.assert_called_once_with("RAW_ENVELOPE", "claude")


# ──────────────────────────────────────────────────────────────────
# run_headless_review
# ──────────────────────────────────────────────────────────────────


class TestRunHeadlessReview:
    def test_success_path_returns_results_dict(self):
        results = {"code_review": (0, "out", "err", "sid")}
        with patch("code_review.start_review_processes", return_value={}), \
             patch("code_review.collect_review_results", return_value=results):
            ok, got = cr.run_headless_review("pr", {})
        assert ok is True
        assert got is results

    def test_returns_false_when_any_returncode_nonzero(self):
        results = {
            "code_review": (0, "out", "err", "sid-a"),
            "security_review": (2, "out", "err", "sid-b"),
        }
        with patch("code_review.start_review_processes", return_value={}), \
             patch("code_review.collect_review_results", return_value=results):
            ok, got = cr.run_headless_review("pr", {})
        assert ok is False
        assert got == {}


# ──────────────────────────────────────────────────────────────────
# correct_one
# ──────────────────────────────────────────────────────────────────


class TestCorrectOne:
    def test_returns_true_immediately_when_already_valid(self):
        results = {"k": (0, "stdout", "err", "sid")}
        with patch("code_review.check_review_output", return_value=(True, "ok")), \
             patch("code_review.run_headless_parallel") as parallel:
            assert cr.correct_one("k", results, "tpl") is True
        parallel.assert_not_called()

    def test_loops_until_valid(self):
        results = {"k": (0, "stdout", "err", "sid")}
        # check_review_output sequence: bad -> bad -> good
        check_seq = iter([(False, "diff1"), (False, "diff2"), (True, "ok")])
        # re-prompt returns a JSON envelope; correct_one calls get_claude_result on it
        envelope = json.dumps({"result": "new_out", "session_id": "sid"})
        with patch("code_review.check_review_output", side_effect=lambda *a, **kw: next(check_seq)), \
             patch("code_review.run_headless_parallel", return_value=(True, [envelope])) as parallel:
            assert cr.correct_one("k", results, "tpl") is True
        assert parallel.call_count == 2

    def test_returns_false_when_subprocess_fails(self):
        results = {"k": (0, "stdout", "err", "sid")}
        with patch("code_review.check_review_output", return_value=(False, "diff")), \
             patch("code_review.run_headless_parallel", return_value=(False, [])):
            assert cr.correct_one("k", results, "tpl") is False


# ──────────────────────────────────────────────────────────────────
# run_correction
# ──────────────────────────────────────────────────────────────────


class TestRunCorrection:
    def test_runs_correct_one_for_each_config_entry(self, tmp_path):
        tpl_a = tmp_path / "a.md"
        tpl_a.write_text("TPL_A")
        tpl_b = tmp_path / "b.md"
        tpl_b.write_text("TPL_B")
        config = {"a": {"template": tpl_a}, "b": {"template": tpl_b}}
        results = {"a": (0, "x", "", "s"), "b": (0, "y", "", "s")}
        with patch("code_review.correct_one", return_value=True) as co:
            assert cr.run_correction(results, config) is True
        assert co.call_count == 2
        # template content read off disk and forwarded to correct_one
        passed_templates = [c.args[2] for c in co.call_args_list]
        assert set(passed_templates) == {"TPL_A", "TPL_B"}

    def test_short_circuits_on_first_failure(self, tmp_path):
        tpl = tmp_path / "t.md"
        tpl.write_text("T")
        config = {"a": {"template": tpl}, "b": {"template": tpl}}
        results = {"a": (0, "x", "", "s"), "b": (0, "y", "", "s")}
        with patch("code_review.correct_one", return_value=False) as co:
            assert cr.run_correction(results, config) is False
        assert co.call_count == 1


# ──────────────────────────────────────────────────────────────────
# generate_pr_review_content  (regression: was calling undefined invoke_agents)
# ──────────────────────────────────────────────────────────────────


class TestGeneratePrReviewContent:
    def test_extracts_result_field_from_claude_envelope(self, tmp_path):
        envelope = json.dumps({"result": "TITLE\nBODY", "session_id": "x"})
        with patch("code_review.run_headless_parallel", return_value=(True, [envelope])) as parallel, \
             patch("code_review.CODE_REVIEW_DIR", tmp_path):
            (tmp_path / "x.md").touch()
            out = cr.generate_pr_review_content([tmp_path / "x.md"])
        # the bare result text should flow back, NOT the envelope
        assert out == "TITLE\nBODY"
        parallel.assert_called_once()

    def test_returns_none_on_failure(self, tmp_path):
        with patch("code_review.run_headless_parallel", return_value=(False, [])), \
             patch("code_review.CODE_REVIEW_DIR", tmp_path):
            (tmp_path / "x.md").touch()
            assert cr.generate_pr_review_content([tmp_path / "x.md"]) is None


# ──────────────────────────────────────────────────────────────────
# save_review_report
# ──────────────────────────────────────────────────────────────────


class TestSaveReviewReport:
    def test_writes_file_named_after_key(self, tmp_path):
        with patch("code_review.CODE_REVIEW_DIR", tmp_path):
            cr.save_review_report("code_review", "REPORT_BODY")
        out = tmp_path / "code_review.md"
        assert out.read_text() == "REPORT_BODY"


# ──────────────────────────────────────────────────────────────────
# run_review  (regression: previously referenced undefined names)
# ──────────────────────────────────────────────────────────────────


class TestRunReview:
    def test_happy_path_writes_one_file_per_review(self, tmp_path, capsys):
        results = {
            "code_review": (0, "CODE_OUT", "", "sid-c"),
            "security_review": (0, "SEC_OUT", "", "sid-s"),
        }
        with patch("code_review.get_pr_number", return_value=1), \
             patch("code_review.view_pr_content", return_value="PR"), \
             patch("code_review.run_headless_review", return_value=(True, results)), \
             patch("code_review.run_correction", return_value=True), \
             patch("code_review.CODE_REVIEW_DIR", tmp_path):
            cr.run_review()
        assert (tmp_path / "code_review.md").read_text() == "CODE_OUT"
        assert (tmp_path / "security_review.md").read_text() == "SEC_OUT"

    def test_aborts_when_review_fails(self, tmp_path, capsys):
        with patch("code_review.get_pr_number", return_value=1), \
             patch("code_review.view_pr_content", return_value="PR"), \
             patch("code_review.run_headless_review", return_value=(False, {})), \
             patch("code_review.run_correction") as correction, \
             patch("code_review.CODE_REVIEW_DIR", tmp_path):
            cr.run_review()
        # correction loop must not run if reviews themselves failed
        correction.assert_not_called()
        assert "Failed to run review" in capsys.readouterr().out

    def test_aborts_when_correction_fails(self, tmp_path, capsys):
        results = {"code_review": (0, "OUT", "", "sid")}
        with patch("code_review.get_pr_number", return_value=1), \
             patch("code_review.view_pr_content", return_value="PR"), \
             patch("code_review.run_headless_review", return_value=(True, results)), \
             patch("code_review.run_correction", return_value=False), \
             patch("code_review.CODE_REVIEW_DIR", tmp_path):
            cr.run_review()
        # no report should be written when correction fails
        assert not (tmp_path / "code_review.md").exists()
        assert "Correction loop failed" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════
# End-to-end: main() with all external boundaries mocked
#
# Boundaries faked here:
#   - subprocess.run     : `gh pr view`, `gh pr view --json`, `gh pr review`
#   - subprocess.Popen   : the 3 parallel review subprocesses (returns canned JSON)
#   - run_headless_parallel : single-call paths (correction loop, issue content)
#   - template_conformance_check / extract_scores / scores_valid : conformance gate
#   - CODE_REVIEW_DIR / REPORT_PATHS / REVIEW_CONFIG_MAP : redirected to tmp_path
# ══════════════════════════════════════════════════════════════════


class _GhStub:
    """Dispatches subprocess.run calls by argv prefix and records the gh pr review body."""

    def __init__(self, pr_number: str = "42", pr_body: str = "PR BODY"):
        self.pr_number = pr_number
        self.pr_body = pr_body
        self.review_body: str | None = None
        self.calls: list[list[str]] = []

    def __call__(self, argv, *, check, capture_output, text):
        self.calls.append(argv)
        if argv[:4] == ["gh", "pr", "view", "--json"]:
            return MagicMock(returncode=0, stdout=f"{self.pr_number}\n", stderr="")
        if argv[:3] == ["gh", "pr", "view"]:
            return MagicMock(returncode=0, stdout=self.pr_body, stderr="")
        if argv[:3] == ["gh", "pr", "review"]:
            # capture --body so we can assert on it later
            self.review_body = argv[argv.index("--body") + 1]
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected gh argv: {argv}")


def _fake_review_popen(key: str, conf: int = 90, qual: int = 90) -> MagicMock:
    """One Popen per parallel review; communicate() returns claude-shaped JSON envelope.

    The envelope must include both `session_id` (for get_claude_session_id) and `result`
    (for get_claude_result). The result text carries score lines so that
    decide_pr_review_action sees real numbers when it reads the saved file back.
    """
    proc = MagicMock()
    result_text = (
        f"# {key}\n\n"
        f"REVIEW-CONTENT-{key}\n\n"
        f"Confidence Score: {conf}\nQuality Score: {qual}\n"
    )
    envelope = {"session_id": f"sid-{key}", "result": result_text}
    proc.communicate.return_value = (json.dumps(envelope), "")
    proc.returncode = 0
    return proc


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Redirect CODE_REVIEW_DIR/REPORT_PATHS/REVIEW_CONFIG_MAP into tmp_path and seed templates."""
    keys = ["security_review", "code_review", "requirements_review"]
    config = {}
    for key in keys:
        tpl = tmp_path / f"{key}_template.md"
        # template body is just the bare key — used as a tag in the conformance mock
        tpl.write_text(key)
        config[key] = {"owner": "claude", "prompt": f"/{key}", "template": tpl}
    report_paths = [tmp_path / f"{k}.md" for k in keys]
    # ensure relative_to(CODE_REVIEW_DIR) inside generate_pr_review_content resolves
    for p in report_paths:
        p.touch()
    monkeypatch.setattr(cr, "CODE_REVIEW_DIR", tmp_path)
    monkeypatch.setattr(cr, "REPORT_PATHS", report_paths)
    monkeypatch.setattr(cr, "REVIEW_CONFIG_MAP", config)
    return {"tmp_path": tmp_path, "keys": keys, "config": config}


class TestE2EMain:
    def test_happy_path_runs_reviews_saves_files_and_posts_pr_review(self, e2e_env, monkeypatch):
        keys = e2e_env["keys"]
        gh = _GhStub(pr_number="42", pr_body="PR BODY TEXT")

        # one Popen per review key, returned in REVIEW_CONFIG_MAP iteration order
        popens = [_fake_review_popen(k) for k in keys]
        popen_iter = iter(popens)

        monkeypatch.setattr(cr.subprocess, "run", gh)
        monkeypatch.setattr(cr.subprocess, "Popen", lambda *a, **kw: next(popen_iter))

        # conformance gate: every review passes immediately, no correction loop
        monkeypatch.setattr(cr, "template_conformance_check", lambda *a, **kw: (True, ""))
        monkeypatch.setattr(cr, "extract_scores", lambda *a, **kw: {"clarity": 9})
        monkeypatch.setattr(cr, "scores_valid", lambda *a, **kw: True)
        # the score-threshold action has its own dedicated tests; force --approve here
        # so this test stays focused on orchestration, not on score decoding
        monkeypatch.setattr(cr, "decide_pr_review_action", lambda paths: "--approve")

        # issue-content generator: claude returns its standard JSON envelope, and
        # generate_pr_review_content now extracts the `result` field via get_claude_result
        body_envelope = json.dumps(
            {"session_id": "issue-sid", "result": "Title line\nBody line 1\nBody line 2"}
        )
        rhp = MagicMock(return_value=(True, [body_envelope]))
        monkeypatch.setattr(cr, "run_headless_parallel", rhp)

        cr.main()

        # one report file per review, populated with the EXTRACTED result text
        # (the JSON envelope is unwrapped in collect_review_results)
        for key in keys:
            saved = (e2e_env["tmp_path"] / f"{key}.md").read_text()
            assert f"REVIEW-CONTENT-{key}" in saved
            # score lines must round-trip so decide_pr_review_action can read them
            assert "Confidence Score: 90" in saved
            assert "Quality Score: 90" in saved

        # gh pr view --json (number lookup) was called twice — once in run_review,
        # once in create_pr_review
        json_calls = [c for c in gh.calls if c[:4] == ["gh", "pr", "view", "--json"]]
        assert len(json_calls) == 2

        # gh pr view <num> was called once with the resolved number
        view_calls = [c for c in gh.calls if c[:3] == ["gh", "pr", "view"] and "--json" not in c]
        assert view_calls == [["gh", "pr", "view", "42"]]

        # PR review posted with the full generated content as body. Action is --approve
        # because every saved review carries passing scores (90/90 ≥ 80 threshold).
        review_calls = [c for c in gh.calls if c[:3] == ["gh", "pr", "review"]]
        assert len(review_calls) == 1
        assert "42" in review_calls[0]
        assert "--approve" in review_calls[0]
        assert "--comment" not in review_calls[0]
        assert "--request-changes" not in review_calls[0]
        assert gh.review_body == "Title line\nBody line 1\nBody line 2"

        # correction loop never fired (only call to run_headless_parallel was for issue content)
        assert rhp.call_count == 1

    def test_correction_loop_re_prompts_until_review_passes(self, e2e_env, monkeypatch):
        keys = e2e_env["keys"]
        gh = _GhStub()
        popens = [_fake_review_popen(k) for k in keys]
        popen_iter = iter(popens)
        monkeypatch.setattr(cr.subprocess, "run", gh)
        monkeypatch.setattr(cr.subprocess, "Popen", lambda *a, **kw: next(popen_iter))

        # template_conformance_check fails the first time it's called for the FIRST key,
        # passes everywhere else. iteration order in run_correction is dict insertion order
        first_key = keys[0]
        call_log: list[tuple[str, str]] = []

        def conformance(actual, template):
            # template body == the key, so it doubles as a tag for which review's gate is firing
            tag = template
            call_log.append((tag, "check"))
            # fail the first conformance check for first_key, then accept anything
            if tag == first_key and ("retry" not in actual):
                return False, "DIFF_BODY"
            return True, ""

        monkeypatch.setattr(cr, "template_conformance_check", conformance)
        monkeypatch.setattr(cr, "extract_scores", lambda *a, **kw: {"x": 9})
        monkeypatch.setattr(cr, "scores_valid", lambda *a, **kw: True)
        # action decision has its own tests; pin it for this orchestration scenario
        monkeypatch.setattr(cr, "decide_pr_review_action", lambda paths: "--approve")

        # run_headless_parallel: called by correct_one (for re-prompt) and by
        # generate_pr_review_content. Both receive a fresh JSON envelope from claude
        # and extract `result` via get_claude_result, so we hand back envelopes here.
        retry_envelope = json.dumps(
            {"session_id": "retry-sid", "result": f"retry-{first_key} corrected output"}
        )
        body_envelope = json.dumps(
            {"session_id": "issue-sid", "result": "PR review summary body"}
        )
        outputs = iter([(True, [retry_envelope]), (True, [body_envelope])])
        rhp = MagicMock(side_effect=lambda *a, **kw: next(outputs))
        monkeypatch.setattr(cr, "run_headless_parallel", rhp)

        cr.main()

        # the correction loop ran exactly once for the failing review
        assert rhp.call_count == 2

        # conformance was checked at least twice for first_key (initial fail + retry pass)
        first_key_checks = [t for (t, _) in call_log if t == first_key]
        assert len(first_key_checks) >= 2

        # report files still get written (run_correction returned True after the retry)
        for key in keys:
            assert (e2e_env["tmp_path"] / f"{key}.md").exists()

        # PR review still posted at the end with the issue-content body
        assert gh.review_body == "PR review summary body"
