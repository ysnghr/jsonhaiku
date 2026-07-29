"""Minimal JSONPath subset — just enough for interactive exploration.

Supports ``$``, ``.field``, ``[N]``, ``[*]``.  No recursive descent
(``..``), no filter expressions, no unions — those belong in the filter
DSL, not the path syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PathSegment", "parse_path", "resolve"]

_TOKEN_RE = re.compile(
    r"""
    \.(\w+)          # .field
    | \[(\d+)\]      # [N]
    | \[\*\]         # [*]
    | (\$)           # root
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class _Root:
    """The root ``$`` segment."""


@dataclass(frozen=True)
class _Field:
    """A named field accessor (``.name``)."""

    name: str


@dataclass(frozen=True)
class _Index:
    """A numeric index (``[0]``)."""

    index: int


@dataclass(frozen=True)
class _Wildcard:
    """A wildcard (``[*]``)."""


PathSegment = _Root | _Field | _Index | _Wildcard


def parse_path(path: str) -> list[PathSegment]:
    """Parse a JSONPath string into a list of segments.

    Raises:
        ValueError: If the path is empty or contains invalid syntax.
    """
    if not path:
        msg = "path must not be empty"
        raise ValueError(msg)

    segments: list[PathSegment] = []
    pos = 0

    while pos < len(path):
        m = _TOKEN_RE.match(path, pos)
        if m is None:
            msg = f"invalid path syntax at position {pos}: {path[pos:]!r}"
            raise ValueError(msg)

        if m.group(3) is not None:
            segments.append(_Root())
        elif m.group(1) is not None:
            segments.append(_Field(m.group(1)))
        elif m.group(2) is not None:
            segments.append(_Index(int(m.group(2))))
        elif m.group(0) == "[*]":
            segments.append(_Wildcard())
        pos = m.end()

    if not segments:
        msg = f"no valid segments in path: {path!r}"
        raise ValueError(msg)
    return segments


@dataclass(frozen=True)
class _Match:
    """A value matched by path resolution, with its concrete path."""

    path: str
    value: object


def resolve(data: object, path: str) -> list[_Match]:
    """Resolve a JSONPath against *data*, returning all matches.

    Returns:
        A list of ``(path, value)`` matches.
    """
    segments = parse_path(path)
    matches: list[_Match] = [_Match(path="$", value=data)]

    for seg in segments:
        if isinstance(seg, _Root):
            matches = [_Match(path="$", value=data)]
        elif isinstance(seg, _Field):
            matches = _apply_field(matches, seg.name)
        elif isinstance(seg, _Index):
            matches = _apply_index(matches, seg.index)
        elif isinstance(seg, _Wildcard):
            matches = _apply_wildcard(matches)

    return matches


def resolve_paths(data: object) -> dict[str, list[object]]:
    """Build a path index — map every leaf and branch path to its values.

    Walks *data* recursively, collecting values at every path like
    ``$[*].room.name``.  Array items are collapsed under ``[*]``.
    """
    index: dict[str, list[object]] = {}
    _walk(data, "$", index)
    return index


def _walk(value: object, path: str, index: dict[str, list[object]]) -> None:
    index.setdefault(path, []).append(value)

    if isinstance(value, dict):
        for key, val in value.items():
            _walk(val, f"{path}.{key}", index)
    elif isinstance(value, list | tuple):
        for item in value:
            _walk(item, f"{path}[*]", index)


def _apply_field(matches: list[_Match], name: str) -> list[_Match]:
    return [
        _Match(path=f"{m.path}.{name}", value=m.value[name])
        for m in matches
        if isinstance(m.value, dict) and name in m.value
    ]


def _apply_index(matches: list[_Match], index: int) -> list[_Match]:
    return [
        _Match(path=f"{m.path}[{index}]", value=m.value[index])
        for m in matches
        if isinstance(m.value, list | tuple) and 0 <= index < len(m.value)
    ]


def _apply_wildcard(matches: list[_Match]) -> list[_Match]:
    result: list[_Match] = []
    for m in matches:
        if isinstance(m.value, list | tuple):
            for i, item in enumerate(m.value):
                result.append(_Match(path=f"{m.path}[{i}]", value=item))
        elif isinstance(m.value, dict):
            for key, val in m.value.items():
                result.append(_Match(path=f"{m.path}.{key}", value=val))
    return result
