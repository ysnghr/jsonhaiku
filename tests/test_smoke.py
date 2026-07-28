"""Smoke tests: the package imports, and its public surface is coherent.

These are cheap and they fail loudly. Every one of them has caught a real
packaging mistake in some project at some point.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from packaging.version import Version

import jsonhaiku


def test_reimport_is_stable() -> None:
    """Re-importing the package must not blow up or rename itself."""
    first = jsonhaiku
    second = importlib.reload(jsonhaiku)
    assert first.__name__ == second.__name__ == "jsonhaiku"


def test_version_is_exposed() -> None:
    assert isinstance(jsonhaiku.__version__, str)
    assert jsonhaiku.__version__


def test_version_is_valid_normalised_pep440() -> None:
    # A malformed version produces an unpublishable wheel; an un-normalised one
    # produces artifact filenames that don't match the string users see.
    parsed = Version(jsonhaiku.__version__)  # raises InvalidVersion if malformed
    assert str(parsed) == jsonhaiku.__version__


def test_version_is_pre_one_zero() -> None:
    """Guardrail: 1.0.0 is an API-stability promise, not a version bump.

    Delete this test in the commit that consciously makes that promise.
    """
    assert Version(jsonhaiku.__version__) < Version("1.0.0")


def test_all_is_sorted_and_resolvable() -> None:
    assert jsonhaiku.__all__ == sorted(jsonhaiku.__all__)
    for name in jsonhaiku.__all__:
        assert hasattr(jsonhaiku, name), f"__all__ advertises missing name: {name}"


def test_star_import_exposes_only_declared_names() -> None:
    namespace: dict[str, object] = {}
    exec("from jsonhaiku import *", namespace)  # noqa: S102
    exported = {k for k in namespace if not k.startswith("__")}
    declared = {name for name in jsonhaiku.__all__ if not name.startswith("__")}
    assert exported == declared


def test_has_docstring() -> None:
    assert jsonhaiku.__doc__ is not None
    assert jsonhaiku.__doc__.strip()


def test_does_not_shadow_a_stdlib_module() -> None:
    assert "jsonhaiku" not in sys.stdlib_module_names


@pytest.mark.parametrize("attribute", ["JsonHaiku"])
def test_planned_api_is_not_yet_advertised(attribute: str) -> None:
    """Fails the day a planned API lands -- at which point, test it properly.

    This keeps the README's "planned API" section honest: nothing is half
    exported before it is documented and covered.
    """
    assert not hasattr(jsonhaiku, attribute)
