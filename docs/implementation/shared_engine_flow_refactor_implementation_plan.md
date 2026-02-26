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
- Preserve strict engine/UI dependency boundaries (engine remains UI-agnostic).
- No local network loopback for `scripts/main.py`.
- Preserve deterministic command/event behavior and replay compatibility.
- Preserve explicit player authority boundaries in network mode.
- Preserve strict player-scoped visibility/redaction rules for projected HUD state.
- Ensure reconnect/save-load/late-join flows rebuild equivalent HUD state from snapshot + transcript.
- Ensure reconnect while a decision is pending restores the same chooser/candidates/mask/prompt state.
- Define and enforce replay/save compatibility policy for presentation schema and artifacts.
- Meet explicit projection/hydration performance and payload-size budgets.
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
  - Emits monotonic per-stream sequence metadata to support idempotent client application.

- `PresentationStateHydrator` (new, shared state rebuild path)
  - Rebuilds HUD/view-model state from authoritative snapshot + event log for reconnect/save-load/late-join.
  - Uses the same projection logic and schema as live session updates.
  - Rebuilds pending-decision UI state (chooser, candidates, mask, prompt payload) exactly.

- `PlayerIntentGateway` (new, shared UI action intake)
  - Normalizes local HUD interactions and network client actions into the same serializable decision/action payloads.
  - Preserves authority checks while preventing local-only action bypass paths.
  - Preserves DecisionRecord invariants for valid and invalid attempts.

- Runtime compositions:
  - Local runner: one authoritative game + in-process command channel + shared presentation orchestrator + two explicit local client facades + local HUD sink(s).
    - Authoritative orchestration runs on a single deterministic loop (no threaded authoritative state mutation).
    - Any optional UI/render threading is read-only and must dispatch actions through `PlayerIntentGateway`.
  - Network runner: one authoritative game + network command channel + shared presentation orchestrator + remote HUD/client sinks.

The key difference between modes remains transport and player identity topology, not engine flow or presentation flow.

### Boundary Rules
- Engine modules (`src/warhammer40k_ai/engine/**`) must not import UI/presentation modules.
- Presentation modules in `src/warhammer40k_ai/ui/**` consume engine outputs and map them to serializable payloads, but do not embed new rules logic.

## PR Breakdown

## PR 1 - Extract Shared Authoritative Setup/Command Driver
### Scope
- Introduce a new shared orchestration module under `src/warhammer40k_ai/engine/`.
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
- Define HUD payload ordering/idempotency contract (`stream_id`, `sequence_id`, duplicate/drop and gap handling semantics).
- Adopt schema policy: `major.minor`; major mismatch is fail-fast, minor increments are additive-only.

### Deliverables
- New interface + adapters.
- Network server refactor to use `NetworkCommandChannel` internally.
- Presentation payload schema artifact + validators.
- Ordering/idempotency contract doc + adapter plumbing for sequence metadata.
- No `scripts/main.py` integration yet.

### Acceptance Criteria
- Network mode behavior remains unchanged.
- Channel interface supports both direct local subscribers and remote clients.
- Channel payloads are sufficient for deterministic HUD projection without runtime-specific branches.
- Presentation payloads include explicit schema version and pass strict validation in both local and network paths.
- Client-side application semantics are idempotent for duplicates and deterministic for out-of-order/gap handling.
- Schema compatibility behavior matches policy (`major` mismatch reject, `minor` additive accepted).

### Tests
- Adapter-level tests (network adapter via stubs, in-process adapter unit tests).
- Schema encode/decode round-trip and validation failure-path tests.
- Ordering/idempotency tests (duplicate message, out-of-order delivery, gap detection/resync trigger).
- Re-run `tests/test_network_server_client.py`.

### Docs
- Update `docs/NETWORK_GAMEPLAY.md` and `docs/NETWORK_SAVELOAD_DESIGN.md` (transport vs orchestration responsibility split).
- Add/Update schema contract documentation for presentation payloads.
- Add ordering/idempotency contract details to `docs/NETWORK_GAMEPLAY.md`.
- Document schema version policy and bump rules in presentation schema docs.

## PR 3 - Local Runtime Migration to Shared Driver (No Loopback)
### Scope
- Add a local authoritative runtime composition used by `scripts/main.py`.
- Route local setup/phase advancement through the shared driver + in-process channel.
- Preserve local UI behavior while replacing bespoke orchestration branches.
- Model local mode as two explicit local client facades over the shared in-process channel (no network loopback).

### Deliverables
- New local runtime bootstrap helper used by `scripts/main.py`.
- Remove duplicated local setup advancement logic that bypasses shared orchestration.

### Acceptance Criteria
- `scripts/main.py` progresses setup/phases through same driver used by network server.
- No websocket usage in local mode.
- Manual phase controls and local deployment interactions continue to work.
- Local runtime consumes the same event envelope contract that network runtime uses.
- Local path remains engine/UI boundary compliant (no UI imports into engine modules).
- Local runtime uses one authoritative loop; no threaded direct mutation of authoritative game/session state.

### Tests
- Add local-runtime orchestration tests.
- Add import-boundary tests asserting engine modules do not import UI/presentation modules.
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
- Keep visibility/redaction policy ownership in the shared `ui/` projection layer, applied before network send.

### Deliverables
- Shared presentation orchestrator + projection interfaces.
- Canonical HUD update/prompt payload schema usable by local and remote clients.
- Local and network sink adapters that consume identical presentation payloads.
- Shared redaction policy implementation and projection filters.
- Explicit redaction policy module under `src/warhammer40k_ai/ui/` used by both local and network projection paths.
- Dialog-to-decision mapping table coverage for all migrated HUD prompts.
- Removal (or deprecation) of duplicate local/network HUD orchestration branches.

### Acceptance Criteria
- Equivalent command/event transcripts produce equivalent HUD state/prompt sequences in local and network modes.
- New HUD elements can be added in one projection path and appear in both runtimes.
- HUD bugfixes in projection/orchestration logic apply to both local and networked play without duplicate patches.
- UI dialog-to-decision mappings remain deterministic and serializable.
- Hidden information is never projected to unauthorized players in either runtime.
- Optional choice dialogs follow one-step selection with explicit `None` candidate; no split Yes/No + selection flows.
- Projection modules remain outside engine package boundaries; no reverse dependency from engine to presentation layer.

### Tests
- Add HUD projection determinism tests.
- Add parity tests that replay the same transcript through local and network compositions and compare HUD outputs.
- Add player-visibility redaction tests (authorized vs unauthorized projection payloads).
- Add dialog mapping tests confirming deterministic action payloads and `None` path handling.
- Add static import-boundary regression tests for engine->UI/presentation dependency direction.
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
- Add explicit reconnect-while-pending-decision parity checks (chooser/candidates/mask/prompt content).
- Add shadow/diff cutover stage comparing legacy vs shared HUD projection prior to legacy-path removal.
- Define replay/save compatibility policy and enforce it in load/replay paths (current-version-only fail-fast for this phase).
- Add performance regression gates for projection latency, hydration latency, and payload size.
- Final cleanup of temporary compatibility scaffolding introduced in prior PRs.

### Deliverables
- Parity regression tests (golden command/event sequence snapshots for setup milestones).
- HUD parity regression tests (golden prompt/view-model sequence snapshots for representative phases).
- Reconnect/save-load/late-join HUD hydration parity tests.
- Pending-decision reconnect parity tests.
- Shadow projection diff tooling/report for cutover gating.
- Replay/save compatibility policy doc + fixtures (current-version success + unsupported-version deterministic fail-fast fixtures).
- Performance baseline report and regression tests/benchmarks for agreed scenarios.
- Finalized runtime API surface.

### Acceptance Criteria
- Local and network modes use the same core orchestration entrypoints.
- No known setup/decision/HUD presentation divergence remains outside transport/topology concerns.
- Rehydrated HUD state matches live-projected HUD state for the same authoritative history.
- Pending-decision reconnect restores the same actionable decision surface before input resumes.
- Shadow/diff run across representative scenarios shows no material divergence before legacy orchestration is removed.
- Replay/save compatibility behavior is explicit, tested, and deterministic (current-version-only success + fail-fast on unsupported versions).
- Performance budgets are met in CI reference scenarios:
  - HUD projection p95 <= 10 ms per authoritative event (reference transcript).
  - Reconnect hydration <= 750 ms for reference snapshot + 2,000-event transcript.
  - Serialized HUD payload size <= 64 KiB p95 per update (pre-transport compression).
  - Budgets measured on pinned CI runner class using a fixed reference transcript fixture.

### Tests
- Run full suite due cross-cutting runtime changes:
  - `python -m pytest tests/`
- Run dedicated performance and compatibility checks:
  - `python -m pytest tests/ -m "integration" -k "hud and (performance or hydration or reconnect or compatibility)"`

### Docs
- Finalize:
  - `docs/ARCHITECTURE.md`
  - `docs/NETWORK_GAMEPLAY.md`
  - `docs/NETWORK_DECISION_FLOW.md`
  - `docs/NETWORK_SAVELOAD_DESIGN.md`
  - `docs/DECISION_RECORD_REPLAY.md`
  - `docs/STATE_BLOB_SCHEMA.md`
  - Add replay/save compatibility policy section (current-version-only fail-fast) and schema versioning policy notes.

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
- Risk: engine/UI boundary erosion during refactor.
  - Mitigation: static import-boundary tests and review gate in PR 3/PR 4.
- Risk: duplicate/out-of-order network delivery causes HUD divergence.
  - Mitigation: sequence/idempotency contract + adapter tests in PR 2 and parity tests in PR 6.
- Risk: pending-decision reconnect mismatch leads to invalid or stale choices.
  - Mitigation: explicit pending-decision hydration contract and parity tests in PR 6.
- Risk: performance regression from shared projection layer.
  - Mitigation: explicit budgets + perf regression checks in PR 6.
- Risk: replay/save compatibility ambiguity at rollout.
  - Mitigation: written current-version-only policy + fixture tests and deterministic version gating in PR 6.
- Risk: cutover regressions when removing legacy HUD path.
  - Mitigation: PR 6 shadow/diff gating before deleting legacy code.
- Risk: event ordering drift.
  - Mitigation: add command/event and HUD parity sequence tests before final cleanup.

## Rollout Strategy
- Merge PRs sequentially; do not batch.
- Require green impacted tests per PR.
- Run shadow projection diff in representative scenarios before removing legacy HUD path.
- Require boundary, ordering/idempotency, compatibility, and performance gates to pass before legacy HUD path removal.
- Run full `tests/` at PR 6 before declaring migration complete.

## Resolved Defaults
- Shared driver module location: `src/warhammer40k_ai/engine/`.
- Local topology: two explicit local client facades over in-process channel with one non-threaded authoritative loop.
- HUD projection/redaction/schema module home: `src/warhammer40k_ai/ui/`.
- Presentation schema version policy: `major.minor`; major mismatch fail-fast, minor additive-only.
- Visibility/redaction ownership: shared `ui/` projection layer, applied before outbound network emission.
- Replay/save compatibility policy for this refactor phase: current-version-only with deterministic fail-fast on unsupported versions.
- Performance gating policy: fixed reference transcript fixture on pinned CI runner class for budget enforcement.

## Implementation Checklist
- [ ] PR 1 merged: shared driver extraction with no behavior change.
- [ ] PR 2 merged: channel abstraction + versioned presentation schema/validation + ordering/idempotency contract in place.
- [ ] PR 3 merged: local runner migrated to shared driver without loopback + engine/UI boundary tests passing.
- [ ] PR 4 merged: shared UI/HUD orchestration + redaction + dialog mapping parity in place for local + network.
- [ ] PR 5 merged: decision-controller de-duplication + DecisionRecord parity for UI intents complete.
- [ ] PR 6 merged: parity regression + pending-decision reconnect parity + compatibility/perf gates + shadow-diff cutover + cleanup + docs finalized.
