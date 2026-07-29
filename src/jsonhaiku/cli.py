"""Command line interface: ``jsonhaiku [FILE]``.

Reads JSON from a file or standard input and writes a description to standard
output, so the library is one pipe away from any shell::

    curl -s https://api.example.com/sessions | jsonhaiku
    jsonhaiku response.json --format typescript
    jsonhaiku shell data.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from jsonhaiku.__about__ import __version__
from jsonhaiku.config import Config
from jsonhaiku.core import describe

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from jsonhaiku.explorer import JsonHaiku
    from jsonhaiku.result import Result

__all__ = ["main"]

STDIN_ARGUMENT = "-"
"""The conventional filename meaning "read standard input"."""

EXIT_OK = 0
EXIT_BAD_INPUT = 1
DEFAULT_INDENT = 2

_VALID_FORMATS = ("compact", "typescript", "json_schema", "yaml", "schema", "tree")

_SHELL_HELP = """\
Commands:
  overview                         top-level orientation
  describe PATH [depth=N]          schema at path
  sample PATH [n=N]                sample values at path
  enum PATH                        unique values at path
  stats PATH                       numeric/string statistics
  search QUERY [path=PATH]         find values containing substring
  filter PATH WHERE_EXPR           filter records by expression
  paths [min=N] [max=N]            list all observed paths
  help                             show this help
  quit / exit                      leave the shell
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: Command line arguments, excluding the program name. Defaults to
            :data:`sys.argv`.

    Returns:
        A process exit status: ``0`` on success, ``1`` if the input could not be
        read or parsed. Usage errors exit with ``2`` via argparse.
    """
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    if effective_argv and effective_argv[0] == "shell":
        if len(effective_argv) < 2:  # noqa: PLR2004
            print("usage: jsonhaiku shell FILE", file=sys.stderr)
            return EXIT_BAD_INPUT
        return _run_shell(effective_argv[1])

    args = _build_parser().parse_args(argv)

    use_stream = args.stream or _should_auto_stream(args.file)
    if use_stream:
        return _run_stream(args)

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
        track_cardinality=args.track_cardinality,
        include_frequency=args.include_frequency,
        include_stats=args.include_stats,
    )
    result = describe(
        data,
        config=config,
        samples=args.samples,
        redact_samples=args.redact_samples,
    )
    if result.samples:
        print(result.render_with_samples(args.format, root_name=args.root_name))
    else:
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
    parser.add_argument(
        "--track-cardinality",
        action="store_true",
        default=False,
        help="detect enums, always-null fields, and collect statistics",
    )
    parser.add_argument(
        "--include-frequency",
        action="store_true",
        default=False,
        help="show observation counts alongside enum values",
    )
    parser.add_argument(
        "--include-stats",
        action="store_true",
        default=True,
        help="show numeric/string/boolean statistics (default: True)",
    )
    parser.add_argument(
        "--no-stats",
        action="store_false",
        dest="include_stats",
        help="disable numeric/string/boolean statistics",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        metavar="K",
        help="select K representative sample records from array input",
    )
    parser.add_argument(
        "--redact-samples",
        action="store_true",
        default=False,
        help="replace PII-like values in samples with safe placeholders",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        default=False,
        help="use streaming mode for large files (auto-enabled above 100 MB)",
    )
    parser.add_argument(
        "--memory-budget",
        type=int,
        default=500,
        metavar="MB",
        help="soft memory budget in MB for streaming mode (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="random seed for reproducible reservoir sampling in streaming mode",
    )
    parser.add_argument("--version", action="version", version=f"jsonhaiku {__version__}")
    return parser


_AUTO_STREAM_THRESHOLD = 100 * 1024 * 1024


def _should_auto_stream(file_arg: str) -> bool:
    """Return True if the file is large enough to auto-enable streaming."""
    if file_arg == STDIN_ARGUMENT:
        return False
    try:
        return Path(file_arg).stat().st_size > _AUTO_STREAM_THRESHOLD
    except OSError:
        return False


def _run_stream(args: argparse.Namespace) -> int:
    """Run streaming mode."""
    from jsonhaiku.renderers.compact import render_compact  # noqa: PLC0415
    from jsonhaiku.streaming import stream_ingest  # noqa: PLC0415

    config = Config(
        detect_content_types=args.detect_content_types,
        max_depth=args.max_depth,
        track_cardinality=args.track_cardinality,
        include_frequency=args.include_frequency,
        include_stats=args.include_stats,
    )

    try:
        stream = _open_stream(args.file)
    except OSError as error:
        return _fail(f"cannot read {args.file}: {error.strerror or error}")

    progress_cb = _make_progress_callback() if sys.stderr.isatty() else None

    try:
        result = stream_ingest(
            stream,
            config=config,
            memory_budget_mb=args.memory_budget,
            seed=args.seed,
            on_progress=progress_cb,
        )
    finally:
        if args.file != STDIN_ARGUMENT:
            stream.close()

    if progress_cb is not None:
        print(file=sys.stderr)

    output = render_compact(result.root, max_depth=args.max_depth)
    print(output)

    if result.warnings:
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
    if result.approximate:
        print("note: some statistics are approximate (HyperLogLog)", file=sys.stderr)

    return EXIT_OK


def _open_stream(file_arg: str) -> IO[bytes]:
    """Open a binary stream for the given file argument."""
    if file_arg == STDIN_ARGUMENT:
        return sys.stdin.buffer
    return Path(file_arg).open("rb")


def _make_progress_callback() -> Callable[[int, int], None]:
    """Return a progress callback that prints a status line to stderr."""

    def on_progress(bytes_read: int, records_seen: int) -> None:
        mb = bytes_read / (1024 * 1024)
        print(f"\r  {mb:.1f} MB read, {records_seen:,} records", end="", file=sys.stderr)

    return on_progress


def _run_shell(file_path: str) -> int:
    """Run the interactive REPL."""
    from jsonhaiku.explorer import JsonHaiku as Explorer  # noqa: PLC0415

    try:
        payload = Path(file_path).read_text(encoding="utf-8")
    except OSError as error:
        return _fail(f"cannot read {file_path}: {error.strerror or error}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        return _fail(f"invalid JSON: {error}")

    h = Explorer(data)
    ov = h.overview()
    print(f"Loaded {ov['root_kind']} ({ov['total_size_bytes']} bytes, {ov['unique_paths']} paths)")
    print('Type "help" for commands, "quit" to exit.\n')

    while True:
        try:
            line = input("haiku> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line in ("quit", "exit"):
            break

        try:
            output = _dispatch_shell(h, line)
            if output is not None:
                print(json.dumps(output, indent=2, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}")

    return EXIT_OK


def _dispatch_shell(h: JsonHaiku, line: str) -> object:
    """Dispatch a REPL command and return its result."""
    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]

    handlers: dict[str, object] = {
        "overview": h.overview,
        "describe": lambda: _shell_describe(h, args),
        "sample": lambda: _shell_sample(h, args),
        "enum": lambda: _shell_enum(h, args),
        "stats": lambda: _shell_stats(h, args),
        "search": lambda: _shell_search(h, args),
        "filter": lambda: _shell_filter(h, args),
        "paths": lambda: _shell_paths(h, args),
    }

    if cmd == "help":
        print(_SHELL_HELP)
        return None

    handler = handlers.get(cmd)
    if handler is not None and callable(handler):
        return handler()

    print(f"unknown command: {cmd!r}. Type 'help' for available commands.")
    return None


def _shell_describe(h: JsonHaiku, args: list[str]) -> dict[str, Any]:
    """Handle the describe shell command."""
    path, kwargs = _parse_shell_args(args, defaults={"depth": "2"})
    depth_str = kwargs.get("depth", "2")
    depth: int | None = None if depth_str == "None" else int(depth_str)
    return h.describe(path=path, depth=depth)


def _shell_sample(h: JsonHaiku, args: list[str]) -> dict[str, Any]:
    """Handle the sample shell command."""
    path, kwargs = _parse_shell_args(args, defaults={"n": "3"})
    return h.sample(path=path, n=int(kwargs.get("n", "3")))


def _shell_enum(h: JsonHaiku, args: list[str]) -> dict[str, Any]:
    """Handle the enum shell command."""
    path, _kwargs = _parse_shell_args(args, defaults={})
    return h.enum(path=path)


def _shell_stats(h: JsonHaiku, args: list[str]) -> dict[str, Any]:
    """Handle the stats shell command."""
    path, _kwargs = _parse_shell_args(args, defaults={})
    return h.stats(path=path)


def _shell_search(h: JsonHaiku, args: list[str]) -> dict[str, Any]:
    """Handle the search shell command."""
    query_parts: list[str] = []
    path = "$"
    for arg in args:
        if arg.startswith("path="):
            path = arg.split("=", 1)[1]
        else:
            query_parts.append(arg)
    query = " ".join(query_parts)
    return h.search(value_contains=query, path=path)


def _shell_filter(h: JsonHaiku, args: list[str]) -> dict[str, Any] | None:
    """Handle the filter shell command."""
    _MIN_FILTER_ARGS = 2  # noqa: N806
    if len(args) < _MIN_FILTER_ARGS:
        print("usage: filter PATH WHERE_EXPR")
        return None
    path = args[0]
    where = " ".join(args[1:])
    return h.filter(path=path, where=where)


def _shell_paths(h: JsonHaiku, args: list[str]) -> list[str]:
    """Handle the paths shell command."""
    kwargs: dict[str, str] = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            kwargs[k] = v
    min_depth = int(kwargs.get("min", "0"))
    max_depth_str = kwargs.get("max")
    max_depth = int(max_depth_str) if max_depth_str is not None else None
    return h.list_paths(min_depth=min_depth, max_depth=max_depth)


def _parse_shell_args(
    args: list[str],
    defaults: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Parse shell arguments into a path and keyword arguments."""
    path = "$"
    kwargs = dict(defaults)

    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            kwargs[key] = value
        elif not arg.startswith("-"):
            path = arg

    return path, kwargs


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
