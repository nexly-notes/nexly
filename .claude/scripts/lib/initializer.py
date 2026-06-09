#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from project_manager.manager import ProjectManager  # type: ignore

DECISIONS_FILE_PATH = Path.cwd() / "claude-3PO" / "docs" / "decisions.md"


def init_implement_state(
    session_id: str, workflow_type: str, tdd: bool, story_id: str
) -> dict:

    return {
        "session_id": session_id,
        "workflow_active": True,
        "workflow_type": workflow_type,
        "status": "in_progress",
        "tdd": tdd,
        "story_id": story_id,
        "phases": [],
        "file_paths": [],
        "reviews": {
            "plan": [],
            "tests": [],
            "code": [],
            "security": [],
            "requirements": [],
        },
    }


def get_questions() -> list[str]:
    content = DECISIONS_FILE_PATH.read_text()
    return content.split("\n")


def init_specs_state(session_id: str, workflow_type: str) -> dict:
    return {
        "session_id": session_id,
        "workflow_active": True,
        "workflow_type": workflow_type,
        "status": "in_progress",
        "phases": [],
        "questions": get_questions(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_type", type=str)
    parser.add_argument("session_id", type=str)
    parser.add_argument("--tdd", action="store_true")
    parser.add_argument("--story-id", type=str)
    args = parser.parse_args()

    if args.workflow_type == "implement":
        init_implement_state(
            args.session_id, args.workflow_type, args.tdd, args.story_id
        )
    elif args.workflow_type == "specs":
        init_specs_state(args.session_id, args.workflow_type)


if __name__ == "__main__":
    main()
