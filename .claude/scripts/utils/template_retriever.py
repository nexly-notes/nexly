import json
from pathlib import Path
from typing_extensions import Literal


DEFAULT_TEMPLATE_DIR = Path.cwd() / "claude-3PO" / "templates"


def build_template_path(template_name: str) -> Path:
    return DEFAULT_TEMPLATE_DIR / f"{template_name}.md"


def retrieve_template(template_name: str) -> str:
    with open(build_template_path(template_name), "r") as file:
        return file.read()
