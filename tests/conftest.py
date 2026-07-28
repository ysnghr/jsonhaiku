"""Shared pytest configuration and fixtures.

Kept deliberately thin for now. Payload fixtures arrive with the first real
inference tests; this file exists so there is one obvious place to put them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_json_file(tmp_path: Path) -> Path:
    """Return a path inside a per-test temp dir for writing JSON fixtures to."""
    return tmp_path / "payload.json"
