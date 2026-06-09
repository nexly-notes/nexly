"""project_manager package: local backlog management + GitHub Projects sync."""
from __future__ import annotations

from .manager import ProjectManager
from .sync import Syncer

__all__ = ["ProjectManager", "Syncer"]
