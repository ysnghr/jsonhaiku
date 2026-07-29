"""Tests for the command line interface."""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest

from jsonhaiku import __version__
from jsonhaiku.cli import main

if TYPE_CHECKING:
    from pathlib import Path

PAYLOAD = '[{"id": 1, "name": "a"}, {"id": 2, "name": null}]'
EXPECTED_COMPACT = '[{\n  "id": "integer",\n  "name": "string | null"\n}]'


@pytest.fixture
def stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed ``PAYLOAD`` to the CLI on standard input."""
    monkeypatch.setattr("sys.stdin", io.StringIO(PAYLOAD))


class TestReadingInput:
    @pytest.mark.usefixtures("stdin")
    def test_reads_standard_input_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([]) == 0
        assert capsys.readouterr().out == EXPECTED_COMPACT + "\n"

    @pytest.mark.usefixtures("stdin")
    def test_reads_standard_input_for_an_explicit_dash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["-"]) == 0
        assert capsys.readouterr().out.strip() == EXPECTED_COMPACT

    def test_reads_a_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "payload.json"
        path.write_text(PAYLOAD, encoding="utf-8")
        assert main([str(path)]) == 0
        assert capsys.readouterr().out.strip() == EXPECTED_COMPACT

    def test_reads_utf8_content(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "payload.json"
        path.write_text('{"kategori": "müzik"}', encoding="utf-8")
        assert main([str(path)]) == 0
        assert "kategori" in capsys.readouterr().out


@pytest.mark.usefixtures("stdin")
class TestFormats:
    def test_compact_is_the_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        main([])
        assert capsys.readouterr().out.startswith("[{")

    def test_schema_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "schema"]) == 0
        document = json.loads(capsys.readouterr().out)
        assert document["type"] == "array"
        assert document["items"]["required"] == ["id", "name"]

    def test_tree_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "tree"]) == 0
        assert json.loads(capsys.readouterr().out)["kind"] == "array"

    def test_indent_is_configurable(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["-f", "tree", "--indent", "0"]) == 0
        assert '\n"kind"' in capsys.readouterr().out

    def test_typescript_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "typescript"]) == 0
        out = capsys.readouterr().out
        assert "interface" in out or "type" in out

    def test_yaml_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "yaml"]) == 0
        out = capsys.readouterr().out
        assert "integer" in out

    def test_json_schema_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "json_schema"]) == 0
        document = json.loads(capsys.readouterr().out)
        assert "$schema" in document

    def test_typescript_with_root_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--format", "typescript", "--root-name", "Session"]) == 0
        out = capsys.readouterr().out
        assert "Session" in out

    def test_detect_content_types_flag(self) -> None:
        assert main(["--detect-content-types"]) == 0

    def test_max_depth_flag(self) -> None:
        assert main(["--max-depth", "1"]) == 0

    def test_track_cardinality_flag(self) -> None:
        assert main(["--track-cardinality"]) == 0

    def test_include_frequency_flag(self) -> None:
        assert main(["--track-cardinality", "--include-frequency"]) == 0

    def test_no_stats_flag(self) -> None:
        assert main(["--track-cardinality", "--no-stats"]) == 0


class TestFailures:
    def test_invalid_json_reports_and_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
        assert main([]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "invalid JSON" in captured.err

    def test_missing_file_reports_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main([str(tmp_path / "nope.json")]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_unknown_format_is_a_usage_error(self) -> None:
        with pytest.raises(SystemExit) as exit_info:
            main(["--format", "nope"])
        assert exit_info.value.code == 2


@pytest.mark.usefixtures("stdin")
class TestSamples:
    def test_samples_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--samples", "2"]) == 0
        out = capsys.readouterr().out
        assert "// Samples:" in out
        assert "// [0]" in out
        assert "// [1]" in out

    def test_redact_samples_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--samples", "1", "--redact-samples"]) == 0
        out = capsys.readouterr().out
        assert "// Samples:" in out

    def test_no_samples_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([]) == 0
        out = capsys.readouterr().out
        assert "// Samples:" not in out


class TestVersion:
    def test_reports_the_package_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            main(["--version"])
        assert exit_info.value.code == 0
        assert capsys.readouterr().out.strip() == f"jsonhaiku {__version__}"
