"""Backward-compatible re-export of the compact renderer.

The implementation moved to :mod:`jsonhaiku.renderers.compact` in Phase 2.
This module keeps ``from jsonhaiku.render import render_compact`` working.
"""

from __future__ import annotations

from jsonhaiku.renderers.compact import render_compact

__all__ = ["render_compact"]
