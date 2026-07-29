"""Compact, LLM-friendly descriptions of large JSON payloads.

``jsonhaiku`` turns a large JSON value into a small, type-aware description that
a language model can reason about without ever seeing the raw data.

.. code-block:: python

    from jsonhaiku import describe, Config

    result = describe(payload)
    print(result.compact)  # compact type map
    print(result.typescript())  # TypeScript interfaces
    print(result.yaml)  # YAML type description
    result.json_schema  # JSON Schema dict

    # With content-type detection and depth limiting:
    cfg = Config(detect_content_types=True, max_depth=3)
    result = describe(payload, config=cfg)

The internal type tree lives in :mod:`jsonhaiku.nodes` and the inference rules in
:mod:`jsonhaiku.core`; both are importable for advanced use, but everything most
callers need is here.
"""

from __future__ import annotations

from jsonhaiku.__about__ import __version__
from jsonhaiku.config import Config
from jsonhaiku.core import UnsupportedValueWarning, describe
from jsonhaiku.result import Result

__all__ = [
    "Config",
    "Result",
    "UnsupportedValueWarning",
    "__version__",
    "describe",
]
