"""Configuration for description and rendering behaviour.

A :class:`Config` bundles every Phase 2 knob into one frozen object.  Pass it
to :func:`jsonhaiku.describe` to enable content-type detection, long-string
truncation, and depth limiting without cluttering the call site.
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
    """

    detect_content_types: bool = False
    long_string_threshold: int = 200
    long_string_sample_len: int = 40
    max_depth: int | None = None
