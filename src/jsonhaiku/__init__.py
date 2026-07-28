"""Compact, LLM-friendly descriptions of large JSON payloads.

``jsonhaiku`` turns a large JSON value into a small, type-aware description that
a language model can reason about without ever seeing the raw data.

.. code-block:: python

    from jsonhaiku import describe

    result = describe(payload)
    print(result.compact)  # the LLM-facing type map
    result.schema  # JSON Schema, for the rest of the toolchain
    result.tree  # plain dicts, for your own tooling

The internal type tree lives in :mod:`jsonhaiku.nodes` and the inference rules in
:mod:`jsonhaiku.core`; both are importable for advanced use, but everything most
callers need is here.
"""

from __future__ import annotations

from jsonhaiku.__about__ import __version__
from jsonhaiku.core import UnsupportedValueWarning, describe
from jsonhaiku.result import Result

__all__ = [
    "Result",
    "UnsupportedValueWarning",
    "__version__",
    "describe",
]
