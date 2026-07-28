"""Command line interface: ``jsonhaiku [FILE]``.

Reads JSON from a file or standard input and writes a description to standard
output, so the library is one pipe away from any shell::

    curl -s https://api.example.com/sessions | jsonhaiku
    jsonhaiku response.json --format schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jsonhaiku.__about__ import __version__
from jsonhaiku.core import describe

if TYPE_CHECKING:
    from collections.abc import Sequence

    from jsonhaiku.result import Result

__all__ = ["main"]

STDIN_ARGUMENT = "-"
"""The conventional filename meaning "read standard input"."""

EXIT_OK = 0
EXIT_BAD_INPUT = 1
DEFAULT_INDENT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: Command line arguments, excluding the program name. Defaults to
            :data:`sys.argv`.

    Returns:
        A process exit status: ``0`` on success, ``1`` if the input could not be
        read or parsed. Usage errors exit with ``2`` via argparse.
    """
    args = _build_parser().parse_args(argv)

    try:
        payload = _read(args.file)
    except OSError as error:
        return _fail(f"cannot read {args.file}: {error.strerror or error}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        return _fail(f"invalid JSON: {error}")

    print(_render(describe(data), args.format, args.indent))
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="jsonhaiku",
        description="Describe a JSON payload compactly, for humans and language models.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=STDIN_ARGUMENT,
        help='JSON file to describe (default: "-", standard input)',
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("compact", "schema", "tree"),
        default="compact",
        help="output format (default: compact)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=DEFAULT_INDENT,
        metavar="N",
        help=f"indentation for the schema and tree formats (default: {DEFAULT_INDENT})",
    )
    parser.add_argument("--version", action="version", version=f"jsonhaiku {__version__}")
    return parser


def _read(file: str) -> str:
    """Read the payload from ``file``, or from standard input for ``-``."""
    if file == STDIN_ARGUMENT:
        return sys.stdin.read()
    return Path(file).read_text(encoding="utf-8")


def _render(result: Result, output_format: str, indent: int) -> str:
    """Render ``result`` in the requested output format."""
    if output_format == "compact":
        return result.compact
    document = result.schema if output_format == "schema" else result.tree
    return json.dumps(document, indent=indent, ensure_ascii=False)


def _fail(message: str) -> int:
    """Report a problem on standard error and return the failure exit status."""
    print(f"jsonhaiku: {message}", file=sys.stderr)
    return EXIT_BAD_INPUT
