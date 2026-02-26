# Shared Engine Flow Refactor Implementation Plan

## Objective
Unify engine execution flow between:
- Local runner (`scripts/main.py`)
- Networked server/client gameplay (`src/warhammer40k_ai/network/*`)

Both modes should run through the same authoritative command/decision pipeline wherever possible, with no network loopback in local mode.

## Problem Summary
Today, command and decision dispatch are already shared (`Game.apply_command`, command/decision dispatchers), but orchestration diverges:
- Local mode advances setup/phases directly from UI loop semantics.
- Network mode has additional server orchestration logic for setup, decision broadcasts, and buffering.

This creates behavior skew risk, duplicate setup flow logic, and higher maintenance for new decision types.

## Design Goals
- One authoritative orchestration path for setup and turn progression.
- One decision lifecycle across local and networked modes.
- No local network loopback for `scripts/main.py`.
- Preserve deterministic command/event behavior and replay compatibility.
- Preserve explicit player authority boundaries in network mode.

## Non-Goals
- No changes to game rules behavior.
- No new decision kinds.
- No protocol rewrite for lobby/auth transport.
- No AI policy/model changes.

## Target Architecture
Introduce a shared authoritative session driver abstraction used by both runtime modes:

- `AuthoritativeSessionDriver` (new, engine-facing orchestration)
  - Owns setup progression state machine driving shared command sequence.
  - Handles decision request publication callbacks (through injected sink).
  - Handles authoritative command application and result fan-out.

- `CommandChannel` abstraction (new)
  - `InProcessCommandChannel`: local path, same-process command fan-out to UI/client facades.
  - `NetworkCommandChannel`: existing transport-backed channel for remote clients.

- Runtime compositions:
  - Local runner: one authoritative game + two local player facades via in-process channel.
  - Network runner: one authoritative game + remote clients via network channel.

The key difference between modes remains transport and player identity topology, not engine flow.

## PR Breakdown

## PR 1 - Extract Shared Authoritative Setup/Command Driver
### Scope
- Introduce a new shared orchestration module under `src/warhammer40k_ai/engine/` (or `src/warhammer40k_ai/runtime/` if preferred after review).
- Move setup-driving behavior currently embedded in `NetworkServer._run_setup_sequence()` into reusable driver methods.
- Keep existing network behavior unchanged by delegating from `NetworkServer` to the new driver.

### Deliverables
- New driver class with:
  - Setup phase progression orchestration.
  - Mission random selection hook injection.
  - Formation buffering orchestration hook points.
  - Command apply entrypoint using existing `handle_command_message`/`Game.apply_command` flow.
- Unit tests for driver sequencing logic with a fake command sink.

### Acceptance Criteria
- Network setup flow is behaviorally identical (same command order/events) pre/post extraction.
- No gameplay behavior regressions in setup-related tests.

### Tests
- Add focused driver tests.
- Run impacted tests:
  - `python -m pytest tests/test_network_server_client.py`
  - setup/decision tests impacted by formation flow.

### Docs
- Update `docs/NETWORK_DECISION_FLOW.md` with the new shared driver role.

## PR 2 - Introduce Channel Abstraction (In-Process + Network Adapters)
### Scope
- Define channel interfaces for command/event/decision fan-out.
- Implement network adapter wrapping existing broadcast/send behavior.
- Implement in-process adapter for local session without sockets.

### Deliverables
- New interface + adapters.
- Network server refactor to use `NetworkCommandChannel` internally.
- No `scripts/main.py` integration yet.

### Acceptance Criteria
- Network mode behavior remains unchanged.
- Channel interface supports both direct local subscribers and remote clients.

### Tests
- Adapter-level tests (network adapter via stubs, in-process adapter unit tests).
- Re-run `tests/test_network_server_client.py`.

### Docs
- Update `docs/NETWORK_GAMEPLAY.md` and `docs/NETWORK_SAVELOAD_DESIGN.md` (transport vs orchestration responsibility split).

## PR 3 - Local Runtime Migration to Shared Driver (No Loopback)
### Scope
- Add a local authoritative runtime composition used by `scripts/main.py`.
- Route local setup/phase advancement through the shared driver + in-process channel.
- Preserve local UI behavior while replacing bespoke orchestration branches.

### Deliverables
- New local runtime bootstrap helper used by `scripts/main.py`.
- Remove duplicated local setup advancement logic that bypasses shared orchestration.

### Acceptance Criteria
- `scripts/main.py` progresses setup/phases through same driver used by network server.
- No websocket usage in local mode.
- Manual phase controls and local deployment interactions continue to work.

### Tests
- Add local-runtime orchestration tests.
- Re-run impacted UI/decision tests (non-integration where possible).

### Docs
- Update `docs/ARCHITECTURE.md` and `docs/NETWORK_DECISION_FLOW.md` with local/runtime topology diagrams.

## PR 4 - Decision Controller Parity and De-duplication
### Scope
- Unify duplicate auto-dice decision handling currently split between network session and network decision controller pathways.
- Ensure one reusable decision-controller component is used in both local and network compositions where appropriate.

### Deliverables
- Shared auto-dice decision controller location/API.
- Removal of duplicated logic branches.

### Acceptance Criteria
- Dice roll decision behavior and authority checks unchanged.
- Decision recording remains schema-compliant.

### Tests
- Decision-record and dice decision tests:
  - `tests/test_decision_record_logging.py`
  - `tests/test_decision_record_replay.py`
  - dice-related decision tests.

### Docs
- Update `docs/DECISION_RECORD_TELEMETRY.md` if call path metadata changes.

## PR 5 - End-to-End Parity Hardening and Cleanup
### Scope
- Remove obsolete orchestration paths.
- Add regression coverage asserting local and network runtimes share equivalent authoritative command sequencing for setup milestones.
- Final cleanup of temporary compatibility scaffolding introduced in prior PRs.

### Deliverables
- Parity regression tests (golden command/event sequence snapshots for setup milestones).
- Finalized runtime API surface.

### Acceptance Criteria
- Local and network modes use the same core orchestration entrypoints.
- No known setup/decision flow divergence remains outside transport/topology concerns.

### Tests
- Run full suite due cross-cutting runtime changes:
  - `python -m pytest tests/`

### Docs
- Finalize:
  - `docs/ARCHITECTURE.md`
  - `docs/NETWORK_GAMEPLAY.md`
  - `docs/NETWORK_DECISION_FLOW.md`
  - `docs/NETWORK_SAVELOAD_DESIGN.md`

## Risks and Mitigations
- Risk: hidden behavior coupling in existing server setup loop.
  - Mitigation: PR 1 preserves behavior by extraction-first, no semantic changes.
- Risk: local UI assumptions about direct `Game` calls.
  - Mitigation: PR 3 keeps UI contracts stable while changing orchestration backend only.
- Risk: event ordering drift.
  - Mitigation: add command/event sequence parity tests before final cleanup.

## Rollout Strategy
- Merge PRs sequentially; do not batch.
- Require green impacted tests per PR.
- Run full `tests/` at PR 5 before declaring migration complete.

## Open Decisions for Developer Confirmation
- Preferred module location for shared driver (`engine/` vs `network/` vs new `runtime/`).
- Whether to model local mode as two explicit local client facades, or a simpler single-process controller pair over the same in-process channel.

## Implementation Checklist
- [ ] PR 1 merged: shared driver extraction with no behavior change.
- [ ] PR 2 merged: channel abstraction in place, network adapter migrated.
- [ ] PR 3 merged: local runner migrated to shared driver without loopback.
- [ ] PR 4 merged: decision-controller de-duplication complete.
- [ ] PR 5 merged: parity regression coverage + cleanup + docs finalized.
