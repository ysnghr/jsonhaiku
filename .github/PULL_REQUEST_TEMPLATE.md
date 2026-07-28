<!--
Thanks for contributing. Keep the PR focused on one logical change; small PRs
get merged in hours, big unannounced ones get stuck.
-->

## What and why

<!-- What does this change, and what problem does it solve? Link the issue. -->

Closes #

## How

<!-- Anything a reviewer needs to know to read the diff: design choices,
     trade-offs, things you deliberately did not do. -->

## Checklist

- [ ] Tests added or updated (a behaviour change without a test will be asked for one)
- [ ] `make check` is green locally (`ruff`, `mypy --strict`, `pytest`)
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] Docstrings updated for any public API touched
- [ ] Snapshot diffs reviewed, if rendering changed (`pytest --snapshot-update`)
- [ ] No new runtime dependency in the core package (extras are fine)
