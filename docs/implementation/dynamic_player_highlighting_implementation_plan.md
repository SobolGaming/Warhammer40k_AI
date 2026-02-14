# Dynamic Player Highlighting Implementation Plan

## Status: PHASE 0 COMPLETE; PHASE 1 CORRECTIONS COMPLETE; PHASE 2 COMPLETE; PHASE 3 COMPLETE; PHASE 4 COMPLETE; PHASE 5 COMPLETE

Issue checklist for implementing player-selected color highlighting for roster headers and deployment zones, with deterministic decision/API support for local and remote play.

## Implementation Prompt

Previously we implemented highlighting of the player roster identifier to show who needs to take the current action. I picked a specific color of neon green. Since in the general case there may be any number of players (in a future planned implementation), I would like the players to be able to select their color, so that it's clearer at a glance which player's action it is. I would like the Attacker and Defender zones of the map to be color coded to the color of the player who is assigned to that zone, after deciding who is attacker and who is defender. I would like the player to be able to pick from a color wheel.

In total
- Please enable players to select their colors
- Color code the Defender and Attacker map zones to be linked to he player colors (likely with muted transparency)
- A small square of color should remain at the end of the players roster identifier section at all times to that players can know who is what color.
- The active player highlight should highlight the entire player roster identifier section in their color, as the indicator of whose action it is.

Create the same style of comprehensive issue checklist task oriented implementation plan with file-level targets as like the other implementation plans in `docs/implementation`. Break development into a phased development plan for easier implementation. Main game rules are located in `docs/warhammer-community`. Wargear rules specifically will likely only be found in the `wahapedia_data` folder.

There is a uv managed virtual environment under `.venv` that can be used for running commands. `uv run python ...` is an example of how to invoke it.

## Feature Acceptance Checklist

- [x] Each player can choose a personal color via a color-wheel dialog.
- [x] The active-player banner highlight uses that player's selected color across the entire roster identifier header.
- [x] A persistent color swatch square is always visible at the end of each roster identifier header.
- [x] Defender and Attacker deployment zones are tinted using the assigned player's selected color with muted transparency.
- [x] The solution works for local and remote control paths using the same deterministic decision API.
- [x] Player color state is serialized and restored via snapshot/network resync.

## Phase 0: Scope and Constraints

- [x] Confirm this is a UI/state/decision-flow feature and does not require rules-text extraction from `docs/warhammer-community` or `wahapedia_data`.
Targets: `docs/warhammer-community`, `wahapedia_data`.
- [x] Confirm no out-of-scope content (Crusade, Forge Worlds, Legends, Boarding Actions, Kill Teams) is introduced.
Targets: implementation review only.
- [x] Define deterministic color model and fallback policy for players without explicit color selection.
Targets: `src/warhammer40k_ai/roster/player.py`, `src/warhammer40k_ai/engine/decision_requests.py`, `src/warhammer40k_ai/engine/game.py`.

### Phase 0 Decisions (Locked)

- Feature classification: This request is UI/state/decision-flow only; no faction/rules text extraction is required from `docs/warhammer-community` or `wahapedia_data`.
- Scope safety: No Crusade/Forge Worlds/Legends/Boarding Actions/Kill Teams data or mechanics are introduced.
- Canonical player color state:
  - `ui_color_rgb`: 3-component RGB list with strict `[0,255]` validation.
  - `ui_color_hue_degrees`: optional integer hue in `[0,359]`.
  - `ui_color_selected`: boolean (defaults to `False` until explicit player selection).
  - `ui_color_source`: source marker (`default` or `selected`).
- Deterministic fallback policy: On game creation (and on dynamic `add_player()`), each player receives a default palette color by stable slot index modulo palette length.
- Deterministic candidate model for selection:
  - Quantized hue wheel step: `15` degrees (`24` discrete options).
  - HSV parameters for generated candidates: saturation `0.85`, value `0.95`.
  - Stable action IDs derived as `CHOOSE_PLAYER_COLOR:<player_id>:<hue>`.

## Phase 1: Engine Decision Surface and Player State

- [x] Add canonical player color state on `Player` (for example: normalized RGB tuple and optional hue metadata), initialized with deterministic defaults.
Targets: `src/warhammer40k_ai/roster/player.py`.
- [x] Add a dedicated setup decision kind for color selection.
Targets: `src/warhammer40k_ai/engine/decision_kinds.py`, `docs/DECISION_TYPES.md`.
- [x] Add decision request builder/helper for player color selection with deterministic candidate ordering and stable action IDs.
Targets: `src/warhammer40k_ai/engine/decision_requests.py`, `src/warhammer40k_ai/engine/game.py`.
- [x] Add validation/apply handlers for the color-selection decision (range checks, payload normalization, deterministic storage).
Targets: `src/warhammer40k_ai/engine/decision_handlers/setup.py`.
- [x] Wire setup-phase queuing for this decision before deployment interaction begins, ensuring local/remote parity and no UI-only state mutation.
Targets: `src/warhammer40k_ai/engine/game_mixins/setup_deployment_reserves_mixin.py`, `src/warhammer40k_ai/UI/phases/phase_manager.py`, `src/warhammer40k_ai/network/server.py` (if setup buffering includes this decision type).
Validation note: `CHOOSE_PLAYER_COLOR` is now included in network formation decision buffering/queueing so remote setup does not advance before color decisions are resolved.

## Phase 2: UI Color-Wheel Dialog

- [x] Implement a dedicated color-wheel dialog for selecting a player color (single dialog, no extra yes/no step).
Targets: `src/warhammer40k_ai/UI/dialogs/player_color_picker_dialog.py` (new), `src/warhammer40k_ai/UI/dialogs/__init__.py`, `src/warhammer40k_ai/UI/dialogs/dialog_manager.py`.
  - Implemented new `PlayerColorPickerDialog` with hue wheel rendering, click-to-select hue snapping, keyboard navigation, preview swatch, and confirm/cancel actions.
  - Exported `PlayerColorPickerDialog` through dialogs package facade so it is available via `from ..dialogs import ...`.
  - Added dialog discovery entry in `DialogManager` for `player_color_picker_dialog` stack synchronization.
- [x] Bind dialog output to decision resolution command path, not direct game-state mutation.
Targets: `src/warhammer40k_ai/UI/phases/phase_manager.py`, `src/warhammer40k_ai/UI/decision_ui_utils.py`.
  - Added `option_id_for_hue_degrees()` helper to `decision_ui_utils` for deterministic hue -> option ID resolution.
  - Local and remote setup color-picker callbacks resolve `CHOOSE_PLAYER_COLOR` through `resolve_decision_command(...)` with `player_id`.
  - Cancel path now resolves deterministically to `first_option_id(request)` instead of mutating player color directly.
- [x] Support both local and remote player control paths by opening the dialog only for pending local decisions and preserving deterministic payload format.
Targets: `src/warhammer40k_ai/UI/phases/phase_manager.py`, `src/warhammer40k_ai/network/server.py`.
  - Added local setup flow: `_start_player_color_selection_flow()` and `_open_next_player_color_prompt()` before hover/formation dialogs.
  - Added remote setup flow entry `_show_player_color()` ahead of hover/plague/leader/transports/reserves remote chain.
  - Updated setup pending checks to treat `CHOOSE_PLAYER_COLOR` as a formation decision and to detect active `player_color_picker_dialog`.

## Phase 3: Rendering Integration

- [x] Add shared player-color resolution helpers for consistent use across roster banner and zone rendering.
Targets: `src/warhammer40k_ai/UI/player_colors.py` (new), `src/warhammer40k_ai/UI/ui_constants.py`.
  - Added shared helpers for player RGB normalization, active-header blending, zone fill/border colors, and contrasting text color.
  - Added shared player-color constants in `ui_constants` (`PLAYER_ZONE_ALPHA`, header blend factor, swatch size, fallback RGB).
- [x] Update roster-pane header rendering so active player uses that player's color for the full header highlight.
Targets: `src/warhammer40k_ai/UI/panels/roster_pane.py`.
  - Replaced hardcoded neon-green active banner with `get_active_roster_header_rgb(...)` derived from the active player's selected color.
  - Added dynamic text contrast for active headers using shared helper logic.
- [x] Add a persistent color swatch square at the end of the player roster identifier section.
Targets: `src/warhammer40k_ai/UI/panels/roster_pane.py`.
  - Added always-visible per-player swatch in roster header based on canonical player color state.
  - Swatch placement is clamped to avoid overlapping the points summary area.
- [x] Refactor deployment-zone rendering to tint zones from assigned player colors instead of fixed green/red.
Targets: `src/warhammer40k_ai/UI/rendering/board_renderer.py`, `src/warhammer40k_ai/UI/game_ui.py`.
  - `draw_deployment_zones(...)` now resolves player by zone owner id and uses shared player-color zone fill/border helpers.
  - `GameUI` now calls zone rendering with `game` context rather than fixed player1/player2 color mapping.
- [x] Ensure zone-to-player assignment is synchronized with attacker/defender resolution before zone draw.
Targets: `src/warhammer40k_ai/engine/game_mixins/setup_deployment_reserves_mixin.py`, `src/warhammer40k_ai/UI/game_ui.py`.
  - Added `sync_deployment_zones_to_attacker_defender()` in setup mixin and invoked it after attacker/defender determination.
  - Added sync call in local deployment setup path and immediately before frame-time zone drawing in `GameUI`.

## Phase 4: Snapshot/Network Determinism

- [x] Verify player-color state is included in existing serialized player state and survives roundtrip load.
Targets: `src/warhammer40k_ai/engine/snapshot.py`, `tests/test_snapshot.py`.
  - Added `test_snapshot_roundtrip_preserves_player_color_state_and_pending_color_decisions` to validate serialized player color fields and loaded-state parity.
  - Verified pending `CHOOSE_PLAYER_COLOR` decisions survive snapshot roundtrip with deterministic candidate ordering and valid RGB payload bounds.
- [x] Ensure pending color decisions and resulting state sync correctly to clients during setup.
Targets: `src/warhammer40k_ai/network/server.py`, `src/warhammer40k_ai/network/protocol.py`, `tests/test_network_server_client.py`, `tests/test_network_protocol.py`.
  - Added protocol-level resync coverage in `test_resync_snapshot_includes_player_color_state_and_pending_color_decisions` for both pending and resolved color-selection state.
  - Extended TLS integration flow (`test_network_server_client_flow_tls`) to assert player-color fields in snapshots and wait for a broadcast `CHOOSE_PLAYER_COLOR` setup decision request.
- [x] Confirm deterministic behavior in decision records (stable candidate IDs/order and valid payload constraints).
Targets: decision handler tests and decision-request builder tests.
  - Added `test_decision_record_player_color_candidates_are_deterministic_and_valid` to assert sorted/stable action IDs and payload constraints (`rgb` bounds, quantized `hue_degrees`) in recorded candidates.
  - Existing builder determinism assertions remain covered in `tests/test_player_color_decision.py` (`test_player_color_request_builder_is_deterministic`).

## Phase 5: Test Plan (pytest via uv)

- [x] Add unit tests for player-color decision validation/apply semantics.
Targets: `tests/test_player_color_decision.py` (new).
  - Added regression coverage for network formation queue creation of `CHOOSE_PLAYER_COLOR` requests.
  - Added UI helper coverage for deterministic hue -> option mapping (`option_id_for_hue_degrees`).
- [x] Add snapshot roundtrip assertions for player colors.
Targets: `tests/test_snapshot.py`.
  - Added snapshot serialization + load assertions for `ui_color_rgb`, `ui_color_hue_degrees`, `ui_color_selected`, and `ui_color_source`.
  - Added snapshot roundtrip assertions for pending `CHOOSE_PLAYER_COLOR` decision queue entries and candidate payload integrity.
- [x] Add rendering tests for roster header highlight + persistent color swatch.
Targets: `tests/test_roster_player_color_rendering.py` (new) or existing UI rendering test module.
  - Added `tests/test_roster_player_color_rendering.py` with active-header color assertion and persistent swatch assertion for inactive headers.
  - Test coverage validates rendered header color derives from player-selected color blend and that swatch color matches canonical player color state.
- [x] Add rendering tests for deployment-zone tinting using selected player colors.
Targets: `tests/test_deployment_zone_player_colors.py` (new).
  - Added `tests/test_deployment_zone_player_colors.py` to assert mission-zone fill RGBA matches `get_zone_fill_rgba(player)` for each zone owner.
  - Coverage validates zone tinting is keyed by owning player id, independent of attacker/defender label text.
- [x] Add/extend network integration tests for setup color decisions in remote play.
Targets: `tests/test_network_server_client.py`, `tests/test_network_game_session.py`.
  - Extended `test_network_server_client_flow_tls` to assert snapshot player-color fields and wait for a `CMD_REQUEST_DECISION` carrying `CHOOSE_PLAYER_COLOR` during setup.
  - Added protocol-level sync coverage for pending/resolved color decisions in `tests/test_network_protocol.py`.
  - Increased async wait timeout defaults in `tests/test_network_server_client.py` to reduce full-suite xdist load flakiness.
- [x] Run phase-2 targeted tests:
  - Command: `uv run python -m pytest tests/test_player_color_decision.py tests/test_network_server_client.py::test_network_server_client_flow_tls -q`
  - Result: `7 passed` (Phase 2 and Phase 1 correction paths validated).
- [x] Run phase-3 targeted tests:
  - Command: `uv run python -m pytest tests/test_player_color_decision.py tests/test_network_server_client.py::test_network_server_client_flow_tls -q`
  - Result: `9 passed` (Phase 3 rendering helpers + zone-sync coverage included).
  - Command: `uv run python -m pytest tests/test_deployment_titanic_skip_turn.py -q`
  - Result: `2 passed` (deployment sequencing remained stable after zone-sync hook insertion).
- [x] Run targeted tests:
  - Command: `uv run python -m pytest tests/test_decision_record_logging.py tests/test_network_protocol.py tests/test_player_color_decision.py -q`
  - Result: `21 passed`.
  - Command: `uv run python -m pytest tests/test_snapshot.py -q`
  - Result: `4 passed`.
  - Command: `uv run python -m pytest tests/test_network_server_client.py::test_network_server_client_flow_tls tests/test_network_game_session.py -q`
  - Result: `4 passed`.
  - Command: `uv run python -m pytest tests/test_roster_player_color_rendering.py tests/test_deployment_zone_player_colors.py tests/test_player_color_decision.py -q`
  - Result: `11 passed`.
  - Command: `uv run python -m pytest tests/test_cult_ambush.py tests/test_hover_mode.py tests/test_network_server_client.py::test_network_server_client_flow_tls -q`
  - Result: `13 passed` (full-suite regressions from new setup color decisions corrected in test harness expectations).
- [x] Run full suite after feature integration:
  - Command: `uv run python -m pytest tests/`
  - Result: `1703 passed, 16 warnings`.

## Phase 6: Documentation Updates

- [ ] Update player configuration documentation to replace hardcoded neon-green behavior with dynamic player-selected colors and persistent swatches.
Targets: `docs/PLAYER_CONFIGURATION.md`.
- [ ] Add UI dialog-to-decision mapping entry for the player color picker dialog and decision payload.
Targets: `docs/NETWORK_SAVELOAD_DESIGN.md`.
- [ ] Update decision catalog for the new decision type.
Targets: `docs/DECISION_TYPES.md`.
- [ ] Keep this implementation plan updated with completion checkmarks, exact pytest commands, and pass/fail results.
Targets: `docs/implementation/dynamic_player_highlighting_implementation_plan.md`.

## Open Questions for Developer Confirmation (Before Coding)

- [ ] Should duplicate/similar player colors be allowed, or should minimum color-distance enforcement be required?
- [x] Should the color wheel be continuous or quantized (recommended: quantized hue bins for deterministic action IDs)?
Resolved for current implementation baseline: quantized hue bins at 15-degree increments.
- [ ] Should the player-color decision run once during setup only, or remain re-openable later (for example via settings/pause menu)?
- [ ] Confirm preferred alpha levels for map-zone tint and active roster highlight readability.
