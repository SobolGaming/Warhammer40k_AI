# Mission Selection Dialog

## Overview
The Mission Selection Dialog is used during the `SELECT_MISSION_OBJECTIVES` setup phase to pick
one compiled mission-pack entry (primary + deployment + terrain layout).

The data source is the authoritative `DECISION_CHOOSE_MISSION` request built from
`src/warhammer40k_ai/engine/mission_selection.py`. The dialog no longer owns a hard-coded
mission table.

## UI behavior
- Scrollable list of mission entries with `ID`, `Pack`, `Primary Mission`, `Deployment`,
  and layout buttons
- Terrain layout buttons per row
- Buttons: Cancel, Pick Random, Confirm
- Keyboard:
  - `Esc` cancel
  - `Enter` confirm
  - `R` pick random
  - Up/Down arrows scroll
- Mouse wheel scrolls the list
- `Pick Random` only chooses from entries marked random-eligible by the mission pack
  metadata. At present that keeps UI random selection on Chapter Approved 2025-26.

## Combination payload
Each entry is:
```python
{
    "id": "A",
    "pack_id": "chapter_approved_2025_2026",
    "pack_short_name": "CA25-26",
    "primary": "Take and Hold",
    "mission_definition_id": "chapter_approved_a",
    "deployment": "Tipping Point",
    "deployment_definition_id": "tipping_point",
    "layouts": [1, 2, 4, 6, 7, 8],
    "secondary_rule_set_id": "chapter_approved_2025_2026",
    "twist_definition_id": "none",
    "random_selection_enabled": True,
}
```

## Integration points
- `PhaseManager._show_mission_selection_dialog` wraps the dialog with
  `MissionSelectionModal` (callback adapter).
- On confirm, the handler:
  - resolves the authoritative mission decision option
  - stores compiled mission metadata in `game.selected_mission_info`
  - assigns the selected primary mission card to both players
- On cancel, the UI resolves the compiler default:
  `CA25-26 / M: Purge the Foe / Crucible of Battle / Layout 1`.
- `Game.execute_create_battlefield_phase` uses `selected_mission_info` to pick
  deployment zones and the terrain layout.
- `Game.execute_select_mission_objectives_phase` uses the same compiler default when no explicit
  choice exists yet, so UI, local runtime, and server auto-setup stay aligned.

## Mission actions (shooting dialog)
When `ShootingDeclarationDialog.allow_actions` is true, action buttons are shown:
- Terraform (`game.can_start_terraform` / `game.start_terraform_action`)
- Sabotage (`game.can_start_sabotage` / `game.start_sabotage_action`)
- Burn Objective (`game.can_start_burn_objective` / `game.start_burn_objective_action`)
- The Ritual (opens a point picker; uses `game.can_start_the_ritual`)
- Move Hazard (opens hazard selection; uses `game.can_start_move_hazard`)

## Files
- `src/warhammer40k_ai/UI/dialogs/mission_selection_dialog.py`
- `src/warhammer40k_ai/UI/dialogs/mission_selection_modal.py`
- `src/warhammer40k_ai/UI/phases/phase_manager.py`
- `src/warhammer40k_ai/engine/mission_cards.py`
- `src/warhammer40k_ai/engine/game.py`
