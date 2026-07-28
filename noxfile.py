"""Local task runner for jsonhaiku.

Nox gives contributors the same commands CI runs, against every supported
interpreter, without needing those interpreters preinstalled -- uv fetches
them.

    nox                 # default sessions: lint, typing, tests
    nox -s tests        # tests on every supported CPython
    nox -s tests-3.12   # one interpreter
    nox -s build        # build and validate the distribution
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import nox

if TYPE_CHECKING:
    from collections.abc import Sequence

# uv resolves and installs an order of magnitude faster than pip, and it can
# download missing interpreters on demand.
nox.options.default_venv_backend = "uv|virtualenv"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["lint", "typing", "tests"]

PYTHONS: Sequence[str] = ("3.10", "3.11", "3.12", "3.13", "3.14")
LINT_PATHS: Sequence[str] = ("src", "tests", "noxfile.py")


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    """Run the test suite with coverage."""
    session.install("-e", ".[test]")
    session.run("pytest", *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    """Check formatting and lint rules without modifying files."""
    session.install(".[lint]")
    session.run("ruff", "check", *LINT_PATHS)
    session.run("ruff", "format", "--check", "--diff", *LINT_PATHS)


@nox.session
def format_code(session: nox.Session) -> None:
    """Apply formatting and auto-fixable lint rules."""
    session.install(".[lint]")
    session.run("ruff", "check", "--fix", *LINT_PATHS)
    session.run("ruff", "format", *LINT_PATHS)


@nox.session
def typing(session: nox.Session) -> None:
    """Type check the package and the test suite in strict mode."""
    session.install("-e", ".[typing]")
    session.run("mypy", *session.posargs)


@nox.session
def build(session: nox.Session) -> None:
    """Build the sdist and wheel, then validate their metadata and contents."""
    session.install("twine", "uv")
    shutil.rmtree("dist", ignore_errors=True)
    session.run("uv", "build")
    session.run("twine", "check", "--strict", "dist/*")


@nox.session(name="pre-commit")
def pre_commit(session: nox.Session) -> None:
    """Run every pre-commit hook over the whole tree."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files", "--show-diff-on-failure")
