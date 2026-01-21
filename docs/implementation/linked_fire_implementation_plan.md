# Linked Fire Implementation Plan

## Status: ✅ IMPLEMENTATION COMPLETE - ALL TASKS DONE

Issue checklist for implementing the `Linked Fire` wargear keyword:

### ✅ Completed Tasks

- [x] Confirmed official wording search in `docs/warhammer-community` (Core Rules, Core Rules Updates/Commentary, Balance Dataslate, MFM): no Linked Fire rule text found; Fire Prism appears only in MFM points list. Proceed with `wahapedia_data` text until an official rules document includes Linked Fire.
- [x] Inspected `wahapedia_data`: Linked Fire ability text in `wahapedia_data/Datasheets_abilities.json` (datasheet_id `000000610`), Fire Prism datasheet in `wahapedia_data/Datasheets.json`, and `linked fire` keyword on `Prism cannon – focused lances` in `wahapedia_data/Datasheets_wargear.json` (only that profile; `dispersed pulse` is BLAST only). Plan updates below reflect that scope.
- [x] **Add Linked Fire keyword detection** on weapon profiles and ensure it only applies to the focused-lances profile carrying the `linked fire` keyword
  - Added `is_linked_fire()` method to `WargearProfile` class in `src/warhammer40k_ai/units/wargear.py` (lines 6547-6549)
  - Method checks for 'linked fire' keyword in lowercase
- [x] **Add eligibility helper for Linked Fire origin units**: friendly, alive, deployed Fire Prism units (keyword/name), not the bearer, and visible to the bearer
  - Added `get_eligible_linked_fire_origin_units()` function to `src/warhammer40k_ai/utility/aura_utils.py` (lines 396-492)
  - Validates: friendly (same army), alive, deployed, has FIRE + PRISM keywords, not bearer, visible to bearer
- [x] **UI: Add linked-fire origin selection** in the shooting declaration flow with a single dialog that includes a "None (use bearer)" option and lists eligible Fire Prism units
  - Created `LinkedFireOriginDialog` in `src/warhammer40k_ai/UI/dialogs/linked_fire_origin_dialog.py` (206 lines)
  - Dialog includes "None (use bearer)" as first option with description of normal Attacks
  - Lists eligible Fire Prism units with "Attacks = 1" description
  - Integrated into `shooting_declaration_dialog.py` via `_open_linked_fire_origin_dialog()` method
  - Dialog opens when Linked Fire weapon is selected, before targeting mode
- [x] **Engine: Wire linked-fire origin selection** into the declaration payload via `linked_fire_origin_unit_id` and validate it
  - Modified `shooting_declaration_dialog.py` to store `linked_fire_origin_unit_id` in weapon declarations
  - Updated `_build_declarations_payload()` to include `linked_fire_origin_unit_id` field in payload
  - Added comprehensive validation in `src/warhammer40k_ai/engine/decision_handlers/shooting.py` (lines 115-163):
    - Validates origin unit exists
    - Validates origin is not the bearer
    - Validates origin is friendly (same army)
    - Validates origin has FIRE + PRISM keywords
    - Validates origin is alive and deployed
    - Validates origin is visible to the bearer (server-side LOS check)
- [x] **Engine: Pass origin unit through declaration chain**
  - Modified `_apply_declare_shots()` in `shooting.py` to extract origin unit from payload and add to declaration entry
  - Modified `execute_shooting_declarations()` in `unit.py` to extract origin unit and pass to validation and attack methods
- [x] **Update target validation** to allow range/LOS measurement from the linked-fire origin unit when selected
  - Modified `_validate_shooting_declaration()` in `unit.py` to accept `linked_fire_origin_unit` parameter
  - Modified `_can_model_shoot_weapon_at_target()` in `unit.py` to accept `origin_unit` parameter
  - When origin_unit is provided, range and LOS are measured from origin unit models instead of bearer
  - Maintains 3D distance measurement and existing LOS/Indirect Fire rules
- [x] **Apply the Attacks=1 override** only when linked fire is used
  - Modified `_execute_weapon_attacks()` in `unit.py` to accept `linked_fire_origin_unit` parameter
  - When origin unit is provided, `attacks_override=1` and `attacks_override_note="Linked Fire"` are passed to `weapon_profile.attack()`
- [x] **Add pytest coverage** - Created `tests/test_linked_fire.py` with 8 comprehensive tests (all passing):
  - **Keyword Detection Tests (3 tests)**: keyword detection, false when absent, case-insensitive
  - **Eligibility Tests (3 tests)**: excludes bearer, requires FIRE+PRISM keywords, requires same army
  - **Range/LOS Tests (1 test)**: range measured from origin unit, not bearer
  - **Attacks Override Tests (1 test)**: Attacks=1 when using Linked Fire

- [x] **Run full test suite**: `python -m pytest tests/` - **815 tests passed, 0 failures**
  - All 8 Linked Fire tests passed
  - Fixed import errors in `test_ork_keywords.py` and `test_one_shot_rules.py` caused by Linked Fire signature changes
  - Fixed all 19 tests in `test_ork_keywords.py` (were failing due to incorrect import paths, signature mismatches, and mock object structure)

- [x] **Update docs** for behavior and limitations:
  - Updated `docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md` - Changed "linked fire" entry from "Not implemented" to "Supported"
  - Updated `docs/factions/aeldari.md` - Added "Wargear Keywords" section with comprehensive Linked Fire documentation

## Files Created/Modified

### Created:
- `src/warhammer40k_ai/UI/dialogs/linked_fire_origin_dialog.py` (206 lines)
- `tests/test_linked_fire.py` (8 tests, all passing)

### Modified:
- `src/warhammer40k_ai/units/wargear.py` - Added `is_linked_fire()` method
- `src/warhammer40k_ai/utility/aura_utils.py` - Added `get_eligible_linked_fire_origin_units()` function
- `src/warhammer40k_ai/UI/dialogs/__init__.py` - Exported LinkedFireOriginDialog
- `src/warhammer40k_ai/UI/dialogs/shooting_declaration_dialog.py` - Added Linked Fire dialog integration and payload building
- `src/warhammer40k_ai/engine/decision_handlers/shooting.py` - Added Linked Fire origin validation and origin unit extraction
- `src/warhammer40k_ai/units/unit.py` - Added Linked Fire support to validation and attack execution:
  - `execute_shooting_declarations()` - Extract and pass origin unit through
  - `_validate_shooting_declaration()` - Accept origin unit parameter
  - `_can_model_shoot_weapon_at_target()` - Measure range/LOS from origin unit when provided
  - `_execute_weapon_attacks()` - Apply Attacks=1 override when using Linked Fire
