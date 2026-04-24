# Versioning

## Source of truth

- App version lives in `src/warhammer40k_ai/version.py` as `APP_VERSION`.
- `pyproject.toml` reads `APP_VERSION` through setuptools dynamic metadata so packaging and runtime share the same value.
- `0.2.105` is the current 10th Edition milestone release line after completed in-scope faction support and active 11th-edition-first port-prep work.

## When to bump

Bump the app version for any commit that changes runtime behavior, network protocol,
rules data, UI logic, or docs that describe behavior. This keeps server/client
compatibility checks meaningful.

## How to bump

Use the helper script:

```
python scripts/bump_version.py --patch
python scripts/bump_version.py --minor
python scripts/bump_version.py --major
python scripts/bump_version.py --set 1.2.3
```

Commit the updated `src/warhammer40k_ai/version.py` alongside your changes.

Note: Python 3.12 or newer is required for version tooling and git hook checks.
On Windows, `py -3.12` is preferred if `python` is not on PATH.

## Git hook enforcement

Install repo hooks once per clone:

```
python scripts/install_git_hooks.py
```

Hooks enforce that `src/warhammer40k_ai/version.py` is updated whenever you
commit other files, and that every commit pushed includes a version bump.

The pre-commit hook will also auto-bump the version (patch) and stage
`version.py` when you commit other files and have not already staged a version
change. If you want a minor/major bump, run the bump script manually first.
