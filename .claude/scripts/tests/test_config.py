"""Tests for the workflow ``Config`` class.

Cover the accessors that bridge ``config.json`` to the rest of the
hook system: phase queries (workflow + mode + agent), score thresholds,
phase order, dirs, file paths, and safe domains.
"""

import pytest

from config import Config


@pytest.fixture
def cfg() -> Config:
    """Return a fresh ``Config`` reading the on-disk ``config.json``."""
    return Config()


# ── Phase queries ─────────────────────────────────────────────────


def test_get_phases_by_workflow_implement(cfg: Config) -> None:
    names = cfg.get_phase_names_by_workflow("implement")
    assert "explore" in names and "write-report" in names


def test_get_phases_by_workflow_specs(cfg: Config) -> None:
    names = cfg.get_phase_names_by_workflow("specs")
    assert "prd" in names and "design" in names


def test_get_phases_by_mode_read_only(cfg: Config) -> None:
    names = cfg.get_phases_by_mode("read-only", names_only=True)
    assert "decision" in names and "prd" in names


def test_get_mode_returns_string_or_none(cfg: Config) -> None:
    assert cfg.get_mode("decision") == "read-only"
    assert cfg.get_mode("explore") is None


# ── Agent queries (singular schema) ───────────────────────────────


def test_get_agent_for_phase(cfg: Config) -> None:
    assert cfg.get_agent("explore") == "Explore"
    assert cfg.get_agent("plan") == "Plan"


def test_get_agent_count_with_default(cfg: Config) -> None:
    assert cfg.get_agent_count("explore") == 3
    assert cfg.get_agent_count("plan") == 1  # default when unspecified


def test_get_agent_missing_returns_none(cfg: Config) -> None:
    assert cfg.get_agent("decision") is None


# ── parallel_with / checkpoint / auto flags ───────────────────────


def test_get_parallel_with(cfg: Config) -> None:
    assert cfg.get_parallel_with("research") == ["explore"]
    assert cfg.get_parallel_with("plan") == []


def test_phases_with_checkpoint(cfg: Config) -> None:
    assert "plan" in cfg.get_checkpoint_phases()


def test_phases_with_auto(cfg: Config) -> None:
    assert "create-tasks" in cfg.get_auto_phases()


# ── phases_order ──────────────────────────────────────────────────


def test_phases_order_implement(cfg: Config) -> None:
    order = cfg.get_phases_order("implement")
    assert order[0] == "explore"
    assert order[-1] == "write-report"


def test_phases_order_specs_first_step(cfg: Config) -> None:
    assert cfg.get_phases_order("specs")[0] == "assessment"


def test_phases_order_unknown_workflow(cfg: Config) -> None:
    assert cfg.get_phases_order("unknown") == []


# ── Score thresholds (review_score_thresholds in JSON) ────────────


def test_get_score_threshold_plan(cfg: Config) -> None:
    assert cfg.get_score_threshold("plan", "confidence") == 80
    assert cfg.get_score_threshold("plan", "quality") == 80


def test_get_score_threshold_missing_returns_zero(cfg: Config) -> None:
    assert cfg.get_score_threshold("plan", "nonexistent") == 0


# ── safe_domains / file_paths / dirs ──────────────────────────────


def test_safe_domains_contains_known(cfg: Config) -> None:
    assert "github.com" in cfg.safe_domains


def test_get_file_path_known_keys(cfg: Config) -> None:
    assert cfg.get_file_path("plan").endswith("latest-plan.md")
    assert cfg.get_file_path("report").endswith("report.md")


def test_get_file_path_unknown_returns_empty(cfg: Config) -> None:
    assert cfg.get_file_path("nope") == ""


def test_get_dir_known_keys(cfg: Config) -> None:
    assert cfg.get_dir("template") == ".claude/templates/"
    assert cfg.get_dir("project") == "project/"


def test_get_dir_unknown_returns_empty(cfg: Config) -> None:
    assert cfg.get_dir("nope") == ""
