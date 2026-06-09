import json
from pathlib import Path
from typing import Any


class Config:

    def __init__(self, config_path: Path | None = None):

        self._path = config_path or Path(__file__).parent / "config.json"
        with open(self._path, "r") as f:
            self._data: dict[str, Any] = json.load(f)
        self._phase_list: list[dict] = self._data.get("phases", [])
        self._phase_map: dict[str, dict] = {p["name"]: p for p in self._phase_list}

    # ── Phase queries by workflow ─────────────────────────────────

    def get_phases_by_workflow(self, workflow_type: str) -> list[dict[str, Any]]:

        return [p for p in self._phase_list if workflow_type in p.get("workflows", [])]

    def get_phase_names_by_workflow(self, workflow_type: str) -> list[str]:

        return [p["name"] for p in self.get_phases_by_workflow(workflow_type)]

    def get_phases_order(self, workflow_type: str) -> list[str]:

        return self._data.get("phases_order", {}).get(workflow_type, [])

    # ── Mode queries ──────────────────────────────────────────────

    def get_mode(self, phase_name: str) -> str | None:

        return self._phase_map.get(phase_name, {}).get("mode")

    def get_phases_by_mode(
        self, mode_type: str, names_only: bool = False
    ) -> list[dict[str, Any]] | list[str]:

        phases = [p for p in self._phase_list if self._mode_matches(p, mode_type)]
        return [p["name"] for p in phases] if names_only else phases

    @staticmethod
    def _mode_matches(phase: dict[str, Any], mode_type: str) -> bool:

        mode = phase.get("mode")
        if mode_type == "read-only":
            return mode in (None, "read-only")
        return mode == mode_type

    # ── Agent queries (singular schema in JSON) ───────────────────

    def get_agent(self, phase_name: str) -> str | None:

        return self._phase_map.get(phase_name, {}).get("agent")

    def get_agent_count(self, phase_name: str) -> int:

        return self._phase_map.get(phase_name, {}).get("agent_count", 1)

    # ── Flag-based phase lists ────────────────────────────────────

    def get_parallel_with(self, phase_name: str) -> list[str]:

        return self._phase_map.get(phase_name, {}).get("parallel_with", [])

    def get_checkpoint_phases(self) -> list[str]:

        return [p["name"] for p in self._phase_list if p.get("checkpoint")]

    def get_auto_phases(self) -> list[str]:

        return [p["name"] for p in self._phase_list if p.get("auto")]

    # ── Score thresholds ──────────────────────────────────────────

    def get_score_threshold(self, phase: str, score_type: str) -> int:

        thresholds = self._data.get("review_score_thresholds", {})
        return thresholds.get(phase, {}).get(score_type, 0)

    # ── Safe domains ──────────────────────────────────────────────

    @property
    def safe_domains(self) -> list[str]:

        return self._data.get("safe_domains", [])

    # ── Paths and dirs ────────────────────────────────────────────

    def get_file_path(self, query: str) -> str:

        return self._data.get("file_paths", {}).get(query, "")

    def get_dir(self, query: str) -> str:

        return self._data.get("dirs", {}).get(query, "")

    # ── Linter queries ──────────────────────────────────────────────

    def get_linter(self) -> str:

        return self._data.get("linter", "ruff")

    def get_formatter(self) -> str:

        return self._data.get("formatter", "black")

    def get_tech_stack(self) -> list[str]:

        return self._data.get("tech_stack", [])
