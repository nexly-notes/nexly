"""Tests for projects.state — per-item ops. Mocks gh/board at the boundary."""
from __future__ import annotations

import json
from unittest.mock import patch

from projects import state
from projects.config import Identity

_IDENT = Identity(repo="o/r", project=1, owner="me")


# ── view ───────────────────────────────────────────────────────────────────


class TestView:
    @patch.object(state.board, "get_project_items", return_value=[
        {"id": "I1", "content": {"number": 5}, "status": "In Progress",
         "priority": "P0", "size": "M", "points": 5},
    ])
    @patch.object(state.gh, "gh_issue_view", return_value={"title": "The title", "body": "The body"})
    def test_prints_fields_and_body_by_number(self, mock_view, mock_items, capsys):
        assert state.view(_IDENT, issue_number="5") == 0
        out = capsys.readouterr().out
        assert "#5: The title" in out
        assert "In Progress" in out and "P0" in out
        assert "Size:" in out and "M" in out
        assert "Sprint" not in out
        assert "The body" in out

    @patch.object(state.gh, "gh_issue_view", return_value={})
    def test_not_found_returns_1(self, mock_view, capsys):
        assert state.view(_IDENT, issue_number="99") == 1
        assert "not found" in capsys.readouterr().err

    def test_garbage_token_returns_1(self, capsys):
        assert state.view(_IDENT, issue_number="not-a-number") == 1
        assert "Could not resolve" in capsys.readouterr().err


class TestResolveIssueNumber:
    def test_bare_int(self):
        assert state._resolve_issue_number("42") == 42

    def test_garbage_returns_none(self):
        assert state._resolve_issue_number("not-an-id") is None


# ── list ───────────────────────────────────────────────────────────────────


class TestList:
    ITEMS = [
        {"id": "I1", "content": {"number": 1, "title": "A"}, "status": "Backlog",
         "priority": "P0", "size": "M", "points": 5},
        {"id": "I2", "content": {"number": 2, "title": "B"}, "status": "Done",
         "priority": "P1", "size": "L", "points": 8},
        {"id": "I3", "content": {}},  # no number — skipped
    ]

    @patch.object(state.board, "get_project_items")
    def test_json_rows(self, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        assert state.list_items(_IDENT, json=True) == 0
        rows = json.loads(capsys.readouterr().out)
        assert {r["number"] for r in rows} == {1, 2}
        assert "sprint" not in rows[0]
        assert rows[0]["size"] == "M"

    @patch.object(state.board, "get_project_items")
    def test_filter_by_status(self, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        state.list_items(_IDENT, status="Done", json=True)
        rows = json.loads(capsys.readouterr().out)
        assert [r["number"] for r in rows] == [2]

    @patch.object(state.board, "get_project_items")
    def test_filter_by_priority(self, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        state.list_items(_IDENT, priority="P0", json=True)
        rows = json.loads(capsys.readouterr().out)
        assert [r["number"] for r in rows] == [1]

    @patch.object(state.board, "get_project_items")
    def test_table_output(self, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        state.list_items(_IDENT, json=False)
        assert "2 item(s)" in capsys.readouterr().out


# ── order ──────────────────────────────────────────────────────────────────


class TestOrder:
    @staticmethod
    def _rows(*specs: tuple[int, str]) -> list[dict]:
        # specs: (number, priority) -> minimal project rows.
        return [
            {"number": n, "title": f"T{n}", "status": "Backlog", "priority": p}
            for n, p in specs
        ]

    ITEMS = [
        {"id": "I1", "content": {"number": 1, "title": "A"}, "status": "Backlog", "priority": "P0"},
        {"id": "I2", "content": {"number": 2, "title": "B"}, "status": "Backlog", "priority": "P2"},
    ]

    # ── _order_rows (pure) ──

    def test_priority_only_ordering(self):
        rows = self._rows((1, "P2"), (2, "P0"), (3, "P1"))
        ordered, unresolved = state._order_rows(rows, {})
        assert [r["number"] for r in ordered] == [2, 3, 1]
        assert unresolved == []

    def test_tie_break_by_number(self):
        rows = self._rows((3, "P1"), (1, "P1"), (2, "P1"))
        ordered, _ = state._order_rows(rows, {})
        assert [r["number"] for r in ordered] == [1, 2, 3]

    def test_low_priority_blocker_emitted_before_high_priority_dependent(self):
        # #1 is P0 but blocked by #2 (P2) -> the blocker wins, #2 comes first.
        rows = self._rows((1, "P0"), (2, "P2"))
        ordered, unresolved = state._order_rows(rows, {1: [2]})
        assert [r["number"] for r in ordered] == [2, 1]
        assert unresolved == []

    def test_cycle_returned_as_unresolved(self):
        rows = self._rows((1, "P0"), (2, "P0"))
        ordered, unresolved = state._order_rows(rows, {1: [2], 2: [1]})
        assert ordered == []
        assert {r["number"] for r in unresolved} == {1, 2}

    def test_out_of_set_blockers_ignored(self):
        rows = self._rows((1, "P0"))
        ordered, unresolved = state._order_rows(rows, {1: [99]})
        assert [r["number"] for r in ordered] == [1]
        assert unresolved == []

    def test_mixed_cycle_and_survivor(self):
        # #3 is acyclic and orderable; #1<->#2 form a cycle -> both branches non-empty.
        rows = self._rows((1, "P0"), (2, "P0"), (3, "P1"))
        ordered, unresolved = state._order_rows(rows, {1: [2], 2: [1]})
        assert [r["number"] for r in ordered] == [3]
        assert {r["number"] for r in unresolved} == {1, 2}

    # ── _format_blocked_by (pure) ──

    def test_format_blocked_by(self):
        assert state._format_blocked_by([2, 3]) == "#2 #3"
        assert state._format_blocked_by([]) == "-"

    # ── _blocker_map (graph -> in-board blockers) ──

    @patch.object(state.gh, "_fetch_node_ids_and_edges", return_value=({}, {(1, 99)}, {}))
    def test_blocker_map_drops_off_board_endpoints(self, mock_edges):
        # Edge (1, 99): #99 isn't on the board, so it's filtered; #1 still seeds [].
        assert state._blocker_map("o/r", [1]) == {1: []}

    @patch.object(state.gh, "_fetch_node_ids_and_edges", return_value=({}, {(1, 3), (1, 2)}, {}))
    def test_blocker_map_blockers_ascending(self, mock_edges):
        # Edges arrive as an unordered set; sorted(edges) makes the list deterministic.
        assert state._blocker_map("o/r", [1, 2, 3]) == {1: [2, 3], 2: [], 3: []}

    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_blocker_map_empty_skips_fetch(self, mock_edges):
        assert state._blocker_map("o/r", []) == {}
        mock_edges.assert_not_called()

    # ── order() wiring ──

    @patch.object(state.board, "get_project_items")
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_table_output_blocker_first(self, mock_edges, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        # #1 is blocked by #2 -> edge (blocked=1, blocker=2).
        mock_edges.return_value = ({}, {(1, 2)}, {})
        assert state.order(_IDENT) == 0
        out = capsys.readouterr().out
        # Digit-leading lines minus the "N item(s) ordered" summary = the body rows.
        body_rows = [ln for ln in out.splitlines() if ln[:1].isdigit() and "item(s)" not in ln]
        seq_and_number = [tuple(ln.split()[:2]) for ln in body_rows]
        assert seq_and_number == [("1", "2"), ("2", "1")]  # blocker #2 emitted before dependent #1
        assert "BLOCKED BY" in out
        assert "#2" in out  # dependent's blocker rendered
        assert "2 item(s) ordered" in out

    @patch.object(state.board, "get_project_items")
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_json_shape(self, mock_edges, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        mock_edges.return_value = ({}, {(1, 2)}, {})
        assert state.order(_IDENT, json=True) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [o["number"] for o in payload["order"]] == [2, 1]
        assert [o["seq"] for o in payload["order"]] == [1, 2]
        dependent = next(o for o in payload["order"] if o["number"] == 1)
        assert dependent["blocked_by"] == [2]
        assert payload["unresolved"] == []

    @patch.object(state.board, "get_project_items", return_value=[])
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_empty_board_skips_edge_fetch(self, mock_edges, mock_items, capsys):
        assert state.order(_IDENT) == 0
        mock_edges.assert_not_called()
        assert "No items found." in capsys.readouterr().out

    @patch.object(state.board, "get_project_items")
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_cycle_exits_nonzero(self, mock_edges, mock_items, capsys):
        mock_items.return_value = self.ITEMS
        mock_edges.return_value = ({}, {(1, 2), (2, 1)}, {})
        assert state.order(_IDENT) == 1
        assert "cycle" in capsys.readouterr().err

    @staticmethod
    def _items(*specs: tuple[int, str]) -> list[dict]:
        # specs: (number, priority) -> minimal project-board items.
        return [
            {"id": f"I{n}", "content": {"number": n, "title": f"T{n}"},
             "status": "Backlog", "priority": p}
            for n, p in specs
        ]

    @patch.object(state.board, "get_project_items")
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_partial_order_with_cycle(self, mock_edges, mock_items, capsys):
        # #3 is orderable; #1<->#2 cycle -> table prints #3, stderr flags the cycle, exit 1.
        mock_items.return_value = self._items((1, "P0"), (2, "P0"), (3, "P1"))
        mock_edges.return_value = ({}, {(1, 2), (2, 1)}, {})
        assert state.order(_IDENT) == 1
        captured = capsys.readouterr()
        assert "1 item(s) ordered" in captured.out
        assert "cycle" in captured.err
        assert "#1" in captured.err and "#2" in captured.err

    @patch.object(state.board, "get_project_items")
    @patch.object(state.gh, "_fetch_node_ids_and_edges")
    def test_multi_blocker_blocked_by_is_ascending(self, mock_edges, mock_items, capsys):
        # #1 blocked by both #2 and #3; edges arrive set-unordered -> blocked_by must sort.
        mock_items.return_value = self._items((1, "P0"), (2, "P2"), (3, "P2"))
        mock_edges.return_value = ({}, {(1, 3), (1, 2)}, {})
        assert state.order(_IDENT, json=True) == 0
        payload = json.loads(capsys.readouterr().out)
        dependent = next(o for o in payload["order"] if o["number"] == 1)
        assert dependent["blocked_by"] == [2, 3]


# ── status ─────────────────────────────────────────────────────────────────


class TestStatus:
    @patch.object(state.board, "get_project_id", return_value="PID")
    @patch.object(state.board, "get_project_fields", return_value=[])
    @patch.object(state.board, "get_project_items", return_value=[{"id": "I5", "content": {"number": 5}}])
    @patch.object(state.board, "set_field")
    def test_sets_status_field(self, mock_set, mock_items, mock_fields, mock_pid):
        assert state.status(_IDENT, issue_number=5, value="Done") == 0
        args = mock_set.call_args[0]
        assert args[3] == "Status" and args[4] == "Done"

    @patch.object(state.board, "get_project_id", return_value="PID")
    @patch.object(state.board, "get_project_fields", return_value=[])
    @patch.object(state.board, "get_project_items", return_value=[])
    @patch.object(state.board, "set_field")
    def test_missing_item_warns(self, mock_set, mock_items, mock_fields, mock_pid, capsys):
        assert state.status(_IDENT, issue_number=5, value="Done") == 0
        mock_set.assert_not_called()
        assert "not found in project" in capsys.readouterr().err


# ── delete ─────────────────────────────────────────────────────────────────


class TestDelete:
    @patch.object(state.board, "get_project_items", return_value=[{"id": "I5", "content": {"number": 5}}])
    @patch.object(state, "_remove_from_project")
    @patch.object(state.gh, "delete_issue")
    def test_removes_and_deletes(self, mock_del, mock_remove, mock_items):
        assert state.delete(_IDENT, issue_number=5, keep_issue=False) == 0
        mock_remove.assert_called_once()
        mock_del.assert_called_once()

    @patch.object(state.board, "get_project_items", return_value=[{"id": "I5", "content": {"number": 5}}])
    @patch.object(state, "_remove_from_project")
    @patch.object(state.gh, "delete_issue")
    def test_keep_issue_skips_delete(self, mock_del, mock_remove, mock_items):
        assert state.delete(_IDENT, issue_number=5, keep_issue=True) == 0
        mock_remove.assert_called_once()
        mock_del.assert_not_called()

    @patch.object(state.board, "get_project_items", return_value=[])
    @patch.object(state, "_remove_from_project")
    @patch.object(state.gh, "delete_issue")
    def test_not_in_project_still_deletes_issue(self, mock_del, mock_remove, mock_items):
        assert state.delete(_IDENT, issue_number=5, keep_issue=False) == 0
        mock_remove.assert_not_called()
        mock_del.assert_called_once()


# ── delete-all ─────────────────────────────────────────────────────────────


class TestDeleteAll:
    _ISSUES = [{"title": "Story X", "number": 5}, {"title": "Story Y", "number": 6}]

    @patch.object(state.backlog, "load_flat_data", return_value=([], {}, {"stories": []}))
    @patch.object(state, "_project_issues", return_value=_ISSUES)
    @patch.object(state, "_perform_delete")
    def test_dry_run_lists_without_deleting(self, mock_perform, mock_issues, mock_load, capsys):
        assert state.delete_all(_IDENT, "b.json", dry_run=True) == 0
        mock_perform.assert_not_called()
        assert "Would delete #5" in capsys.readouterr().out

    @patch.object(state.backlog, "load_flat_data", return_value=([], {}, {"stories": []}))
    @patch.object(state, "_project_issues", return_value=_ISSUES)
    @patch.object(state, "_perform_delete")
    def test_real_run_performs_delete(self, mock_perform, mock_issues, mock_load):
        assert state.delete_all(_IDENT, "b.json", dry_run=False) == 0
        mock_perform.assert_called_once()

    @patch.object(state.backlog, "load_flat_data", return_value=([], {}, {"stories": []}))
    @patch.object(state, "_project_issues", return_value=[])
    @patch.object(state, "_perform_delete")
    def test_no_issues_returns_zero(self, mock_perform, mock_issues, mock_load, capsys):
        assert state.delete_all(_IDENT, "b.json") == 0
        mock_perform.assert_not_called()
        assert "No issues found" in capsys.readouterr().out
