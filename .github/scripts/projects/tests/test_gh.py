"""Tests for projects.gh — shared client. Mocks at the subprocess boundary."""
from __future__ import annotations

from unittest.mock import patch

from projects import gh


class TestRun:
    @patch("projects.gh.subprocess.run")
    def test_returns_stdout_stripped(self, mock_run):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "out\n", "stderr": ""})()
        assert gh.run(["gh", "x"]) == "out"

    @patch("projects.gh.subprocess.run")
    def test_raises_on_failure_when_checked(self, mock_run):
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
        try:
            gh.run(["gh", "x"])
        except RuntimeError as exc:
            assert "boom" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    @patch("projects.gh.subprocess.run")
    def test_no_raise_when_check_false(self, mock_run):
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": "x", "stderr": ""})()
        assert gh.run(["gh", "x"], check=False) == "x"


class TestGhJson:
    @patch.object(gh, "run", return_value='{"a": 1}')
    def test_parses_json(self, mock_run):
        assert gh.gh_json(["gh", "x"]) == {"a": 1}

    @patch.object(gh, "run", return_value="")
    def test_empty_returns_none(self, mock_run):
        assert gh.gh_json(["gh", "x"]) is None


class TestIssueUrl:
    def test_basic(self):
        assert gh.issue_url("o/r", 42) == "https://github.com/o/r/issues/42"


class TestAddLabels:
    @patch.object(gh, "run")
    @patch.object(gh, "ensure_label")
    def test_ensures_and_adds(self, mock_label, mock_run):
        gh.add_labels("o/r", 5, ["feature", "backend"])
        assert mock_label.call_count == 2
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "issue", "edit"]
        assert "--add-label" in cmd and "feature" in cmd and "backend" in cmd

    @patch.object(gh, "run")
    @patch.object(gh, "ensure_label")
    def test_empty_is_noop(self, mock_label, mock_run):
        gh.add_labels("o/r", 5, [])
        mock_label.assert_not_called()
        mock_run.assert_not_called()

    @patch.object(gh, "run")
    @patch.object(gh, "ensure_label")
    def test_filters_blank(self, mock_label, mock_run):
        gh.add_labels("o/r", 5, ["feature", "", "  "])
        cmd = mock_run.call_args[0][0]
        assert cmd.count("--add-label") == 1


class TestFetchNodeIdsAndEdges:
    @patch.object(gh, "gh_json")
    def test_parses_ids_and_edges(self, mock_gh):
        mock_gh.return_value = {
            "data": {"repository": {
                "i100": {"id": "NODE-100", "number": 100,
                         "blockedBy": {"nodes": [{"number": 200}]}, "parent": None},
                "i200": {"id": "NODE-200", "number": 200,
                         "blockedBy": {"nodes": []}, "parent": None},
            }}
        }
        ids, edges, parents = gh._fetch_node_ids_and_edges("org/repo", {100, 200})
        assert ids == {100: "NODE-100", 200: "NODE-200"}
        assert edges == {(100, 200)}
        assert parents == {}

    @patch.object(gh, "gh_json")
    def test_empty_input_skips_query(self, mock_gh):
        ids, edges, parents = gh._fetch_node_ids_and_edges("org/repo", set())
        assert ids == {} and edges == set() and parents == {}
        mock_gh.assert_not_called()

    def test_query_uses_blockedBy_field(self):
        assert "blockedBy(" in gh._build_node_id_edges_query("org/repo", [100])


class TestFetchIssueBodies:
    @patch.object(gh, "gh_json")
    def test_parses_bodies(self, mock_gh):
        mock_gh.return_value = {"data": {"repository": {
            "i100": {"number": 100, "id": "N100", "body": "Body A"},
        }}}
        assert gh._fetch_issue_bodies("org/repo", {100}) == {100: ("N100", "Body A")}

    @patch.object(gh, "gh_json")
    def test_empty_input_skips_query(self, mock_gh):
        assert gh._fetch_issue_bodies("org/repo", set()) == {}
        mock_gh.assert_not_called()


class TestCollectBodyUpdateMutations:
    def test_emits_mutation_when_body_differs(self):
        story = {"title": "A", "issue_number": 100, "description": "New context"}
        bodies = {100: ("N100", "")}
        mutations = gh._collect_body_update_mutations([story], bodies)
        assert len(mutations) == 1
        assert "updateIssue" in mutations[0]
        assert "New context" in mutations[0]

    def test_skips_when_body_matches(self):
        from projects import backlog
        story = {"title": "A", "issue_number": 100, "description": "Same body"}
        bodies = {100: ("N100", backlog.build_issue_body(story))}
        assert gh._collect_body_update_mutations([story], bodies) == []

    def test_uses_groomed_sections_in_body(self):
        story = {"title": "A", "issue_number": 100, "tasks": ["Step one"]}
        bodies = {100: ("N100", "")}
        mutations = gh._collect_body_update_mutations([story], bodies)
        assert len(mutations) == 1
        assert "## Tasks" in mutations[0]
        assert "Step one" in mutations[0]

    def test_skips_when_no_issue_number(self):
        assert gh._collect_body_update_mutations([{"title": "A", "description": "X"}], {}) == []

    def test_empty_input(self):
        assert gh._collect_body_update_mutations([], {}) == []


class TestUpdateIssueBodies:
    @patch.object(gh, "_fetch_issue_bodies")
    @patch.object(gh, "execute_batched_mutations")
    def test_runs_mutations_when_body_differs(self, mock_exec, mock_fetch):
        mock_fetch.return_value = {100: ("N100", "stale body")}
        gh.update_issue_bodies("org/repo", [{"title": "A", "issue_number": 100, "description": "Fresh"}])
        mutations = mock_exec.call_args[0][0]
        assert len(mutations) == 1
        assert "updateIssue" in mutations[0]

    @patch.object(gh, "_fetch_issue_bodies")
    @patch.object(gh, "execute_batched_mutations")
    def test_skips_when_no_issue_numbers(self, mock_exec, mock_fetch):
        gh.update_issue_bodies("org/repo", [{"title": "A", "description": "X"}])
        mock_fetch.assert_not_called()
        mock_exec.assert_not_called()


class TestExecuteBatchedMutations:
    def test_empty(self, capsys):
        gh.execute_batched_mutations([])
        assert "No field updates" in capsys.readouterr().out

    @patch("projects.gh.subprocess.run")
    def test_single_batch(self, mock_run, capsys):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()
        gh.execute_batched_mutations([f"m{i}: stub" for i in range(5)])
        out = capsys.readouterr().out
        assert "5 field updates" in out
        assert "Batch 1/1" in out

    @patch("projects.gh.subprocess.run")
    def test_multiple_batches(self, mock_run, capsys):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()
        gh.execute_batched_mutations([f"m{i}: stub" for i in range(35)])
        out = capsys.readouterr().out
        assert "Batch 1/2" in out and "Batch 2/2" in out


class TestSetBlockingRelationships:
    @patch.object(gh, "_fetch_node_ids_and_edges",
                  return_value=({100: "NODE-100", 200: "NODE-200"}, set(), {}))
    @patch.object(gh, "execute_batched_mutations")
    def test_calls_addBlockedBy(self, mock_exec, mock_fetch):
        # blocked_by carries the blocker's issue number directly (no id map).
        items = [{"title": "B", "issue_number": 100, "blocked_by": [200]}]
        gh.set_blocking_relationships("org/repo", items)
        mutations = mock_exec.call_args[0][0]
        assert any("addBlockedBy" in m for m in mutations)
        assert len(mutations) == 1

    @patch.object(gh, "_fetch_node_ids_and_edges", return_value=({}, set(), {}))
    @patch.object(gh, "execute_batched_mutations")
    def test_skips_empty(self, mock_exec, mock_fetch, capsys):
        gh.set_blocking_relationships("org/repo", [])
        assert "No blocking" in capsys.readouterr().out
        mock_exec.assert_not_called()

    @patch.object(gh, "_fetch_node_ids_and_edges",
                  return_value=({100: "NODE-100", 200: "NODE-200"}, {(100, 200)}, {}))
    @patch.object(gh, "execute_batched_mutations")
    def test_skips_pairs_already_set(self, mock_exec, mock_fetch):
        items = [{"title": "B", "issue_number": 100, "blocked_by": [200]}]
        gh.set_blocking_relationships("org/repo", items)
        assert mock_exec.call_args[0][0] == []


class TestDeleteIssueMutations:
    def test_builds_aliases(self):
        muts = gh.delete_issue_mutations({1: "N1", 2: "N2"})
        assert len(muts) == 2
        assert all("deleteIssue" in m for m in muts)


class TestEnsureLabel:
    @patch.object(gh, "run")
    def test_force_create(self, mock_run):
        gh.ensure_label("bug", "o/r")
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "label", "create"]
        assert "--force" in cmd
