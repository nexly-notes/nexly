"""Pytest configuration for project_manager tests.

Registers the ``e2e`` marker and auto-skips e2e tests unless explicitly
selected with ``pytest -m e2e``.
"""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "e2e: live end-to-end test against real GitHub "
        "(destructive; opt-in via `pytest -m e2e`)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    markexpr = config.getoption("markexpr", default="") or ""
    if "e2e" in markexpr:
        return
    skip = pytest.mark.skip(reason="e2e test; run with `pytest -m e2e`")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
