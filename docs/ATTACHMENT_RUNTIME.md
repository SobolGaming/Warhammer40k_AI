# Attachment Runtime

Status: Current implementation after PR-008 (April 2026)

This document describes the current attachment build/runtime seam.
The engine is still running the 10th-edition pregame flow, so build-authored
attachment bindings are supported as an optional setup input, not a mandatory roster rule.

## Scope

- Leader and joined-support relationships remain explicit runtime state on `Unit`.
- Build-time `AttachmentBinding` records can now be projected into runtime setup when
  matching runtime units are available.
- The existing `DECLARE_BATTLE_FORMATIONS` decision flow remains the fallback path for
  unresolved attachments.

## Runtime Modules

- `src/warhammer40k_ai/roster/army_attachment_runtime.py`
- `src/warhammer40k_ai/units/unit_mixins/attachment_runtime_mixin.py`
- `src/warhammer40k_ai/units/unit_mixins/state_attachment_mixin.py`

`army.py` and `unit.py` remain the stable facades. Attachment-specific orchestration now
lives in the focused roster/unit modules above.

## Build To Runtime Mapping

- `AttachmentBinding` continues to live in the build-side army model.
- Runtime units now carry optional `build_entry_id` values.
- Parsed lists assign deterministic `parsed_unit_*` entry ids so parsed armies can
  participate in the same attachment-binding seam.
- `Army.apply_authored_attachment_bindings()` resolves build entry ids to runtime units
  and applies any matching Leader or joined-support relationships.

If no authored bindings are present, or if a roster source does not author them,
runtime attachment choice still happens through the existing setup decisions.

## Declare Battle Formations Behavior

At the start of `DECLARE_BATTLE_FORMATIONS`:

1. Army-level formation restrictions are applied.
2. Authored attachment bindings are applied when present.
3. `ATTACH_LEADER` and `ATTACH_SUPPORT_ARTILLERY` decisions are built only for units
   that are still unresolved.

This means current 10th-edition lists keep working without any roster-format change,
while optional 11th-style pre-authored bindings can already pre-seed runtime state.

## Validation Rules

- Leader attachment validation is centralized in `army_attachment_runtime.py`.
- Joined-support validation is also centralized there.
- Mandatory joined-support units now fail with a clear error when an eligible bodyguard
  exists but the unit was neither attached during `DECLARE_BATTLE_FORMATIONS` nor
  supplied by an authored attachment binding.

## Bodyguard Death

Attachment teardown remains runtime-driven:

- a dead bodyguard detaches surviving Leaders instead of deleting their unit state
- joined-support detach state is explicit

This keeps character-owned abilities and later runtime state available after the joined
bodyguard unit is removed.

## Replay And Snapshots

- Army snapshot state already preserves build-side `attachment_bindings`.
- Runtime units preserve `build_entry_id` and attachment relationships.
- Snapshot/replay round-trips therefore retain authored attachment state across load.
