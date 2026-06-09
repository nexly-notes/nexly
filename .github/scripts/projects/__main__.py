"""Enable ``python -m projects <command> …`` from ``.github/scripts/``."""
from __future__ import annotations

from projects.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
