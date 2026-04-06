# Pregame Setup Flow

Status: Current implementation after PR-006 (April 2026)

This document describes the explicit pregame state model now exposed by the engine.
It does not treat preview-era 11th-edition sequencing text as finalized rules content.
Instead, it records the announced structure as explicit step data while keeping the
current live runtime and network command flow stable.

## Goals

- Make setup progression explicit and testable instead of inferring it from `SetupPhase` enum arithmetic.
- Preserve the current public/runtime entrypoints:
  - `Game.is_in_setup_phase()`
  - `Game.get_current_setup_phase()`
  - `Game.advance_setup_phase()`
  - `Game.execute_current_setup_phase()`
- Keep `game.py` and `player.py` as façade modules while moving setup/runtime logic into focused modules.

## Engine Modules

PR-005 moved the extracted responsibilities into:

- `src/warhammer40k_ai/engine/game_setup_flow.py`
- `src/warhammer40k_ai/engine/game_phase_flow.py`
- `src/warhammer40k_ai/engine/game_decision_runtime.py`
- `src/warhammer40k_ai/engine/game_scoring.py`
- `src/warhammer40k_ai/engine/game_serialization.py`
- `src/warhammer40k_ai/roster/player_control.py`
- `src/warhammer40k_ai/roster/player_resources.py`
- `src/warhammer40k_ai/roster/player_scoring.py`
- `src/warhammer40k_ai/roster/player_missions.py`
- `src/warhammer40k_ai/roster/player_ui.py`

## Explicit Pregame Steps

The engine now exposes `Game.get_pregame_flow_state()`, which returns an ordered
pregame step list with one of four statuses per step:

- `current`: active step right now
- `completed`: resolved in the current runtime
- `pending`: not reached yet
- `stubbed`: explicit placeholder step that is not fully implemented yet

Current ordered steps:

1. `muster_armies`
2. `determine_mission`
3. `determine_deployment`
4. `optional_twist`
5. `create_battlefield`
6. `determine_attacker_and_defender`
7. `select_secondary_missions`
8. `declare_battle_formations`
9. `deploy_armies`
10. `redeploy_units`
11. `determine_first_turn_order`
12. `resolve_prebattle_rules`

The first seven steps are the explicit preview-aligned pregame model.
Steps 8-12 are the legacy compatibility tail that still reflects the current runtime.

## Declare Battle Formations Attachment Seeding

`DECLARE_BATTLE_FORMATIONS` now has an explicit build/runtime attachment seam:

- If an army carries authored `AttachmentBinding` records that can be matched to
  runtime units through `build_entry_id`, those bindings are applied first.
- `ATTACH_LEADER` and `ATTACH_SUPPORT_ARTILLERY` decisions are then queued only for
  unresolved units.
- This keeps the current live flow intact for parsed lists and other rosters
  that did not author attachments at list-build time, while allowing optional
  build-authored bindings to pre-seed runtime setup.

## Mapping To Current `SetupPhase`

The explicit step model intentionally keeps the existing `SetupPhase` enum stable.

| Pregame step | Current engine anchor |
|---|---|
| `muster_armies` | `SetupPhase.MUSTER_ARMIES` |
| `determine_mission` | `SetupPhase.SELECT_MISSION_OBJECTIVES` |
| `determine_deployment` | Derived from compiled mission-pack data during `SELECT_MISSION_OBJECTIVES` |
| `optional_twist` | Explicit twist state during `SELECT_MISSION_OBJECTIVES` (completed for "no twist", stubbed for provisional placeholders) |
| `create_battlefield` | `SetupPhase.CREATE_BATTLEFIELD` |
| `determine_attacker_and_defender` | `SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER` |
| `select_secondary_missions` | Stubbed placeholder after attacker/defender resolution |
| `declare_battle_formations` | `SetupPhase.DECLARE_BATTLE_FORMATIONS` |
| `deploy_armies` | `SetupPhase.DEPLOY_ARMIES` |
| `redeploy_units` | `SetupPhase.REDEPLOY_UNITS` |
| `determine_first_turn_order` | `SetupPhase.DETERMINE_FIRST_TURN_ORDER` |
| `resolve_prebattle_rules` | `SetupPhase.RESOLVE_PREBATTLE_RULES` |

## Driver-Managed Phases

The shared authoritative/local setup driver still auto-runs only the currently
implemented pre-formation phases:

- `MUSTER_ARMIES`
- `SELECT_MISSION_OBJECTIVES`
- `CREATE_BATTLEFIELD`
- `DETERMINE_ATTACKER_AND_DEFENDER`

That set is now sourced from `game_setup_flow.driver_managed_setup_phases()`
instead of being duplicated locally.

## Provisional Preview Steps

Three preview-era steps are now explicit even though the runtime is not yet a full
11th-edition mission/deployment implementation:

- `determine_deployment`: derived from compiler-selected `DeploymentDefinition` data.
- `optional_twist`: explicit state is recorded from the selected mission pack. Current Chapter Approved
  entries resolve this step as "no twist"; provisional preview entries still remain stubbed.
- `select_secondary_missions`: explicit placeholder only; current secondary handling still starts from
  command-phase deck draw / current mode flags.

This is deliberate. The step model records the intended pregame structure without
hard-coding preview content as final release canon.

## Save/Load And Replay

The explicit pregame step model is derived from serialized setup state that already
round-trips in snapshots:

- `setup_phase`
- `setup_complete`
- `selected_mission_info`
- `secondary_mission_mode`

That means save/load and replay continue to work through the new setup-flow
extraction without requiring a separate snapshot schema for the step graph.
