### DialogManager (Modal Stack) Architecture

This project uses a **centralized, callback-based modal stack** for UI dialogs to ensure:

- Dialogs that receive events are always drawn when active
- Modal dialogs reliably block underlying game input (no "SPACE advanced phase while dialog was open" bugs)
- Adding new dialogs does not require editing multiple phase handlers and draw loops

### Core idea

The `DialogManager` maintains a **stack** of dialogs:

- **Draw order**: bottom -> top (stack order)
- **Event routing**: only the **topmost active** dialog receives events
- **Modal behavior**: while a modal dialog is active, **clicks/keys/wheel are consumed** even if the dialog does not explicitly handle them
- **Passthrough**: dialogs can expose `should_passthrough_event(event)` to allow specific events to reach the phase handler
- **Hover previews**: `MOUSEMOTION` is allowed to pass through modal dialogs so hover/path previews still update

Each stack entry has a `modal` flag (default `True` when opened).

Implementation lives in:

- `src/warhammer40k_ai/UI/dialogs/dialog_manager.py`

### What counts as an "active dialog"

A dialog is considered **active** if either of these is true:

- `dialog.visible == True`
- `dialog.is_targeting_mode == True` (used by targeting-style overlays)

This lets "targeting mode" behave like a modal overlay even if it does not use `visible`.

### How dialogs get onto the stack

`DialogManager` performs **best-effort discovery** every frame/event:

- It scans known dialog attributes on `GameView` (and some on `HumanUIInterface`)
- If it finds a dialog that has become active since the last check, it is moved to the **top** of the stack
- Inactive dialogs are **pruned** automatically
- Discovery order is a tie-breaker when multiple dialogs activate in the same frame.
  Reactive selectors (`overwatch_shooter_dialog`, `battle_focus_dialog`) are intentionally kept late in that order so they correctly take focus/highlight over movement dialogs.

This means most dialogs do not need to manually call `dialog_manager.open()` to be drawn/handled.
We still call `open()` in a few places (e.g. setup modals) to make the "last opened is topmost" intent explicit.

Discovery list is defined in:

- `DialogManager._discover_dialogs()` (`src/warhammer40k_ai/UI/dialogs/dialog_manager.py`)

### Where draw and event routing happen

- **Event routing** happens first in `PhaseManager.handle_event()`:

  - `self.game_view.dialog_manager.handle_event(event)`
  - If it returns `True`, the phase handler does not see the event.

- **Drawing** happens once per frame in `GameView.draw()`:

  - `self.dialog_manager.draw(self.screen)`

This guarantees the "if it can handle events, it must be drawn" invariant. Events allowed to passthrough
(`should_passthrough_event` or `MOUSEMOTION`) can still reach the phase handler.

### Callback-based dialogs (recommended pattern)

All dialogs should follow the `BaseDialog` pattern:

- `show(..., callback=...)` or explicit `on_confirm` / `on_cancel` callables
- `handle_event(event) -> bool` returns whether the dialog consumed the event
- `draw(screen)` renders the dialog when visible

The important point is that **dialogs should not return structured results** to callers via `handle_event`.
Instead, they should call callbacks and close/hide themselves.

### Special case: MissionSelectionDialog

`MissionSelectionDialog` is legacy and returns dicts like `{"action": "confirm", ...}` from `handle_event()`.

We wrapped it with a callback adapter:

- `MissionSelectionModal` (`src/warhammer40k_ai/UI/dialogs/mission_selection_modal.py`)

`MissionSelectionModal`:

- Exposes the standard dialog surface: `visible`, `draw`, `handle_event`
- Converts return dicts into `on_confirm(result)` / `on_cancel()` callbacks

Setup phase uses this modal adapter in `SetupPhaseHandler._show_mission_selection_dialog()`.

### Adding a new dialog (checklist)

- **Implement dialog**
  - Prefer inheriting from `BaseDialog` (`src/warhammer40k_ai/UI/dialogs/base_dialog.py`)
  - Use callbacks for outputs

- **Store it on `GameView`**
  - `self.my_new_dialog = MyNewDialog(...)`

- **(Recommended) add to discovery list**
  - Add `my_new_dialog` to `DialogManager._discover_dialogs()` so it automatically draws/routes.

- **Show it**
  - `self.my_new_dialog.show(...)`
  - Optional but fine: `self.dialog_manager.open(self.my_new_dialog, modal=True)`

### Notes / limitations

- The discovery list is centralized and explicit. If a dialog is not on the list, it can still be used,
  but you must manually call `dialog_manager.open()` to put it on the stack.
- Some "nested" dialogs (e.g. floor selection within individual model movement) are managed internally
  by their parent dialog and do not need to be registered with `DialogManager`.

### Performance note

- `UnitDetailPanel` (the right-click detailed unit info pane) now caches a pre-rendered content surface.
  Scrolling only updates viewport offset instead of re-wrapping/re-rendering every line each frame.
  Cache invalidation occurs when the focused unit changes, panel width changes, or the periodic refresh window expires.
  Default panel typography was also increased by +2pt across large/medium/small/tiny fonts for readability.
- `RuleDetailPanel` now uses the same pre-rendered content-surface approach; wheel scrolling is viewport-only.
- `MissionSelectionDialog` caches its full mission table surface and only rebuilds when combinations or selection state change.
- `ShootingDeclarationDialog` caches hot-path text rasterization for repeated weapon/declaration rows.
- `RosterPane` composition text is now ellipsized to available width and reserves right-side space for Aspect Shrine token icons to prevent overflow/overlap.

### Movement Choice behavior

- `MovementChoiceDialog` disables movement action buttons when the selected unit has already resolved movement
  (moved, advanced, or fell back) this phase.
  In that state, the dialog shows `Already Moved this Phase`, and no `SELECT_MOVEMENT_ACTION` request is created.

### Dice roll behavior

- Command Re-roll is only shown in reroll options when stratagem availability checks pass for the current player/phase.
  This prevents stale follow-up reroll prompts from offering unavailable Command Re-roll actions.
- Dice roll dialogs now show explicit success/pass conditions for every roll type (`>=`, `<=`, etc.).
- Battle-shock sum rolls now show raw sum and modifier math (`raw N -> modified M`) plus modifier reasons when provided.
- Hit/Wound/Save rolls now show the final needed value and modifier context (base-to-final shift and rule reasons when available).
- All `REQUEST_DICE_ROLL` specs now include a unified `roll_explanation` payload generated by the engine.
  It standardizes pass/success condition data and modifier contributors for both sum-based and target-based rolls.
- Contributor entries include typed sources (`detachment_ability`, `faction_rule`, `unit_ability`, `enhancement`,
  `stratagem`, `aura`, `core_rule`, `rule`) and optional aura range/distance fields when available.
- Shadow of Chaos Daemonic Terror (`D3` mortal wounds on failed Battle-shock) now resolves through `REQUEST_DICE_ROLL`
  so the player sees an explicit `Make Roll` decision and resulting roll telemetry/events.
- `utility.dice.get_roll(...)` now emits `REQUEST_DICE_ROLL` directly when a game context is active or an explicit game is passed,
  ensuring roll helpers still produce deterministic dice decisions and roll telemetry.
- `DiceCollection.from_string(...)` accepts `D6`, `2D6`, additive/subtractive modifiers such as
  `D6+1` and `2D6-3`, and legacy prefix modifiers such as `2 + D6`; invalid parser input raises
  `ValueError` before any dice request is emitted.
- `D3` request rolls now resolve using a physical `D6` with explicit mapping (`1-2 => 1`, `3-4 => 2`, `5-6 => 3`).
  Roll UI and telemetry expose both raw `D6` values and mapped `D3` results to avoid ambiguity.

### Battle-shock command step

- In the core Command phase Battle-shock step, automatic tests are requested for units that are Below Half-strength.
- Below Starting Strength command-phase tests are applied by explicit rule hooks (auras/abilities that force those tests), not by the core baseline step.
