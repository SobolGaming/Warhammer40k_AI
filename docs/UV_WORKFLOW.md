# uv Workflow

This repository uses `uv` for local development and CI dependency management.
Use the project-local `.venv` created by `uv sync`; do not install project
dependencies into the system Python or a global user site.

## Install uv

Install uv with the official standalone installer for your platform:

<https://docs.astral.sh/uv/getting-started/installation/>

## Environment Setup

From the repository root:

```bash
uv sync --extra test
```

For UI work:

```bash
uv sync --extra test --extra ui --extra ui-test
```

For optional ML-boundary work:

```bash
uv sync --extra ml
```

## Running Commands

Run commands through uv so imports and console scripts resolve from the
repo-local environment:

```bash
uv run python -m pytest tests/ -m "not slow and not integration"
uv run python scripts/run_headless_self_play.py --games 1 --workers 1
uv run warhammer40k-ai --version
```

## Lockfile Policy

`uv.lock` is checked in. Update it whenever `pyproject.toml` dependencies,
extras, build metadata, or supported Python bounds change:

```bash
uv lock
```

If your machine is behind endpoint security or a managed TLS root store and
uv reports `UnknownIssuer`, use OS certificates:

```bash
uv --system-certs lock
uv --system-certs sync --extra test
```

CI uses `uv sync --frozen`, so dependency changes without a matching lockfile
update should fail early.
