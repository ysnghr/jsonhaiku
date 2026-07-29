"""Tests for CLI streaming flags (--stream, --memory-budget, --seed)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jsonhaiku.cli import _AUTO_STREAM_THRESHOLD, _should_auto_stream, main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def array_file(tmp_path: Path) -> Path:
    path = tmp_path / "data.json"
    records = [{"id": i, "name": f"item-{i}"} for i in range(20)]
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


class TestStreamFlag:
    def test_stream_mode_produces_output(
        self, array_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["--stream", str(array_file)])
        assert rc == 0
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_stream_with_seed(self, array_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--stream", "--seed", "42", str(array_file)])
        assert rc == 0
        out1 = capsys.readouterr().out

        rc = main(["--stream", "--seed", "42", str(array_file)])
        assert rc == 0
        out2 = capsys.readouterr().out

        assert out1 == out2

    def test_stream_with_memory_budget(
        self, array_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["--stream", "--memory-budget", "100", str(array_file)])
        assert rc == 0
        assert len(capsys.readouterr().out.strip()) > 0

    def test_stream_bad_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--stream", "/nonexistent/file.json"])
        assert rc == 1
        assert "cannot read" in capsys.readouterr().err

    def test_stream_single_object(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "obj.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        rc = main(["--stream", str(path)])
        assert rc == 0
        assert len(capsys.readouterr().out.strip()) > 0


class TestAutoStream:
    def test_small_file_no_auto_stream(self, array_file: Path) -> None:
        assert not _should_auto_stream(str(array_file))

    def test_stdin_no_auto_stream(self) -> None:
        assert not _should_auto_stream("-")

    def test_nonexistent_file_no_auto_stream(self) -> None:
        assert not _should_auto_stream("/nonexistent/file.json")

    def test_threshold_value(self) -> None:
        assert _AUTO_STREAM_THRESHOLD == 100 * 1024 * 1024
