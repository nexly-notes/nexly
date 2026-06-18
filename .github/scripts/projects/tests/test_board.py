"""Tests for projects.board — Projects v2 field model. Mocks the gh client."""
from __future__ import annotations

from unittest.mock import patch

from projects import board


_FIELD_MAP = {
    "Status": {"id": "FS", "options": {"Backlog": "OS_B", "In Progress": "OS_IP", "Done": "OS_D"}},
    "Priority": {"id": "FP", "options": {"P0": "OP0", "P1": "OP1", "P2": "OP2"}},
    "Size": {"id": "FSZ", "options": {"XS": "Z0", "S": "Z1", "M": "Z2", "L": "Z3", "XL": "Z4"}},
    "Points": {"id": "FPT", "type": "NUMBER"},
}


# ── Field specs ────────────────────────────────────────────────────────────


class TestFieldSpecs:
    def test_convert_fields(self):
        names = [n for n, _, _ in board.CONVERT_FIELDS]
        assert names == ["Status", "Priority", "Size", "Points"]

    def test_size_options(self):
        size_opts = next(o for n, _, o in board.CONVERT_FIELDS if n == "Size")
        assert size_opts == ["XS", "S", "M", "L", "XL"]

    def test_points_is_number_field(self):
        ptype = next(t for n, t, _ in board.CONVERT_FIELDS if n == "Points")
        assert ptype == "NUMBER"


# ── field-map / item lookup ────────────────────────────────────────────────


class TestBuildFieldMap:
    def test_basic(self):
        fmap = board.build_field_map([{"id": "F1", "name": "Status", "type": "TEXT"}])
        assert fmap["Status"]["id"] == "F1"

    def test_with_options(self):
        fields = [{
            "id": "F1", "name": "Status", "type": "SINGLE_SELECT",
            "options": [{"id": "O1", "name": "Done"}, {"id": "O2", "name": "Backlog"}],
        }]
        assert board.build_field_map(fields)["Status"]["options"] == {"Done": "O1", "Backlog": "O2"}

    def test_empty(self):
        assert board.build_field_map([]) == {}


class TestFindItemId:
    def test_found(self):
        items = [{"id": "I1", "content": {"number": 1}}, {"id": "I2", "content": {"number": 2}}]
        assert board.find_item_id(items, 2) == "I2"

    def test_not_found(self):
        assert board.find_item_id([{"id": "I1", "content": {"number": 1}}], 99) is None


# ── GraphQL field-value builders ───────────────────────────────────────────


class TestBuildFieldValue:
    def test_single_select(self):
        assert board.build_field_value(_FIELD_MAP, "Status", "Done") == {"singleSelectOptionId": '"OS_D"'}

    def test_single_select_invalid(self, capsys):
        assert board.build_field_value(_FIELD_MAP, "Status", "Nope") is None
        assert "not found" in capsys.readouterr().err

    def test_number(self):
        assert board.build_field_value(_FIELD_MAP, "Points", 5) == {"number": "5"}

    def test_text(self):
        assert board.build_field_value({"Notes": {"id": "F"}}, "Notes", "hi") == {"text": '"hi"'}

    def test_none_value(self):
        assert board.build_field_value(_FIELD_MAP, "Status", None) is None

    def test_field_not_found(self):
        assert board.build_field_value({}, "Missing", "x") is None


class TestMutationForField:
    def test_builds_alias(self):
        m = board.mutation_for_field("PID", "ITEM", "FS", {"singleSelectOptionId": '"O1"'}, 0)
        assert m.startswith("m0: updateProjectV2ItemFieldValue")
        assert "O1" in m


# ── set_field (CLI item-edit) ──────────────────────────────────────────────


class TestSetField:
    @patch.object(board.gh, "run")
    def test_single_select(self, mock_run):
        board.set_field("PID", "ITEM", _FIELD_MAP, "Status", "Done")
        cmd = mock_run.call_args[0][0]
        assert "--single-select-option-id" in cmd and "OS_D" in cmd

    @patch.object(board.gh, "run")
    def test_number(self, mock_run):
        board.set_field("PID", "ITEM", _FIELD_MAP, "Points", 8)
        cmd = mock_run.call_args[0][0]
        assert "--number" in cmd and "8" in cmd

    def test_none_value(self):
        board.set_field("PID", "ITEM", {}, "Status", None)

    def test_field_not_found(self, capsys):
        board.set_field("PID", "ITEM", {}, "Missing", "val")
        assert "not found" in capsys.readouterr().err


# ── ensure_project_field ───────────────────────────────────────────────────


class TestEnsureProjectField:
    @patch.object(board, "_create_single_select_field")
    def test_creates_single_select_when_missing(self, mock_create):
        assert board.ensure_project_field("PID", "Size", "SINGLE_SELECT", {}, ["XS", "S"]) is True
        mock_create.assert_called_once()

    @patch.object(board, "_create_simple_field")
    def test_creates_number_when_missing(self, mock_create):
        assert board.ensure_project_field("PID", "Points", "NUMBER", {}) is True
        mock_create.assert_called_once_with("PID", "Points", "NUMBER")

    @patch.object(board, "_create_single_select_field")
    def test_skips_when_present(self, mock_create):
        assert board.ensure_project_field("PID", "Status", "SINGLE_SELECT", _FIELD_MAP, ["x"]) is False
        mock_create.assert_not_called()


# ── Remote value snapshot ──────────────────────────────────────────────────


class TestExtractItemFieldValues:
    def test_all_canonical_fields(self):
        result = board.extract_item_field_values({
            "id": "X", "status": "In Progress", "priority": "P0",
            "size": "M", "points": 5,
        })
        assert result == {
            "Status": "In Progress", "Priority": "P0", "Size": "M", "Points": 5,
        }

    def test_missing_excluded(self):
        result = board.extract_item_field_values({"id": "X", "status": "Backlog"})
        assert result == {"Status": "Backlog"}

    def test_empty(self):
        assert board.extract_item_field_values({"id": "X"}) == {}


class TestBuildRemoteValuesMap:
    def test_builds_map(self):
        items = [{"id": "I1", "status": "In Progress", "priority": "P0"}, {"id": "I2", "priority": "P1"}]
        result = board.build_remote_values_map(items)
        assert result["I1"] == {"Status": "In Progress", "Priority": "P0"}
        assert result["I2"] == {"Priority": "P1"}

    def test_skips_items_without_id(self):
        assert board.build_remote_values_map([{"status": "Backlog"}]) == {}


class TestShouldSkipField:
    def test_skips_when_match(self):
        assert board.should_skip_field("Status", "Backlog", {"Status": "Backlog"}) is True

    def test_no_skip_when_differs(self):
        assert board.should_skip_field("Status", "Done", {"Status": "Backlog"}) is False

    def test_no_skip_when_absent(self):
        assert board.should_skip_field("Status", "Done", {}) is False


# ── Project metadata (mock gh) ─────────────────────────────────────────────


class TestProjectMetadata:
    @patch.object(board.gh, "gh_json", return_value={"data": {"user": {"projectV2": {"id": "PID"}}}})
    def test_get_project_id(self, mock_gh):
        assert board.get_project_id(1, "me") == "PID"

    @patch.object(board.gh, "gh_json", return_value={"fields": [{"id": "F1", "name": "Status"}]})
    def test_get_project_fields(self, mock_gh):
        assert board.get_project_fields(1, "me") == [{"id": "F1", "name": "Status"}]

    @patch.object(board.gh, "gh_json", return_value={"items": [{"id": "I1"}]})
    def test_get_project_items(self, mock_gh):
        assert board.get_project_items(1, "me") == [{"id": "I1"}]
