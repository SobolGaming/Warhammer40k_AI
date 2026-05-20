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

## UI Smoke Checks

For pygame UI boot coverage without opening a real window, use SDL's dummy
video driver. The smoke script initializes the local authoritative runtime,
publishes `game_loaded`, advances setup to the manual deployment boundary,
builds deployment plans, draws a few frames, and exercises ESC/SPACE/resize
events. It is a crash smoke only; it does not verify rendering quality.

```bash
SDL_VIDEODRIVER=dummy uv run python scripts/smoke_ui_local.py \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt
```

PowerShell:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
uv run python scripts/smoke_ui_local.py `
  --player1-army army_lists/chaos_test.txt `
  --player2-army army_lists/aeldari_test.txt
```

For network loopback coverage, run the two-client smoke. It starts a localhost
server on an ephemeral port, handshakes two clients, submits army lists, starts
the game, loads snapshots into `NetworkGameSession`, waits for setup/formation
traffic, resolves one available local decision, asserts no `ErrorMessage`
payloads, asserts no unexpected resync storm, and stops both clients and the
server cleanly before reporting success.

```bash
uv run python scripts/smoke_network_loopback.py \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt
```

PowerShell:

```powershell
uv run python scripts/smoke_network_loopback.py `
  --player1-army army_lists/chaos_test.txt `
  --player2-army army_lists/aeldari_test.txt
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
