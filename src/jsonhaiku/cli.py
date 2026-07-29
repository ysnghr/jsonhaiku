"""Command line interface: ``jsonhaiku [FILE]``.

Reads JSON from a file or standard input and writes a description to standard
output, so the library is one pipe away from any shell::

    curl -s https://api.example.com/sessions | jsonhaiku
    jsonhaiku response.json --format typescript
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jsonhaiku.__about__ import __version__
from jsonhaiku.config import Config
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

_VALID_FORMATS = ("compact", "typescript", "json_schema", "yaml", "schema", "tree")


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

    config = Config(
        detect_content_types=args.detect_content_types,
        max_depth=args.max_depth,
    )
    result = describe(data, config=config)
    print(_render(result, args.format, args.indent, args.root_name))
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
        choices=_VALID_FORMATS,
        default="compact",
        help="output format (default: compact)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=DEFAULT_INDENT,
        metavar="N",
        help=f"indentation for JSON formats (default: {DEFAULT_INDENT})",
    )
    parser.add_argument(
        "--root-name",
        default="Root",
        metavar="NAME",
        help='interface name for the typescript format (default: "Root")',
    )
    parser.add_argument(
        "--detect-content-types",
        action="store_true",
        default=False,
        help="scan string values for HTML, URL, date, UUID, email, JWT patterns",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="truncate output below this nesting depth",
    )
    parser.add_argument("--version", action="version", version=f"jsonhaiku {__version__}")
    return parser


def _read(file: str) -> str:
    """Read the payload from ``file``, or from standard input for ``-``."""
    if file == STDIN_ARGUMENT:
        return sys.stdin.read()
    return Path(file).read_text(encoding="utf-8")


def _render(result: Result, output_format: str, indent: int, root_name: str) -> str:
    """Render ``result`` in the requested output format."""
    if output_format == "compact":
        return result.compact
    if output_format == "typescript":
        return result.typescript(root_name=root_name)
    if output_format == "yaml":
        return result.yaml
    if output_format == "json_schema":
        return json.dumps(result.json_schema, indent=indent, ensure_ascii=False)
    if output_format == "schema":
        return json.dumps(result.schema, indent=indent, ensure_ascii=False)
    document = result.tree
    return json.dumps(document, indent=indent, ensure_ascii=False)


def _fail(message: str) -> int:
    """Report a problem on standard error and return the failure exit status."""
    print(f"jsonhaiku: {message}", file=sys.stderr)
    return EXIT_BAD_INPUT
