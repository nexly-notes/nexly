import json
from pathlib import Path
from typing import Any, Callable, Literal


from filelock import BaseFileLock, FileLock

Status = Literal["not_started", "in_progress", "completed", "skipped"]
Verdict = Literal["pass", "fail"]
ReviewType = Literal["plan", "tests", "code", "security", "requirements"]


class StateFileManager:

    def __init__(self, path: Path):
        # Sibling `.lock` file serializes cross-process writes.
        self._path = path
        self._lock = FileLock(path.with_suffix(".lock"))

    @property
    def lock(self) -> BaseFileLock:
        return self._lock

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> dict[str, Any] | None:

        # Missing file is a valid empty state — no error.
        if not self._path.exists():
            return None
        content = self._path.read_text(encoding="utf-8").strip()
        # Empty file is also a valid empty state.
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Corrupt file → treat as absent; a rewrite will overwrite it.
            return None

    def write(self, data: dict[str, Any]) -> None:

        # Ensure the target directory exists before writing.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Compact JSON — single line, no pretty-print indent.
        self._path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    def read_jsonl(self) -> list[dict[str, Any]] | None:

        # Missing file is a valid empty state — no error.
        if not self._path.exists():
            return None
        content = self._path.read_text(encoding="utf-8").strip()
        # Empty file is also a valid empty state.
        if not content:
            return None
        try:
            return [json.loads(line) for line in content.splitlines()]
        except json.JSONDecodeError:
            # Corrupt file → treat as absent; a rewrite will overwrite it.
            return None

    def write_jsonl(self, data: list[dict[str, Any]]) -> None:

        # Ensure the target directory exists before writing.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write JSONL — one JSON object per line.
        self._path.write_text(
            "\n".join(json.dumps(item, separators=(",", ":")) for item in data),
            encoding="utf-8",
        )


class StateStore:

    def __init__(
        self,
        session_id: str,
        state_path: Path | None = None,
        default_state: dict[str, Any] | None = None,
        default_state_jsonl: list[dict[str, Any]] | None = None,
    ):
        # Resolve path lazily so cwd is read at construction, not import.
        path = (
            state_path
            if state_path is not None
            else Path.cwd() / "claude-3PO" / "scripts" / "state.jsonl"
        )
        # Compose the file manager — all raw IO and locking lives there.
        self._fm = StateFileManager(path)
        # `or {}` keeps the attribute as a real dict even when caller passed None.
        self._default_state = default_state or {}
        self._default_state_jsonl = default_state_jsonl or []
        self._session_id = session_id

    # ── Core I/O ──────────────────────────────────────────────────

    def _update_jsonl(self, fn: Callable[[list[dict[str, Any]]], None]) -> None:

        with self._fm.lock:
            data = self._fm.read_jsonl()
            # Nothing persisted → start with empty list before the mutator runs.
            if data is None:
                data = []
            before = "\n".join(json.dumps(item, separators=(",", ":")) for item in data)
            fn(data)
            after = "\n".join(json.dumps(item, separators=(",", ":")) for item in data)
            # No-op writes are skipped only if the file is already on disk.
            if before == after and self._fm.exists():
                return
            self._fm.write_jsonl(data)

    def load_jsonl(self) -> list[dict[str, Any]]:

        with self._fm.lock:
            data = self._fm.read_jsonl()
            # Nothing persisted → hand back a copy of the default.
            if data is None:
                return list(self._default_state_jsonl)
            return data

    def save_jsonl(self, data: list[dict[str, Any]] | None = None) -> None:

        with self._fm.lock:
            data_to_write = data if data is not None else []
            self._fm.write_jsonl(data_to_write)

    def load_by_session_id(
        self, session_id: str | None = None
    ) -> dict[str, Any] | None:

        # Fall back to the id this store was constructed with.
        target = session_id if session_id is not None else self._session_id
        # load_jsonl already takes the lock and returns a defaulted list.
        rows = self.load_jsonl()
        return next((row for row in rows if row.get("session_id") == target), None)

    def _seed_default(self) -> dict[str, Any]:

        # Default state always carries the constructor session_id as identity.
        return dict(self._default_state) | {"session_id": self._session_id}

    def _find_row_index(self, rows: list[dict[str, Any]]) -> int | None:

        # Locate this store's row in the JSONL list, or None if not yet seeded.
        return next(
            (i for i, r in enumerate(rows) if r.get("session_id") == self._session_id),
            None,
        )

    def load(self) -> dict[str, Any]:

        # JSONL lookup by session_id; fall back to a freshly seeded default row.
        with self._fm.lock:
            rows = self._fm.read_jsonl() or []
            idx = self._find_row_index(rows)
            return rows[idx] if idx is not None else self._seed_default()

    def save(self, state: dict[str, Any] | None = None) -> None:

        # Upsert one row keyed by session_id; identity always wins over payload.
        payload = dict(state) if state is not None else {}
        payload["session_id"] = self._session_id

        def _upsert(rows: list[dict[str, Any]]) -> None:
            idx = self._find_row_index(rows)
            if idx is None:
                rows.append(payload)
            else:
                rows[idx] = payload

        self._update_jsonl(_upsert)

    def update(self, fn: Callable[[dict[str, Any]], None]) -> None:

        # Read-modify-write a single row, guarding identity from the mutator.
        def _row_update(rows: list[dict[str, Any]]) -> None:
            idx = self._find_row_index(rows)
            if idx is None:
                rows.append(self._seed_default())
                idx = len(rows) - 1
            row = rows[idx]
            fn(row)
            if row.get("session_id") != self._session_id:
                raise ValueError(
                    "update(): mutator changed session_id; identity is immutable."
                )

        self._update_jsonl(_row_update)

    def init(self) -> None:

        # Seed a fresh default row for this session — upserts if one exists.
        self.save(self._seed_default())

    @property
    def state(self) -> dict[str, Any]:
        return self.load()

    @property
    def session_id(self) -> str:
        # Identity is owned by the store, not the persisted row.
        return self._session_id

    @property
    def workflow_active(self) -> bool:
        return self.state.get("workflow_active", False)

    @property
    def workflow_status(self) -> str:
        return self.state.get("status", "")

    @property
    def workflow_type(self) -> str:
        return self.state.get("workflow_type", "")

    @property
    def test_mode(self) -> str:
        return self.state.get("test_mode", "")

    @property
    def story_id(self) -> str:
        return self.state.get("story_id", "")

    def set(self, key: str, value: Any) -> None:

        def _set(d: dict[str, Any]) -> None:
            d[key] = value

        self.update(_set)

    def set_workflow_active(self, workflow_active: bool) -> None:
        self.set("workflow_active", workflow_active)

    def set_workflow_type(self, workflow_type: str) -> None:
        self.set("workflow_type", workflow_type)

    def set_workflow_status(self, workflow_status: str) -> None:
        self.set("workflow_status", workflow_status)

    def set_story_id(self, story_id: str) -> None:
        self.set("story_id", story_id)

    def set_test_mode(self, test_mode: str) -> None:
        self.set("test_mode", test_mode)

    # ── TDD ───────────────────────────────────────────────────────

    @property
    def tdd(self) -> bool:
        return self.state.get("tdd", False)

    def set_tdd(self, tdd: bool) -> None:
        self.set("tdd", tdd)

    # ── File paths ────────────────────────────────────────────────

    @property
    def file_paths(self) -> list[str]:
        return self.state.get("file_paths", [])

    def add_file_path(self, path: str) -> None:

        def _add(d: dict[str, Any]) -> None:
            d["file_paths"].append(path)

        self.update(_add)

    def set_file_paths(self, paths: list[str]) -> None:
        def _set(d: dict[str, Any]) -> None:
            d["file_paths"] = paths

        self.update(_set)

    def is_file_path_in_scope(self, path: str) -> bool:

        return any(fp == path for fp in self.file_paths)

    # ── Reviews ───────────────────────────────────────────────────
    # Schema: reviews[review_type] = {iteration_left, status, verdict, history: [..]}

    @property
    def reviews(self) -> dict[ReviewType, list[dict[str, Any]]]:
        return self.state.get("reviews", {})

    def get_reviews(self, review_type: ReviewType) -> list[dict[str, Any]]:

        # `history` is the per-type list of review attempts.
        return self.reviews.get(review_type, [])

    def add_review(
        self,
        review_type: ReviewType,
        confidence_score: int,
        quality_score: int,
        status: Status,
        verdict: Verdict,
    ) -> None:

        def _add(d: dict[str, Any]) -> None:
            reviews = self.get_reviews(review_type)
            reviews.append(
                {
                    "confidence_score": confidence_score,
                    "quality_score": quality_score,
                    "status": status,
                    "verdict": verdict,
                }
            )

        self.update(_add)

    def update_review(
        self,
        review_type: ReviewType,
        iteration_left: int,
        status: Status,
        verdict: Verdict,
    ) -> None:

        def _update(d: dict[str, Any]) -> None:
            reviews = self.get_reviews(review_type)
            if not reviews:
                return
            review = reviews[-1]
            review["iteration_left"] = iteration_left
            review["status"] = status
            review["verdict"] = verdict

        self.update(_update)

    def get_review_iteration_left(self, review_type: ReviewType) -> int:

        reviews = self.get_reviews(review_type)
        if not reviews:
            return 3
        return reviews[-1]["iteration_left"]

    def all_reviews_passed(self, review_type: ReviewType) -> bool:

        reviews = self.get_reviews(review_type)
        # Empty reviews shouldn't count as "all passed".
        return bool(reviews) and all(r["verdict"] == "pass" for r in reviews)

    # ── Phases ────────────────────────────────────────────────────

    @property
    def phases(self) -> list[dict[str, Any]]:
        return self.state.get("phases", [])

    def add_phase(self, name: str, status: Status) -> None:

        def _add(d: dict[str, Any]) -> None:
            d["phases"].append({"name": name, "status": status})

        self.update(_add)

    @property
    def active_phases(self) -> list[dict[str, Any]]:

        return [s for s in self.phases if s["status"] == "in_progress"]

    @property
    def current_phases(self) -> list[dict[str, Any]]:

        # Prefer in-progress; otherwise fall back to the most recent completed.
        active = self.active_phases
        if active:
            return active
        completed = self.completed_phases
        return [completed[-1]] if completed else []

    @property
    def current_phase(self) -> str | None:
        phases = self.phases
        if not phases:
            return None
        return phases[-1]["name"]

    @property
    def current_phases_names(self) -> list[str]:
        return [s["name"] for s in self.current_phases]

    @property
    def completed_phases(self) -> list[dict[str, Any]]:

        return [s for s in self.phases if s["status"] == "completed"]

    @property
    def completed_phases_names(self) -> list[str]:
        return [s["name"] for s in self.completed_phases]

    @property
    def last_completed_phase(self) -> str | None:
        completed = self.completed_phases
        if not completed:
            return None
        return completed[-1]["name"]

    def get_phase_by_status(self, status: Status) -> dict[str, Any] | None:

        return next((s for s in self.phases if s["status"] == status), None)

    def update_phase_status(self, name: str, status: Status) -> None:

        def _update(d: dict[str, Any]) -> None:
            # phases is a list of {name, status} — find by name, then mutate.
            for phase in d.get("phases", []):
                if phase["name"] == name:
                    phase["status"] = status
                    return

        self.update(_update)

    def any_active_phase(self) -> bool:

        return any(phase["status"] == "in_progress" for phase in self.phases)

    def all_phases_completed(self) -> bool:

        return all(phase["status"] == "completed" for phase in self.phases)

    # ── Agents ────────────────────────────────────────────────────

    @property
    def agents(self) -> list[dict[str, Any]]:
        return self.state.get("agents", [])

    def add_agent(self, name: str, status: Status) -> None:

        def _add(d: dict[str, Any]) -> None:
            d["agents"].append({"name": name, "status": status})

        self.update(_add)

    def get_agents_by_status(self, status: Status) -> list[dict[str, Any]]:

        return [a for a in self.agents if a["status"] == status]

    def is_agent_in_progress(self, name: str) -> bool:

        return any(
            agent["name"] == name
            for agent in self.get_agents_by_status(status="in_progress")
        )

    def is_agent_completed(self, agent_name: str) -> bool:

        # any() guards against the all([])-returns-True trap on missing agents.
        return any(
            agent["name"] == agent_name
            for agent in self.get_agents_by_status(status="completed")
        )

    def get_agent_status(self, name: str) -> Status | None:

        agent = next((a for a in self.agents if a["name"] == name), None)
        return agent["status"] if agent else None

    def get_agents_count(self, name: str, status: Status | None = None) -> int:

        if status is None:
            return len([agent for agent in self.agents if agent["name"] == name])
        return len(
            [
                agent
                for agent in self.agents
                if agent["name"] == name and agent["status"] == status
            ]
        )

    # ── Tests status ──────────────────────────────────────────────

    @property
    def tests_status(self) -> Verdict:
        return self.state.get("tests_status", "")

    def update_tests_status(self, status: Verdict) -> None:

        def _update(d: dict[str, Any]) -> None:
            d["tests_status"] = status

        self.update(_update)
