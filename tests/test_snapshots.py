"""Snapshot tests over a realistic payload.

These are the regression net for every later phase: enum detection, statistics
and sampling will all change what jsonhaiku emits for this fixture, and each of
those changes should be a deliberate, reviewed snapshot diff rather than a
surprise.

Update with ``pytest --snapshot-update`` and *read the diff* — it is exactly
what a language model would see.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from jsonhaiku import Config, describe

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sessions() -> list[object]:
    """Load the anonymised conference-schedule fixture."""
    payload: list[object] = json.loads(
        (FIXTURES / "conference_sessions.json").read_text(encoding="utf-8")
    )
    return payload


def test_compact(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).compact == snapshot


def test_schema(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).schema == snapshot


def test_tree(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).tree == snapshot


def test_typescript(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).typescript() == snapshot


def test_yaml(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).yaml == snapshot


def test_json_schema(sessions: list[object], snapshot: SnapshotAssertion) -> None:
    assert describe(sessions).json_schema == snapshot


def test_compact_with_content_types(
    sessions: list[object], snapshot: SnapshotAssertion,
) -> None:
    cfg = Config(detect_content_types=True)
    assert describe(sessions, config=cfg).compact == snapshot


def test_description_size_does_not_grow_with_the_payload(sessions: list[object]) -> None:
    """The whole point: description size tracks the *shape*, not the record count.

    Twenty times the records, byte-identical description — which is where the
    savings come from on a real API response.
    """
    small = describe(sessions)
    large = describe(sessions * 20)
    assert large.compact == small.compact

    raw = json.dumps(sessions * 20, separators=(",", ":"))
    assert len(raw) / len(large.compact) > 50
