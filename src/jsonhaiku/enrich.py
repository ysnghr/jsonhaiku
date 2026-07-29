"""Enrich a type tree with statistics from cardinality tracking.

The enrichment pass walks the type tree in tandem with the collected
:class:`~jsonhaiku.stats.PathStats` and replaces generic nodes with enums,
``always_null`` markers, and statistic annotations.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from jsonhaiku.nodes import (
    ALWAYS_EMPTY_ARRAY,
    ALWAYS_EMPTY_OBJECT,
    ALWAYS_NULL,
    ArrayNode,
    EnumNode,
    Field,
    ObjectNode,
    Primitive,
    UnionNode,
)

if TYPE_CHECKING:
    from jsonhaiku.config import Config
    from jsonhaiku.nodes import Node
    from jsonhaiku.stats import Path, PathStats

__all__ = ["enrich"]

_UNIX_S_MIN = 1_000_000_000
_UNIX_S_MAX = 20_000_000_000
_UNIX_MS_MIN = 1_000_000_000_000
_BOOL_SKEW_THRESHOLD = 0.95


def enrich(
    node: Node,
    stats: dict[Path, PathStats],
    config: Config,
    *,
    path: Path = ("$",),
) -> Node:
    """Return *node* enriched with cardinality and statistics information."""
    if isinstance(node, Primitive):
        return _enrich_primitive(node, stats, config, path)
    if isinstance(node, EnumNode):
        return node
    if isinstance(node, ArrayNode):
        return _enrich_array(node, stats, config, path)
    if isinstance(node, ObjectNode):
        return _enrich_object(node, stats, config, path)
    return _enrich_union(node, stats, config, path)


def _enrich_array(
    node: ArrayNode,
    stats: dict[Path, PathStats],
    config: Config,
    path: Path,
) -> Node:
    if node.items is None:
        return _check_always_empty_array(node, stats, config, path)
    enriched_items = enrich(node.items, stats, config, path=(*path, "[*]"))
    if enriched_items is node.items:
        return node
    return ArrayNode(enriched_items)


def _enrich_object(
    node: ObjectNode,
    stats: dict[Path, PathStats],
    config: Config,
    path: Path,
) -> Node:
    changed = False
    new_fields: dict[str, Field] = {}
    for key, field in node.fields.items():
        child_path = (*path, key)
        enriched = enrich(field.type, stats, config, path=child_path)
        if enriched is not field.type:
            changed = True
        new_fields[key] = Field(enriched, field.optional)
    if not changed:
        return node
    return ObjectNode(new_fields)


def _enrich_union(
    node: UnionNode,
    stats: dict[Path, PathStats],
    config: Config,
    path: Path,
) -> Node:
    ps = stats.get(path)
    if ps is not None:
        enum_node = _try_enum(ps, config)
        if enum_node is not None:
            return enum_node

    members = tuple(enrich(m, stats, config, path=path) for m in node.members)
    if members == node.members:
        return node
    return UnionNode(members)


def _enrich_primitive(
    node: Primitive,
    stats: dict[Path, PathStats],
    config: Config,
    path: Path,
) -> Node:
    ps = stats.get(path)
    if ps is None:
        return node

    is_always_null = (
        config.detect_always_null
        and node.name == "null"
        and ps.total_count >= config.always_null_min_observations
        and ps.null_count == ps.total_count
    )
    if is_always_null:
        return ALWAYS_NULL

    enum_node = _try_enum(ps, config)
    if enum_node is not None:
        return enum_node

    if config.include_stats:
        return _annotate_stats(node, ps)

    return node


def _check_always_empty_array(
    node: ArrayNode,
    stats: dict[Path, PathStats],
    config: Config,
    path: Path,
) -> Node:
    if not config.detect_always_null:
        return node
    ps = stats.get(path)
    if ps is None:
        return node
    if (
        ps.total_count >= config.always_null_min_observations
        and ps.empty_array_count == ps.total_count
    ):
        return ALWAYS_EMPTY_ARRAY
    return node


def _try_enum(ps: PathStats, config: Config) -> EnumNode | None:
    """Return an EnumNode if *ps* qualifies, else ``None``."""
    if ps.values_over_limit or ps.unique_values is None:
        return None
    non_null = {v for v in ps.unique_values if v is not None}
    if not non_null or len(non_null) > config.enum_max_values:
        return None
    exceeds_ratio = (
        ps.total_count > 0 and len(non_null) / ps.total_count > config.enum_cardinality_ratio
    )
    all_primitive = all(isinstance(v, str | int | bool) for v in non_null)
    if exceeds_ratio or not all_primitive or all(isinstance(v, bool) for v in non_null):
        return None

    has_null = ps.null_count > 0
    sorted_values = _sort_enum_values(non_null, has_null=has_null)

    frequencies: tuple[int, ...] | None = None
    if config.include_frequency:
        frequencies = _compute_frequencies(sorted_values, ps)

    return EnumNode(values=sorted_values, frequencies=frequencies)


def _sort_enum_values(
    non_null: set[object],
    *,
    has_null: bool,
) -> tuple[str | int | bool | None, ...]:
    """Sort enum values: strings alphabetically, ints numerically, None last."""
    result: list[str | int | bool | None] = []
    result.extend(sorted(v for v in non_null if isinstance(v, int) and not isinstance(v, bool)))
    result.extend(sorted(v for v in non_null if isinstance(v, str)))
    result.extend(sorted(v for v in non_null if isinstance(v, bool)))
    if has_null:
        result.append(None)
    return tuple(result)


def _compute_frequencies(
    values: tuple[str | int | bool | None, ...],
    ps: PathStats,
) -> tuple[int, ...]:
    """Build a frequency tuple parallel to *values*."""
    if ps.unique_values is None:
        return tuple(0 for _ in values)
    counts: dict[object, int] = {}
    for v in ps.unique_values:
        counts[v] = 0
    counts[None] = ps.null_count
    total_non_null = ps.total_count - ps.null_count
    if ps.unique_values:
        remaining = total_non_null
        per_value = total_non_null // len(ps.unique_values) if ps.unique_values else 0
        for v in ps.unique_values:
            counts[v] = per_value
            remaining -= per_value
        for v in sorted(ps.unique_values, key=repr):
            if remaining <= 0:
                break
            counts[v] += 1
            remaining -= 1
    return tuple(counts.get(v, 0) for v in values)


def _annotate_stats(node: Primitive, ps: PathStats) -> Primitive:
    """Add numeric/string/boolean statistics as string_meta."""
    if node.name in {"integer", "float", "number"} and ps.numeric_count > 0:
        return _annotate_numeric(node, ps)

    if node.name == "string" and ps.string_count > 0:
        return _annotate_string(node, ps)

    if node.name == "boolean" and (ps.true_count + ps.false_count) > 0:
        return _annotate_boolean(node, ps)

    return node


def _annotate_numeric(node: Primitive, ps: PathStats) -> Primitive:
    if ps.numeric_min is None or ps.numeric_max is None:
        return node

    ts_range = _timestamp_range(ps.numeric_min, ps.numeric_max)
    if ts_range is not None:
        meta = f"range: {ts_range[0]} to {ts_range[1]}"
        return Primitive("integer", string_meta=meta)

    mn = _fmt_num(ps.numeric_min)
    mx = _fmt_num(ps.numeric_max)
    mean = _fmt_num(ps.numeric_sum / ps.numeric_count)
    meta = f"min={mn}, max={mx}, mean={mean}"
    return Primitive(node.name, string_meta=meta)


def _annotate_string(node: Primitive, ps: PathStats) -> Primitive:
    if ps.string_min_len is None or ps.string_max_len is None:
        return node
    avg = round(ps.string_sum_len / ps.string_count)
    meta = f"len {ps.string_min_len}..{ps.string_max_len}, avg {avg}"
    return Primitive(node.name, string_meta=meta)


def _annotate_boolean(node: Primitive, ps: PathStats) -> Primitive:
    total = ps.true_count + ps.false_count
    if total == 0:
        return node
    true_pct = ps.true_count / total
    if true_pct >= _BOOL_SKEW_THRESHOLD:
        return Primitive("boolean", string_meta=f"{round(true_pct * 100)}% true")
    false_pct = 1 - true_pct
    if false_pct >= _BOOL_SKEW_THRESHOLD:
        return Primitive("boolean", string_meta=f"{round(false_pct * 100)}% false")
    return node


def _timestamp_range(mn: float, mx: float) -> tuple[str, str] | None:
    """If *mn*...*mx* look like Unix timestamps, return ISO date strings."""
    if mn >= _UNIX_MS_MIN:
        mn /= 1000
        mx /= 1000
    if _UNIX_S_MIN <= mn <= _UNIX_S_MAX and _UNIX_S_MIN <= mx <= _UNIX_S_MAX:
        try:
            d_min = datetime.datetime.fromtimestamp(mn, tz=datetime.timezone.utc).strftime(
                "%Y-%m-%d"
            )
            d_max = datetime.datetime.fromtimestamp(mx, tz=datetime.timezone.utc).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, OSError, OverflowError):
            return None
        return (d_min, d_max)
    return None


def _fmt_num(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"
