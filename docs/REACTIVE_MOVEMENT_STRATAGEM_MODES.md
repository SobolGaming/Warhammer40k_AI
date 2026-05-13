# Reactive Movement And Stratagem Modes

Status: preview infrastructure for PR-014I. This document describes generic engine
surfaces only; it does not promote any preview faction-focus rule to live release data.

## Reactive Move Specs

`ReactiveMoveSpec` in `src/warhammer40k_ai/engine/reactive_movement.py` is the
serializable contract for preview reactive movement. It records the trigger window,
source unit, target reference, move kind, max-distance expression, destination policy,
end-state policy, profile gate, and source provenance.

The spec maps to one of three decision kinds:

- `REACTIVE_MOVE` for normal and fallback-like reactive movement.
- `SURGE_MOVE` for surge movement with directional constraints.
- `SELECT_REACTIVE_RESERVE_EXIT` for effects that remove a unit from the battlefield
  and place it into Strategic Reserves.

The reserve-exit path is represented by `ReactiveReserveExitTransition`, which records
reserve-status state changes and reason traces. It is not a `MOVE_UNIT` placement
payload and does not synthesize model positions.

## Stratagem Modes

`StratagemMode` records a mode id, CP delta, charge-target policy, optional roll cap,
profile gate, provenance, and arbitrary serializable payload. Generic modal stratagems
use `SELECT_STRATAGEM_MODE`; Heroic Intervention variants use
`SELECT_HEROIC_INTERVENTION_MODE` so charge schedulers can identify the policy before
charge resolution.

## Ledger Exceptions

`StratagemApplicationLedger` supports explicit phase-scoped repeat exceptions through
`StratagemUseException`. An exception can allow another use of a named stratagem in the
phase, but the ledger still blocks re-applying tracked stratagems to the same target
unit. Every evaluation returns a reason trace for replay and audit.

## Preview Gate

All PR-014I helper requests carry `preview_gated=true` unless their profiles are
explicitly marked `current`. Tests under `tests/preview_11e/` exercise generic mechanics
without requiring final 11e faction packs.
