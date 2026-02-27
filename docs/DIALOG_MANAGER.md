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
