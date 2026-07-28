"""Compact, LLM-friendly descriptions of large JSON payloads.

``jsonhaiku`` turns a large JSON value into a small, type-aware description
that a language model can reason about without ever seeing the raw data.

Nothing but the version is public yet -- the ``describe()`` surface lands with
core type inference. See the README for the planned API.
"""

from __future__ import annotations

from jsonhaiku.__about__ import __version__

__all__ = ["__version__"]
