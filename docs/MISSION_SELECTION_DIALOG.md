# Mission Selection Dialog

## Overview
The Mission Selection Dialog is used during the `SELECT_MISSION_OBJECTIVES` setup phase to pick
an approved Chapter Approved 2025/2026 mission combination (primary + deployment + terrain layout).

The data source is `MissionSelectionDialog.APPROVED_COMBINATIONS` in
`src/warhammer40k_ai/UI/dialogs/mission_selection_dialog.py`.

## UI behavior
- Scrollable list of combinations (A-T)
- Terrain layout buttons per row
- Buttons: Cancel, Pick Random, Confirm
- Keyboard:
  - `Esc` cancel
  - `Enter` confirm
  - `R` pick random
  - Up/Down arrows scroll
- Mouse wheel scrolls the list

## Combination format
Each entry is:
```python
{
    "id": "A",
    "primary": "Take and Hold",
    "deployment": "Tipping Point",
    "layouts": [1, 2, 4, 6, 7, 8],
}
```

## Integration points
- `PhaseManager._show_mission_selection_dialog` wraps the dialog with
  `MissionSelectionModal` (callback adapter).
- On confirm, the handler:
  - sets `game.selected_mission_info`
  - assigns a primary mission card (from `engine/mission_cards.py`) to both players
  - falls back to a stub primary if the name is unknown
- On cancel, `Game.execute_select_mission_objectives_phase` uses the default:
  `M: Purge the Foe / Crucible of Battle / Layout 1`.
- `Game.execute_create_battlefield_phase` uses `selected_mission_info` to pick
  deployment zones and the terrain layout.

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
