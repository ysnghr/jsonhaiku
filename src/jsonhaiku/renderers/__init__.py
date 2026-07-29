"""Output renderers — one module per format, each a pure function over the type tree.

The four renderers share nothing at runtime; the package exists only so ``import
jsonhaiku.renderers.typescript`` reads naturally.
"""

from __future__ import annotations

from jsonhaiku.renderers.compact import render_compact
from jsonhaiku.renderers.json_schema import render_json_schema
from jsonhaiku.renderers.typescript import render_typescript
from jsonhaiku.renderers.yaml import render_yaml

__all__ = [
    "render_compact",
    "render_json_schema",
    "render_typescript",
    "render_yaml",
]
