# Shared Engine Flow Refactor Implementation Plan

## Objective
Unify engine execution flow between:
- Local runner (`scripts/main.py`)
- Networked server/client gameplay (`src/warhammer40k_ai/network/*`)

Both modes should run through the same authoritative command/decision pipeline and the same UI/HUD orchestration pipeline wherever possible, with no network loopback in local mode.

## Problem Summary
Today, command and decision dispatch are already shared (`Game.apply_command`, command/decision dispatchers), but orchestration diverges:
- Local mode advances setup/phases directly from UI loop semantics.
- Network mode has additional server orchestration logic for setup, decision broadcasts, and buffering.
- UI/HUD updates and prompts are not consistently projected from one shared orchestration surface, so local and network flows can drift in behavior.

This creates behavior skew risk, duplicate setup flow logic, and duplicate UI/HUD maintenance where bugfixes or new HUD features can land in only one runtime.

## Design Goals
- One authoritative orchestration path for setup and turn progression.
- One decision lifecycle across local and networked modes.
- One shared UI/HUD projection path across local and networked modes.
- One versioned, validated presentation payload schema used by both local and network runtimes.
- No local network loopback for `scripts/main.py`.
- Preserve deterministic command/event behavior and replay compatibility.
- Preserve explicit player authority boundaries in network mode.
- Preserve strict player-scoped visibility/redaction rules for projected HUD state.
- Ensure reconnect/save-load/late-join flows rebuild equivalent HUD state from snapshot + transcript.
- Ensure new UI/HUD elements and bugfixes are implemented once and applied to both modes.

## Non-Goals
- No changes to game rules behavior.
- No new decision kinds.
- No protocol rewrite for lobby/auth transport.
- No AI policy/model changes.
- No visual redesign of HUD styling/layout in this refactor.

## Target Architecture
Introduce a shared authoritative session driver abstraction used by both runtime modes:

- `AuthoritativeSessionDriver` (new, engine-facing orchestration)
  - Owns setup progression state machine driving shared command sequence.
  - Handles decision request publication callbacks (through injected sink).
  - Handles authoritative command application and result fan-out.

- `CommandChannel` abstraction (new)
  - `InProcessCommandChannel`: local path, same-process command fan-out to UI/client facades.
  - `NetworkCommandChannel`: existing transport-backed channel for remote clients.

- `SessionPresentationOrchestrator` (new, shared UI/HUD orchestration)
  - Consumes authoritative command/event/decision outputs.
  - Produces deterministic HUD/view-model state updates and UI prompt descriptors.
  - Applies per-player visibility/redaction before emission.
  - Emits the same versioned presentation payload contract to local HUD and network clients.

- `PresentationStateHydrator` (new, shared state rebuild path)
  - Rebuilds HUD/view-model state from authoritative snapshot + event log for reconnect/save-load/late-join.
  - Uses the same projection logic and schema as live session updates.

- `PlayerIntentGateway` (new, shared UI action intake)
  - Normalizes local HUD interactions and network client actions into the same serializable decision/action payloads.
  - Preserves authority checks while preventing local-only action bypass paths.
  - Preserves DecisionRecord invariants for valid and invalid attempts.

- Runtime compositions:
  - Local runner: one authoritative game + in-process command channel + shared presentation orchestrator + local HUD sink(s).
  - Network runner: one authoritative game + network command channel + shared presentation orchestrator + remote HUD/client sinks.

The key difference between modes remains transport and player identity topology, not engine flow or presentation flow.

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
- No UI/HUD behavior changes introduced in this extraction PR.

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
- Define event envelope contract needed by shared presentation orchestration.
- Define versioned presentation payload schema and strict encode/decode validation boundaries.

### Deliverables
- New interface + adapters.
- Network server refactor to use `NetworkCommandChannel` internally.
- Presentation payload schema artifact + validators.
- No `scripts/main.py` integration yet.

### Acceptance Criteria
- Network mode behavior remains unchanged.
- Channel interface supports both direct local subscribers and remote clients.
- Channel payloads are sufficient for deterministic HUD projection without runtime-specific branches.
- Presentation payloads include explicit schema version and pass strict validation in both local and network paths.

### Tests
- Adapter-level tests (network adapter via stubs, in-process adapter unit tests).
- Schema encode/decode round-trip and validation failure-path tests.
- Re-run `tests/test_network_server_client.py`.

### Docs
- Update `docs/NETWORK_GAMEPLAY.md` and `docs/NETWORK_SAVELOAD_DESIGN.md` (transport vs orchestration responsibility split).
- Add/Update schema contract documentation for presentation payloads.

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
- Local runtime consumes the same event envelope contract that network runtime uses.

### Tests
- Add local-runtime orchestration tests.
- Re-run impacted UI/decision tests (non-integration where possible).

### Docs
- Update `docs/ARCHITECTURE.md` and `docs/NETWORK_DECISION_FLOW.md` with local/runtime topology diagrams.

## PR 4 - Introduce Shared UI/HUD Orchestration Path
### Scope
- Add `SessionPresentationOrchestrator` and migrate HUD/view-model updates to it.
- Replace runtime-specific HUD prompt/update branches with shared projection logic.
- Route both local HUD and network client HUD updates through shared presentation payloads.
- Add `PlayerIntentGateway` so HUD actions enter the same decision/action pipeline in both modes.
- Enforce per-player visibility/redaction in shared projection path.
- Enforce deterministic dialog-to-decision mapping for optional choices (single selection dialog with explicit `None` option).

### Deliverables
- Shared presentation orchestrator + projection interfaces.
- Canonical HUD update/prompt payload schema usable by local and remote clients.
- Local and network sink adapters that consume identical presentation payloads.
- Shared redaction policy implementation and projection filters.
- Dialog-to-decision mapping table coverage for all migrated HUD prompts.
- Removal (or deprecation) of duplicate local/network HUD orchestration branches.

### Acceptance Criteria
- Equivalent command/event transcripts produce equivalent HUD state/prompt sequences in local and network modes.
- New HUD elements can be added in one projection path and appear in both runtimes.
- HUD bugfixes in projection/orchestration logic apply to both local and networked play without duplicate patches.
- UI dialog-to-decision mappings remain deterministic and serializable.
- Hidden information is never projected to unauthorized players in either runtime.
- Optional choice dialogs follow one-step selection with explicit `None` candidate; no split Yes/No + selection flows.

### Tests
- Add HUD projection determinism tests.
- Add parity tests that replay the same transcript through local and network compositions and compare HUD outputs.
- Add player-visibility redaction tests (authorized vs unauthorized projection payloads).
- Add dialog mapping tests confirming deterministic action payloads and `None` path handling.
- Re-run impacted UI/HUD and decision tests.

### Docs
- Update `docs/NETWORK_SAVELOAD_DESIGN.md` with any new/changed UI dialog-to-decision mappings.
- Update `docs/NETWORK_GAMEPLAY.md` and `docs/ARCHITECTURE.md` with shared presentation flow.

## PR 5 - Decision Controller Parity and De-duplication
### Scope
- Unify duplicate auto-dice decision handling currently split between network session and network decision controller pathways.
- Ensure one reusable decision-controller component is used in both local and network compositions where appropriate.
- Ensure `PlayerIntentGateway` and decision controller integration preserve deterministic candidate ordering/action ids and DecisionRecord semantics.

### Deliverables
- Shared auto-dice decision controller location/API.
- Shared decision-intake path for HUD-originated actions (local + network).
- Removal of duplicated logic branches.

### Acceptance Criteria
- Dice roll decision behavior and authority checks unchanged.
- Decision recording remains schema-compliant.
- UI-originated valid actions and rejected invalid attempts both produce schema-valid DecisionRecords with actionable rejection reasons.

### Tests
- Decision-record and dice decision tests:
  - `tests/test_decision_record_logging.py`
  - `tests/test_decision_record_replay.py`
  - dice-related decision tests.
- Add valid/invalid UI-intent ingestion tests for both local and network compositions.

### Docs
- Update `docs/DECISION_RECORD_TELEMETRY.md` and `docs/DECISION_RECORD_REPLAY.md` if call path metadata changes.

## PR 6 - End-to-End Parity Hardening and Cleanup
### Scope
- Remove obsolete orchestration paths.
- Add regression coverage asserting local and network runtimes share equivalent authoritative command sequencing for setup milestones.
- Add regression coverage asserting local and network runtimes share equivalent HUD prompt/update sequencing for the same authoritative transcript.
- Add reconnect/save-load/late-join hydration parity checks using snapshot + transcript replay.
- Add shadow/diff cutover stage comparing legacy vs shared HUD projection prior to legacy-path removal.
- Final cleanup of temporary compatibility scaffolding introduced in prior PRs.

### Deliverables
- Parity regression tests (golden command/event sequence snapshots for setup milestones).
- HUD parity regression tests (golden prompt/view-model sequence snapshots for representative phases).
- Reconnect/save-load/late-join HUD hydration parity tests.
- Shadow projection diff tooling/report for cutover gating.
- Finalized runtime API surface.

### Acceptance Criteria
- Local and network modes use the same core orchestration entrypoints.
- No known setup/decision/HUD presentation divergence remains outside transport/topology concerns.
- Rehydrated HUD state matches live-projected HUD state for the same authoritative history.
- Shadow/diff run across representative scenarios shows no material divergence before legacy orchestration is removed.

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
- Risk: HUD currently relies on runtime-specific update branches.
  - Mitigation: PR 4 introduces one shared presentation orchestrator and parity tests.
- Risk: hidden-info leakage through shared payloads.
  - Mitigation: enforce projection-time redaction + player-scoped tests in PR 4.
- Risk: schema drift between runtime producers/consumers.
  - Mitigation: versioned schema + strict validation and round-trip tests in PR 2.
- Risk: cutover regressions when removing legacy HUD path.
  - Mitigation: PR 6 shadow/diff gating before deleting legacy code.
- Risk: event ordering drift.
  - Mitigation: add command/event and HUD parity sequence tests before final cleanup.

## Rollout Strategy
- Merge PRs sequentially; do not batch.
- Require green impacted tests per PR.
- Run shadow projection diff in representative scenarios before removing legacy HUD path.
- Run full `tests/` at PR 6 before declaring migration complete.

## Open Decisions for Developer Confirmation
- Preferred module location for shared driver (`engine/` vs `network/` vs new `runtime/`).
- Whether to model local mode as two explicit local client facades, or a simpler single-process controller pair over the same in-process channel.
- Canonical home for HUD projection schemas (`ui/`, `runtime/`, or dedicated `presentation/` module) while keeping engine/UI boundaries clean.
- Versioning policy for presentation payload schema (strict bump rules and deprecation window expectations).
- Canonical ownership point for visibility/redaction policy definitions.

## Implementation Checklist
- [ ] PR 1 merged: shared driver extraction with no behavior change.
- [ ] PR 2 merged: channel abstraction + versioned presentation schema/validation in place.
- [ ] PR 3 merged: local runner migrated to shared driver without loopback.
- [ ] PR 4 merged: shared UI/HUD orchestration + redaction + dialog mapping parity in place for local + network.
- [ ] PR 5 merged: decision-controller de-duplication + DecisionRecord parity for UI intents complete.
- [ ] PR 6 merged: parity regression coverage + hydration parity + shadow-diff cutover + cleanup + docs finalized.
