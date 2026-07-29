"""Single source of truth for the package version.

Hatchling reads ``__version__`` from this module at build time (see
``[tool.hatch.version]`` in ``pyproject.toml``), so the distribution metadata
and the runtime attribute can never drift apart.

Versioning policy:
    * ``0.x.y`` -- anything may break on a minor bump.
    * ``1.0.0`` -- API stability commitment. Not before the progressive
      disclosure API (Phase 5) has settled.
"""

__version__ = "0.7.0.dev0"
