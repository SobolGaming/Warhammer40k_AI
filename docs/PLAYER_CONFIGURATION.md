# Player Configuration System

The game supports local player control for interactive gameplay and a remote-control flag for future external controllers.

## Command Line Arguments

### Army Lists
- `--player1-army <file>` - Army list file for Player 1 (default: army_lists/chaos_test.txt)
- `--player2-army <file>` - Army list file for Player 2 (default: army_lists/aeldari_test.txt)

### Advanced Options
- `--manual-phases` - Require SPACE key to advance phases, including individual deployment actions

## Usage Examples

### Local vs Local
```bash
python scripts/main.py --player1-army army_lists/chaos_test.txt --player2-army army_lists/aeldari_test.txt
```

### Manual Phases
```bash
python scripts/main.py --manual-phases
```

## Manual Phases Mode (`--manual-phases`)

This mode provides step-by-step control over game progression:

### Setup Phases
- Requires SPACE key to advance through each setup phase
- Shows detailed progress and phase descriptions
- Allows observation of attacker/defender determination and deployment zone setup

### Deployment Phase
- Each unit deployment requires a separate SPACE key press
- Shows deployment action tracking: "Unit deployed at (x, y)" or "Unit placed in Reserves"
- Displays whose turn it is during alternating deployment
- Local-only deployment helpers (e.g., `HumanDeploymentDecisionMaker`) are injected at runtime
  when setup phases are executed; they are not serialized into command payloads.

### Battle Rounds
- SPACE key required to advance between each phase

## Player Control Model

Each `Player` instance includes a `control` value:

- `PlayerControl.LOCAL`: Controlled by the local UI
- `PlayerControl.REMOTE`: Intended for external controllers (no local input)

The UI checks `player.has_control()` before enabling interactions, which allows future networked or automation control to be added without changing core game flow.

## Controller Hooks (Non-Local)

Remote controllers should drive gameplay by resolving `DecisionRequest` entries.

Reactive enemy-move D6 triggers (e.g., Loping Speed/Trail Finding) queue:
- `CONFIRM_YES_NO` with `reactive_move_kind`, `reactive_move_unit_id`, `reactive_move_moving_unit_id`, `reactive_move_range`,
  `reactive_move_source`, `reactive_move_movement_type`.
- On acceptance, `MOVE_UNIT` with `movement_type="loping_speed"` and `max_distance`.

Blood Surge queues:
- `CONFIRM_YES_NO` with `reactive_move_kind="blood_surge"` and `reactive_move_attacker_unit_id`.
- On acceptance, `MOVE_UNIT` with `movement_type="blood_surge"` and `max_distance`.

Battle Focus reactive maneuvers queue:
- `SELECT_OVERWATCH_SHOOTER` with context `ability="battle_focus"` and `maneuver="opportunity"` or `"fade_back"`.
- On selection, `MOVE_UNIT` with `movement_type="reactive"` and `max_distance`.

Transport reactive disembark queues:
- `DISEMBARK` with `unit_id`, `transport_id`, and `reactive_disembark_*` context fields.
- Choose the option with `transport_id` to disembark; choose `transport_id=None` to remain embarked.

Optional hooks for automation:
- `Player.set_next_optional_decision("LOPING_SPEED"|"BLOOD_SURGE"|"TRANSPORT_REACTIVE_DISEMBARK", True|False)` or
  `Player.decision_hook` to auto-accept/decline.
- `Player.set_next_optional_selection("BATTLE_FOCUS_OPPORTUNITY"|"BATTLE_FOCUS_FADE_BACK", unit|name|index)` to auto-select.
- `Player.reactive_move_position_hook` to return `model_positions` for reactive moves (`movement_type` in
  `"loping_speed"`, `"blood_surge"`, or `"reactive"`); return `None` to leave pending.

## User Interface Highlights

### Roster Panes
- Player names update with attacker/defender roles after setup
- Unit health indicators and deployment status
- Interactive selection for deployment and details

### Info Panel
- Game phase and turn indicators
- Deployment action tracking
- Manual mode indicators

### Battlefield View
- Zoom and pan controls
- Deployment zones with labels and boundaries
- Objective markers and unit visualization
