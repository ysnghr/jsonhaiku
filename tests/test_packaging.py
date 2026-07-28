"""Tests that the *installed distribution* is correct, not just the source tree.

With a src-layout these can only pass against a real install, which is exactly
the point: they turn packaging mistakes into red tests instead of into bug
reports from users.
"""

from __future__ import annotations

from importlib import metadata, resources

import jsonhaiku

DISTRIBUTION = "jsonhaiku"


def test_distribution_is_installed() -> None:
    """A src-layout import that resolves without metadata means a stray path."""
    assert metadata.distribution(DISTRIBUTION) is not None


def test_runtime_version_matches_distribution_metadata() -> None:
    installed = metadata.version(DISTRIBUTION)
    assert jsonhaiku.__version__ == installed, (
        f"jsonhaiku.__version__ is {jsonhaiku.__version__!r} but the installed "
        f"distribution reports {installed!r}. After bumping __about__.py, "
        f"reinstall the package (`uv pip install -e '.[dev]'`)."
    )


def test_py_typed_marker_is_packaged() -> None:
    """Without py.typed, downstream users get zero type hints (PEP 561)."""
    marker = resources.files(DISTRIBUTION).joinpath("py.typed")
    assert marker.is_file()


def test_core_install_has_no_runtime_dependencies() -> None:
    """The core library must stay trivially addable to any project."""
    requires = metadata.requires(DISTRIBUTION) or []
    unconditional = [req for req in requires if "extra ==" not in req]
    assert unconditional == [], f"unexpected hard dependencies: {unconditional}"


def test_metadata_advertises_supported_python() -> None:
    meta = metadata.metadata(DISTRIBUTION)
    assert meta["Requires-Python"] == ">=3.10"
    assert meta["Name"] == DISTRIBUTION


def test_metadata_advertises_typing_and_license() -> None:
    meta = metadata.metadata(DISTRIBUTION)
    classifiers = meta.get_all("Classifier") or []
    assert "Typing :: Typed" in classifiers
    # PEP 639: the SPDX expression replaces the legacy License:: classifier.
    assert meta["License-Expression"] == "MIT"


def test_expected_extras_are_declared() -> None:
    provided = set(metadata.metadata(DISTRIBUTION).get_all("Provides-Extra") or [])
    assert {"dev", "lint", "test", "tokens", "typing"} <= provided
