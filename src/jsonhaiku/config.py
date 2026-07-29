"""Configuration for description and rendering behaviour.

A :class:`Config` bundles every knob into one frozen object.  Pass it to
:func:`jsonhaiku.describe` to enable content-type detection, cardinality
tracking, and depth limiting without cluttering the call site.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Config"]


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable configuration for :func:`jsonhaiku.describe`.

    Attributes:
        detect_content_types: Scan string values for common patterns (HTML,
            URL, ISO date, UUID, email, JWT) and emit specialised type names.
        long_string_threshold: Strings longer than this (in characters) are
            flagged as long when *detect_content_types* is enabled.
        long_string_sample_len: Maximum characters kept in the truncated
            ``sample:`` preview of a long string.
        max_depth: When set, renderers replace subtrees deeper than this with
            a compact summary.
        track_cardinality: Master switch for cardinality tracking, enum
            detection, and statistics collection.
        enum_max_values: Maximum distinct non-null values for a field to be
            rendered as an enum.
        enum_cardinality_ratio: Maximum ratio of distinct values to total
            observations for enum detection.
        unique_value_cap: Drop the unique-value set once it exceeds this many
            entries, to bound memory usage.
        include_frequency: When ``True``, enum renderings include observation
            counts for each value.
        include_stats: When ``True``, numeric and string statistics are
            rendered alongside type names.
        detect_always_null: Replace fields that are always ``null``, always an
            empty array, or always an empty object with explicit markers.
        always_null_min_observations: Minimum observations before a field is
            considered "always null/empty".
    """

    detect_content_types: bool = False
    long_string_threshold: int = 200
    long_string_sample_len: int = 40
    max_depth: int | None = None

    track_cardinality: bool = False
    enum_max_values: int = 20
    enum_cardinality_ratio: float = 0.05
    unique_value_cap: int = 100
    include_frequency: bool = False
    include_stats: bool = True
    detect_always_null: bool = True
    always_null_min_observations: int = 3
